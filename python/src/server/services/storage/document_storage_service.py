"""
Document Storage Service

Handles storage of documents in Supabase with parallel processing support.
"""
import os
import asyncio
import concurrent.futures
from typing import List, Dict, Any, Optional
from supabase import Client
from urllib.parse import urlparse
from fastapi import WebSocket

from ...config.logfire_config import search_logger, safe_span
from ..embeddings.embedding_service import create_embeddings_batch_async
from ..embeddings.contextual_embedding_service import (
    process_chunk_with_context,
    generate_contextual_embeddings_batch
)
from ..client_manager import get_supabase_client


async def add_documents_to_supabase(
    client, 
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
    
    This is the simpler sequential version for smaller batches.
    
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
    with safe_span("add_documents_to_supabase",
                           total_documents=len(contents),
                           batch_size=batch_size) as span:
        
        # Simple progress reporting helper with batch info support
        async def report_progress(message: str, percentage: int, batch_info: dict = None):
            if progress_callback and asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(message, percentage, batch_info)
            if websocket:
                data = {
                    "type": "document_storage_progress",
                    "message": message,
                    "percentage": percentage
                }
                if batch_info:
                    data.update(batch_info)
                await websocket.send_json(data)
                await asyncio.sleep(0)  # Yield control
        
        # Get unique URLs to delete existing records
        unique_urls = list(set(urls))
        
        # Delete existing records for these URLs
        try:
            if unique_urls:
                client.table("crawled_pages").delete().in_("url", unique_urls).execute()
                search_logger.info(f"Deleted existing records for {len(unique_urls)} URLs")
        except Exception as e:
            search_logger.warning(f"Batch delete failed: {e}. Trying one-by-one deletion as fallback.")
            # Fallback: delete records one by one
            for url in unique_urls:
                try:
                    client.table("crawled_pages").delete().eq("url", url).execute()
                except Exception as inner_e:
                    search_logger.error(f"Error deleting record for URL {url}: {inner_e}")
        
        # Check if contextual embeddings are enabled
        use_contextual_embeddings = os.getenv("USE_CONTEXTUAL_EMBEDDINGS", "false") == "true"
        
        # Process in batches to avoid memory issues
        for batch_num, i in enumerate(range(0, len(contents), batch_size), 1):
            batch_end = min(i + batch_size, len(contents))
            
            # Get batch slices
            batch_urls = urls[i:batch_end]
            batch_chunk_numbers = chunk_numbers[i:batch_end]
            batch_contents = contents[i:batch_end]
            batch_metadatas = metadatas[i:batch_end]
            
            # Prepare progress message
            total_batches = (len(contents) + batch_size - 1) // batch_size
            overall_percentage = int((i / len(contents)) * 100)
            batch_msg = f"Processing batch {batch_num}/{total_batches}"
            batch_info = {
                'completed_batches': batch_num - 1,
                'total_batches': total_batches,
                'current_batch': batch_num,
                'active_workers': 1,
                'chunks_in_batch': 0,
                'total_chunks_in_batch': batch_end - i
            }
            await report_progress(batch_msg, overall_percentage, batch_info)
            
            # Apply contextual embedding to each chunk if enabled
            if use_contextual_embeddings:
                # Use synchronous batch processing
                full_documents = []
                for j, url in enumerate(batch_urls):
                    full_documents.append(url_to_full_document.get(url, ""))
                
                # Generate contextual embeddings in batch
                contextual_results = generate_contextual_embeddings_batch(full_documents, batch_contents)
                contextual_contents = []
                
                for j, (contextual_text, success) in enumerate(contextual_results):
                    contextual_contents.append(contextual_text)
                    if success:
                        batch_metadatas[j]["contextual_embedding"] = True
            else:
                # If not using contextual embeddings, use original contents
                contextual_contents = batch_contents
            
            # Create embeddings for the batch
            embeddings_msg = f"Batch {batch_num}/{total_batches}: Creating embeddings..."
            embeddings_percentage = overall_percentage + 10
            batch_info['chunks_in_batch'] = len(batch_contents) // 2  # Halfway through
            await report_progress(embeddings_msg, min(embeddings_percentage, 99), batch_info)
            
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
            
            # Insert batch with retry logic
            storing_msg = f"Batch {batch_num}/{total_batches}: Storing in database..."
            storing_percentage = overall_percentage + 15
            batch_info['chunks_in_batch'] = len(batch_contents)  # All chunks processed
            await report_progress(storing_msg, min(storing_percentage, 99), batch_info)
            
            max_retries = 3
            retry_delay = 1.0
            
            for retry in range(max_retries):
                try:
                    client.table("crawled_pages").insert(batch_data).execute()
                    completion_percentage = int(batch_end / len(contents) * 100)
                    complete_msg = f"Batch {batch_num}/{total_batches}: Completed storing {len(batch_data)} chunks"
                    batch_info['completed_batches'] = batch_num
                    batch_info['chunks_in_batch'] = len(batch_data)
                    await report_progress(complete_msg, completion_percentage, batch_info)
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
                                client.table("crawled_pages").insert(record).execute()
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


