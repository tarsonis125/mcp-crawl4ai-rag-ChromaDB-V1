"""
Synchronous Document Storage Service

Provides synchronous document storage operations for use in background threads.
Maintains parallel processing for contextual embeddings while avoiding async/await.
"""
import os
import concurrent.futures
from typing import List, Dict, Any, Optional
from queue import Queue
from urllib.parse import urlparse

from ...config.logfire_config import search_logger
from ..credential_service import get_credential_sync
from ..llm_provider_service import get_llm_client_sync, get_embedding_model_sync


def add_documents_to_supabase_sync(
    client,
    urls: List[str],
    chunk_numbers: List[int],
    contents: List[str],
    metadatas: List[Dict[str, Any]],
    url_to_full_document: Dict[str, str],
    batch_size: int = 10,
    progress_queue: Optional[Queue] = None,
    enable_parallel_batches: bool = True
) -> None:
    """
    Synchronous version of add_documents_to_supabase for use in background threads.
    
    Maintains all functionality including parallel contextual embeddings,
    but uses synchronous operations to avoid event loop coordination issues.
    
    Args:
        client: Supabase client
        urls: List of URLs
        chunk_numbers: List of chunk numbers
        contents: List of document contents
        metadatas: List of document metadata
        url_to_full_document: Dictionary mapping URLs to their full document content
        batch_size: Size of each batch for insertion
        progress_queue: Optional queue for progress reporting
        enable_parallel_batches: Enable parallel processing for contextual embeddings
    """
    search_logger.info(f"Starting synchronous document storage for {len(contents)} chunks")
    
    # Helper to report progress
    def report_progress(message: str, percentage: int, batch_info: dict = None):
        if progress_queue:
            update = {
                'status': 'document_storage',
                'log': message,
                'percentage': percentage  # Use the main percentage field
            }
            if batch_info:
                update.update(batch_info)
            progress_queue.put(update)
    
    # Get unique URLs to delete existing records
    unique_urls = list(set(urls))
    
    # Delete existing records for these URLs
    try:
        if unique_urls:
            client.table("crawled_pages").delete().in_("url", unique_urls).execute()
            search_logger.info(f"Deleted existing records for {len(unique_urls)} URLs")
    except Exception as e:
        search_logger.warning(f"Batch delete failed: {e}. Trying one-by-one deletion.")
        for url in unique_urls:
            try:
                client.table("crawled_pages").delete().eq("url", url).execute()
            except Exception as inner_e:
                search_logger.error(f"Error deleting record for URL {url}: {inner_e}")
    
    # Check if contextual embeddings are enabled
    try:
        use_contextual_embeddings = get_credential_sync("USE_CONTEXTUAL_EMBEDDINGS", "false") == "true"
        # Use the configured number of workers (default 10)
        max_workers = int(get_credential_sync("CONTEXTUAL_EMBEDDINGS_MAX_WORKERS", "10"))
    except:
        use_contextual_embeddings = os.getenv("USE_CONTEXTUAL_EMBEDDINGS", "false") == "true"
        max_workers = 10
    
    search_logger.info(f"Contextual embeddings: {use_contextual_embeddings}, Max workers: {max_workers}")
    
    # Get OpenAI client for embeddings
    openai_client = get_llm_client_sync()
    embedding_model = get_embedding_model_sync()
    
    # Initialize batch tracking
    completed_batches = 0
    total_batches = (len(contents) + batch_size - 1) // batch_size
    
    # Process in batches
    for batch_num, i in enumerate(range(0, len(contents), batch_size), 1):
        batch_end = min(i + batch_size, len(contents))
        
        # Get batch slices
        batch_urls = urls[i:batch_end]
        batch_chunk_numbers = chunk_numbers[i:batch_end]
        batch_contents = contents[i:batch_end]
        batch_metadatas = metadatas[i:batch_end]
        
        # Report batch start for EVERY batch
        # Calculate progress based on current batch being processed
        batch_start_progress = int(((batch_num - 1) / total_batches) * 100)
        report_progress(
            f"Processing batch {batch_num}/{total_batches} ({len(batch_contents)} chunks)",
            batch_start_progress,
            {
                'current_batch': batch_num,
                'total_batches': total_batches,
                'chunks_in_batch': len(batch_contents)
            }
        )
        
        # Apply contextual embedding if enabled
        if use_contextual_embeddings:
            # Import the batch function
            from ..embeddings.contextual_embedding_service import generate_contextual_embeddings_batch
            
            # Prepare full documents list for batch processing
            full_documents = []
            for j, content in enumerate(batch_contents):
                url = batch_urls[j]
                full_document = url_to_full_document.get(url, "")
                full_documents.append(full_document)
            
            # Process chunks in batches using the batch function
            # This reduces API calls by ~80% (5 chunks per API call)
            try:
                results = generate_contextual_embeddings_batch(full_documents, batch_contents)
                
                # Extract results
                contextual_contents = []
                successful_count = 0
                for idx, (contextual_text, success) in enumerate(results):
                    contextual_contents.append(contextual_text)
                    if success:
                        batch_metadatas[idx]["contextual_embedding"] = True
                        successful_count += 1
                
                search_logger.info(f"Batch {batch_num}: Generated {successful_count}/{len(batch_contents)} contextual embeddings using batch API")
            except Exception as e:
                search_logger.error(f"Error in batch contextual embedding: {e}")
                # Fallback to original contents
                contextual_contents = batch_contents
                successful_count = 0
        else:
            contextual_contents = batch_contents
        
        # Create embeddings for the batch using synchronous OpenAI client
        try:
            response = openai_client.embeddings.create(
                input=contextual_contents,
                model=embedding_model
            )
            batch_embeddings = [item.embedding for item in response.data]
        except Exception as e:
            search_logger.error(f"Error creating embeddings for batch {batch_num}: {e}")
            # Create zero embeddings as fallback
            batch_embeddings = [[0.0] * 1536 for _ in contextual_contents]
        
        # Prepare batch data
        batch_data = []
        for j in range(len(contextual_contents)):
            # Use source_id from metadata if available, otherwise extract from URL
            if batch_metadatas[j].get('source_id'):
                source_id = batch_metadatas[j]['source_id']
            else:
                # Fallback: Extract source_id from URL
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
        
        # Insert batch using Supabase
        try:
            client.table("crawled_pages").insert(batch_data).execute()
            completed_batches += 1
            search_logger.info(f"Successfully stored batch {batch_num}/{total_batches}")
            
            # Report batch completion progress
            batch_complete_progress = int((batch_num / total_batches) * 100)
            report_progress(
                f"Completed batch {batch_num}/{total_batches}",
                batch_complete_progress,
                {
                    'current_batch': batch_num,
                    'total_batches': total_batches,
                    'completed_batches': completed_batches
                }
            )
        except Exception as e:
            search_logger.error(f"Error storing batch {batch_num}: {e}")
            # Try to insert one by one as fallback
            for data in batch_data:
                try:
                    client.table("crawled_pages").insert([data]).execute()
                except Exception as inner_e:
                    search_logger.error(f"Error storing individual chunk: {inner_e}")
    
    # Final progress report
    report_progress(
        f"Document storage complete: {completed_batches}/{total_batches} batches",
        100,
        {
            'total_chunks': len(contents),
            'total_batches': total_batches,
            'completed_batches': completed_batches
            # DON'T send 'status': 'completed' - only the orchestration service should do that!
        }
    )
    
    search_logger.info(f"Document storage completed: {completed_batches}/{total_batches} batches stored")