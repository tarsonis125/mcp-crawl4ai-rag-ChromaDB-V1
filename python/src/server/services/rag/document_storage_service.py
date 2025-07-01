"""
Document Storage Service Module for Archon RAG with Threading Optimizations

This module provides core document storage and processing functionality
with proper threading patterns for high-performance AI operations while maintaining
WebSocket connection health and system stability.

Enhanced with:
- Async/await patterns throughout
- ThreadPoolExecutor for CPU-intensive operations
- WebSocket-safe progress reporting
- Memory adaptive processing
- Rate limiting for AI operations
"""

import json
# Removed direct logging import - using unified config
import os
import re
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse

from fastapi import WebSocket

from ...utils import (
    get_supabase_client,
    add_documents_to_supabase,
    add_documents_to_supabase_parallel,
    add_code_examples_to_supabase,
    update_source_info,
    extract_source_summary,
    generate_code_example_summary,
    get_utils_threading_service
)
from ..threading_service import ProcessingMode
from ...config.logfire_config import search_logger, get_logger

logger = get_logger(__name__)


class DocumentStorageService:
    """Enhanced service class for document storage with threading optimizations"""
    
    def __init__(self, supabase_client=None):
        """Initialize with optional supabase client and threading service"""
        self.supabase_client = supabase_client or get_supabase_client()
        self.threading_service = get_utils_threading_service()

    async def smart_chunk_markdown_async(
        self, 
        text: str, 
        chunk_size: int = 5000,
        websocket: Optional[WebSocket] = None
    ) -> List[str]:
        """
        Split text into chunks intelligently with threading optimizations.
        
        This function implements a context-aware chunking strategy that:
        1. Preserves code blocks (```) as complete units when possible
        2. Prefers to break at paragraph boundaries (\\n\\n)
        3. Falls back to sentence boundaries (. ) if needed
        4. Only splits mid-content when absolutely necessary
        
        Args:
            text: Text to chunk
            chunk_size: Maximum chunk size
            websocket: Optional WebSocket for progress updates
            
        Returns:
            List of text chunks
        """
        if not text or not isinstance(text, str):
            search_logger.warning("Invalid text provided for chunking")
            return []
            
        with search_logger.span("smart_chunk_markdown_async", 
                               text_length=len(text),
                               chunk_size=chunk_size) as span:
            try:
                # For large texts, run chunking in thread pool
                if len(text) > 50000:  # 50KB threshold
                    chunks = await self.threading_service.run_cpu_intensive(
                        self._chunk_text_sync, text, chunk_size
                    )
                else:
                    chunks = self._chunk_text_sync(text, chunk_size)
                
                # WebSocket progress update
                if websocket:
                    await websocket.send_json({
                        "type": "chunking_completed",
                        "chunks_created": len(chunks),
                        "original_length": len(text)
                    })
                
                span.set_attribute("chunks_created", len(chunks))
                span.set_attribute("success", True)
                
                search_logger.info(f"Successfully chunked text",
                                  original_length=len(text),
                                  chunks_created=len(chunks),
                                  avg_chunk_size=len(text)//len(chunks) if chunks else 0)
                
                return chunks
                
            except Exception as e:
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                search_logger.error(f"Error in smart chunking: {e}")
                
                # Fallback to simple chunking
                try:
                    fallback_chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
                    search_logger.warning(f"Used fallback chunking, created {len(fallback_chunks)} chunks")
                    return fallback_chunks
                except Exception as fallback_error:
                    search_logger.error(f"Even fallback chunking failed: {fallback_error}")
                    return [text] if text else []

    def smart_chunk_markdown(self, text: str, chunk_size: int = 5000) -> List[str]:
        """
        Legacy sync version - use smart_chunk_markdown_async for better performance.
        
        This function implements a context-aware chunking strategy that:
        1. Preserves code blocks (```) as complete units when possible
        2. Prefers to break at paragraph boundaries (\\n\\n)
        3. Falls back to sentence boundaries (. ) if needed
        4. Only splits mid-content when absolutely necessary
        """
        return self._chunk_text_sync(text, chunk_size)

    def _chunk_text_sync(self, text: str, chunk_size: int) -> List[str]:
        """Synchronous chunking function that runs in thread pool"""
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
        """
        Extracts headers and stats from a chunk.
        
        Args:
            chunk: Markdown chunk
            
        Returns:
            Dictionary with headers and stats
        """
        headers = re.findall(r'^(#+)\s+(.+)$', chunk, re.MULTILINE)
        header_str = '; '.join([f'{h[0]} {h[1]}' for h in headers]) if headers else ''

        return {
            "headers": header_str,
            "char_count": len(chunk),
            "word_count": len(chunk.split())
        }

    def process_code_example(self, code_block_dict):
        """Process a single code example to generate its summary with error handling."""
        try:
            # Handle both dict format and tuple format
            if isinstance(code_block_dict, dict):
                code = code_block_dict.get('code', '')
                context_before = code_block_dict.get('context_before', '')
                context_after = code_block_dict.get('context_after', '')
            else:
                # Fallback for tuple format (shouldn't happen but just in case)
                code, context_before, context_after = code_block_dict
            
            return generate_code_example_summary(code, context_before, context_after)
        except Exception as e:
            logger.warning(f"Error processing code example: {e}")
            return f"Code example (processing failed: {str(e)})"

    async def upload_document(
        self, 
        file_content: str, 
        filename: str,
        knowledge_type: str = "technical", 
        tags: List[str] = None,
        chunk_size: int = 5000,
        websocket: Optional[WebSocket] = None,
        progress_callback: Optional[Any] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Upload and process a document with threading optimizations.
        
        Args:
            file_content: The content of the document
            filename: Name of the file
            knowledge_type: Type of knowledge (default: "technical")
            tags: List of tags for the document
            chunk_size: Maximum size of each chunk
            websocket: Optional WebSocket for progress updates
            progress_callback: Optional progress callback
            
        Returns:
            Tuple of (success, result_dict)
        """
        with search_logger.span("upload_document_async",
                               filename=filename,
                               content_length=len(file_content),
                               knowledge_type=knowledge_type) as span:
            try:
                # Create a fake URL for the document
                doc_url = f"file://{filename}"
                
                # Extract source_id
                parsed_url = urlparse(doc_url)
                source_id = parsed_url.netloc or parsed_url.path
                
                # Progress reporting
                async def report_progress(message: str, percentage: int):
                    if progress_callback:
                        await progress_callback(message, percentage)
                    if websocket:
                        await websocket.send_json({
                            "type": "upload_progress",
                            "message": message,
                            "percentage": percentage,
                            "filename": filename
                        })
                
                await report_progress("Starting document processing...", 10)
                
                # Chunk the content with progress reporting
                chunks = await self.smart_chunk_markdown_async(
                    file_content, 
                    chunk_size=chunk_size,
                    websocket=websocket
                )
                
                await report_progress("Document chunked, processing metadata...", 30)
                
                # Prepare data for Supabase
                urls = []
                chunk_numbers = []
                contents = []
                metadatas = []
                total_word_count = 0
                
                # Process chunks in parallel for metadata extraction
                async def process_chunk_metadata(chunk: str, index: int) -> Dict[str, Any]:
                    if len(chunk) < 10000:
                        meta = self.extract_section_info(chunk)
                    else:
                        # Use thread pool for large chunks
                        meta = await self.threading_service.run_cpu_intensive(
                            self.extract_section_info, chunk
                        )
                    
                    meta.update({
                        "chunk_index": index,
                        "url": doc_url,
                        "source": source_id,
                        "knowledge_type": knowledge_type,
                        "filename": filename
                    })
                    if tags:
                        meta["tags"] = tags
                    return meta
                
                # Process metadata for all chunks
                metadata_tasks = [
                    process_chunk_metadata(chunk, i) 
                    for i, chunk in enumerate(chunks)
                ]
                
                processed_metadatas = await asyncio.gather(*metadata_tasks)
                
                # Build final data structures
                for i, (chunk, meta) in enumerate(zip(chunks, processed_metadatas)):
                    urls.append(doc_url)
                    chunk_numbers.append(i)
                    contents.append(chunk)
                    metadatas.append(meta)
                    total_word_count += meta.get("word_count", 0)
                
                await report_progress("Metadata processed, updating source info...", 50)
                
                # Create url_to_full_document mapping
                url_to_full_document = {doc_url: file_content}
                
                # Update source information in thread pool
                source_summary = await self.threading_service.run_cpu_intensive(
                    extract_source_summary, source_id, file_content[:5000]
                )
                
                await self.threading_service.run_io_bound(
                    update_source_info, 
                    self.supabase_client, 
                    source_id, 
                    source_summary, 
                    total_word_count
                )
                
                await report_progress("Source info updated, storing document chunks...", 70)
                
                # Get worker count from settings
                max_workers = int(os.getenv("CONTEXTUAL_EMBEDDINGS_MAX_WORKERS", "3"))
                
                # Add documentation chunks to Supabase using parallel function
                await add_documents_to_supabase_parallel(
                    client=self.supabase_client,
                    urls=urls,
                    chunk_numbers=chunk_numbers,
                    contents=contents,
                    metadatas=metadatas,
                    url_to_full_document=url_to_full_document,
                    batch_size=15,
                    websocket=websocket,
                    progress_callback=progress_callback,
                    max_workers=max_workers
                )
                
                await report_progress("Document upload completed!", 100)
                
                result = {
                    "chunks_stored": len(chunks),
                    "total_word_count": total_word_count,
                    "source_id": source_id,
                    "filename": filename
                }
                
                span.set_attribute("success", True)
                span.set_attribute("chunks_stored", len(chunks))
                span.set_attribute("total_word_count", total_word_count)
                
                search_logger.info("Document upload completed successfully",
                                  filename=filename,
                                  chunks_stored=len(chunks),
                                  total_word_count=total_word_count)
                
                return True, result
                
            except Exception as e:
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                search_logger.error(f"Error uploading document: {e}")
                
                if websocket:
                    await websocket.send_json({
                        "type": "upload_error",
                        "error": str(e),
                        "filename": filename
                    })
                
                return False, {"error": f"Error uploading document: {str(e)}"}

    async def store_documents_with_progress(
        self, 
        urls: List[str], 
        chunk_numbers: List[int],
        contents: List[str], 
        metadatas: List[Dict[str, Any]],
        url_to_full_document: Dict[str, str],
        websocket: Optional[WebSocket] = None,
        progress_callback: Optional[Any] = None, 
        batch_size: int = 20
    ) -> None:
        """
        Store documents with threading optimizations and progress reporting.
        
        Args:
            urls: List of URLs
            chunk_numbers: List of chunk numbers
            contents: List of document contents
            metadatas: List of metadata dictionaries
            url_to_full_document: URL to full document mapping
            websocket: Optional WebSocket for progress updates
            progress_callback: Optional progress callback
            batch_size: Batch size for processing
        """
        with search_logger.span("store_documents_with_progress",
                               total_documents=len(contents),
                               batch_size=batch_size) as span:
            
            # Get worker count from settings
            max_workers = int(os.getenv("CONTEXTUAL_EMBEDDINGS_MAX_WORKERS", "3"))
            
            # Use the parallel async function
            await add_documents_to_supabase_parallel(
                client=self.supabase_client,
                urls=urls,
                chunk_numbers=chunk_numbers,
                contents=contents,
                metadatas=metadatas,
                url_to_full_document=url_to_full_document,
                batch_size=batch_size,
                websocket=websocket,
                progress_callback=progress_callback,
                max_workers=max_workers
            )
            
            span.set_attribute("success", True)
            span.set_attribute("total_documents", len(contents))

    def store_code_examples(self, code_examples: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        """
        Store code examples in the database using the working function.
        
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
            
            # Use the working function
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