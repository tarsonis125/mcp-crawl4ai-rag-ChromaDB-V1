"""
Embedding Service

Handles all OpenAI embedding operations with proper rate limiting and error handling.
"""
import os
import asyncio
from typing import List, Optional, Any
from fastapi import WebSocket
import openai
from contextlib import asynccontextmanager

from ...config.logfire_config import search_logger, safe_span
from ..threading_service import get_threading_service


@asynccontextmanager
async def get_openai_client():
    """
    Create an async OpenAI client context manager.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not found in environment")
    
    client = openai.AsyncOpenAI(api_key=api_key)
    
    try:
        yield client
    finally:
        # Cleanup if needed
        pass


def create_embedding(text: str) -> List[float]:
    """
    Create an embedding for a single text using OpenAI's API.
    
    This is a synchronous wrapper around the async version for backward compatibility.
    
    Args:
        text: Text to create an embedding for
        
    Returns:
        List of floats representing the embedding
    """
    try:
        # Check if we're in an async context
        try:
            loop = asyncio.get_running_loop()
            # If we're already in an async context, we can't run sync - return zero embedding
            search_logger.warning("create_embedding called from async context - returning zero embedding")
            return [0.0] * 1536
        except RuntimeError:
            # No running loop, safe to use asyncio.run
            return asyncio.run(create_embedding_async(text))
    except Exception as e:
        search_logger.error(f"Error creating embedding: {e}")
        # Return zero embedding if there's an error
        return [0.0] * 1536


async def create_embedding_async(text: str) -> List[float]:
    """
    Create an embedding for a single text using async OpenAI API.
    
    Args:
        text: Text to create an embedding for
        
    Returns:
        List of floats representing the embedding
    """
    try:
        embeddings = await create_embeddings_batch_async([text])
        return embeddings[0] if embeddings else [0.0] * 1536
    except Exception as e:
        search_logger.error(f"Error creating single embedding: {e}")
        return [0.0] * 1536


def create_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Create embeddings for multiple texts in a single API call.
    
    This is a synchronous wrapper around the async version for backward compatibility.
    
    Args:
        texts: List of texts to create embeddings for
        
    Returns:
        List of embeddings (each embedding is a list of floats)
    """
    if not texts:
        return []
    
    try:
        # Check if we're in an async context
        try:
            loop = asyncio.get_running_loop()
            # If we're already in an async context, we can't run sync - return zero embeddings
            search_logger.warning("create_embeddings_batch called from async context - returning zero embeddings")
            return [[0.0] * 1536 for _ in texts]
        except RuntimeError:
            # No running loop, safe to use asyncio.run
            return asyncio.run(create_embeddings_batch_async(texts))
    except Exception as e:
        search_logger.error(f"Error creating batch embeddings: {e}")
        # Return zero embeddings as fallback
        return [[0.0] * 1536 for _ in texts]


async def create_embeddings_batch_async(
    texts: List[str], 
    websocket: Optional[Any] = None,
    progress_callback: Optional[Any] = None
) -> List[List[float]]:
    """
    Create embeddings for multiple texts with threading optimizations.
    
    Args:
        texts: List of texts to create embeddings for
        websocket: Optional WebSocket for progress updates
        progress_callback: Optional callback for progress reporting
        
    Returns:
        List of embeddings (each embedding is a list of floats)
    """
    if not texts:
        return []
    
    # Validate that all items in texts are strings
    validated_texts = []
    for i, text in enumerate(texts):
        if not isinstance(text, str):
            search_logger.error(f"Invalid text type at index {i}: {type(text)}, value: {text}")
            # Try to convert to string
            try:
                validated_texts.append(str(text))
            except Exception as e:
                search_logger.error(f"Failed to convert text at index {i} to string: {e}")
                validated_texts.append("")  # Use empty string as fallback
        else:
            validated_texts.append(text)
    
    texts = validated_texts
    
    threading_service = get_threading_service()
    
    with safe_span("create_embeddings_batch_async", 
                           text_count=len(texts),
                           total_chars=sum(len(t) for t in texts)) as span:
        
        try:
            async with get_openai_client() as client:
                # Split into smaller batches if needed
                batch_size = 20  # OpenAI's batch limit
                all_embeddings = []
                total_tokens_used = 0
                
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i + batch_size]
                    
                    # Estimate tokens for this specific batch
                    batch_tokens = sum(len(text.split()) for text in batch) * 1.3  # Rough estimate
                    total_tokens_used += batch_tokens
                    
                    # Rate limit each batch individually
                    async with threading_service.rate_limited_operation(batch_tokens):
                        retry_count = 0
                        max_retries = 3
                        
                        while retry_count < max_retries:
                            try:
                                # Create embeddings for this batch
                                response = await client.embeddings.create(
                                    model="text-embedding-3-small",
                                    input=batch
                                )
                                
                                batch_embeddings = [item.embedding for item in response.data]
                                all_embeddings.extend(batch_embeddings)
                                break  # Success, exit retry loop
                                
                            except openai.RateLimitError as e:
                                error_message = str(e)
                                if "insufficient_quota" in error_message:
                                    # Calculate approximate cost
                                    tokens_so_far = total_tokens_used - batch_tokens
                                    cost_so_far = (tokens_so_far / 1_000_000) * 0.02  # $0.02 per 1M tokens for text-embedding-3-small
                                    
                                    search_logger.error(
                                        f"⚠️ OpenAI BILLING QUOTA EXHAUSTED! You need to add more credits to your OpenAI account.\n"
                                        f"Tokens used so far: {tokens_so_far:,} (≈${cost_so_far:.4f})\n"
                                        f"Error: {error_message}"
                                    )
                                    span.set_attribute("quota_exhausted", True)
                                    span.set_attribute("tokens_used_before_quota", tokens_so_far)
                                    
                                    # Return zero embeddings for remaining texts
                                    remaining = len(texts) - len(all_embeddings)
                                    all_embeddings.extend([[0.0] * 1536 for _ in range(remaining)])
                                    
                                    # Notify via progress callback
                                    if progress_callback:
                                        await progress_callback(
                                            f"❌ QUOTA EXHAUSTED - Add credits to OpenAI account! (used {tokens_so_far:,} tokens ≈${cost_so_far:.4f})",
                                            100
                                        )
                                    
                                    return all_embeddings
                                else:
                                    retry_count += 1
                                    if retry_count < max_retries:
                                        wait_time = 2 ** retry_count  # Exponential backoff
                                        search_logger.warning(f"Rate limit hit (not quota), waiting {wait_time}s before retry {retry_count}/{max_retries}")
                                        await asyncio.sleep(wait_time)
                                    else:
                                        search_logger.error(f"Max retries exceeded for batch {i//batch_size + 1}")
                                        # Add zero embeddings for this batch
                                        all_embeddings.extend([[0.0] * 1536 for _ in batch])
                        
                        # Progress reporting with cost estimation
                        if progress_callback:
                            progress = ((i + len(batch)) / len(texts)) * 100
                            cost_estimate = (total_tokens_used / 1_000_000) * 0.02  # $0.02 per 1M tokens
                            await progress_callback(
                                f"Created embeddings for {i + len(batch)}/{len(texts)} texts (tokens: {total_tokens_used:,} ≈${cost_estimate:.4f})",
                                progress
                            )
                        
                        # WebSocket progress update
                        if websocket:
                            await websocket.send_json({
                                "type": "embedding_progress",
                                "processed": i + len(batch),
                                "total": len(texts),
                                "percentage": progress,
                                "tokens_used": total_tokens_used
                            })
                        
                        # Yield control for WebSocket health
                        await asyncio.sleep(0.1)
                
                span.set_attribute("embeddings_created", len(all_embeddings))
                span.set_attribute("success", True)
                span.set_attribute("total_tokens_used", total_tokens_used)
                
                return all_embeddings
                    
        except Exception as e:
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            search_logger.error(f"Failed to create embeddings batch: {e}")
            
            # Return zero embeddings as fallback
            return [[0.0] * 1536 for _ in texts]


# Deprecated functions - kept for backward compatibility
async def get_openai_api_key() -> Optional[str]:
    """
    DEPRECATED: Use os.getenv("OPENAI_API_KEY") directly.
    API key is loaded into environment at startup.
    """
    return os.getenv("OPENAI_API_KEY")


def get_openai_api_key_sync() -> Optional[str]:
    """
    DEPRECATED: Use os.getenv("OPENAI_API_KEY") directly.
    API key is loaded into environment at startup.
    """
    return os.getenv("OPENAI_API_KEY")