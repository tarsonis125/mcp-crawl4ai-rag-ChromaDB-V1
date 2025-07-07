"""
Code Extraction Service

Handles extraction, processing, and storage of code examples from documents.
"""
import asyncio
from typing import List, Dict, Any, Optional, Callable
from urllib.parse import urlparse

from ...config.logfire_config import safe_logfire_info, safe_logfire_error
from ..storage.code_storage_service import (
    extract_code_blocks,
    generate_code_summaries_batch,
    add_code_examples_to_supabase
)
from ..credential_service import credential_service


class CodeExtractionService:
    """
    Service for extracting and processing code examples from documents.
    """
    
    def __init__(self, supabase_client):
        """
        Initialize the code extraction service.
        
        Args:
            supabase_client: The Supabase client for database operations
        """
        self.supabase_client = supabase_client
    
    async def extract_and_store_code_examples(
        self,
        crawl_results: List[Dict[str, Any]],
        url_to_full_document: Dict[str, str],
        progress_callback: Optional[Callable] = None
    ) -> int:
        """
        Extract code examples from crawled documents and store them.
        
        Args:
            crawl_results: List of crawled documents with url and markdown content
            url_to_full_document: Mapping of URLs to full document content
            progress_callback: Optional async callback for progress updates
            
        Returns:
            Number of code examples stored
        """
        # Extract code blocks from all documents
        all_code_blocks = await self._extract_code_blocks_from_documents(
            crawl_results, progress_callback
        )
        
        if not all_code_blocks:
            safe_logfire_info("No code examples found in any crawled documents")
            return 0
        
        # Log what we found
        safe_logfire_info(f"Found {len(all_code_blocks)} total code blocks to process")
        for i, block_data in enumerate(all_code_blocks[:3]):
            block = block_data['block']
            safe_logfire_info(f"Sample code block {i+1} | language={block.get('language', 'none')} | code_length={len(block.get('code', ''))}")
        
        # Generate summaries for code blocks
        summary_results = await self._generate_code_summaries(
            all_code_blocks, progress_callback
        )
        
        # Prepare code examples for storage
        storage_data = self._prepare_code_examples_for_storage(
            all_code_blocks, summary_results
        )
        
        # Store code examples in database
        return await self._store_code_examples(
            storage_data, url_to_full_document, progress_callback
        )
    
    async def _extract_code_blocks_from_documents(
        self,
        crawl_results: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract code blocks from all documents.
        
        Returns:
            List of code blocks with metadata
        """
        if progress_callback:
            await progress_callback({
                'status': 'code_storage',
                'percentage': 91,
                'log': 'Extracting code examples from crawled content...'
            })
        
        all_code_blocks = []
        total_docs = len(crawl_results)
        
        for idx, doc in enumerate(crawl_results):
            try:
                source_url = doc['url']
                md = doc.get('markdown', '')
                
                if not md:
                    safe_logfire_info(f"No markdown content for code extraction | url={source_url}")
                    continue
                
                # Log markdown content info for debugging
                safe_logfire_info(f"Extracting code from document | url={source_url} | markdown_length={len(md)}")
                
                # Debug: Check if markdown contains code blocks
                has_backticks = '```' in md
                backtick_count = md.count('```')
                # Use a lower threshold to catch more code blocks
                min_length = 20  # Much lower to ensure we catch code examples
                safe_logfire_info(f"Code block debug | url={source_url} | has_backticks={has_backticks} | backtick_count={backtick_count} | min_length={min_length}")
                
                # Extract code blocks from markdown WITH the min_length parameter
                code_blocks = extract_code_blocks(md, min_length=min_length)
                safe_logfire_info(f"Found {len(code_blocks)} code blocks | url={source_url}")
                
                # Fallback: If no code blocks found, try to extract from HTML patterns
                if len(code_blocks) == 0:
                    safe_logfire_info(f"No markdown code blocks found, attempting HTML extraction | url={source_url}")
                    html_code_blocks = self._extract_html_code_blocks(md, min_length)
                    if html_code_blocks:
                        safe_logfire_info(f"Found {len(html_code_blocks)} code blocks from HTML patterns | url={source_url}")
                        code_blocks = html_code_blocks
                
                # Debug: If no code blocks found but backticks exist, log sample
                if len(code_blocks) == 0 and has_backticks:
                    # Find first code block for debugging
                    start_idx = md.find('```')
                    if start_idx != -1:
                        end_idx = md.find('```', start_idx + 3)
                        if end_idx != -1:
                            content_between = md[start_idx+3:end_idx]
                            first_line = content_between.split('\n')[0] if '\n' in content_between else content_between[:50]
                            content_length = end_idx - start_idx - 3
                            safe_logfire_info(f"Debug: Found backticks but no code blocks extracted")
                            safe_logfire_info(f"First line after backticks: '{first_line}'")
                            safe_logfire_info(f"Content length between backticks: {content_length}")
                            safe_logfire_info(f"Sample: {content_between[:100]}...")
                
                if code_blocks:
                    parsed_url = urlparse(source_url)
                    source_id = parsed_url.netloc or parsed_url.path
                    
                    for block in code_blocks:
                        all_code_blocks.append({
                            'block': block,
                            'source_url': source_url,
                            'source_id': source_id
                        })
                
                # Update progress during extraction
                if progress_callback and idx % 5 == 0:
                    progress = 91 + int((idx / total_docs) * 2)
                    await progress_callback({
                        'status': 'code_storage',
                        'percentage': progress,
                        'log': f'Extracting code from document {idx + 1}/{total_docs}...'
                    })
                    
            except Exception as e:
                safe_logfire_error(f"Error processing code from document | url={doc.get('url')} | error={str(e)}")
        
        return all_code_blocks
    
    def _extract_html_code_blocks(self, content: str, min_length: int = 20) -> List[Dict[str, Any]]:
        """
        Extract code blocks from HTML patterns in content.
        This is a fallback when markdown conversion didn't preserve code blocks.
        
        Args:
            content: The content to search for HTML code patterns
            min_length: Minimum length for code blocks
            
        Returns:
            List of code blocks with metadata
        """
        import re
        
        code_blocks = []
        
        # Pattern 1: <pre><code>...</code></pre>
        pre_code_pattern = r'<pre[^>]*>\s*<code[^>]*>(.*?)</code>\s*</pre>'
        matches = re.finditer(pre_code_pattern, content, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            code_content = match.group(1).strip()
            # Clean up HTML entities
            code_content = self._decode_html_entities(code_content)
            
            if len(code_content) >= min_length:
                # Try to extract language from class attribute
                full_match = match.group(0)
                lang_match = re.search(r'class=["\'].*?language-(\w+)', full_match)
                language = lang_match.group(1) if lang_match else ""
                
                # Extract context
                start_pos = match.start()
                end_pos = match.end()
                context_before = content[max(0, start_pos - 1000):start_pos].strip()
                context_after = content[end_pos:min(len(content), end_pos + 1000)].strip()
                
                code_blocks.append({
                    'code': code_content,
                    'language': language,
                    'context_before': context_before,
                    'context_after': context_after,
                    'full_context': f"{context_before}\n\n{code_content}\n\n{context_after}"
                })
        
        # Pattern 2: <code>...</code> (standalone)
        if not code_blocks:  # Only if we didn't find pre/code blocks
            code_pattern = r'<code[^>]*>(.*?)</code>'
            matches = re.finditer(code_pattern, content, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                code_content = match.group(1).strip()
                code_content = self._decode_html_entities(code_content)
                
                # Check if it's multiline or substantial enough
                if len(code_content) >= min_length and ('\n' in code_content or len(code_content) > 100):
                    start_pos = match.start()
                    end_pos = match.end()
                    context_before = content[max(0, start_pos - 1000):start_pos].strip()
                    context_after = content[end_pos:min(len(content), end_pos + 1000)].strip()
                    
                    code_blocks.append({
                        'code': code_content,
                        'language': "",
                        'context_before': context_before,
                        'context_after': context_after,
                        'full_context': f"{context_before}\n\n{code_content}\n\n{context_after}"
                    })
        
        return code_blocks
    
    def _decode_html_entities(self, text: str) -> str:
        """Decode common HTML entities in code."""
        replacements = {
            '&lt;': '<',
            '&gt;': '>',
            '&amp;': '&',
            '&quot;': '"',
            '&#39;': "'",
            '&nbsp;': ' ',
            '&#x27;': "'",
            '&#x2F;': '/',
            '&#60;': '<',
            '&#62;': '>',
        }
        
        for entity, char in replacements.items():
            text = text.replace(entity, char)
        
        return text
    
    async def _generate_code_summaries(
        self,
        all_code_blocks: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, str]]:
        """
        Generate summaries for all code blocks.
        
        Returns:
            List of summary results
        """
        if progress_callback:
            await progress_callback({
                'status': 'code_storage',
                'percentage': 93,
                'log': f'Generating summaries for {len(all_code_blocks)} code examples...'
            })
        
        # Use default max workers
        max_workers = 3
        
        # Extract just the code blocks for batch processing
        code_blocks_for_summaries = [item['block'] for item in all_code_blocks]
        
        # Generate summaries with progress tracking
        summary_progress_callback = None
        if progress_callback:
            summary_progress_callback = lambda data: asyncio.create_task(progress_callback(data))
        
        return await generate_code_summaries_batch(
            code_blocks_for_summaries,
            max_workers,
            progress_callback=summary_progress_callback
        )
    
    def _prepare_code_examples_for_storage(
        self,
        all_code_blocks: List[Dict[str, Any]],
        summary_results: List[Dict[str, str]]
    ) -> Dict[str, List[Any]]:
        """
        Prepare code examples for storage by organizing data into arrays.
        
        Returns:
            Dictionary with arrays for storage
        """
        code_urls = []
        code_chunk_numbers = []
        code_examples = []
        code_summaries = []
        code_metadatas = []
        
        for idx, (code_item, summary_result) in enumerate(zip(all_code_blocks, summary_results)):
            block = code_item['block']
            source_url = code_item['source_url']
            source_id = code_item['source_id']
            
            summary = summary_result.get('summary', 'Code example for demonstration purposes.')
            example_name = summary_result.get('example_name', 'Code Example')
            
            code_urls.append(source_url)
            code_chunk_numbers.append(len(code_examples))
            code_examples.append(block['code'])
            code_summaries.append(summary)
            
            code_meta = {
                "chunk_index": len(code_examples) - 1,
                "url": source_url,
                "source": source_id,
                "source_id": source_id,
                "language": block.get('language', ''),
                "char_count": len(block['code']),
                "word_count": len(block['code'].split()),
                "example_name": example_name,
                "title": example_name
            }
            code_metadatas.append(code_meta)
        
        return {
            'urls': code_urls,
            'chunk_numbers': code_chunk_numbers,
            'examples': code_examples,
            'summaries': code_summaries,
            'metadatas': code_metadatas
        }
    
    async def _store_code_examples(
        self,
        storage_data: Dict[str, List[Any]],
        url_to_full_document: Dict[str, str],
        progress_callback: Optional[Callable] = None
    ) -> int:
        """
        Store code examples in the database.
        
        Returns:
            Number of code examples stored
        """
        if progress_callback:
            await progress_callback({
                'status': 'code_storage',
                'percentage': 95,
                'log': f'Storing {len(storage_data["examples"])} code examples...'
            })
        
        try:
            await add_code_examples_to_supabase(
                client=self.supabase_client,
                urls=storage_data['urls'],
                chunk_numbers=storage_data['chunk_numbers'],
                code_examples=storage_data['examples'],
                summaries=storage_data['summaries'],
                metadatas=storage_data['metadatas'],
                batch_size=20,
                url_to_full_document=url_to_full_document
            )
            
            safe_logfire_info(f"Successfully stored {len(storage_data['examples'])} code examples")
            return len(storage_data['examples'])
            
        except Exception as e:
            safe_logfire_error(f"Error storing code examples | error={str(e)}")
            return 0