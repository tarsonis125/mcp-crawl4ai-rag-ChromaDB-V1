"""
Utility functions for the Crawl4AI MCP server with optimized threading.

Enhanced with:
- ThreadPoolExecutor for CPU-intensive operations
- Rate limiting for OpenAI API calls  
- Memory adaptive processing
- WebSocket-safe operations
- Proper async/await patterns
"""
import os
import concurrent.futures
from typing import List, Dict, Any, Optional, Tuple
import json
from supabase import create_client, Client
from urllib.parse import urlparse
import openai
import re
import time
import asyncio
import logging
import uuid
from datetime import datetime
import threading
from contextlib import asynccontextmanager
from fastapi import WebSocket

# Import Logfire
from .logfire_config import search_logger

# Import threading service for optimizations
from .services.threading_service import (
    get_threading_service, 
    ProcessingMode, 
    ThreadingConfig, 
    RateLimitConfig
)

# Global threading service instance for optimization
_threading_service = None

async def initialize_threading_service(
    threading_config: Optional[ThreadingConfig] = None,
    rate_limit_config: Optional[RateLimitConfig] = None
):
    """Initialize the global threading service for utilities"""
    global _threading_service
    if _threading_service is None:
        from .services.threading_service import ThreadingService
        _threading_service = ThreadingService(threading_config, rate_limit_config)
        await _threading_service.start()
    return _threading_service

def get_utils_threading_service():
    """Get the threading service instance (lazy initialization)"""
    global _threading_service
    if _threading_service is None:
        _threading_service = get_threading_service()
    return _threading_service

# OpenAI client will be configured dynamically when needed

# Deprecated functions - kept for backwards compatibility but should not be used
# The OpenAI API key is loaded into environment at startup via initialize_credentials()
# All code should use os.getenv("OPENAI_API_KEY") directly

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

def get_supabase_client() -> Client:
    """
    Get a Supabase client instance.
    
    Returns:
        Supabase client instance
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables")
    
    try:
        # Let Supabase handle connection pooling internally
        client = create_client(url, key)
        
        # Extract project ID from URL for logging purposes only
        import re
        match = re.match(r'https://([^.]+)\.supabase\.co', url)
        if match:
            project_id = match.group(1)
            search_logger.info(f"Supabase client initialized", 
                             project_id=project_id)
        else:
            search_logger.info("Supabase client initialized successfully")
        
        return client
    except Exception as e:
        search_logger.error(f"Error initializing Supabase client: {e}")
        raise

def create_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Create embeddings for multiple texts in a single API call.
    
    Args:
        texts: List of texts to create embeddings for
        
    Returns:
        List of embeddings (each embedding is a list of floats)
    """
    if not texts:
        return []
    
    # Get API key directly from environment (loaded at startup)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: No OpenAI API key found in environment")
        return [[0.0] * 1536 for _ in texts]
    
    # Create OpenAI client with the API key
    client = openai.OpenAI(api_key=api_key)
    
    max_retries = 3
    retry_delay = 1.0  # Start with 1 second delay
    
    for retry in range(max_retries):
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small", # Hardcoding embedding model for now, will change this later to be more dynamic
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            if retry < max_retries - 1:
                print(f"Error creating batch embeddings (attempt {retry + 1}/{max_retries}): {e}")
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print(f"Failed to create batch embeddings after {max_retries} attempts: {e}")
                # Try creating embeddings one by one as fallback
                print("Attempting to create embeddings individually...")
                embeddings = []
                successful_count = 0
                
                for i, text in enumerate(texts):
                    try:
                        individual_response = client.embeddings.create(
                            model="text-embedding-3-small",
                            input=[text]
                        )
                        embeddings.append(individual_response.data[0].embedding)
                        successful_count += 1
                    except Exception as individual_error:
                        print(f"Failed to create embedding for text {i}: {individual_error}")
                        # Add zero embedding as fallback
                        embeddings.append([0.0] * 1536)
                
                print(f"Successfully created {successful_count}/{len(texts)} embeddings individually")
                return embeddings

def create_embedding(text: str) -> List[float]:
    """
    Create an embedding for a single text using OpenAI's API.
    
    Args:
        text: Text to create an embedding for
        
    Returns:
        List of floats representing the embedding
    """
    try:
        embeddings = create_embeddings_batch([text])
        return embeddings[0] if embeddings else [0.0] * 1536
    except Exception as e:
        print(f"Error creating embedding: {e}")
        # Return empty embedding if there's an error
        return [0.0] * 1536

@asynccontextmanager
async def get_openai_client():
    """
    Get OpenAI client with rate limiting context manager.
    
    Usage:
        async with get_openai_client() as client:
            response = await client.embeddings.create(...)
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

async def create_embeddings_batch_async(
    texts: List[str], 
    websocket: Optional[WebSocket] = None,
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
    
    threading_service = get_utils_threading_service()
    
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

def generate_contextual_embedding(full_document: str, chunk: str) -> Tuple[str, bool]:
    """
    Generate contextual information for a chunk within a document to improve retrieval.
    
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

async def add_documents_to_supabase(
    client: Client, 
    urls: List[str], 
    chunk_numbers: List[int],
    contents: List[str], 
    metadatas: List[Dict[str, Any]],
    url_to_full_document: Dict[str, str],
    batch_size: int = 15,
    progress_callback: Optional[Any] = None,
    websocket: Optional[WebSocket] = None,
    enable_parallel_batches: bool = True
) -> None:
    """
    Add documents to Supabase with threading optimizations and WebSocket safety.
    
    Args:
        client: Supabase client
        urls: List of URLs
        chunk_numbers: List of chunk numbers
        contents: List of document contents
        metadatas: List of document metadata
        url_to_full_document: Dictionary mapping URLs to their full document content
        batch_size: Size of each batch for insertion
        progress_callback: Optional async callback function for progress reporting
        websocket: Optional WebSocket for progress updates
    """
    threading_service = get_utils_threading_service()
    
    with search_logger.span("add_documents_to_supabase",
                           total_documents=len(contents),
                           batch_size=batch_size) as span:
        
        # Get unique URLs to delete existing records
        unique_urls = list(set(urls))
        
        # Delete existing records for these URLs using thread pool
        try:
            if unique_urls:
                await threading_service.run_io_bound(
                    lambda: client.table("crawled_pages").delete().in_("url", unique_urls).execute()
                )
                search_logger.info(f"Deleted existing records for {len(unique_urls)} URLs")
        except Exception as e:
            search_logger.warning(f"Batch delete failed: {e}. Trying individual deletion.")
            # Fallback: delete records one by one
            for url in unique_urls:
                try:
                    await threading_service.run_io_bound(
                        lambda u=url: client.table("crawled_pages").delete().eq("url", u).execute()
                    )
                except Exception as inner_e:
                    search_logger.error(f"Error deleting record for URL {url}: {inner_e}")
        
        # Check configuration
        use_contextual_embeddings = os.getenv("USE_CONTEXTUAL_EMBEDDINGS", "false") == "true"
        max_workers = int(os.getenv("CONTEXTUAL_EMBEDDINGS_MAX_WORKERS", "2"))
        
        search_logger.info(f"Processing {len(contents)} documents",
                          use_contextual_embeddings=use_contextual_embeddings,
                          max_workers=max_workers,
                          batch_size=batch_size)
        
        # Helper function to report progress
        async def report_progress(message: str, percentage: int):
            if progress_callback and asyncio.iscoroutinefunction(progress_callback):
                await progress_callback('document_storage', percentage, message)
            
            if websocket:
                await websocket.send_json({
                    "type": "document_storage_progress",
                    "message": message,
                    "percentage": percentage
                })
            
            search_logger.info(f"Progress: {message} ({percentage}%)")
        
        # Process in batches
        total_batches = (len(contents) + batch_size - 1) // batch_size
        
        for batch_num, i in enumerate(range(0, len(contents), batch_size), 1):
            batch_end = min(i + batch_size, len(contents))
            batch_progress_msg = f"Batch {batch_num}/{total_batches}: Processing items {i+1}-{batch_end} of {len(contents)}"
            
            # Calculate overall progress
            if i == 0:
                overall_percentage = 10
            else:
                overall_percentage = int((i / len(contents)) * 100)
            
            await report_progress(batch_progress_msg, overall_percentage)
            
            # Get batch slices
            batch_urls = urls[i:batch_end]
            batch_chunk_numbers = chunk_numbers[i:batch_end]
            batch_contents = contents[i:batch_end]
            batch_metadatas = metadatas[i:batch_end]
            
            # Apply contextual embedding if enabled
            if use_contextual_embeddings:
                embedding_msg = f"Batch {batch_num}/{total_batches}: Creating contextual embeddings..."
                embedding_percentage = overall_percentage + 5
                await report_progress(embedding_msg, min(embedding_percentage, 99))
                
                # Prepare arguments for parallel processing
                process_args = []
                for j, content in enumerate(batch_contents):
                    url = batch_urls[j]
                    full_document = url_to_full_document.get(url, "")
                    process_args.append((url, content, full_document))
                
                # Process with adaptive concurrency
                async def process_contextual_chunk(args):
                    url, content, full_document = args
                    return await asyncio.get_event_loop().run_in_executor(
                        None, process_chunk_with_context, args
                    )
                
                contextual_results = await threading_service.batch_process(
                    items=process_args,
                    process_func=process_contextual_chunk,
                    mode=ProcessingMode.CPU_INTENSIVE,
                    websocket=websocket
                )
                
                # Extract results
                contextual_contents = []
                for j, result in enumerate(contextual_results):
                    if result and len(result) == 2:
                        contextual_text, success = result
                        if success:
                            contextual_contents.append(contextual_text)
                            batch_metadatas[j]["contextual_embedding"] = True
                        else:
                            contextual_contents.append(batch_contents[j])
                    else:
                        contextual_contents.append(batch_contents[j])
            else:
                contextual_contents = batch_contents
            
            # Create embeddings for the batch
            embeddings_msg = f"Batch {batch_num}/{total_batches}: Creating embeddings..."
            embeddings_percentage = overall_percentage + 10
            await report_progress(embeddings_msg, min(embeddings_percentage, 99))
            
            batch_embeddings = await create_embeddings_batch_async(
                contextual_contents, 
                websocket=websocket
            )
            
            # Prepare batch data
            batch_data = []
            for j in range(len(contextual_contents)):
                # Extract source_id from URL
                parsed_url = urlparse(batch_urls[j])
                source_id = parsed_url.netloc or parsed_url.path
                
                data = {
                    "url": batch_urls[j],
                    "chunk_number": batch_chunk_numbers[j],
                    "content": contextual_contents[j],
                    "metadata": {
                        "chunk_size": len(contextual_contents[j]),
                        **batch_metadatas[j]
                    },
                    "source_id": source_id,
                    "embedding": batch_embeddings[j]
                }
                batch_data.append(data)
            
            # Insert batch with retry logic using thread pool
            storing_msg = f"Batch {batch_num}/{total_batches}: Storing in database..."
            storing_percentage = overall_percentage + 15
            await report_progress(storing_msg, min(storing_percentage, 99))
            
            max_retries = 3
            retry_delay = 1.0
            
            for retry in range(max_retries):
                try:
                    await threading_service.run_io_bound(
                        lambda: client.table("crawled_pages").insert(batch_data).execute()
                    )
                    completion_percentage = int(batch_end / len(contents) * 100)
                    complete_msg = f"Batch {batch_num}/{total_batches}: Completed storing {len(batch_data)} chunks"
                    await report_progress(complete_msg, completion_percentage)
                    break
                    
                except Exception as e:
                    if retry < max_retries - 1:
                        search_logger.warning(f"Error inserting batch (attempt {retry + 1}/{max_retries}): {e}")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        search_logger.error(f"Failed to insert batch after {max_retries} attempts: {e}")
                        # Try individual inserts as last resort
                        successful_inserts = 0
                        for record in batch_data:
                            try:
                                await threading_service.run_io_bound(
                                    lambda r=record: client.table("crawled_pages").insert(r).execute()
                                )
                                successful_inserts += 1
                            except Exception as individual_error:
                                search_logger.error(f"Failed individual insert for {record['url']}: {individual_error}")
                        
                        search_logger.info(f"Individual inserts: {successful_inserts}/{len(batch_data)} successful")
            
            # WebSocket-safe delay between batches
            if i + batch_size < len(contents):
                delay = 1.5 if use_contextual_embeddings else 0.5
                await asyncio.sleep(delay)
        
        # Final completion
        await report_progress(f"Successfully stored all {len(contents)} documents", 100)
        span.set_attribute("success", True)
        span.set_attribute("total_processed", len(contents))


async def add_documents_to_supabase_parallel(
    client: Client, 
    urls: List[str], 
    chunk_numbers: List[int],
    contents: List[str], 
    metadatas: List[Dict[str, Any]],
    url_to_full_document: Dict[str, str],
    batch_size: int = 15,
    progress_callback: Optional[Any] = None,
    websocket: Optional[WebSocket] = None,
    max_workers: int = 3
) -> None:
    """
    Add documents to Supabase with parallel batch processing and worker tracking.
    """
    threading_service = get_utils_threading_service()
    
    with search_logger.span("add_documents_to_supabase_parallel",
                           total_documents=len(contents),
                           batch_size=batch_size,
                           max_workers=max_workers) as span:
        
        # Get unique URLs to delete existing records
        unique_urls = list(set(urls))
        
        # Delete existing records for these URLs
        try:
            if unique_urls:
                await threading_service.run_io_bound(
                    lambda: client.table("crawled_pages").delete().in_("url", unique_urls).execute()
                )
                search_logger.info(f"Deleted existing records for {len(unique_urls)} URLs")
        except Exception as e:
            search_logger.warning(f"Batch delete failed: {e}")
        
        # Check configuration
        use_contextual_embeddings = os.getenv("USE_CONTEXTUAL_EMBEDDINGS", "false") == "true"
        
        # Create batches
        total_batches = (len(contents) + batch_size - 1) // batch_size
        batches = []
        
        for batch_num, i in enumerate(range(0, len(contents), batch_size), 1):
            batch_end = min(i + batch_size, len(contents))
            batch = {
                'batch_num': batch_num,
                'start_idx': i,
                'end_idx': batch_end,
                'urls': urls[i:batch_end],
                'chunk_numbers': chunk_numbers[i:batch_end],
                'contents': contents[i:batch_end],
                'metadatas': metadatas[i:batch_end]
            }
            batches.append(batch)
        
        # Track worker progress
        worker_progress = {}
        completed_batches = 0
        lock = asyncio.Lock()
        
        async def process_batch(batch_data: Dict[str, Any], worker_id: int) -> None:
            nonlocal completed_batches
            
            batch_num = batch_data['batch_num']
            batch_contents = batch_data['contents']
            batch_urls = batch_data['urls']
            batch_metadatas = batch_data['metadatas']
            batch_chunk_numbers = batch_data['chunk_numbers']
            
            try:
                # Report worker started
                worker_data = {
                    "worker_id": str(worker_id),
                    "status": "processing",
                    "batch_num": batch_num,
                    "total_batches": total_batches,
                    "completed_batches": completed_batches,
                    "progress": 0,
                    "message": f"Worker {worker_id} processing batch {batch_num}/{total_batches}",
                    "pages_crawled": 0,
                    "total_pages": batch_size
                }
                
                # Update worker progress tracking
                async with lock:
                    worker_progress[str(worker_id)] = worker_data
                
                if websocket:
                    # Send both worker progress and aggregated progress with workers
                    await websocket.send_json({
                        "type": "document_storage_progress",
                        "percentage": int((completed_batches / total_batches) * 100),
                        "completed_batches": completed_batches,
                        "total_batches": total_batches,
                        "workers": list(worker_progress.values()),
                        "parallelWorkers": max_workers,
                        "totalJobs": total_batches,
                        "message": f"Document storage: {completed_batches}/{total_batches} batches completed"
                    })
                    await asyncio.sleep(0)  # Yield control after WebSocket send
                
                # Apply contextual embedding if enabled
                if use_contextual_embeddings:
                    # Report embedding progress
                    async with lock:
                        worker_progress[str(worker_id)]["progress"] = 20
                        worker_progress[str(worker_id)]["message"] = f"Worker {worker_id}: Creating embeddings"
                    
                    if websocket:
                        await websocket.send_json({
                            "type": "document_storage_progress",
                            "percentage": int((completed_batches / total_batches) * 100),
                            "completed_batches": completed_batches,
                            "total_batches": total_batches,
                            "workers": list(worker_progress.values()),
                            "parallelWorkers": max_workers,
                            "totalJobs": total_batches,
                            "message": f"Document storage: {completed_batches}/{total_batches} batches completed"
                        })
                        await asyncio.sleep(0)  # Yield control after WebSocket send
                    
                    process_args = []
                    for j, content in enumerate(batch_contents):
                        url = batch_urls[j]
                        full_document = url_to_full_document.get(url, "")
                        process_args.append((url, content, full_document))
                    
                    # Process contextual embeddings
                    contextual_contents = []
                    for args in process_args:
                        result = await asyncio.get_event_loop().run_in_executor(
                            None, process_chunk_with_context, args
                        )
                        if result and len(result) == 2:
                            contextual_text, success = result
                            contextual_contents.append(contextual_text if success else args[1])
                        else:
                            contextual_contents.append(args[1])
                else:
                    contextual_contents = batch_contents
                
                # Create embeddings
                async with lock:
                    worker_progress[str(worker_id)]["progress"] = 50
                    worker_progress[str(worker_id)]["message"] = f"Worker {worker_id}: Creating embeddings"
                
                if websocket:
                    await websocket.send_json({
                        "type": "document_storage_progress",
                        "percentage": int((completed_batches / total_batches) * 100),
                        "completed_batches": completed_batches,
                        "total_batches": total_batches,
                        "workers": list(worker_progress.values()),
                        "parallelWorkers": max_workers,
                        "totalJobs": total_batches,
                        "message": f"Document storage: {completed_batches}/{total_batches} batches completed"
                    })
                    await asyncio.sleep(0)  # Yield control after WebSocket send
                
                batch_embeddings = await create_embeddings_batch_async(contextual_contents, websocket=None)
                
                # Prepare batch data
                batch_data = []
                for j in range(len(contextual_contents)):
                    parsed_url = urlparse(batch_urls[j])
                    source_id = parsed_url.netloc or parsed_url.path
                    
                    data = {
                        "url": batch_urls[j],
                        "chunk_number": batch_chunk_numbers[j],
                        "content": contextual_contents[j],
                        "metadata": {
                            "chunk_size": len(contextual_contents[j]),
                            **batch_metadatas[j]
                        },
                        "source_id": source_id,
                        "embedding": batch_embeddings[j]
                    }
                    batch_data.append(data)
                
                # Store in database
                async with lock:
                    worker_progress[str(worker_id)]["progress"] = 80
                    worker_progress[str(worker_id)]["message"] = f"Worker {worker_id}: Storing in database"
                
                if websocket:
                    await websocket.send_json({
                        "type": "document_storage_progress",
                        "percentage": int((completed_batches / total_batches) * 100),
                        "completed_batches": completed_batches,
                        "total_batches": total_batches,
                        "workers": list(worker_progress.values()),
                        "parallelWorkers": max_workers,
                        "totalJobs": total_batches,
                        "message": f"Document storage: {completed_batches}/{total_batches} batches completed"
                    })
                    await asyncio.sleep(0)  # Yield control after WebSocket send
                
                await threading_service.run_io_bound(
                    lambda: client.table("crawled_pages").insert(batch_data).execute()
                )
                
                # Update completed count
                async with lock:
                    completed_batches += 1
                
                # Report completion
                async with lock:
                    worker_progress[str(worker_id)]["progress"] = 100
                    worker_progress[str(worker_id)]["status"] = "completed"
                    worker_progress[str(worker_id)]["message"] = f"Worker {worker_id} completed batch {batch_num}"
                
                if websocket:
                    # Send overall progress with updated worker info
                    overall_progress = int((completed_batches / total_batches) * 100)
                    await websocket.send_json({
                        "type": "document_storage_progress",
                        "percentage": overall_progress,
                        "completed_batches": completed_batches,
                        "total_batches": total_batches,
                        "workers": list(worker_progress.values()),
                        "parallelWorkers": max_workers,
                        "totalJobs": total_batches,
                        "message": f"Document storage: {completed_batches}/{total_batches} batches completed"
                    })
                    await asyncio.sleep(0)  # Yield control after WebSocket send
                
            except Exception as e:
                search_logger.error(f"Worker {worker_id} failed on batch {batch_num}: {e}")
                
                # Update worker status to error
                async with lock:
                    worker_progress[str(worker_id)]["status"] = "error"
                    worker_progress[str(worker_id)]["error"] = str(e)
                    worker_progress[str(worker_id)]["message"] = f"Worker {worker_id} failed: {str(e)[:100]}"
                
                if websocket:
                    # Send comprehensive error update with all worker data
                    await websocket.send_json({
                        "type": "document_storage_progress",
                        "percentage": int((completed_batches / total_batches) * 100),
                        "completed_batches": completed_batches,
                        "total_batches": total_batches,
                        "workers": list(worker_progress.values()),
                        "parallelWorkers": max_workers,
                        "totalJobs": total_batches,
                        "message": f"Document storage: {completed_batches}/{total_batches} batches completed (worker {worker_id} failed)",
                        "worker_error": {
                            "worker_id": worker_id,
                            "batch_num": batch_num,
                            "error": str(e)
                        }
                    })
                    await asyncio.sleep(0)  # Yield control after WebSocket send
        
        # Create worker pool
        semaphore = asyncio.Semaphore(max_workers)
        worker_id_counter = 0
        active_workers = {}
        
        async def worker_wrapper(batch: Dict[str, Any]) -> None:
            nonlocal worker_id_counter
            
            async with semaphore:
                # Assign worker ID
                async with lock:
                    for i in range(1, max_workers + 1):
                        if i not in active_workers:
                            worker_id = i
                            active_workers[worker_id] = batch['batch_num']
                            break
                
                try:
                    await process_batch(batch, worker_id)
                finally:
                    # Release worker ID
                    async with lock:
                        if worker_id in active_workers:
                            del active_workers[worker_id]
        
        # Create background tasks that don't block
        background_tasks = set()
        
        # Track completion without blocking
        tasks_completed = 0
        tasks_total = len(batches)
        completion_event = asyncio.Event()
        
        async def track_completion(task):
            nonlocal tasks_completed
            try:
                await task
            except Exception as e:
                search_logger.error(f"Batch processing error: {e}")
            finally:
                async with lock:
                    tasks_completed += 1
                    if tasks_completed == tasks_total:
                        completion_event.set()
        
        # Start all tasks without blocking
        for batch in batches:
            task = asyncio.create_task(worker_wrapper(batch))
            tracking_task = asyncio.create_task(track_completion(task))
            background_tasks.add(tracking_task)
            # Remove reference when done to prevent memory leak
            tracking_task.add_done_callback(background_tasks.discard)
        
        # Wait for all tasks to complete without blocking event loop
        await completion_event.wait()
        
        # Final completion
        if progress_callback and asyncio.iscoroutinefunction(progress_callback):
            await progress_callback('document_storage', 100, f"Successfully stored all {len(contents)} documents")
        
        span.set_attribute("success", True)
        span.set_attribute("total_processed", len(contents))

def search_documents(
    client: Client,
    query: str,
    match_count: int = 5,
    threshold: float = 0.7,
    filter_metadata: dict = None,
    use_hybrid_search: bool = False,
    cached_api_key: str = None
) -> List[Dict[str, Any]]:
    """
    Search for documents in the database using semantic search.
    
    Args:
        client: Supabase client
        query: Search query string
        match_count: Number of results to return
        threshold: Similarity threshold for results
        filter_metadata: Optional metadata filter dict
        use_hybrid_search: Whether to use hybrid keyword + semantic search
        cached_api_key: Cached OpenAI API key for embeddings
    
    Returns:
        List of matching documents
    """
    with search_logger.span("vector_search", 
                           query_length=len(query),
                           match_count=match_count,
                           threshold=threshold,
                           has_filter=filter_metadata is not None) as span:
        try:
            search_logger.info("Document search started", 
                              query=query[:100] + "..." if len(query) > 100 else query,
                              match_count=match_count,
                              threshold=threshold,
                              filter_metadata=filter_metadata)
            
            # Create embedding for the query
            with search_logger.span("create_embedding"):
                query_embedding = create_embedding(query)
                
                if not query_embedding:
                    search_logger.error("Failed to create embedding for query")
                    return []
                
                span.set_attribute("embedding_dimensions", len(query_embedding))
            
            # Build the filter for the RPC call
            with search_logger.span("prepare_rpc_params"):
                rpc_params = {
                    "query_embedding": query_embedding,
                    "match_count": match_count
                }
                
                # Add filter to RPC params if provided
                if filter_metadata:
                    search_logger.debug("Adding filter to RPC params", filter_metadata=filter_metadata)
                    
                    # Check if we have a source filter specifically
                    if "source" in filter_metadata:
                        # Use the version with source_filter parameter
                        rpc_params["source_filter"] = filter_metadata["source"]
                        # Also add the general filter as empty jsonb to satisfy the function signature
                        rpc_params["filter"] = {}
                    else:
                        # Use the general filter parameter
                        rpc_params["filter"] = filter_metadata
                    
                    span.set_attribute("filter_applied", True)
                    span.set_attribute("filter_keys", list(filter_metadata.keys()) if filter_metadata else [])
                else:
                    # No filter provided - use empty jsonb for filter parameter
                    rpc_params["filter"] = {}
            
            # Call the RPC function
            with search_logger.span("supabase_rpc_call"):
                search_logger.debug("Calling Supabase RPC function", 
                                  function_name="match_crawled_pages",
                                  rpc_params_keys=list(rpc_params.keys()))
                
                response = client.rpc("match_crawled_pages", rpc_params).execute()
                span.set_attribute("rpc_success", True)
                span.set_attribute("raw_results_count", len(response.data) if response.data else 0)
            
            results_count = len(response.data) if response.data else 0
            
            span.set_attribute("success", True)
            span.set_attribute("final_results_count", results_count)
            
            if results_count > 0:
                search_logger.debug("Search results preview",
                                  first_result_url=response.data[0].get('url') if response.data else None,
                                  first_result_similarity=response.data[0].get('similarity') if response.data else None)
            
            search_logger.info("Document search completed successfully", 
                              final_results_count=results_count)
            
            return response.data or []
            
        except Exception as e:
            span.record_exception(e)
            span.set_attribute("success", False)
            span.set_attribute("error_type", type(e).__name__)
            
            search_logger.exception("Document search failed",
                                   error=str(e),
                                   error_type=type(e).__name__,
                                   query=query[:50])
            # Return empty list on error instead of raising
            return []


def extract_code_blocks(markdown_content: str, min_length: int = 1000) -> List[Dict[str, Any]]:
    """
    Extract code blocks from markdown content along with context.
    
    Args:
        markdown_content: The markdown content to extract code blocks from
        min_length: Minimum length of code blocks to extract (default: 1000 characters)
        
    Returns:
        List of dictionaries containing code blocks and their context
    """
    code_blocks = []
    
    # Skip if content starts with triple backticks (edge case for files wrapped in backticks)
    content = markdown_content.strip()
    start_offset = 0
    if content.startswith('```'):
        # Skip the first triple backticks
        start_offset = 3
        print("Skipping initial triple backticks")
    
    # Find all occurrences of triple backticks
    backtick_positions = []
    pos = start_offset
    while True:
        pos = markdown_content.find('```', pos)
        if pos == -1:
            break
        backtick_positions.append(pos)
        pos += 3
    
    # Process pairs of backticks
    i = 0
    while i < len(backtick_positions) - 1:
        start_pos = backtick_positions[i]
        end_pos = backtick_positions[i + 1]
        
        # Extract the content between backticks
        code_section = markdown_content[start_pos+3:end_pos]
        
        # Check if there's a language specifier on the first line
        lines = code_section.split('\n', 1)
        if len(lines) > 1:
            # Check if first line is a language specifier (no spaces, common language names)
            first_line = lines[0].strip()
            if first_line and not ' ' in first_line and len(first_line) < 20:
                language = first_line
                code_content = lines[1].strip() if len(lines) > 1 else ""
            else:
                language = ""
                code_content = code_section.strip()
        else:
            language = ""
            code_content = code_section.strip()
        
        # Skip if code block is too short
        if len(code_content) < min_length:
            i += 2  # Move to next pair
            continue
        
        # Extract context before (1000 chars)
        context_start = max(0, start_pos - 1000)
        context_before = markdown_content[context_start:start_pos].strip()
        
        # Extract context after (1000 chars)
        context_end = min(len(markdown_content), end_pos + 3 + 1000)
        context_after = markdown_content[end_pos + 3:context_end].strip()
        
        code_blocks.append({
            'code': code_content,
            'language': language,
            'context_before': context_before,
            'context_after': context_after,
            'full_context': f"{context_before}\n\n{code_content}\n\n{context_after}"
        })
        
        # Move to next pair (skip the closing backtick we just processed)
        i += 2
    
    return code_blocks


def generate_code_example_summary(code: str, context_before: str, context_after: str) -> str:
    """
    Generate a summary for a code example using its surrounding context.
    
    Args:
        code: The code example
        context_before: Context before the code
        context_after: Context after the code
        
    Returns:
        A summary of what the code example demonstrates
    """
    # Get the decrypted API key
    api_key = get_openai_api_key_sync()
    if not api_key:
        print("Error: No OpenAI API key available for code example summary")
        return "Code example for demonstration purposes."
    
    # Create OpenAI client with the decrypted key
    client = openai.OpenAI(api_key=api_key)
    
    model_choice = os.getenv("MODEL_CHOICE")
    
    # Create the prompt
    prompt = f"""<context_before>
{context_before[-500:] if len(context_before) > 500 else context_before}
</context_before>

<code_example>
{code[:1500] if len(code) > 1500 else code}
</code_example>

<context_after>
{context_after[:500] if len(context_after) > 500 else context_after}
</context_after>

Based on the code example and its surrounding context, provide a concise summary (2-3 sentences) that describes what this code example demonstrates and its purpose. Focus on the practical application and key concepts illustrated.
"""
    
    try:
        response = client.chat.completions.create(
            model=model_choice,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides concise code example summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=100
        )
        
        result = response.choices[0].message.content.strip()
        
        # Add a small delay to prevent rate limiting when running in parallel
        time.sleep(0.3)  # Keep as time.sleep - this is in a sync function
        
        return result
    
    except Exception as e:
        print(f"Error generating code example summary: {e}")
        return "Code example for demonstration purposes."


def add_code_examples_to_supabase(
    client: Client,
    urls: List[str],
    chunk_numbers: List[int],
    code_examples: List[str],
    summaries: List[str],
    metadatas: List[Dict[str, Any]],
    batch_size: int = 20
):
    """
    Add code examples to the Supabase code_examples table in batches.
    
    Args:
        client: Supabase client
        urls: List of URLs
        chunk_numbers: List of chunk numbers
        code_examples: List of code example contents
        summaries: List of code example summaries
        metadatas: List of metadata dictionaries
        batch_size: Size of each batch for insertion
    """
    if not urls:
        return
        
    # Delete existing records for these URLs
    unique_urls = list(set(urls))
    for url in unique_urls:
        try:
            client.table('code_examples').delete().eq('url', url).execute()
        except Exception as e:
            print(f"Error deleting existing code examples for {url}: {e}")
    
    # Process in batches
    total_items = len(urls)
    for i in range(0, total_items, batch_size):
        batch_end = min(i + batch_size, total_items)
        batch_texts = []
        
        # Create combined texts for embedding (code + summary)
        for j in range(i, batch_end):
            combined_text = f"{code_examples[j]}\n\nSummary: {summaries[j]}"
            batch_texts.append(combined_text)
        
        # Create embeddings for the batch
        embeddings = create_embeddings_batch(batch_texts)
        
        # Check if embeddings are valid (not all zeros)
        valid_embeddings = []
        for embedding in embeddings:
            if embedding and not all(v == 0.0 for v in embedding):
                valid_embeddings.append(embedding)
            else:
                print(f"Warning: Zero or invalid embedding detected, creating new one...")
                # Try to create a single embedding as fallback
                single_embedding = create_embedding(batch_texts[len(valid_embeddings)])
                valid_embeddings.append(single_embedding)
        
        # Prepare batch data
        batch_data = []
        for j, embedding in enumerate(valid_embeddings):
            idx = i + j
            
            # Extract source_id from URL
            parsed_url = urlparse(urls[idx])
            source_id = parsed_url.netloc or parsed_url.path
            
            batch_data.append({
                'url': urls[idx],
                'chunk_number': chunk_numbers[idx],
                'content': code_examples[idx],
                'summary': summaries[idx],
                'metadata': metadatas[idx],  # Store as JSON object, not string
                'source_id': source_id,
                'embedding': embedding
            })
        
        # Insert batch into Supabase with retry logic
        max_retries = 3
        retry_delay = 1.0  # Start with 1 second delay
        
        for retry in range(max_retries):
            try:
                client.table('code_examples').insert(batch_data).execute()
                # Success - break out of retry loop
                break
            except Exception as e:
                if retry < max_retries - 1:
                    print(f"Error inserting batch into Supabase (attempt {retry + 1}/{max_retries}): {e}")
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)  # Keep as time.sleep - this is in a sync function
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Final attempt failed
                    print(f"Failed to insert batch after {max_retries} attempts: {e}")
                    # Optionally, try inserting records one by one as a last resort
                    print("Attempting to insert records individually...")
                    successful_inserts = 0
                    for record in batch_data:
                        try:
                            client.table('code_examples').insert(record).execute()
                            successful_inserts += 1
                        except Exception as individual_error:
                            print(f"Failed to insert individual record for URL {record['url']}: {individual_error}")
                    
                    if successful_inserts > 0:
                        print(f"Successfully inserted {successful_inserts}/{len(batch_data)} records individually")
        print(f"Inserted batch {i//batch_size + 1} of {(total_items + batch_size - 1)//batch_size} code examples")


def generate_source_title_and_metadata(source_id: str, content: str, knowledge_type: str = "technical", tags: List[str] = None) -> Tuple[str, Dict[str, Any]]:
    """
    Generate a descriptive title and metadata for a source using OpenAI.
    
    Args:
        source_id: The source ID (domain)
        content: The content to analyze
        knowledge_type: Type of knowledge (technical/business)
        tags: List of tags to include in metadata
        
    Returns:
        Tuple of (title, metadata_dict)
    """
    if tags is None:
        tags = []
    
    # Get the decrypted API key
    api_key = get_openai_api_key_sync()
    if not api_key:
        print(f"Error: No OpenAI API key available for title/metadata generation for {source_id}")
        return f"Content from {source_id}", {
            "knowledge_type": knowledge_type,
            "tags": tags,
            "auto_generated": False
        }
    
    # Create OpenAI client with the decrypted key
    client = openai.OpenAI(api_key=api_key)
    
    # Get the model choice from environment variables
    model_choice = os.getenv("MODEL_CHOICE", "gpt-4o-mini")
    
    # Limit content length to avoid token limits
    truncated_content = content[:15000] if len(content) > 15000 else content
    
    # Create the prompt for generating title and metadata
    prompt = f"""<source_content>
{truncated_content}
</source_content>

Analyze the above content from '{source_id}' and provide:

1. A concise, descriptive title (max 80 characters) that clearly describes what this resource is about. Examples:
   - "Pydantic AI API Reference"
   - "FastAPI Complete Guide" 
   - "React Component Library Documentation"
   - "Machine Learning Best Practices"

2. Determine the knowledge type: "technical" or "business"

3. Generate 3-7 relevant tags that categorize this content (e.g., python, ai, framework, documentation, tutorial, api, etc.)

4. Identify the primary category (e.g., documentation, tutorial, reference, guide, blog, paper)

5. If applicable, identify the programming language or technology focus

Respond in this exact JSON format:
{{
  "title": "Your generated title here",
  "knowledge_type": "technical",
  "tags": ["tag1", "tag2", "tag3"],
  "category": "documentation",
  "technology": "python",
  "difficulty": "beginner|intermediate|advanced"
}}"""
    
    try:
        # Call the OpenAI API to generate title and metadata
        response = client.chat.completions.create(
            model=model_choice,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes technical content and generates descriptive titles and metadata. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        
        # Parse the JSON response
        response_text = response.choices[0].message.content.strip()
        
        # Try to extract JSON from the response
        import json
        try:
            # Find JSON in the response (in case there's extra text)
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
            else:
                result = json.loads(response_text)
            
            # Extract title and build metadata
            title = result.get("title", f"Content from {source_id}")
            metadata = {
                "knowledge_type": result.get("knowledge_type", knowledge_type),
                "tags": result.get("tags", tags),
                "category": result.get("category", "documentation"),
                "technology": result.get("technology"),
                "difficulty": result.get("difficulty"),
                "auto_generated": True,
                "generated_at": time.strftime("%Y-%m-%d")
            }
            
            # Remove None values
            metadata = {k: v for k, v in metadata.items() if v is not None}
            
            print(f"Generated title for {source_id}: {title}")
            
            # Add a small delay to prevent rate limiting when running in parallel
            time.sleep(0.3)  # Keep as time.sleep - this is in a sync function
            
            return title, metadata
            
        except json.JSONDecodeError as json_error:
            print(f"Error parsing JSON response for {source_id}: {json_error}")
            print(f"Response was: {response_text}")
            # Fallback to basic title and metadata
            return f"Content from {source_id}", {
                "knowledge_type": knowledge_type,
                "tags": tags,
                "auto_generated": False
            }
    
    except Exception as e:
        print(f"Error generating title/metadata with LLM for {source_id}: {e}")
        return f"Content from {source_id}", {
            "knowledge_type": knowledge_type,
            "tags": tags,
            "auto_generated": False
        }


def update_source_info(client: Client, source_id: str, summary: str, word_count: int, content: str = "", knowledge_type: str = "technical", tags: List[str] = None, update_frequency: int = 7):
    """
    Update or insert source information in the sources table with enhanced title and metadata.
    
    Args:
        client: Supabase client
        source_id: The source ID (domain)
        summary: Summary of the source
        word_count: Total word count for the source
        content: Full content for title/metadata generation
        knowledge_type: Type of knowledge (technical/business)
        tags: List of tags to include in metadata
        update_frequency: Update frequency in days (1=daily, 7=weekly, 30=monthly, 0=never)
    """
    if tags is None:
        tags = []
    
    # Generate enhanced title and metadata using LLM
    title, metadata = generate_source_title_and_metadata(
        source_id=source_id, 
        content=content,  # Pass content as keyword argument
        knowledge_type=knowledge_type,
        tags=tags
    )
    
    # Check if source already exists
    existing_source = client.from_('sources').select('source_id').eq('source_id', source_id).execute()
    
    source_data = {
        'source_id': source_id,
        'title': title,
        'summary': summary,
        'total_word_count': word_count,
        'metadata': metadata,
        'update_frequency': update_frequency,  # Store the update frequency
        'updated_at': 'now()'
    }
    
    if existing_source.data:
        # Update existing source
        result = client.from_('sources').update(source_data).eq('source_id', source_id).execute()
        print(f"Updated existing source: {source_id}")
    else:
        # Insert new source
        source_data['created_at'] = 'now()'
        result = client.from_('sources').insert(source_data).execute()
        print(f"Created new source: {source_id}")
    
    return result


def extract_source_summary(source_id: str, content: str, max_length: int = 500) -> str:
    """
    Extract a summary for a source from its content using an LLM.
    
    This function uses the OpenAI API to generate a concise summary of the source content.
    
    Args:
        source_id: The source ID (domain)
        content: the content to extract a summary from
        max_length: Maximum length of the summary
        
    Returns:
        A summary string
    """
    # Default summary if we can't extract anything meaningful
    default_summary = f"Content from {source_id}"
    
    if not content or len(content.strip()) == 0:
        return default_summary
    
    # Get the decrypted API key
    api_key = get_openai_api_key_sync()
    if not api_key:
        print(f"Error: No OpenAI API key available for source summary generation for {source_id}")
        return default_summary
    
    # Create OpenAI client with the decrypted key
    client = openai.OpenAI(api_key=api_key)
    
    # Get the model choice from environment variables
    model_choice = os.getenv("MODEL_CHOICE")
    
    # Limit content length to avoid token limits
    truncated_content = content[:25000] if len(content) > 25000 else content
    
    # Create the prompt for generating the summary
    prompt = f"""<source_content>
{truncated_content}
</source_content>

The above content is from the documentation for '{source_id}'. Please provide a concise summary (3-5 sentences) that describes what this library/tool/framework is about. The summary should help understand what the library/tool/framework accomplishes and the purpose.
"""
    
    try:
        # Call the OpenAI API to generate the summary
        response = client.chat.completions.create(
            model=model_choice,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides concise library/tool/framework summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=150
        )
        
        # Extract the generated summary
        summary = response.choices[0].message.content.strip()
        
        # Ensure the summary is not too long
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
        
        # Add a small delay to prevent rate limiting when running in parallel
        time.sleep(0.3)  # Keep as time.sleep - this is in a sync function
            
        return summary
    
    except Exception as e:
        print(f"Error generating summary with LLM for {source_id}: {e}. Using default summary.")
        return default_summary


def search_code_examples(
    client: Client, 
    query: str, 
    match_count: int = 10, 
    filter_metadata: Optional[Dict[str, Any]] = None,
    source_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search for code examples in Supabase using vector similarity.
    
    Args:
        client: Supabase client
        query: Query text
        match_count: Maximum number of results to return
        filter_metadata: Optional metadata filter
        source_id: Optional source ID to filter results
        
    Returns:
        List of matching code examples
    """
    # Create a more descriptive query for better embedding match
    # Since code examples are embedded with their summaries, we should make the query more descriptive
    enhanced_query = f"Code example for {query}\n\nSummary: Example code showing {query}"
    
    # Create embedding for the enhanced query
    query_embedding = create_embedding(enhanced_query)
    
    # Execute the search using the match_code_examples function
    try:
        # Only include filter parameter if filter_metadata is provided and not empty
        params = {
            'query_embedding': query_embedding,
            'match_count': match_count
        }
        
        # Only add the filter if it's actually provided and not empty
        if filter_metadata:
            params['filter'] = filter_metadata
            
        # Add source filter if provided
        if source_id:
            params['source_filter'] = source_id
        
        result = client.rpc('match_code_examples', params).execute()
        
        return result.data if result.data else []
    except Exception as e:
        print(f"Error searching code examples: {e}")
        return []
