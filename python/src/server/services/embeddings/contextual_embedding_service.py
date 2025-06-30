"""
Contextual Embedding Service

Handles generation of contextual embeddings for improved RAG retrieval.
Includes proper rate limiting for OpenAI API calls.
"""
import os
import time
import asyncio
from typing import List, Tuple
import openai

from ...config.logfire_config import search_logger
from ..threading_service import get_threading_service


def generate_contextual_embedding(full_document: str, chunk: str) -> Tuple[str, bool]:
    """
    Generate contextual information for a chunk within a document to improve retrieval.
    
    This synchronous version is kept for ThreadPoolExecutor compatibility.
    Uses a small delay to prevent rate limiting when running in parallel.
    
    Args:
        full_document: The complete document text
        chunk: The specific chunk of text to generate context for
        
    Returns:
        Tuple containing:
        - The contextual text that situates the chunk within the document
        - Boolean indicating if contextual embedding was performed
    """
    # Get API key directly from environment (loaded at startup)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: No OpenAI API key found in environment")
        return chunk, False
    
    # Create OpenAI client with the API key
    client = openai.OpenAI(api_key=api_key)
    
    model_choice = os.getenv("MODEL_CHOICE")
    
    try:
        # Create the prompt for generating contextual information
        # Reduced from 25000 to 5000 to avoid token rate limits
        prompt = f"""<document> 
{full_document[:5000]} 
</document>
Here is the chunk we want to situate within the whole document 
<chunk> 
{chunk}
</chunk> 
Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""

        # Call the OpenAI API to generate contextual information
        response = client.chat.completions.create(
            model=model_choice,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides concise contextual information."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200
        )
        
        # Extract the generated context
        context = response.choices[0].message.content.strip()
        
        # Combine the context with the original chunk
        contextual_text = f"{context}\n---\n{chunk}"
        
        # Add a small delay to prevent rate limiting when running in parallel
        time.sleep(0.3)  # Keep as time.sleep - this is in a sync function
        
        return contextual_text, True
    
    except Exception as e:
        error_str = str(e)
        if "rate_limit_exceeded" in error_str:
            print(f"RATE LIMIT HIT in contextual embedding: {error_str[:200]}...")
        else:
            print(f"Error generating contextual embedding: {e}. Using original chunk instead.")
        return chunk, False


async def generate_contextual_embedding_async(full_document: str, chunk: str) -> Tuple[str, bool]:
    """
    Generate contextual information for a chunk with proper rate limiting.
    
    This async version uses the threading service for rate limiting.
    
    Args:
        full_document: The complete document text
        chunk: The specific chunk of text to generate context for
        
    Returns:
        Tuple containing:
        - The contextual text that situates the chunk within the document
        - Boolean indicating if contextual embedding was performed
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        search_logger.error("No OpenAI API key found in environment")
        return chunk, False
    
    model_choice = os.getenv("MODEL_CHOICE", "gpt-4.1-nano")
    threading_service = get_threading_service()
    
    # Estimate tokens: document preview (5000 chars ≈ 1250 tokens) + chunk + prompt
    estimated_tokens = 1250 + len(chunk.split()) + 100  # Rough estimate
    
    try:
        # Use rate limiting before making the API call
        async with threading_service.rate_limited_operation(estimated_tokens):
            client = openai.AsyncOpenAI(api_key=api_key)
            
            prompt = f"""<document> 
{full_document[:5000]} 
</document>
Here is the chunk we want to situate within the whole document 
<chunk> 
{chunk}
</chunk> 
Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""

            response = await client.chat.completions.create(
                model=model_choice,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that provides concise contextual information."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            context = response.choices[0].message.content.strip()
            contextual_text = f"{context}\n---\n{chunk}"
            
            return contextual_text, True
            
    except Exception as e:
        if "rate_limit_exceeded" in str(e) or "429" in str(e):
            search_logger.warning(f"Rate limit hit in contextual embedding: {e}")
        else:
            search_logger.error(f"Error generating contextual embedding: {e}")
        return chunk, False


def process_chunk_with_context(args):
    """
    Process a single chunk with contextual embedding.
    This function is designed to be used with concurrent.futures.
    
    Args:
        args: Tuple containing (url, content, full_document)
        
    Returns:
        Tuple containing:
        - The contextual text that situates the chunk within the document
        - Boolean indicating if contextual embedding was performed
    """
    url, content, full_document = args
    return generate_contextual_embedding(full_document, content)


async def process_chunk_with_context_async(url: str, content: str, full_document: str) -> Tuple[str, bool]:
    """
    Process a single chunk with contextual embedding using async/await.
    
    Args:
        url: URL of the document
        content: The chunk content
        full_document: The complete document text
        
    Returns:
        Tuple containing:
        - The contextual text that situates the chunk within the document
        - Boolean indicating if contextual embedding was performed
    """
    return await generate_contextual_embedding_async(full_document, content)


def generate_contextual_embeddings_batch(full_documents: List[str], chunks: List[str]) -> List[Tuple[str, bool]]:
    """
    Generate contextual information for multiple chunks in a single API call to avoid rate limiting.
    
    Args:
        full_documents: List of complete document texts
        chunks: List of specific chunks to generate context for
        
    Returns:
        List of tuples containing:
        - The contextual text that situates the chunk within the document
        - Boolean indicating if contextual embedding was performed
    """
    # Get API key directly from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: No OpenAI API key found in environment")
        return [(chunk, False) for chunk in chunks]
    
    # Create OpenAI client
    client = openai.OpenAI(api_key=api_key)
    model_choice = os.getenv("MODEL_CHOICE", "gpt-4.1-nano")
    
    try:
        # Build batch prompt
        batch_prompt = "Process the following chunks and provide contextual information for each:\n\n"
        
        for i, (doc, chunk) in enumerate(zip(full_documents, chunks)):
            batch_prompt += f"CHUNK {i+1}:\n"
            batch_prompt += f"<document>\n{doc[:5000]}\n</document>\n"
            batch_prompt += f"<chunk>\n{chunk}\n</chunk>\n\n"
        
        batch_prompt += "For each chunk, provide a short succinct context to situate it within the overall document for improving search retrieval. Format your response as:\nCHUNK 1: [context]\nCHUNK 2: [context]\netc."
        
        # Make single API call for all chunks
        response = client.chat.completions.create(
            model=model_choice,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates contextual information for document chunks."},
                {"role": "user", "content": batch_prompt}
            ],
            temperature=0
        )
        
        # Parse response
        response_text = response.choices[0].message.content
        results = []
        
        # Extract contexts from response
        lines = response_text.strip().split('\n')
        chunk_contexts = {}
        
        for line in lines:
            if line.strip().startswith("CHUNK"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    chunk_num = int(parts[0].strip().split()[1]) - 1
                    context = parts[1].strip()
                    chunk_contexts[chunk_num] = context
        
        # Build results
        for i, chunk in enumerate(chunks):
            if i in chunk_contexts:
                contextual_text = chunk_contexts[i] + "\n\n" + chunk
                results.append((contextual_text, True))
            else:
                results.append((chunk, False))
        
        return results
        
    except Exception as e:
        if "rate_limit_exceeded" in str(e) or "429" in str(e):
            print(f"RATE LIMIT HIT in batch contextual embedding: {e}")
        else:
            print(f"Error in batch contextual embedding: {e}")
        return [(chunk, False) for chunk in chunks]