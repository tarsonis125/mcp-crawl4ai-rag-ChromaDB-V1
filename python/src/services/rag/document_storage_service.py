"""
Document Storage Service Module for Archon RAG

This module provides core document storage and processing functionality
that can be shared between MCP tools and FastAPI endpoints.
"""

import json
import logging
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse

from src.utils import (
    get_supabase_client,
    add_documents_to_supabase,
    add_code_examples_to_supabase,
    update_source_info,
    extract_source_summary
)

from src.utils import (
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

    def upload_document(self, file_content: str, filename: str, 
                       knowledge_type: str = "technical", tags: List[str] = None, 
                       chunk_size: int = 5000) -> Tuple[bool, Dict[str, Any]]:
        """
        Upload and process a document using the proven working approach.
        
        Args:
            file_content: The content of the document
            filename: Name of the file
            knowledge_type: Type of knowledge (default: "technical")
            tags: List of tags for the document
            chunk_size: Maximum size of each chunk
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Create a fake URL for the document
            doc_url = f"file://{filename}"
            
            # Extract source_id
            parsed_url = urlparse(doc_url)
            source_id = parsed_url.netloc or parsed_url.path
            
            # Chunk the content
            chunks = self.smart_chunk_markdown(file_content, chunk_size=chunk_size)
            
            # Prepare data for Supabase - EXACTLY like the working MCP server
            urls = []
            chunk_numbers = []
            contents = []
            metadatas = []
            total_word_count = 0
            
            for i, chunk in enumerate(chunks):
                urls.append(doc_url)
                chunk_numbers.append(i)
                contents.append(chunk)
                
                # Extract metadata
                meta = self.extract_section_info(chunk)
                meta["chunk_index"] = i
                meta["url"] = doc_url
                meta["source"] = source_id
                meta["knowledge_type"] = knowledge_type
                meta["filename"] = filename
                if tags:
                    meta["tags"] = tags
                metadatas.append(meta)
                
                # Accumulate word count
                total_word_count += meta.get("word_count", 0)
            
            # Create url_to_full_document mapping
            url_to_full_document = {doc_url: file_content}
            
            # Update source information FIRST (before inserting documents)
            source_summary = extract_source_summary(source_id, file_content[:5000])  # Use first 5000 chars for summary
            update_source_info(self.supabase_client, source_id, source_summary, total_word_count)
            
            # Add documentation chunks to Supabase using the WORKING function
            add_documents_to_supabase(
                client=self.supabase_client,
                urls=urls,
                chunk_numbers=chunk_numbers,
                contents=contents,
                metadatas=metadatas,
                url_to_full_document=url_to_full_document
            )
            
            return True, {
                "chunks_stored": len(chunks),
                "total_word_count": total_word_count,
                "source_id": source_id,
                "filename": filename
            }
            
        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            return False, {"error": f"Error uploading document: {str(e)}"}

    def store_documents_with_progress(self, urls: List[str], chunk_numbers: List[int],
                                    contents: List[str], metadatas: List[Dict[str, Any]],
                                    url_to_full_document: Dict[str, str],
                                    progress_callback=None, batch_size: int = 20) -> None:
        """
        Store documents using the WORKING function from utils.py - no broken async bullshit.
        """
        # Just call the working function that has proper parallel processing
        add_documents_to_supabase(
            client=self.supabase_client,
            urls=urls,
            chunk_numbers=chunk_numbers,
            contents=contents,
            metadatas=metadatas,
            url_to_full_document=url_to_full_document,
            batch_size=batch_size
        )

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