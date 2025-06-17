"""
Document Storage Service Module for Archon RAG

This module provides core document storage and processing functionality
that can be shared between MCP tools and FastAPI endpoints.
"""

import json
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse

from src.utils import (
    get_supabase_client,
    add_documents_to_supabase,
    add_code_examples_to_supabase,
    update_source_info,
    extract_source_summary,
    process_chunk_with_context,
    create_embeddings_batch
)

from src.utils_rag import (
    smart_chunk_markdown,
    extract_section_info,
    extract_code_blocks,
    generate_code_example_summary
)

logger = logging.getLogger(__name__)


class DocumentStorageService:
    """Service class for document storage and processing operations"""
    
    def __init__(self, supabase_client=None):
        """Initialize with optional supabase client"""
        self.supabase_client = supabase_client or get_supabase_client()

    def smart_chunk_markdown(self, text: str, chunk_size: int = 5000) -> List[str]:
        """
        Split text into chunks intelligently with error handling.
        
        This function implements a context-aware chunking strategy that:
        1. Preserves code blocks (```) as complete units when possible
        2. Prefers to break at paragraph boundaries (\\n\\n)
        3. Falls back to sentence boundaries (. ) if needed
        4. Only splits mid-content when absolutely necessary
        """
        if not text or not isinstance(text, str):
            logger.warning("Invalid text provided for chunking")
            return []
            
        try:
            chunks = []
            start = 0
            text_length = len(text)

            while start < text_length:
                # Calculate end position
                end = start + chunk_size

                # If we're at the end of the text, just take what's left
                if end >= text_length:
                    remaining = text[start:].strip()
                    if remaining:
                        chunks.append(remaining)
                    break

                # Try to find a code block boundary first (```)
                chunk = text[start:end]
                code_block = chunk.rfind('```')
                if code_block != -1 and code_block > chunk_size * 0.3:
                    end = start + code_block

                # If no code block, try to break at a paragraph
                elif '\n\n' in chunk:
                    last_break = chunk.rfind('\n\n')
                    if last_break > chunk_size * 0.3:
                        end = start + last_break

                # If no paragraph break, try to break at a sentence
                elif '. ' in chunk:
                    last_period = chunk.rfind('. ')
                    if last_period > chunk_size * 0.3:
                        end = start + last_period + 1

                # Extract chunk and clean it up
                chunk = text[start:end].strip()
                if chunk:
                    chunks.append(chunk)

                # Move start position for next chunk
                start = end

            logger.debug(f"Successfully chunked text into {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error in smart chunking: {e}")
            # Fallback to simple chunking
            try:
                return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
            except Exception as fallback_error:
                logger.error(f"Even fallback chunking failed: {fallback_error}")
                return [text] if text else []

    def extract_section_info(self, chunk: str) -> Dict[str, Any]:
        """Extracts headers and stats from a chunk with error handling."""
        try:
            import re
            headers = re.findall(r'^(#+)\s+(.+)$', chunk, re.MULTILINE)
            header_str = '; '.join([f'{h[0]} {h[1]}' for h in headers]) if headers else ''

            return {
                "headers": header_str,
                "char_count": len(chunk),
                "word_count": len(chunk.split())
            }
        except Exception as e:
            logger.warning(f"Error extracting section info: {e}")
            return {
                "headers": "",
                "char_count": len(chunk) if chunk else 0,
                "word_count": len(chunk.split()) if chunk else 0
            }

    def process_code_example(self, args):
        """Process a single code example to generate its summary with error handling."""
        try:
            code, context_before, context_after = args
            return generate_code_example_summary(code, context_before, context_after)
        except Exception as e:
            logger.warning(f"Error processing code example: {e}")
            return f"Code example (processing failed: {str(e)})"

    def upload_document(self, file_content: str, filename: str, 
                       knowledge_type: str = "technical", tags: List[str] = None, 
                       chunk_size: int = 5000) -> Tuple[bool, Dict[str, Any]]:
        """
        Upload and process a document for RAG storage.
        
        Args:
            file_content: The content of the document
            filename: Name of the file
            knowledge_type: Type of knowledge (default: "technical")
            tags: List of tags for the document
            chunk_size: Maximum size of each chunk (default: 5000)
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            if tags is None:
                tags = []
                
            # Create a pseudo-URL for the uploaded document
            doc_url = f"upload://{filename}"
            
            # Chunk the content
            chunks = self.smart_chunk_markdown(file_content, chunk_size)
            
            # Create documents for storage
            documents = []
            total_word_count = 0
            
            for i, chunk in enumerate(chunks):
                section_info = self.extract_section_info(chunk)
                total_word_count += section_info["word_count"]
                
                documents.append({
                    "content": chunk,
                    "url": doc_url,
                    "chunk_index": i,
                    "metadata": {
                        "source_id": f"upload_{filename}",
                        "title": filename,
                        "knowledge_type": knowledge_type,
                        "tags": tags,
                        "headers": section_info["headers"],
                        "char_count": section_info["char_count"],
                        "word_count": section_info["word_count"]
                    }
                })
            
            # Calculate total word count for source info
            total_word_count = sum(doc['metadata']['word_count'] for doc in documents)
            source_id = f"upload_{filename}"
            
            # Create source FIRST (before inserting documents to avoid foreign key constraint)
            source_summary = extract_source_summary(source_id, file_content[:5000])
            update_source_info(self.supabase_client, source_id, source_summary, total_word_count, file_content[:5000], knowledge_type, tags, 0)  # File uploads default to never update
            
            # Store in Supabase - prepare data for the function
            urls = [doc['url'] for doc in documents]
            chunk_numbers = [doc['chunk_index'] for doc in documents]  # Keep 0-based indexing like original
            contents = [doc['content'] for doc in documents]
            metadatas = [doc['metadata'] for doc in documents]
            url_to_full_document = {doc_url: file_content}  # Document upload mapping
            
            add_documents_to_supabase(
                client=self.supabase_client,
                urls=urls,
                chunk_numbers=chunk_numbers,
                contents=contents,
                metadatas=metadatas,
                url_to_full_document=url_to_full_document
            )
            chunks_stored = len(documents)
            
            return True, {
                "filename": filename,
                "chunks_stored": chunks_stored,
                "content_length": len(file_content),
                "total_word_count": total_word_count,
                "knowledge_type": knowledge_type,
                "tags": tags,
                "source_id": source_id
            }
            
        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            return False, {"error": f"Error uploading document: {str(e)}"}

    async def store_documents_with_progress(self, urls: List[str], chunk_numbers: List[int],
                                          contents: List[str], metadatas: List[Dict[str, Any]],
                                          url_to_full_document: Dict[str, str],
                                          progress_callback=None, batch_size: int = 20) -> None:
        """
        Enhanced version of add_documents_to_supabase with progress reporting.
        Maps internal 0-100% progress to external range via callback.
        """
        async def report_progress_internal(percentage: float, message: str):
            if progress_callback:
                # The callback will handle mapping to external range (55% to 90%)
                await progress_callback(percentage, message)
        
        # Get unique URLs to delete existing records
        unique_urls = list(set(urls))
        total_batches = (len(contents) + batch_size - 1) // batch_size
        
        await report_progress_internal(0, f'Preparing to process {len(contents)} chunks in {total_batches} batches...')
        
        # Delete existing records for these URLs to prevent duplicates
        await report_progress_internal(1, f'Cleaning {len(unique_urls)} existing URL records (prevents duplicates)...')
        
        try:
            if unique_urls:
                self.supabase_client.table("crawled_pages").delete().in_("url", unique_urls).execute()
                # Deletion completed
        except Exception as e:
            await report_progress_internal(2, f'Batch delete failed, using fallback: {str(e)[:50]}...')
            # Fallback: delete records one by one
            for i, url in enumerate(unique_urls):
                try:
                    self.supabase_client.table("crawled_pages").delete().eq("url", url).execute()
                    if i % 10 == 0:  # Progress every 10 deletions
                        await report_progress_internal(2 + (i / len(unique_urls)) * 3, f'Deleting records: {i+1}/{len(unique_urls)}')
                except Exception:
                    pass  # Continue with next URL
            # Deletion completed
        
        await report_progress_internal(5, 'Document preparation complete, starting batch processing...')
        
        # Check if contextual embeddings are enabled
        use_contextual_embeddings = os.getenv("USE_CONTEXTUAL_EMBEDDINGS", "false") == "true"
        
        # Use simple linear progress from 5% to 95% without conflicting calculations
        current_progress = 5.0
        progress_per_batch = 90.0 / total_batches  # Evenly distribute 90% across all batches
        
        for batch_idx in range(0, len(contents), batch_size):
            batch_end = min(batch_idx + batch_size, len(contents))
            current_batch = (batch_idx // batch_size) + 1
            
            # Get batch slices
            batch_urls = urls[batch_idx:batch_end]
            batch_chunk_numbers = chunk_numbers[batch_idx:batch_end]
            batch_contents = contents[batch_idx:batch_end]
            batch_metadatas = metadatas[batch_idx:batch_end]
            
            await report_progress_internal(current_progress, f'Processing batch {current_batch}/{total_batches} ({len(batch_contents)} chunks)...')
            
            # Apply contextual embedding if enabled (with proper concurrent processing)
            if use_contextual_embeddings:
                current_progress += progress_per_batch * 0.1  # 10% of batch progress
                await report_progress_internal(current_progress, f'Batch {current_batch}/{total_batches}: Processing contextual embeddings (parallel)...')
                
                # Process with concurrent workers to handle rate limits properly
                max_workers = int(os.getenv("CONTEXTUAL_EMBEDDINGS_MAX_WORKERS", "3"))
                
                # Prepare args for concurrent processing
                process_args = []
                for j, content in enumerate(batch_contents):
                    url = batch_urls[j]
                    full_document = url_to_full_document.get(url, "")
                    process_args.append((url, content, full_document))
                
                # Process concurrently with ThreadPoolExecutor
                import concurrent.futures
                contextual_contents = [None] * len(batch_contents)  # Pre-allocate to maintain order
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all tasks
                    future_to_index = {executor.submit(process_chunk_with_context, args): idx 
                                     for idx, args in enumerate(process_args)}
                    
                    completed = 0
                    # Process as they complete
                    for future in concurrent.futures.as_completed(future_to_index):
                        idx = future_to_index[future]
                        try:
                            result, success = future.result()
                            contextual_contents[idx] = result
                            if success:
                                batch_metadatas[idx]["contextual_embedding"] = True
                        except Exception as e:
                            print(f"Error processing chunk {idx}: {e}")
                            contextual_contents[idx] = batch_contents[idx]
                        
                        completed += 1
                
                current_progress += progress_per_batch * 0.4  # 40% of batch progress for contextual embeddings
                await report_progress_internal(current_progress, f'Batch {current_batch}/{total_batches}: Contextual embeddings complete')
            else:
                contextual_contents = batch_contents
                current_progress += progress_per_batch * 0.5  # Skip contextual processing, move to embeddings
            
            await report_progress_internal(current_progress, f'Batch {current_batch}/{total_batches}: Creating embeddings...')
            
            # Create embeddings for the entire batch at once - this is another slow operation
            batch_embeddings = create_embeddings_batch(contextual_contents)
            
            current_progress += progress_per_batch * 0.2  # 20% of batch progress for embeddings
            await report_progress_internal(current_progress, f'Batch {current_batch}/{total_batches}: Preparing for database insertion...')
            
            # Prepare batch data
            batch_data = []
            for j in range(len(contextual_contents)):
                chunk_size = len(contextual_contents[j])
                parsed_url = urlparse(batch_urls[j])
                source_id = parsed_url.netloc or parsed_url.path
                
                data = {
                    "url": batch_urls[j],
                    "chunk_number": batch_chunk_numbers[j],
                    "content": contextual_contents[j],
                    "metadata": {
                        "chunk_size": chunk_size,
                        **batch_metadatas[j]
                    },
                    "source_id": source_id,
                    "embedding": batch_embeddings[j]
                }
                batch_data.append(data)
            
            current_progress += progress_per_batch * 0.1  # 10% of batch progress for preparation
            
            await report_progress_internal(current_progress, f'Batch {current_batch}/{total_batches}: Inserting into database...')
            
            # Insert batch into Supabase with retry logic
            max_retries = 3
            retry_delay = 1.0
            
            for retry in range(max_retries):
                try:
                    self.supabase_client.table("crawled_pages").insert(batch_data).execute()
                    break  # Success
                except Exception as e:
                    if retry < max_retries - 1:
                        await report_progress_internal(current_progress, f'Batch {current_batch}/{total_batches}: Retry {retry + 1}/{max_retries}...')
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        # Final attempt failed, try individual inserts
                        await report_progress_internal(current_progress, f'Batch {current_batch}/{total_batches}: Trying individual records...')
                        successful_inserts = 0
                        for i, record in enumerate(batch_data):
                            try:
                                self.supabase_client.table("crawled_pages").insert(record).execute()
                                successful_inserts += 1
                            except:
                                pass
                        
                        if successful_inserts == 0:
                            raise Exception(f"Failed to insert batch {current_batch}: {str(e)}")
            
            current_progress += progress_per_batch * 0.2  # 20% of batch progress for database insertion
            await report_progress_internal(current_progress, f'Completed batch {current_batch}/{total_batches}')
        
        await report_progress_internal(100, f'All {len(contents)} document chunks stored successfully')

    def store_code_examples(self, code_examples: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        """
        Store code examples in the database.
        
        Args:
            code_examples: List of code example dicts with 'url', 'code_block', 'summary'
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            if not code_examples:
                return True, {"code_examples_stored": 0}
                
            # Prepare data for code examples insertion
            code_urls = [ex['url'] for ex in code_examples]
            code_chunk_numbers = [i for i in range(len(code_examples))]  # Sequential numbering (0-based)
            code_blocks = [ex['code_block'] for ex in code_examples]
            code_summaries = [ex['summary'] for ex in code_examples]
            code_metadatas = [{'source_url': ex['url'], 'extraction_method': 'agentic_rag'} for ex in code_examples]
            
            add_code_examples_to_supabase(
                client=self.supabase_client,
                urls=code_urls,
                chunk_numbers=code_chunk_numbers,
                code_examples=code_blocks,
                summaries=code_summaries,
                metadatas=code_metadatas
            )
            
            return True, {"code_examples_stored": len(code_examples)}
            
        except Exception as e:
            logger.error(f"Error storing code examples: {e}")
            return False, {"error": f"Error storing code examples: {str(e)}"}