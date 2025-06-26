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

from ...logfire_config import search_logger
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
    with search_logger.span("add_documents_to_supabase",
                           total_documents=len(contents),
                           batch_size=batch_size) as span:
        
        # Simple progress reporting helper
        async def report_progress(message: str, percentage: int):
            if progress_callback and asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(message, percentage)
            if websocket:
                await websocket.send_json({
                    "type": "document_storage_progress",
                    "message": message,
                    "percentage": percentage
                })
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
            overall_percentage = int((i / len(contents)) * 100)
            batch_msg = f"Processing batch {batch_num}/{(len(contents) + batch_size - 1) // batch_size}"
            await report_progress(batch_msg, overall_percentage)
            
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
            embeddings_msg = f"Batch {batch_num}/{(len(contents) + batch_size - 1) // batch_size}: Creating embeddings..."
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
            
            # Insert batch with retry logic
            storing_msg = f"Batch {batch_num}/{(len(contents) + batch_size - 1) // batch_size}: Storing in database..."
            storing_percentage = overall_percentage + 15
            await report_progress(storing_msg, min(storing_percentage, 99))
            
            max_retries = 3
            retry_delay = 1.0
            
            for retry in range(max_retries):
                try:
                    client.table("crawled_pages").insert(batch_data).execute()
                    completion_percentage = int(batch_end / len(contents) * 100)
                    complete_msg = f"Batch {batch_num}/{(len(contents) + batch_size - 1) // batch_size}: Completed storing {len(batch_data)} chunks"
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


async def add_documents_to_supabase_parallel(
    client, 
    urls: List[str], 
    chunk_numbers: List[int],
    contents: List[str], 
    metadatas: List[Dict[str, Any]],
    url_to_full_document: Dict[str, str],
    batch_size: int = 15,
    progress_callback: Optional[Any] = None,
    websocket: Optional[WebSocket] = None,
    max_workers: int = 10  # Changed from 3 to 10 for better parallelization
) -> None:
    """
    Add documents to Supabase with simplified parallel batch processing.
    
    Uses ThreadPoolExecutor for CPU-intensive contextual embeddings and
    async for I/O operations. Shows worker progress during embedding phase.
    """
    with search_logger.span("add_documents_to_supabase_parallel",
                           total_documents=len(contents),
                           batch_size=batch_size,
                           max_workers=max_workers) as span:
        
        # Get unique URLs to delete existing records
        unique_urls = list(set(urls))
        
        # Delete existing records for these URLs
        try:
            if unique_urls:
                # Direct Supabase call, no threading service needed
                client.table("crawled_pages").delete().in_("url", unique_urls).execute()
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
        
        # Process batches sequentially but with parallel contextual embeddings
        completed_batches = 0
        
        for batch in batches:
            batch_num = batch['batch_num']
            batch_contents = batch['contents']
            batch_urls = batch['urls']
            batch_metadatas = batch['metadatas']
            batch_chunk_numbers = batch['chunk_numbers']
            
            try:
                # Report batch progress
                if progress_callback:
                    await progress_callback(
                        'document_storage',
                        int((completed_batches / total_batches) * 100),
                        f"Processing batch {batch_num}/{total_batches}",
                        completed_batches=completed_batches,
                        total_batches=total_batches,
                        parallelWorkers=max_workers if use_contextual_embeddings else 1,
                        totalJobs=total_batches
                    )
                
                # Apply contextual embedding if enabled
                if use_contextual_embeddings:
                    # Prepare arguments for parallel processing
                    process_args = []
                    for j, content in enumerate(batch_contents):
                        url = batch_urls[j]
                        full_document = url_to_full_document.get(url, "")
                        process_args.append((url, content, full_document))
                    
                    # Show workers during contextual embedding phase
                    if websocket:
                        # Create worker status for ThreadPool workers
                        workers = []
                        for worker_id in range(1, min(len(process_args), max_workers) + 1):
                            workers.append({
                                "worker_id": str(worker_id),
                                "status": "processing",
                                "batch_num": batch_num,
                                "progress": 0,
                                "message": f"Worker {worker_id}: Generating contextual embeddings"
                            })
                        
                        await websocket.send_json({
                            "type": "document_storage_progress",
                            "percentage": int((completed_batches / total_batches) * 100),
                            "completed_batches": completed_batches,
                            "total_batches": total_batches,
                            "workers": workers,
                            "parallelWorkers": max_workers,
                            "totalJobs": total_batches,
                            "message": f"Batch {batch_num}: Generating contextual embeddings with {len(workers)} workers"
                        })
                        await asyncio.sleep(0)
                    
                    # Process in parallel using ThreadPoolExecutor (like the original)
                    contextual_contents = []
                    
                    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                        # Submit all tasks
                        future_to_idx = {
                            executor.submit(process_chunk_with_context, arg): idx 
                            for idx, arg in enumerate(process_args)
                        }
                        
                        # Track progress
                        completed = 0
                        total = len(future_to_idx)
                        
                        # Process results as they complete
                        for future in concurrent.futures.as_completed(future_to_idx):
                            idx = future_to_idx[future]
                            try:
                                result, success = future.result()
                                contextual_contents.append((idx, result))
                                if success:
                                    batch_metadatas[idx]["contextual_embedding"] = True
                            except Exception as e:
                                search_logger.error(f"Error processing chunk {idx}: {e}")
                                contextual_contents.append((idx, batch_contents[idx]))
                            
                            completed += 1
                            
                            # Update worker progress
                            if websocket and completed % 5 == 0:  # Update every 5 completions
                                # Update worker statuses
                                active_workers = min(total - completed, max_workers)
                                workers = []
                                for worker_id in range(1, active_workers + 1):
                                    workers.append({
                                        "worker_id": str(worker_id),
                                        "status": "processing",
                                        "batch_num": batch_num,
                                        "progress": int((completed / total) * 100),
                                        "message": f"Worker {worker_id}: Processing chunk {completed}/{total}"
                                    })
                                
                                await websocket.send_json({
                                    "type": "document_storage_progress",
                                    "percentage": int((completed_batches / total_batches) * 100),
                                    "completed_batches": completed_batches,
                                    "total_batches": total_batches,
                                    "workers": workers,
                                    "parallelWorkers": active_workers,
                                    "totalJobs": total_batches,
                                    "message": f"Batch {batch_num}: Generated {completed}/{total} contextual embeddings"
                                })
                                await asyncio.sleep(0)
                    
                    # Sort results back into original order
                    contextual_contents.sort(key=lambda x: x[0])
                    contextual_contents = [content for _, content in contextual_contents]
                else:
                    # No contextual embeddings
                    contextual_contents = batch_contents
                
                # Create embeddings
                if websocket:
                    await websocket.send_json({
                        "type": "document_storage_progress",
                        "percentage": int((completed_batches / total_batches) * 100),
                        "completed_batches": completed_batches,
                        "total_batches": total_batches,
                        "workers": [],  # No workers for embedding creation
                        "parallelWorkers": 1,
                        "totalJobs": total_batches,
                        "message": f"Batch {batch_num}: Creating embeddings"
                    })
                    await asyncio.sleep(0)
                
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
                if websocket:
                    await websocket.send_json({
                        "type": "document_storage_progress",
                        "percentage": int((completed_batches / total_batches) * 100),
                        "completed_batches": completed_batches,
                        "total_batches": total_batches,
                        "workers": [],
                        "parallelWorkers": 1,
                        "totalJobs": total_batches,
                        "message": f"Batch {batch_num}: Storing in database"
                    })
                    await asyncio.sleep(0)
                
                # Direct database insert
                client.table("crawled_pages").insert(batch_data).execute()
                
                # Update completed count
                completed_batches += 1
                
                # Report completion
                if websocket:
                    overall_progress = int((completed_batches / total_batches) * 100)
                    await websocket.send_json({
                        "type": "document_storage_progress",
                        "percentage": overall_progress,
                        "completed_batches": completed_batches,
                        "total_batches": total_batches,
                        "workers": [],
                        "parallelWorkers": 1,
                        "totalJobs": total_batches,
                        "message": f"Completed batch {batch_num}/{total_batches}"
                    })
                    await asyncio.sleep(0)
                
            except Exception as e:
                search_logger.error(f"Failed to process batch {batch_num}: {e}")
                if websocket:
                    await websocket.send_json({
                        "type": "document_storage_progress",
                        "percentage": int((completed_batches / total_batches) * 100),
                        "completed_batches": completed_batches,
                        "total_batches": total_batches,
                        "workers": [],
                        "parallelWorkers": 1,
                        "totalJobs": total_batches,
                        "message": f"Batch {batch_num} failed: {str(e)}",
                        "error": str(e)
                    })
                    await asyncio.sleep(0)
                raise
        
        # Final completion
        if progress_callback and asyncio.iscoroutinefunction(progress_callback):
            await progress_callback('document_storage', 100, f"Successfully stored all {len(contents)} documents")
        
        span.set_attribute("success", True)
        span.set_attribute("total_processed", len(contents))