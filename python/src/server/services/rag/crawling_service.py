"""
Crawling Service Module for Archon RAG

This module provides core crawling functionality that can be shared between
MCP tools and FastAPI endpoints. It handles web crawling operations including
single page crawling, batch crawling, and recursive crawling.
"""

import json
# Removed direct logging import - using unified config
import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urldefrag
from xml.etree import ElementTree
import requests
import traceback

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, MemoryAdaptiveDispatcher
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from src.server.utils import get_supabase_client
from ...config.logfire_config import get_logger

logger = get_logger(__name__)


class CrawlingService:
    """Service class for web crawling operations"""
    
    # Common code block selectors for various editors and documentation frameworks
    CODE_BLOCK_SELECTORS = [
        # Milkdown
        ".milkdown-code-block pre",
        
        # Monaco Editor
        ".monaco-editor .view-lines",
        
        # CodeMirror
        ".cm-editor .cm-content",
        ".cm-line",
        
        # Prism.js (used by Docusaurus, Docsify, Gatsby)
        "pre[class*='language-']",
        "code[class*='language-']",
        ".prism-code",
        
        # highlight.js
        "pre code.hljs",
        ".hljs",
        
        # Shiki (used by VitePress, Nextra)
        ".shiki",
        "div[class*='language-'] pre",
        ".astro-code",
        
        # Generic patterns
        "pre code",
        ".code-block",
        ".codeblock",
        ".highlight pre"
    ]
    
    def __init__(self, crawler=None, supabase_client=None):
        """Initialize with optional crawler and supabase client"""
        self.crawler = crawler
        self.supabase_client = supabase_client or get_supabase_client()
    
    def _get_markdown_generator(self):
        """Get markdown generator that preserves code blocks."""
        return DefaultMarkdownGenerator(
            content_source="html",  # Use raw HTML to preserve code blocks
            options={
                "mark_code": True,         # Mark code blocks properly
                "handle_code_in_pre": True,  # Handle <pre><code> tags
                "body_width": 0,            # No line wrapping
                "skip_internal_links": True,  # Add to reduce noise
                "include_raw_html": False,    # Prevent HTML in markdown
                "escape": False,             # Don't escape special chars in code
                "decode_unicode": True,      # Decode unicode characters
                "strip_empty_lines": False,  # Preserve empty lines in code
                "preserve_code_formatting": True,  # Custom option if supported
                "code_language_callback": lambda el: el.get('class', '').replace('language-', '') if el else ''
            }
        )
    
    def is_sitemap(self, url: str) -> bool:
        """Check if a URL is a sitemap with error handling."""
        try:
            return url.endswith('sitemap.xml') or 'sitemap' in urlparse(url).path
        except Exception as e:
            logger.warning(f"Error checking if URL is sitemap: {e}")
            return False

    def is_txt(self, url: str) -> bool:
        """Check if a URL is a text file with error handling."""
        try:
            return url.endswith('.txt')
        except Exception as e:
            logger.warning(f"Error checking if URL is text file: {e}")
            return False

    def parse_sitemap(self, sitemap_url: str) -> List[str]:
        """Parse a sitemap and extract URLs with comprehensive error handling."""
        urls = []
        
        try:
            logger.info(f"Parsing sitemap: {sitemap_url}")
            resp = requests.get(sitemap_url, timeout=30)
            
            if resp.status_code != 200:
                logger.error(f"Failed to fetch sitemap: HTTP {resp.status_code}")
                return urls
                
            try:
                tree = ElementTree.fromstring(resp.content)
                urls = [loc.text for loc in tree.findall('.//{*}loc') if loc.text]
                logger.info(f"Successfully extracted {len(urls)} URLs from sitemap")
                
            except ElementTree.ParseError as e:
                logger.error(f"Error parsing sitemap XML: {e}")
            except Exception as e:
                logger.error(f"Unexpected error parsing sitemap: {e}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching sitemap: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in sitemap parsing: {e}")
            logger.error(traceback.format_exc())

        return urls

    def _transform_github_url(self, url: str) -> str:
        """Transform GitHub URLs to raw content URLs for better content extraction."""
        import re
        
        # Pattern for GitHub file URLs
        github_file_pattern = r'https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)'
        match = re.match(github_file_pattern, url)
        if match:
            owner, repo, branch, path = match.groups()
            raw_url = f'https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}'
            logger.info(f"Transformed GitHub file URL to raw: {url} -> {raw_url}")
            return raw_url
        
        # Pattern for GitHub directory URLs
        github_dir_pattern = r'https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)'
        match = re.match(github_dir_pattern, url)
        if match:
            # For directories, we can't directly get raw content
            # Return original URL but log a warning
            logger.warning(f"GitHub directory URL detected: {url} - consider using specific file URLs or GitHub API")
        
        return url
    
    def _is_documentation_site(self, url: str) -> bool:
        """Check if URL is likely a documentation site that needs special handling."""
        doc_patterns = [
            'docs.',
            'documentation.',
            '/docs/',
            '/documentation/',
            'readthedocs',
            'gitbook',
            'docusaurus',
            'vitepress',
            'docsify',
            'mkdocs'
        ]
        
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in doc_patterns)
    
    def _get_wait_selector_for_docs(self, url: str) -> str:
        """Get appropriate wait selector based on documentation framework."""
        url_lower = url.lower()
        
        # Common selectors for different documentation frameworks
        if 'docusaurus' in url_lower:
            return '.markdown, .theme-doc-markdown, article'
        elif 'vitepress' in url_lower:
            return '.VPDoc, .vp-doc, .content'
        elif 'gitbook' in url_lower:
            return '.markdown-section, .page-wrapper'
        elif 'mkdocs' in url_lower:
            return '.md-content, article'
        elif 'docsify' in url_lower:
            return '#main, .markdown-section'
        elif 'copilotkit' in url_lower:
            # CopilotKit uses a custom setup, wait for any content
            return 'div[class*="content"], div[class*="doc"], #__next'
        elif 'milkdown' in url_lower:
            # Milkdown uses a custom rendering system
            return 'main, article, .prose, [class*="content"]'
        else:
            # Simplified generic selector - just wait for body to have content
            return 'body'

    async def crawl_single_page(self, url: str, retry_count: int = 3) -> Dict[str, Any]:
        """
        Crawl a single web page and return the result with retry logic.
        
        Args:
            url: URL of the web page to crawl
            retry_count: Number of retry attempts
            
        Returns:
            Dict with success status, content, and metadata
        """
        # Transform GitHub URLs to raw content URLs if applicable
        original_url = url
        url = self._transform_github_url(url)
        
        last_error = None
        
        for attempt in range(retry_count):
            try:
                if not self.crawler:
                    logger.error(f"No crawler instance available for URL: {url}")
                    return {
                        "success": False,
                        "error": "No crawler instance available - crawler initialization may have failed"
                    }
                
                # Use ENABLED cache mode for better performance, BYPASS only on retries
                cache_mode = CacheMode.BYPASS if attempt > 0 else CacheMode.ENABLED
                
                # Check if this is a documentation site that needs special handling
                is_doc_site = self._is_documentation_site(url)
                
                # Enhanced configuration for documentation sites
                if is_doc_site:
                    wait_selector = self._get_wait_selector_for_docs(url)
                    logger.info(f"Detected documentation site, using wait selector: {wait_selector}")
                    
                    crawl_config = CrawlerRunConfig(
                        cache_mode=cache_mode, 
                        stream=False,  # Disable streaming for now
                        markdown_generator=self._get_markdown_generator(),
                        # Wait for documentation content to load
                        wait_for=wait_selector,
                        # Use domcontentloaded for problematic sites
                        wait_until='domcontentloaded' if 'milkdown' in url.lower() else 'networkidle',
                        # Increased timeout for JavaScript rendering
                        page_timeout=45000,  # 45 seconds
                        # Give JavaScript time to render
                        delay_before_return_html=2.0,
                        # Enable image waiting for completeness
                        wait_for_images=True,
                        # Scan full page to trigger lazy loading
                        scan_full_page=True,
                        # Keep images for documentation sites
                        exclude_all_images=False,
                        # Still remove popups
                        remove_overlay_elements=True,
                        # Process iframes for complete content
                        process_iframes=True
                    )
                else:
                    # Configuration for regular sites
                    crawl_config = CrawlerRunConfig(
                        cache_mode=cache_mode, 
                        stream=False,
                        markdown_generator=self._get_markdown_generator(),
                        wait_until='networkidle',  # Wait for network to be idle
                        delay_before_return_html=1.0,  # Give time for rendering
                        scan_full_page=True  # Trigger lazy loading
                    )
                
                logger.info(f"Crawling {url} (attempt {attempt + 1}/{retry_count})")
                logger.info(f"Using wait_until: {crawl_config.wait_until}, page_timeout: {crawl_config.page_timeout}")
                
                try:
                    result = await self.crawler.arun(url=url, config=crawl_config)
                except Exception as e:
                    last_error = f"Crawler exception for {url}: {str(e)}"
                    logger.error(last_error)
                    if attempt < retry_count - 1:
                        await asyncio.sleep(2 ** attempt)
                    continue
                
                if not result.success:
                    last_error = f"Failed to crawl {url}: {result.error_message}"
                    logger.warning(f"Crawl attempt {attempt + 1} failed: {last_error}")
                    
                    # Exponential backoff before retry
                    if attempt < retry_count - 1:
                        await asyncio.sleep(2 ** attempt)
                    continue
                
                # Validate content
                if not result.markdown or len(result.markdown.strip()) < 50:
                    last_error = f"Insufficient content from {url}"
                    logger.warning(f"Crawl attempt {attempt + 1}: {last_error}")
                    
                    if attempt < retry_count - 1:
                        await asyncio.sleep(2 ** attempt)
                    continue
                
                # Success! Return both markdown AND HTML
                # Debug logging to see what we got
                markdown_sample = result.markdown[:1000] if result.markdown else "NO MARKDOWN"
                has_triple_backticks = '```' in result.markdown if result.markdown else False
                backtick_count = result.markdown.count('```') if result.markdown else 0
                
                logger.info(f"Crawl result for {url} | has_markdown={bool(result.markdown)} | markdown_length={len(result.markdown) if result.markdown else 0} | has_triple_backticks={has_triple_backticks} | backtick_count={backtick_count}")
                
                # Log markdown info for debugging if needed
                if backtick_count > 0:
                    logger.info(f"Markdown has {backtick_count} code blocks for {url}")
                
                if 'getting-started' in url:
                    logger.info(f"Markdown sample for getting-started: {markdown_sample}")
                
                return {
                    "success": True,
                    "url": original_url,  # Use original URL for tracking
                    "markdown": result.markdown,
                    "html": result.html,  # Use raw HTML instead of cleaned_html for code extraction
                    "title": result.title or "Untitled",
                    "links": result.links,
                    "content_length": len(result.markdown)
                }
                
            except asyncio.TimeoutError:
                last_error = f"Timeout crawling {url}"
                logger.warning(f"Crawl attempt {attempt + 1} timed out")
            except Exception as e:
                last_error = f"Error crawling page: {str(e)}"
                logger.error(f"Error on attempt {attempt + 1} crawling {url}: {e}")
                logger.error(traceback.format_exc())
            
            # Exponential backoff before retry
            if attempt < retry_count - 1:
                await asyncio.sleep(2 ** attempt)
        
        # All retries failed
        return {
            "success": False,
            "error": last_error or f"Failed to crawl {url} after {retry_count} attempts"
        }

    async def crawl_markdown_file(self, url: str, progress_callback=None, 
                                 start_progress: int = 10, end_progress: int = 20) -> List[Dict[str, Any]]:
        """Crawl a .txt or markdown file with comprehensive error handling and progress reporting."""
        try:
            # Transform GitHub URLs to raw content URLs if applicable
            original_url = url
            url = self._transform_github_url(url)
            logger.info(f"Crawling markdown file: {url}")
            
            # Define local report_progress helper like in other methods
            async def report_progress(percentage: int, message: str):
                """Helper to report progress if callback is available"""
                if progress_callback:
                    await progress_callback('crawling', percentage, message)
            
            # Report initial progress
            await report_progress(start_progress, f"Fetching text file: {url}")
            
            # Use consistent configuration even for text files
            crawl_config = CrawlerRunConfig(
                cache_mode=CacheMode.ENABLED,
                stream=False
            )

            result = await self.crawler.arun(url=url, config=crawl_config)
            if result.success and result.markdown:
                logger.info(f"Successfully crawled markdown file: {url}")
                
                # Report completion progress
                await report_progress(end_progress, f"Text file crawled successfully: {original_url}")
                
                return [{'url': original_url, 'markdown': result.markdown, 'html': result.html}]
            else:
                logger.error(f"Failed to crawl {url}: {result.error_message}")
                return []
        except Exception as e:
            logger.error(f"Exception while crawling markdown file {url}: {e}")
            logger.error(traceback.format_exc())
            return []

    async def crawl_batch_with_progress(self, urls: List[str], max_concurrent: int = 10, 
                                       progress_callback=None, start_progress: int = 15, 
                                       end_progress: int = 60) -> List[Dict[str, Any]]:
        """Batch crawl multiple URLs in parallel with progress reporting."""
        if not self.crawler:
            logger.error("No crawler instance available for batch crawling")
            if progress_callback:
                await progress_callback('error', 0, 'Crawler not available')
            return []
            
        # Check if any URLs are documentation sites
        has_doc_sites = any(self._is_documentation_site(url) for url in urls)
        
        if has_doc_sites:
            logger.info("Detected documentation sites in batch, using enhanced configuration")
            # Use generic documentation selectors for batch crawling
            crawl_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS, 
                stream=False,  # Disable streaming for now
                markdown_generator=self._get_markdown_generator(),
                wait_for='body',  # Simple selector for batch
                wait_until='networkidle',  # Wait for network idle
                page_timeout=30000,  # 30 seconds for JavaScript sites
                delay_before_return_html=2.0,  # JavaScript rendering time
                wait_for_images=True,
                scan_full_page=True,  # Trigger lazy loading
                exclude_all_images=False,
                remove_overlay_elements=True,
                process_iframes=True
            )
        else:
            # Configuration for regular batch crawling
            crawl_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS, 
                stream=False,
                markdown_generator=self._get_markdown_generator(),
                wait_until='networkidle',
                delay_before_return_html=1.0,
                scan_full_page=True
            )
        dispatcher = MemoryAdaptiveDispatcher(
            memory_threshold_percent=70.0,
            check_interval=1.0,
            max_session_permit=max_concurrent
        )

        async def report_progress(percentage: int, message: str):
            """Helper to report progress if callback is available"""
            if progress_callback:
                await progress_callback('crawling', percentage, message)

        total_urls = len(urls)
        await report_progress(start_progress, f'Starting to crawl {total_urls} URLs...')
        
        # Process URLs in batches for better performance
        batch_size = min(20, max_concurrent)  # Increased to 20 for faster processing
        successful_results = []
        processed = 0
        
        # Transform all URLs at the beginning
        url_mapping = {}  # Map transformed URLs back to original
        transformed_urls = []
        for url in urls:
            transformed = self._transform_github_url(url)
            transformed_urls.append(transformed)
            url_mapping[transformed] = url
        
        for i in range(0, total_urls, batch_size):
            batch_urls = transformed_urls[i:i + batch_size]
            batch_start = i
            batch_end = min(i + batch_size, total_urls)
            
            # Report batch start with smooth progress
            progress_percentage = start_progress + int((i / total_urls) * (end_progress - start_progress))
            await report_progress(progress_percentage, f'Processing batch {batch_start+1}-{batch_end} of {total_urls} URLs...')
            
            # Crawl this batch
            batch_results = await self.crawler.arun_many(urls=batch_urls, config=crawl_config, dispatcher=dispatcher)
            
            # Check if we got a streaming result
            if hasattr(batch_results, '__aiter__'):
                # Handle streaming results
                j = 0
                async for result in batch_results:
                    processed += 1
                    if result.success and result.markdown:
                        # Map back to original URL
                        original_url = url_mapping.get(result.url, result.url)
                        successful_results.append({
                            'url': original_url, 
                            'markdown': result.markdown,
                            'html': result.html  # Use raw HTML
                        })
                    
                    # Report individual URL progress with smooth increments
                    progress_percentage = start_progress + int((processed / total_urls) * (end_progress - start_progress))
                    # Report more frequently for smoother progress
                    if processed % 5 == 0 or processed == total_urls:  # Report every 5 URLs or at the end
                        await report_progress(progress_percentage, f'Crawled {processed}/{total_urls} pages ({len(successful_results)} successful)')
                    j += 1
            else:
                # Handle non-streaming results (list)
                for j, result in enumerate(batch_results):
                    processed += 1
                    if result.success and result.markdown:
                        # Map back to original URL
                        original_url = url_mapping.get(result.url, result.url)
                        successful_results.append({
                            'url': original_url, 
                            'markdown': result.markdown,
                            'html': result.html  # Use raw HTML
                        })
                    
                    # Report individual URL progress with smooth increments
                    progress_percentage = start_progress + int((processed / total_urls) * (end_progress - start_progress))
                    # Report more frequently for smoother progress
                    if processed % 5 == 0 or processed == total_urls:  # Report every 5 URLs or at the end
                        await report_progress(progress_percentage, f'Crawled {processed}/{total_urls} pages ({len(successful_results)} successful)')
        
        await report_progress(end_progress, f'Batch crawling completed: {len(successful_results)}/{total_urls} pages successful')
        return successful_results

    async def crawl_recursive_with_progress(self, start_urls: List[str], max_depth: int = 3, 
                                          max_concurrent: int = 10, progress_callback=None, 
                                          start_progress: int = 10, end_progress: int = 60) -> List[Dict[str, Any]]:
        """Recursively crawl internal links from start URLs up to a maximum depth with progress reporting."""
        if not self.crawler:
            logger.error("No crawler instance available for recursive crawling")
            if progress_callback:
                await progress_callback('error', 0, 'Crawler not available')
            return []
            
        # Check if start URLs include documentation sites
        has_doc_sites = any(self._is_documentation_site(url) for url in start_urls)
        
        if has_doc_sites:
            logger.info("Detected documentation sites for recursive crawl, using enhanced configuration")
            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS, 
                stream=False,  # Disable streaming for now
                markdown_generator=self._get_markdown_generator(),
                wait_for='body',
                wait_until='networkidle',  # Wait for network idle
                page_timeout=30000,  # 30 seconds
                delay_before_return_html=2.0,  # JavaScript rendering time
                wait_for_images=True,
                scan_full_page=True,  # Trigger lazy loading
                exclude_all_images=False,
                remove_overlay_elements=True,
                process_iframes=True
            )
        else:
            # Configuration for regular recursive crawling
            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS, 
                stream=False,
                markdown_generator=self._get_markdown_generator(),
                wait_until='networkidle',
                delay_before_return_html=1.0,
                scan_full_page=True
            )
        dispatcher = MemoryAdaptiveDispatcher(
            memory_threshold_percent=70.0,
            check_interval=1.0,
            max_session_permit=max_concurrent
        )

        async def report_progress(percentage: int, message: str, **kwargs):
            """Helper to report progress if callback is available"""
            if progress_callback:
                # Add step information for multi-progress tracking
                step_info = {
                    'currentStep': message,
                    'stepMessage': message,
                    **kwargs
                }
                await progress_callback('crawling', percentage, message, **step_info)

        visited = set()

        def normalize_url(url):
            return urldefrag(url)[0]

        current_urls = set([normalize_url(u) for u in start_urls])
        results_all = []
        total_processed = 0

        for depth in range(max_depth):
            urls_to_crawl = [normalize_url(url) for url in current_urls if normalize_url(url) not in visited]
            if not urls_to_crawl:
                break

            # Calculate progress for this depth level
            depth_start = start_progress + int((depth / max_depth) * (end_progress - start_progress) * 0.8)
            depth_end = start_progress + int(((depth + 1) / max_depth) * (end_progress - start_progress) * 0.8)
            
            await report_progress(depth_start, f'Crawling depth {depth + 1}/{max_depth}: {len(urls_to_crawl)} URLs to process')

            # Process URLs in larger batches for better performance
            batch_size = min(30, max_concurrent)  # Process in batches of 30 for speed
            next_level_urls = set()
            depth_successful = 0
            
            for batch_idx in range(0, len(urls_to_crawl), batch_size):
                batch_urls = urls_to_crawl[batch_idx:batch_idx + batch_size]
                batch_end_idx = min(batch_idx + batch_size, len(urls_to_crawl))
                
                # Calculate progress for this batch within the depth
                batch_progress = depth_start + int((batch_idx / len(urls_to_crawl)) * (depth_end - depth_start))
                await report_progress(batch_progress, 
                                    f'Depth {depth + 1}: crawling URLs {batch_idx + 1}-{batch_end_idx} of {len(urls_to_crawl)}',
                                    totalPages=total_processed + batch_idx, 
                                    processedPages=len(results_all))
                
                # Crawl this batch
                batch_results = await self.crawler.arun_many(urls=batch_urls, config=run_config, dispatcher=dispatcher)
                
                # Check if we got a streaming result
                if hasattr(batch_results, '__aiter__'):
                    # Handle streaming results
                    i = 0
                    async for result in batch_results:
                        norm_url = normalize_url(result.url)
                        visited.add(norm_url)
                        total_processed += 1
                        
                        if result.success and result.markdown:
                            results_all.append({
                                'url': result.url, 
                                'markdown': result.markdown,
                                'html': result.html  # Always use raw HTML for code extraction
                            })
                            depth_successful += 1
                            
                            # Find internal links for next depth
                            for link in result.links.get("internal", []):
                                next_url = normalize_url(link["href"])
                                if next_url not in visited:
                                    next_level_urls.add(next_url)
                        
                        # Report progress every few URLs
                        current_idx = batch_idx + i + 1
                        if current_idx % 5 == 0 or current_idx == len(urls_to_crawl):
                            current_progress = depth_start + int((current_idx / len(urls_to_crawl)) * (depth_end - depth_start))
                            await report_progress(current_progress,
                                                f'Depth {depth + 1}: processed {current_idx}/{len(urls_to_crawl)} URLs ({depth_successful} successful)',
                                                totalPages=total_processed, 
                                                processedPages=len(results_all))
                        i += 1
                else:
                    # Handle non-streaming results (list)
                    for i, result in enumerate(batch_results):
                        norm_url = normalize_url(result.url)
                        visited.add(norm_url)
                        total_processed += 1
                        
                        if result.success and result.markdown:
                            results_all.append({
                                'url': result.url, 
                                'markdown': result.markdown,
                                'html': result.html  # Always use raw HTML for code extraction
                            })
                            depth_successful += 1
                            
                            # Find internal links for next depth
                            for link in result.links.get("internal", []):
                                next_url = normalize_url(link["href"])
                                if next_url not in visited:
                                    next_level_urls.add(next_url)
                        
                        # Report progress every few URLs
                        current_idx = batch_idx + i + 1
                        if current_idx % 5 == 0 or current_idx == len(urls_to_crawl):
                            current_progress = depth_start + int((current_idx / len(urls_to_crawl)) * (depth_end - depth_start))
                            await report_progress(current_progress,
                                                f'Depth {depth + 1}: processed {current_idx}/{len(urls_to_crawl)} URLs ({depth_successful} successful)',
                                                totalPages=total_processed, 
                                                processedPages=len(results_all))

            current_urls = next_level_urls
            
            # Report completion of this depth
            await report_progress(depth_end, 
                                f'Depth {depth + 1} completed: {depth_successful} pages crawled, {len(next_level_urls)} URLs found for next depth')

        await report_progress(end_progress, f'Recursive crawling completed: {len(results_all)} total pages crawled across {max_depth} depth levels')
        return results_all