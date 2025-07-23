"""
Code Extraction Service

Handles extraction, processing, and storage of code examples from documents.
"""
import asyncio
import re
from typing import List, Dict, Any, Optional, Callable
from urllib.parse import urlparse

from ...config.logfire_config import safe_logfire_info, safe_logfire_error
from ..storage.code_storage_service import (
    extract_code_blocks,
    generate_code_summaries_batch,
    add_code_examples_to_supabase
)


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
        progress_callback: Optional[Callable] = None,
        start_progress: int = 0,
        end_progress: int = 100
    ) -> int:
        """
        Extract code examples from crawled documents and store them.
        
        Args:
            crawl_results: List of crawled documents with url and markdown content
            url_to_full_document: Mapping of URLs to full document content
            progress_callback: Optional async callback for progress updates
            start_progress: Starting progress percentage (default: 0)
            end_progress: Ending progress percentage (default: 100)
            
        Returns:
            Number of code examples stored
        """
        # Divide the progress range into phases:
        # - Extract code blocks: start_progress to 40% of range
        # - Generate summaries: 40% to 80% of range  
        # - Store examples: 80% to end_progress
        progress_range = end_progress - start_progress
        extract_end = start_progress + int(progress_range * 0.4)
        summary_end = start_progress + int(progress_range * 0.8)
        
        # Extract code blocks from all documents
        all_code_blocks = await self._extract_code_blocks_from_documents(
            crawl_results, progress_callback, start_progress, extract_end
        )
        
        if not all_code_blocks:
            safe_logfire_info("No code examples found in any crawled documents")
            # Still report completion when no code examples found
            if progress_callback:
                await progress_callback({
                    'status': 'code_extraction',
                    'percentage': end_progress,
                    'log': 'No code examples found to extract'
                })
            return 0
        
        # Log what we found
        safe_logfire_info(f"Found {len(all_code_blocks)} total code blocks to process")
        for i, block_data in enumerate(all_code_blocks[:3]):
            block = block_data['block']
            safe_logfire_info(f"Sample code block {i+1} | language={block.get('language', 'none')} | code_length={len(block.get('code', ''))}")
        
        # Generate summaries for code blocks with mapped progress
        summary_results = await self._generate_code_summaries(
            all_code_blocks, progress_callback, extract_end, summary_end
        )
        
        # Prepare code examples for storage
        storage_data = self._prepare_code_examples_for_storage(
            all_code_blocks, summary_results
        )
        
        # Store code examples in database with final phase progress
        return await self._store_code_examples(
            storage_data, url_to_full_document, progress_callback, summary_end, end_progress
        )
    
    async def _extract_code_blocks_from_documents(
        self,
        crawl_results: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None,
        start_progress: int = 0,
        end_progress: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Extract code blocks from all documents.
        
        Returns:
            List of code blocks with metadata
        """
        # Progress will be reported during the loop below
        
        all_code_blocks = []
        total_docs = len(crawl_results)
        completed_docs = 0
        
        for idx, doc in enumerate(crawl_results):
            try:
                source_url = doc['url']
                html_content = doc.get('html', '')
                md = doc.get('markdown', '')
                
                # Debug logging
                safe_logfire_info(f"Document content check | url={source_url} | has_html={bool(html_content)} | has_markdown={bool(md)} | html_len={len(html_content) if html_content else 0} | md_len={len(md) if md else 0}")
                
                # Use a reasonable threshold to extract meaningful code blocks
                min_length = 100  # Extract code blocks >= 100 characters
                
                # Check markdown first to see if it has code blocks
                if md:
                    has_backticks = '```' in md
                    backtick_count = md.count('```')
                    safe_logfire_info(f"Markdown check | url={source_url} | has_backticks={has_backticks} | backtick_count={backtick_count}")
                    
                    if 'getting-started' in source_url and md:
                        # Log a sample of the markdown
                        sample = md[:500]
                        safe_logfire_info(f"Markdown sample for getting-started: {sample}...")
                
                # Simple extraction logic - try markdown first, then HTML as fallback
                code_blocks = []
                
                # If markdown has triple backticks, extract code blocks from it
                if md and '```' in md:
                    safe_logfire_info(f"Using markdown extraction (found backticks) | url={source_url}")
                    code_blocks = extract_code_blocks(md, min_length=min_length)
                    safe_logfire_info(f"Found {len(code_blocks)} code blocks from markdown | url={source_url}")
                
                # If no code blocks from markdown, try HTML extraction as fallback
                if len(code_blocks) == 0 and html_content:
                    safe_logfire_info(f"No code blocks in markdown, trying HTML extraction | url={source_url} | html_length={len(html_content)}")
                    code_blocks = self._extract_html_code_blocks(html_content, min_length)
                    safe_logfire_info(f"Found {len(code_blocks)} code blocks from HTML | url={source_url}")
                
                # Debug: If no code blocks found from markdown but backticks exist, log sample
                if len(code_blocks) == 0 and not html_content and md and '```' in md:
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
                
                # Update progress only after completing document extraction
                completed_docs += 1
                if progress_callback and total_docs > 0:
                    # Calculate progress within the specified range
                    raw_progress = (completed_docs / total_docs)
                    mapped_progress = start_progress + int(raw_progress * (end_progress - start_progress))
                    await progress_callback({
                        'status': 'code_extraction',
                        'percentage': mapped_progress,
                        'log': f'Extracted code from {completed_docs}/{total_docs} documents',
                        'completed_documents': completed_docs,
                        'total_documents': total_docs
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
        
        # Add detailed logging
        safe_logfire_info(f"Processing HTML of length {len(content)} for code extraction")
        
        # Check if we have actual content
        if len(content) < 1000:
            safe_logfire_info(f"Warning: HTML content seems too short, first 500 chars: {content[:500]}")
        
        # Look for specific indicators of code blocks
        has_prism = 'prism' in content.lower()
        has_highlight = 'highlight' in content.lower()
        has_shiki = 'shiki' in content.lower()
        has_codemirror = 'codemirror' in content.lower() or 'cm-' in content
        safe_logfire_info(f"Code library indicators | prism={has_prism} | highlight={has_highlight} | shiki={has_shiki} | codemirror={has_codemirror}")
        
        # Check for any pre tags with different attributes
        pre_matches = re.findall(r'<pre[^>]*>', content[:5000], re.IGNORECASE)
        if pre_matches:
            safe_logfire_info(f"Found {len(pre_matches)} <pre> tags in first 5000 chars")
            for i, pre_tag in enumerate(pre_matches[:3]):  # Show first 3
                safe_logfire_info(f"Pre tag {i+1}: {pre_tag}")
        
        code_blocks = []
        extracted_positions = set()  # Track already extracted code block positions
        
        # Comprehensive patterns for various code block formats
        # Order matters - more specific patterns first
        patterns = [
            # Milkdown specific patterns - check their actual HTML structure
            (r'<pre[^>]*><code[^>]*class=["\'][^"\']*language-(\w+)[^"\']*["\'][^>]*>(.*?)</code></pre>', 'milkdown-typed'),
            (r'<div[^>]*class=["\'][^"\']*code-wrapper[^"\']*["\'][^>]*>.*?<pre[^>]*>(.*?)</pre>', 'milkdown-wrapper'),
            (r'<pre[^>]*class=["\'][^"\']*code-block[^"\']*["\'][^>]*><code[^>]*>(.*?)</code></pre>', 'milkdown'),
            (r'<div[^>]*data-code-block[^>]*>.*?<pre[^>]*>(.*?)</pre>', 'milkdown-alt'),
            (r'<div[^>]*class=["\'][^"\']*milkdown[^"\']*["\'][^>]*>.*?<pre[^>]*><code[^>]*>(.*?)</code></pre>', 'milkdown-div'),
            
            # Monaco Editor - capture all view-lines content
            (r'<div[^>]*class=["\'][^"\']*monaco-editor[^"\']*["\'][^>]*>.*?<div[^>]*class=["\'][^"\']*view-lines[^"\']*[^>]*>(.*?)</div>(?=.*?</div>.*?</div>)', 'monaco'),
            
            # CodeMirror - capture cm-content with all nested cm-line divs
            (r'<div[^>]*class=["\'][^"\']*cm-content[^"\']*["\'][^>]*>((?:<div[^>]*class=["\'][^"\']*cm-line[^"\']*["\'][^>]*>.*?</div>\s*)+)</div>', 'codemirror'),
            
            # Prism.js with language - must be before generic pre
            (r'<pre[^>]*class=["\'][^"\']*language-(\w+)[^"\']*["\'][^>]*>\s*<code[^>]*>(.*?)</code>\s*</pre>', 'prism'),
            
            # highlight.js - must be before generic pre/code
            (r'<pre[^>]*><code[^>]*class=["\'][^"\']*hljs(?:\s+language-(\w+))?[^"\']*["\'][^>]*>(.*?)</code></pre>', 'hljs'),
            
            # Shiki patterns
            (r'<pre[^>]*class=["\'][^"\']*shiki[^"\']*["\'][^>]*>\s*<code[^>]*>(.*?)</code>\s*</pre>', 'shiki'),
            (r'<pre[^>]*class=["\'][^"\']*astro-code[^"\']*["\'][^>]*>(.*?)</pre>', 'astro-shiki'),
            
            # VitePress/Vue patterns
            (r'<div[^>]*class=["\'][^"\']*language-(\w+)[^"\']*["\'][^>]*>.*?<pre[^>]*>(.*?)</pre>', 'vitepress'),
            
            # Standard pre/code patterns - should be near the end
            (r'<pre[^>]*><code[^>]*class=["\'][^"\']*language-(\w+)[^"\']*["\'][^>]*>(.*?)</code></pre>', 'standard-lang'),
            (r'<pre[^>]*>\s*<code[^>]*>(.*?)</code>\s*</pre>', 'standard'),
            
            # Generic patterns - should be last
            (r'<div[^>]*class=["\'][^"\']*code-block[^"\']*["\'][^>]*>.*?<pre[^>]*>(.*?)</pre>', 'generic-div'),
            (r'<div[^>]*class=["\'][^"\']*codeblock[^"\']*["\'][^>]*>(.*?)</div>', 'generic-codeblock'),
            (r'<div[^>]*class=["\'][^"\']*highlight[^"\']*["\'][^>]*>.*?<pre[^>]*>(.*?)</pre>', 'highlight')
        ]
        
        for pattern_tuple in patterns:
            pattern_str, source_type = pattern_tuple
            matches = list(re.finditer(pattern_str, content, re.DOTALL | re.IGNORECASE))
            
            # Log pattern matches for Milkdown patterns and CodeMirror
            if matches and ('milkdown' in source_type or 'codemirror' in source_type or 'milkdown' in content[:1000].lower()):
                safe_logfire_info(f"Pattern {source_type} found {len(matches)} matches")
            
            for match in matches:
                # Extract code content based on pattern type
                if source_type in ['standard-lang', 'prism', 'vitepress', 'hljs', 'milkdown-typed']:
                    # These patterns capture language in group 1, code in group 2
                    if match.lastindex and match.lastindex >= 2:
                        language = match.group(1)
                        code_content = match.group(2).strip()
                    else:
                        code_content = match.group(1).strip()
                        language = ""
                else:
                    # Most patterns have code in group 1
                    code_content = match.group(1).strip()
                    # Try to extract language from the full match
                    full_match = match.group(0)
                    lang_match = re.search(r'class=["\'].*?language-(\w+)', full_match)
                    language = lang_match.group(1) if lang_match else ""
                
                # Clean up HTML entities
                code_content = self._decode_html_entities(code_content)
                
                # For CodeMirror, extract text from cm-lines
                if source_type == 'codemirror':
                    # Extract text from each cm-line div
                    cm_lines = re.findall(r'<div[^>]*class=["\'][^"\']*cm-line[^"\']*["\'][^>]*>(.*?)</div>', code_content, re.DOTALL)
                    if cm_lines:
                        # Clean each line and join
                        cleaned_lines = []
                        for line in cm_lines:
                            # Remove span tags but keep content
                            line = re.sub(r'<span[^>]*>', '', line)
                            line = re.sub(r'</span>', '', line)
                            # Remove other HTML tags
                            line = re.sub(r'<[^>]+>', '', line)
                            cleaned_lines.append(line)
                        code_content = '\n'.join(cleaned_lines)
                    else:
                        # Fallback: just clean HTML
                        code_content = re.sub(r'<span[^>]*>', '', code_content)
                        code_content = re.sub(r'</span>', '', code_content)
                        code_content = re.sub(r'<[^>]+>', '\n', code_content)
                
                # For Monaco, extract text from nested divs
                if source_type == 'monaco':
                    # Extract actual code from Monaco's complex structure
                    code_content = re.sub(r'<div[^>]*>', '\n', code_content)
                    code_content = re.sub(r'</div>', '', code_content)
                    code_content = re.sub(r'<span[^>]*>', '', code_content)
                    code_content = re.sub(r'</span>', '', code_content)
                
                # Skip if too short after cleaning
                if len(code_content) >= min_length:
                    # Extract position info for deduplication
                    start_pos = match.start()
                    end_pos = match.end()
                    
                    # Check if we've already extracted code from this position
                    position_key = (start_pos, end_pos)
                    overlapping = False
                    for existing_start, existing_end in extracted_positions:
                        # Check if this match overlaps with an existing extraction
                        if not (end_pos <= existing_start or start_pos >= existing_end):
                            overlapping = True
                            break
                    
                    if not overlapping:
                        extracted_positions.add(position_key)
                        
                        # Extract context
                        context_before = content[max(0, start_pos - 1000):start_pos].strip()
                        context_after = content[end_pos:min(len(content), end_pos + 1000)].strip()
                        
                        # Log successful extraction
                        safe_logfire_info(f"Extracted code block | source_type={source_type} | language={language} | length={len(code_content)}")
                        
                        code_blocks.append({
                            'code': code_content,
                            'language': language,
                            'context_before': context_before,
                            'context_after': context_after,
                            'full_context': f"{context_before}\n\n{code_content}\n\n{context_after}",
                            'source_type': source_type  # Track which pattern matched
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
        progress_callback: Optional[Callable] = None,
        start_progress: int = 0,
        end_progress: int = 100
    ) -> List[Dict[str, str]]:
        """
        Generate summaries for all code blocks.
        
        Returns:
            List of summary results
        """
        # Progress is handled by generate_code_summaries_batch
        
        # Use default max workers
        max_workers = 3
        
        # Extract just the code blocks for batch processing
        code_blocks_for_summaries = [item['block'] for item in all_code_blocks]
        
        # Generate summaries with mapped progress tracking
        summary_progress_callback = None
        if progress_callback:
            # Create a wrapper that maps the progress to the correct range
            async def mapped_callback(data: dict):
                # Map the percentage from generate_code_summaries_batch (0-100) to our range
                if 'percentage' in data:
                    raw_percentage = data['percentage']
                    # Map from 0-100 to start_progress-end_progress
                    mapped_percentage = start_progress + int((raw_percentage / 100) * (end_progress - start_progress))
                    data['percentage'] = mapped_percentage
                    # Change the status to match what the orchestration expects
                    data['status'] = 'code_extraction'
                await progress_callback(data)
            
            summary_progress_callback = mapped_callback
        
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
        progress_callback: Optional[Callable] = None,
        start_progress: int = 0,
        end_progress: int = 100
    ) -> int:
        """
        Store code examples in the database.
        
        Returns:
            Number of code examples stored
        """
        # Create mapped progress callback for storage phase
        storage_progress_callback = None
        if progress_callback:
            async def mapped_storage_callback(data: dict):
                # Extract values from the dictionary
                message = data.get('log', '')
                percentage = data.get('percentage', 0)
                
                # Map storage progress (0-100) to our range (start_progress to end_progress)
                mapped_percentage = start_progress + int((percentage / 100) * (end_progress - start_progress))
                
                update_data = {
                    'status': 'code_storage',
                    'percentage': mapped_percentage,
                    'log': message
                }
                
                # Pass through any additional batch info
                if 'batch_number' in data:
                    update_data['batch_number'] = data['batch_number']
                if 'total_batches' in data:
                    update_data['total_batches'] = data['total_batches']
                
                await progress_callback(update_data)
            storage_progress_callback = mapped_storage_callback
        
        try:
            await add_code_examples_to_supabase(
                client=self.supabase_client,
                urls=storage_data['urls'],
                chunk_numbers=storage_data['chunk_numbers'],
                code_examples=storage_data['examples'],
                summaries=storage_data['summaries'],
                metadatas=storage_data['metadatas'],
                batch_size=20,
                url_to_full_document=url_to_full_document,
                progress_callback=storage_progress_callback
            )
            
            # Ensure we report completion at end_progress
            if progress_callback:
                await progress_callback({
                    'status': 'code_storage',
                    'percentage': end_progress,
                    'log': f'Code extraction completed. Stored {len(storage_data["examples"])} code examples.'
                })
            
            safe_logfire_info(f"Successfully stored {len(storage_data['examples'])} code examples")
            return len(storage_data['examples'])
            
        except Exception as e:
            safe_logfire_error(f"Error storing code examples | error={str(e)}")
            return 0