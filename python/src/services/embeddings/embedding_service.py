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

from ...logfire_config import search_logger
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
        # Use asyncio.run to call the async version
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a task
            future = asyncio.ensure_future(create_embedding_async(text))
            return loop.run_until_complete(future)
        else:
            # If no event loop is running, use asyncio.run
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
        # Use asyncio.run to call the async version
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a task
            future = asyncio.ensure_future(create_embeddings_batch_async(texts))
            return loop.run_until_complete(future)
        else:
            # If no event loop is running, use asyncio.run
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
    
    threading_service = get_threading_service()
    
    with search_logger.span("create_embeddings_batch_async", 
                           text_count=len(texts),
                           total_chars=sum(len(t) for t in texts)) as span:
        
        try:
            # Estimate token usage for rate limiting
            estimated_tokens = sum(len(text.split()) for text in texts) * 1.3  # Rough estimate
            
            async with threading_service.rate_limited_operation(estimated_tokens):
                async with get_openai_client() as client:
                    # Split into smaller batches if needed
                    batch_size = 20  # OpenAI's batch limit
                    all_embeddings = []
                    
                    for i in range(0, len(texts), batch_size):
                        batch = texts[i:i + batch_size]
                        
                        # Create embeddings for this batch
                        response = await client.embeddings.create(
                            model="text-embedding-3-small",
                            input=batch
                        )
                        
                        batch_embeddings = [item.embedding for item in response.data]
                        all_embeddings.extend(batch_embeddings)
                        
                        # Progress reporting
                        if progress_callback:
                            progress = ((i + len(batch)) / len(texts)) * 100
                            await progress_callback(
                                f"Created embeddings for {i + len(batch)}/{len(texts)} texts",
                                progress
                            )
                        
                        # WebSocket progress update
                        if websocket:
                            await websocket.send_json({
                                "type": "embedding_progress",
                                "processed": i + len(batch),
                                "total": len(texts),
                                "percentage": progress
                            })
                        
                        # Yield control for WebSocket health
                        await asyncio.sleep(0.1)
                    
                    span.set_attribute("embeddings_created", len(all_embeddings))
                    span.set_attribute("success", True)
                    
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