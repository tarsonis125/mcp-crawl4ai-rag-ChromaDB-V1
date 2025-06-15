"""
RAG Module for Archon MCP Server

This module provides tools for:
- Web crawling (single pages, smart crawling, recursive crawling)
- Document upload and processing
- RAG query and search
- Source management
- Code example extraction and search

All tools in this module work with web content and document storage/retrieval.

Enhanced with comprehensive error handling and graceful degradation.
"""
from mcp.server.fastmcp import FastMCP, Context
from sentence_transformers import CrossEncoder
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urldefrag
from xml.etree import ElementTree
import requests
import asyncio
import json
import os
import re
import concurrent.futures
import logging
import traceback

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, MemoryAdaptiveDispatcher

# Import Logfire
from ..logfire_config import rag_logger, mcp_logger, search_logger

from src.utils import (
    get_supabase_client,
    add_documents_to_supabase, 
    search_documents,
    extract_code_blocks,
    generate_code_example_summary,
    add_code_examples_to_supabase,
    update_source_info,
    extract_source_summary,
    search_code_examples,
    create_embedding,
    create_embeddings_batch,
    generate_source_title_and_metadata,
    process_chunk_with_context
)

# Helper functions to get settings from credential service
def get_setting(key: str, default: str = "false") -> str:
    """Get a setting from the credential service or fall back to environment variable."""
    try:
        from src.credential_service import credential_service
        if hasattr(credential_service, '_cache') and credential_service._cache_initialized:
            cached_value = credential_service._cache.get(key)
            if isinstance(cached_value, dict) and cached_value.get("is_encrypted"):
                encrypted_value = cached_value.get("encrypted_value")
                if encrypted_value:
                    try:
                        return credential_service._decrypt_value(encrypted_value)
                    except Exception:
                        pass
            elif cached_value:
                return str(cached_value)
        # Fallback to environment variable
        return os.getenv(key, default)
    except Exception:
        return os.getenv(key, default)

def get_bool_setting(key: str, default: bool = False) -> bool:
    """Get a boolean setting from credential service."""
    value = get_setting(key, "false" if not default else "true")
    return value.lower() in ("true", "1", "yes", "on")

# Setup logging for the RAG module
logger = logging.getLogger(__name__)

def rerank_results(model: CrossEncoder, query: str, results: List[Dict[str, Any]], content_key: str = "content") -> List[Dict[str, Any]]:
    """
    Rerank search results using a cross-encoder model.
    
    Args:
        model: The cross-encoder model to use for reranking
        query: The search query
        results: List of search results
        content_key: The key in each result dict that contains the text content
        
    Returns:
        Reranked list of results
    """
    if not model or not results:
        return results
    
    try:
        # Extract content from results
        texts = [result.get(content_key, "") for result in results]
        
        # Create pairs of [query, document] for the cross-encoder
        pairs = [[query, text] for text in texts]
        
        # Get relevance scores from the cross-encoder
        scores = model.predict(pairs)
        
        # Add scores to results and sort by score (descending)
        for i, result in enumerate(results):
            result["rerank_score"] = float(scores[i])
        
        # Sort by rerank score
        reranked = sorted(results, key=lambda x: x.get("rerank_score", 0), reverse=True)
        
        return reranked
    except Exception as e:
        print(f"Error during reranking: {e}")
        return results


def is_sitemap(url: str) -> bool:
    """Check if a URL is a sitemap with error handling."""
    try:
        return url.endswith('sitemap.xml') or 'sitemap' in urlparse(url).path
    except Exception as e:
        logger.warning(f"Error checking if URL is sitemap: {e}")
        return False


def is_txt(url: str) -> bool:
    """Check if a URL is a text file with error handling."""
    try:
        return url.endswith('.txt')
    except Exception as e:
        logger.warning(f"Error checking if URL is text file: {e}")
        return False


def safe_parse_sitemap(sitemap_url: str) -> List[str]:
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


def smart_chunk_markdown(text: str, chunk_size: int = 5000) -> List[str]:
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
        logger.error(traceback.format_exc())
        # Fallback to simple chunking
        try:
            return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        except Exception as fallback_error:
            logger.error(f"Even fallback chunking failed: {fallback_error}")
            return [text] if text else []


def extract_section_info(chunk: str) -> Dict[str, Any]:
    """Extracts headers and stats from a chunk with error handling."""
    try:
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


def safe_process_code_example(args):
    """Process a single code example to generate its summary with error handling."""
    try:
        code, context_before, context_after = args
        return generate_code_example_summary(code, context_before, context_after)
    except Exception as e:
        logger.warning(f"Error processing code example: {e}")
        return f"Code example (processing failed: {str(e)})"


# Helper functions for crawling with enhanced error handling
async def safe_crawl_markdown_file(crawler: AsyncWebCrawler, url: str) -> List[Dict[str, Any]]:
    """Crawl a .txt or markdown file with comprehensive error handling."""
    try:
        logger.info(f"Crawling markdown file: {url}")
        crawl_config = CrawlerRunConfig()

        result = await crawler.arun(url=url, config=crawl_config)
        if result.success and result.markdown:
            logger.info(f"Successfully crawled markdown file: {url}")
            return [{'url': url, 'markdown': result.markdown}]
        else:
            logger.error(f"Failed to crawl {url}: {result.error_message}")
            return []
    except Exception as e:
        logger.error(f"Exception while crawling markdown file {url}: {e}")
        logger.error(traceback.format_exc())
        return []


# Function aliases to match original naming conventions
parse_sitemap = safe_parse_sitemap
crawl_markdown_file = safe_crawl_markdown_file
process_code_example = safe_process_code_example

# Helper functions for crawling
async def crawl_batch_with_progress(crawler: AsyncWebCrawler, urls: List[str], max_concurrent: int = 10, progress_callback=None, start_progress: int = 15, end_progress: int = 60) -> List[Dict[str, Any]]:
    """Batch crawl multiple URLs in parallel with progress reporting."""
    crawl_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, stream=False)
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
    
    results = await crawler.arun_many(urls=urls, config=crawl_config, dispatcher=dispatcher)
    
    # Process results and report progress
    successful_results = []
    processed = 0
    
    for result in results:
        processed += 1
        if result.success and result.markdown:
            successful_results.append({'url': result.url, 'markdown': result.markdown})
        
        # Calculate progress between start_progress and end_progress
        progress_percentage = start_progress + int((processed / total_urls) * (end_progress - start_progress))
        await report_progress(progress_percentage, f'Crawled {processed}/{total_urls} pages ({len(successful_results)} successful)')
    
    await report_progress(end_progress, f'Batch crawling completed: {len(successful_results)}/{total_urls} pages successful')
    return successful_results


async def crawl_recursive_with_progress(crawler: AsyncWebCrawler, start_urls: List[str], max_depth: int = 3, max_concurrent: int = 10, progress_callback=None, start_progress: int = 10, end_progress: int = 60) -> List[Dict[str, Any]]:
    """Recursively crawl internal links from start URLs up to a maximum depth with progress reporting."""
    run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, stream=False)
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

        results = await crawler.arun_many(urls=urls_to_crawl, config=run_config, dispatcher=dispatcher)
        next_level_urls = set()
        depth_successful = 0

        for i, result in enumerate(results):
            norm_url = normalize_url(result.url)
            visited.add(norm_url)
            total_processed += 1

            if result.success and result.markdown:
                results_all.append({'url': result.url, 'markdown': result.markdown})
                depth_successful += 1
                
                # Find internal links for next depth
                for link in result.links.get("internal", []):
                    next_url = normalize_url(link["href"])
                    if next_url not in visited:
                        next_level_urls.add(next_url)

            # Report progress within this depth level
            if len(urls_to_crawl) > 0:
                depth_progress = depth_start + int((i + 1) / len(urls_to_crawl) * (depth_end - depth_start))
                await report_progress(depth_progress, 
                                    f'Depth {depth + 1}: processed {i + 1}/{len(urls_to_crawl)} URLs ({depth_successful} successful)',
                                    totalPages=total_processed, processedPages=len(results_all))

        current_urls = next_level_urls
        
        # Report completion of this depth
        await report_progress(depth_end, 
                            f'Depth {depth + 1} completed: {depth_successful} pages crawled, {len(next_level_urls)} URLs found for next depth')

    await report_progress(end_progress, f'Recursive crawling completed: {len(results_all)} total pages crawled across {max_depth} depth levels')
    return results_all


# Standalone functions for direct import (needed by api_wrapper.py)


async def smart_crawl_url_direct(ctx, url: str, max_depth: int = 3, max_concurrent: int = 10, chunk_size: int = 5000) -> str:
    """
    Standalone function for smart crawling that can be imported directly.
    
    Intelligently crawl a URL based on its type (sitemap, text file, or webpage).
    """
    try:
        crawler = ctx.request_context.lifespan_context.crawler
        supabase_client = ctx.request_context.lifespan_context.supabase_client
        reranking_model = getattr(ctx.request_context.lifespan_context, 'reranking_model', None)
        
        # Get progress callback if available
        progress_callback = getattr(ctx, 'progress_callback', None)
        
        async def report_progress(status: str, percentage: int, message: str, **kwargs):
            """Helper to report progress if callback available"""
            if progress_callback:
                # Add step information for multi-progress tracking
                step_info = {
                    'currentStep': status,
                    'stepMessage': message,
                    **kwargs
                }
                await progress_callback(status, percentage, message, **step_info)
        
        await report_progress('analyzing', 2, f'Analyzing URL type: {url}')
        
        # Determine crawl strategy based on URL type
        if is_sitemap(url):
            await report_progress('sitemap', 4, 'Detected sitemap, extracting URLs...')
            
            # Parse sitemap and get URLs
            urls = parse_sitemap(url)
            if not urls:
                return json.dumps({
                    "success": False,
                    "error": "Failed to extract URLs from sitemap"
                })
            
            await report_progress('sitemap', 6, f'Found {len(urls)} URLs in sitemap')
            
            # Batch crawl the sitemap URLs
            results = await crawl_batch_with_progress(
                crawler, urls, max_concurrent, progress_callback, 6, 22
            )
            crawl_type = "sitemap"
            
        elif is_txt(url):
            await report_progress('text_file', 4, 'Detected text file, downloading...')
            
            # Crawl the text file directly
            results = await crawl_markdown_file(crawler, url)
            crawl_type = "text_file"
            
            await report_progress('text_file', 22, f'Downloaded text file: {len(results)} file processed')
            
        else:
            await report_progress('webpage', 4, 'Detected webpage, starting recursive crawl...')
            
            # Recursive crawling for regular webpages
            results = await crawl_recursive_with_progress(
                crawler, [url], max_depth, max_concurrent, progress_callback, 4, 22
            )
            crawl_type = "webpage"
        
        if not results:
            return json.dumps({
                "success": False,
                "error": "No content retrieved from crawling"
            })
        
        await report_progress('processing', 24, f'Processing {len(results)} pages into chunks...')
        
        # Process all crawled content
        all_documents = []
        all_code_examples = []
        total_chunks = 0
        total_word_count = 0
        
        for i, page_result in enumerate(results):
            page_url = page_result['url']
            markdown_content = page_result['markdown']
            
            # Create chunks from the content
            chunks = smart_chunk_markdown(markdown_content, chunk_size)
            
            # Process each chunk
            for j, chunk in enumerate(chunks):
                section_info = extract_section_info(chunk)
                total_word_count += section_info["word_count"]
                
                # Get knowledge metadata from context if available
                knowledge_metadata = getattr(ctx, 'knowledge_metadata', {})
                
                document_metadata = {
                    "source": urlparse(page_url).netloc or page_url,
                    "title": f"Page {i+1} from {crawl_type}",
                    "headers": section_info["headers"],
                    "char_count": section_info["char_count"],
                    "word_count": section_info["word_count"],
                    "crawl_type": crawl_type,
                    "source_type": "url",
                    **knowledge_metadata
                }
                
                all_documents.append({
                    "content": chunk,
                    "url": page_url,
                    "chunk_index": j,
                    "metadata": document_metadata
                })
            
            # Extract code examples if enabled (sequential processing to avoid progress conflicts)
            if get_bool_setting("USE_AGENTIC_RAG", False):
                code_blocks = extract_code_blocks(markdown_content)
                if code_blocks:
                    # Process code examples sequentially to maintain progress accuracy
                    for j, code_block in enumerate(code_blocks):
                        summary = process_code_example(code_block)
                        all_code_examples.append({
                            'code_block': code_block,
                            'summary': summary,
                            'url': page_url
                        })
                        
                        # Report progress for code processing
                        if j % 5 == 0:  # Every 5 code blocks
                            code_progress = 24 + int((i + 1) / len(results) * 6) + int((j / len(code_blocks)) * 0.5)
                            await report_progress('processing', code_progress, f'Processed {j+1}/{len(code_blocks)} code examples')
            
            # Report progress during processing
            progress_pct = 24 + int((i + 1) / len(results) * 6)  # 24-30%
            await report_progress('processing', progress_pct, f'Processed {i + 1}/{len(results)} pages')
        
        await report_progress('storing', 30, 'Storing content in database...')
        
        # Prepare data for Supabase insertion
        urls = [doc['url'] for doc in all_documents]
        chunk_numbers = [doc['chunk_index'] for doc in all_documents]  # Keep 0-based indexing like original
        contents = [doc['content'] for doc in all_documents]
        metadatas = [doc['metadata'] for doc in all_documents]
        url_to_full_document = {}
        
        # Build url_to_full_document mapping from results
        for page_result in results:
            url_to_full_document[page_result['url']] = page_result['markdown']
        
        await report_progress('storing', 35, 'Preparing source information...')
        
        # Track sources and their content for source info creation (BEFORE document insertion)
        source_content_map = {}
        source_word_counts = {}
        
        # Calculate word counts per source
        for doc in all_documents:
            source_id = doc['metadata']['source']
            word_count = doc['metadata']['word_count']
            
            if source_id not in source_word_counts:
                source_word_counts[source_id] = 0
                # Store content for summary generation (first 5000 chars from the first page of this source)
                for page_result in results:
                    if urlparse(page_result['url']).netloc == source_id:
                        source_content_map[source_id] = page_result['markdown'][:5000]
                        break
            
            source_word_counts[source_id] += word_count
        
        # STEP 4: Create source records (35-45%)
        await report_progress('source_creation', 0, f'Creating source records for {len(source_content_map)} sources...')
        
        # Create sources FIRST (before inserting documents to avoid foreign key constraint)
        for i, (source_id, content) in enumerate(source_content_map.items()):
            word_count = source_word_counts.get(source_id, 0)
            source_summary = extract_source_summary(source_id, content)
            
            # Get metadata from context including update_frequency
            knowledge_metadata = getattr(ctx, 'knowledge_metadata', {})
            update_frequency = knowledge_metadata.get('update_frequency', 7)
            
            update_source_info(
                supabase_client, 
                source_id, 
                source_summary, 
                word_count, 
                content[:5000], 
                "technical",  # Hardcoded back to working value
                [],           # Hardcoded back to working value
                update_frequency
            )
            
            progress_pct = int((i + 1) / len(source_content_map) * 100)
            await report_progress('source_creation', progress_pct, f'Created source {i+1}/{len(source_content_map)}: {source_id}')
        
        # STEP 5: Store documents (45-90%) - Let this step handle its own 0-100% progress
        try:
            await store_documents_with_progress(
                supabase_client=supabase_client,
                urls=urls,
                chunk_numbers=chunk_numbers,
                contents=contents,
                metadatas=metadatas,
                url_to_full_document=url_to_full_document,
                progress_callback=lambda pct, msg: report_progress('document_storage', pct, msg)  # Direct 0-100%
            )
            
        except Exception as e:
            error_msg = f"Failed to store documents: {str(e)}"
            await report_progress('error', 0, error_msg)
            raise Exception(error_msg)
            
        chunks_stored = len(all_documents)
        
        # STEP 6: Store code examples (90-95%)
        code_examples_stored = 0
        if all_code_examples:
            await report_progress('code_storage', 0, f'Storing {len(all_code_examples)} code examples...')
            
            # Prepare data for code examples insertion
            code_urls = [ex['url'] for ex in all_code_examples]
            code_chunk_numbers = [i for i in range(len(all_code_examples))]  # Sequential numbering (0-based)
            code_blocks = [ex['code_block'] for ex in all_code_examples]
            code_summaries = [ex['summary'] for ex in all_code_examples]
            code_metadatas = [{'source_url': ex['url'], 'extraction_method': 'agentic_rag'} for ex in all_code_examples]
            
            add_code_examples_to_supabase(
                client=supabase_client,
                urls=code_urls,
                chunk_numbers=code_chunk_numbers,
                code_examples=code_blocks,
                summaries=code_summaries,
                metadatas=code_metadatas
            )
            code_examples_stored = len(all_code_examples)
            await report_progress('code_storage', 100, f'Stored {code_examples_stored} code examples')
        
        # STEP 7: Finalization (95-100%)
        await report_progress('finalization', 100, f'Successfully crawled {len(results)} pages with {chunks_stored} chunks stored')
        
        return json.dumps({
            "success": True,
            "crawl_type": crawl_type,
            "url": url,
            "urls_processed": len(results),
            "chunks_stored": chunks_stored,
            "code_examples_stored": code_examples_stored,
            "total_chunks": chunks_stored,
            "content_length": sum(len(r['markdown']) for r in results),
            "total_word_count": total_word_count,
            "source_id": source_id
        })
        
    except Exception as e:
        error_msg = f"Error in smart crawl: {str(e)}"
        if 'progress_callback' in locals():
            await report_progress('error', 0, error_msg)
        return json.dumps({
            "success": False,
            "error": error_msg
        })


async def delete_source(ctx, source_id: str) -> str:
    """
    Delete a source and all associated crawled pages and code examples from the database.
    
    Args:
        ctx: Context with supabase_client accessible via ctx.request_context.lifespan_context.supabase_client
        source_id: The source ID to delete
    
    Returns:
        JSON string with deletion results
    """
    try:
        print(f"DEBUG: Starting delete_source for source_id: {source_id}")
        
        # Get supabase client with error handling
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            print(f"DEBUG: Successfully got supabase_client: {type(supabase_client)}")
        except Exception as client_error:
            print(f"ERROR: Failed to get supabase_client: {client_error}")
            return json.dumps({
                "success": False,
                "error": f"Failed to get database client: {str(client_error)}"
            })
        
        # Delete from crawled_pages table
        try:
            print(f"DEBUG: Deleting from crawled_pages table for source_id: {source_id}")
            pages_response = supabase_client.table("crawled_pages").delete().eq("source_id", source_id).execute()
            pages_deleted = len(pages_response.data) if pages_response.data else 0
            print(f"DEBUG: Deleted {pages_deleted} pages from crawled_pages")
        except Exception as pages_error:
            print(f"ERROR: Failed to delete from crawled_pages: {pages_error}")
            return json.dumps({
                "success": False,
                "error": f"Failed to delete crawled pages: {str(pages_error)}"
            })
        
        # Delete from code_examples table
        try:
            print(f"DEBUG: Deleting from code_examples table for source_id: {source_id}")
            code_response = supabase_client.table("code_examples").delete().eq("source_id", source_id).execute()
            code_deleted = len(code_response.data) if code_response.data else 0
            print(f"DEBUG: Deleted {code_deleted} code examples")
        except Exception as code_error:
            print(f"ERROR: Failed to delete from code_examples: {code_error}")
            return json.dumps({
                "success": False,
                "error": f"Failed to delete code examples: {str(code_error)}"
            })
        
        # Delete from sources table
        try:
            print(f"DEBUG: Deleting from sources table for source_id: {source_id}")
            source_response = supabase_client.table("sources").delete().eq("source_id", source_id).execute()
            source_deleted = len(source_response.data) if source_response.data else 0
            print(f"DEBUG: Deleted {source_deleted} source records")
        except Exception as source_error:
            print(f"ERROR: Failed to delete from sources: {source_error}")
            return json.dumps({
                "success": False,
                "error": f"Failed to delete source: {str(source_error)}"
            })
        
        print(f"DEBUG: Delete operation completed successfully")
        return json.dumps({
            "success": True,
            "source_id": source_id,
            "pages_deleted": pages_deleted,
            "code_examples_deleted": code_deleted,
            "source_records_deleted": source_deleted
        })
        
    except Exception as e:
        print(f"ERROR: Unexpected error in delete_source: {e}")
        print(f"ERROR: Exception type: {type(e)}")
        import traceback
        print(f"ERROR: Traceback: {traceback.format_exc()}")
        return json.dumps({
            "success": False,
            "error": f"Error deleting source: {str(e)}"
        })


# MCP Tool Definitions
def register_rag_tools(mcp: FastMCP):
    """Register all RAG tools with the MCP server."""
    
    @mcp.tool()
    async def crawl_single_page(ctx: Context, url: str) -> str:
        """
        Crawl a single web page and store its content in Supabase.
        
        This tool is ideal for quickly retrieving content from a specific URL without following links.
        The content is stored in Supabase for later retrieval and querying.
        
        Args:
            url: URL of the web page to crawl (must be a valid HTTP/HTTPS URL)
        
        Returns:
            JSON string with the operation results including success status, content metrics, and any errors
        """
        try:
            # Get the crawler from the context
            crawler = ctx.request_context.lifespan_context.crawler
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            crawl_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, stream=False)
            result = await crawler.arun(url=url, config=crawl_config)
            
            if not result.success:
                return json.dumps({
                    "success": False,
                    "error": f"Failed to crawl {url}: {result.error_message}"
                })
            
            # Process the content
            markdown_content = result.markdown
            chunks = smart_chunk_markdown(markdown_content, chunk_size=5000)
            
            # Create documents for Supabase
            documents = []
            total_word_count = 0
            
            for i, chunk in enumerate(chunks):
                section_info = extract_section_info(chunk)
                total_word_count += section_info["word_count"]
                
                documents.append({
                    "content": chunk,
                    "url": url,
                    "chunk_index": i,
                    "metadata": {
                        "source_id": urlparse(url).netloc,
                        "title": result.title or "Untitled",
                        "headers": section_info["headers"],
                        "char_count": section_info["char_count"],
                        "word_count": section_info["word_count"]
                    }
                })
            
            # Calculate total word count for source info
            total_word_count = sum(doc['metadata']['word_count'] for doc in documents)
            source_id = urlparse(url).netloc
            
            # Create source FIRST (before inserting documents to avoid foreign key constraint)
            source_summary = extract_source_summary(source_id, markdown_content[:5000])
            update_source_info(supabase_client, source_id, source_summary, total_word_count, markdown_content[:5000], "technical", [], 0)  # Single page crawls default to never update
            
            # Store in Supabase - prepare data for the function
            urls = [doc['url'] for doc in documents]
            chunk_numbers = [doc['chunk_index'] for doc in documents]  # Keep 0-based indexing like original
            contents = [doc['content'] for doc in documents]
            metadatas = [doc['metadata'] for doc in documents]
            url_to_full_document = {url: markdown_content}  # Single page mapping
            
            add_documents_to_supabase(
                client=supabase_client,
                urls=urls,
                chunk_numbers=chunk_numbers,
                contents=contents,
                metadatas=metadatas,
                url_to_full_document=url_to_full_document
            )
            chunks_stored = len(documents)
            
            # Process code examples if enabled
            code_examples_stored = 0
            if get_bool_setting("USE_AGENTIC_RAG", False):
                code_blocks = extract_code_blocks(markdown_content)
                if code_blocks:
                    # Process code examples sequentially to avoid progress conflicts
                    code_summaries = []
                    for code_block in code_blocks:
                        summary = safe_process_code_example(code_block)
                        code_summaries.append(summary)
                    
                    # Prepare data for code examples insertion
                    code_urls = [url for _ in code_blocks]  # All from same URL
                    code_chunk_numbers = [i for i in range(len(code_blocks))]  # Sequential numbering (0-based)
                    code_metadatas = [{'source_url': url, 'extraction_method': 'agentic_rag'} for _ in code_blocks]
                    
                    add_code_examples_to_supabase(
                        client=supabase_client,
                        urls=code_urls,
                        chunk_numbers=code_chunk_numbers,
                        code_examples=code_blocks,
                        summaries=code_summaries,
                        metadatas=code_metadatas
                    )
                    code_examples_stored = len(code_blocks)
            
            # Source information already updated before document insertion
            
            return json.dumps({
                "success": True,
                "url": url,
                "chunks_stored": chunks_stored,
                "code_examples_stored": code_examples_stored,
                "content_length": len(markdown_content),
                "total_word_count": total_word_count,
                "source_id": urlparse(url).netloc,
                "links_count": {
                    "internal": len(result.links.get("internal", [])),
                    "external": len(result.links.get("external", []))
                }
            })
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error crawling page: {str(e)}"
            })
    
    @mcp.tool()
    async def smart_crawl_url(ctx: Context, url: str, max_depth: int = 3, max_concurrent: int = 10, chunk_size: int = 5000) -> str:
        """
        Intelligently crawl a URL based on its type.
        
        Automatically detects sitemaps, text files, or regular webpages and applies appropriate crawling method.
        
        Args:
            url: URL to crawl (webpage, sitemap.xml, or .txt file)
            max_depth: Maximum recursion depth for regular URLs (default: 3)
            max_concurrent: Maximum concurrent browser sessions (default: 10)
            chunk_size: Maximum size of each content chunk (default: 5000)
        
        Returns:
            JSON string with crawling results and statistics
        """
        # Call the standalone function
        return await smart_crawl_url_direct(ctx, url, max_depth, max_concurrent, chunk_size)
    
    @mcp.tool()
    async def get_available_sources(ctx: Context) -> str:
        """
        Get all available sources from the sources table.
        
        Returns a list of all unique sources that have been crawled and stored in the database.
        
        Returns:
            JSON string with list of sources and their metadata
        """
        try:
            # Get the Supabase client from the context
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            response = supabase_client.table("sources").select("*").execute()
            
            sources = []
            for row in response.data:
                sources.append({
                    "source_id": row["source_id"],
                    "title": row.get("title", ""),
                    "description": row.get("description", ""),
                    "created_at": row.get("created_at", ""),
                    "last_updated": row.get("last_updated", "")
                })
            
            return json.dumps({
                "success": True,
                "sources": sources,
                "total_count": len(sources)
            })
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error retrieving sources: {str(e)}"
            })
    
    @mcp.tool()
    async def perform_rag_query(
        ctx: Context,
        query: str,
        source: str = None,
        match_count: int = 5
    ) -> str:
        """
        Perform a RAG (Retrieval Augmented Generation) query on stored content.
        
        This tool searches the vector database for content relevant to the query and returns
        the matching documents. Optionally filter by source domain.
        Get the source by using the get_available_sources tool before calling this search!
        
        Args:
            query: The search query
            source: Optional source domain to filter results (e.g., 'example.com')
            match_count: Maximum number of results to return (default: 5)
        
        Returns:
            JSON string with search results
        """
        with rag_logger.span("mcp_rag_query",
                            query_length=len(query),
                            source=source,
                            match_count=match_count,
                            client_type="mcp") as span:
            try:
                rag_logger.info("MCP RAG query started",
                               query=query[:100] + "..." if len(query) > 100 else query,
                               source=source,
                               match_count=match_count)
                
                # Get Supabase client
                with rag_logger.span("get_client"):
                    client = get_supabase_client()
                    span.set_attribute("client_obtained", True)
                
                # Build filter metadata if source is provided
                filter_metadata = None
                if source:
                    with rag_logger.span("build_filter"):
                        filter_metadata = {"source": source}
                        rag_logger.debug("Built filter metadata", source=source)
                        span.set_attribute("filter_applied", True)
                
                # Perform vector search
                with rag_logger.span("vector_search"):
                    results = search_documents(
                        client=client,
                        query=query,
                        match_count=match_count,
                        filter_metadata=filter_metadata
                    )
                    span.set_attribute("raw_results_count", len(results))
                
                # Format results for MCP response
                with rag_logger.span("format_response"):
                    formatted_results = []
                    for i, result in enumerate(results):
                        try:
                            formatted_result = {
                                "id": result.get("id", f"result_{i}"),
                                "content": result.get("content", "")[:1000],  # Limit content
                                "metadata": result.get("metadata", {}),
                                "similarity_score": result.get("similarity", 0.0)
                            }
                            formatted_results.append(formatted_result)
                        except Exception as format_error:
                            rag_logger.warning("Failed to format result", 
                                             result_index=i, 
                                             error=str(format_error))
                            continue
                
                response_data = {
                    "success": True,
                    "results": formatted_results,
                    "query": query,
                    "source": source,
                    "match_count": match_count,
                    "total_found": len(formatted_results),
                    "execution_path": "mcp_vector_search"
                }
                
                span.set_attribute("final_results_count", len(formatted_results))
                span.set_attribute("success", True)
                
                rag_logger.info("MCP RAG query completed successfully",
                               results_count=len(formatted_results),
                               execution_path="mcp_vector_search")
                
                return json.dumps(response_data, indent=2)
                
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error_type", type(e).__name__)
                
                rag_logger.exception("MCP RAG query failed",
                                    error=str(e),
                                    error_type=type(e).__name__,
                                    query=query[:50],
                                    source=source)
                
                # Return error as JSON for graceful handling
                error_response = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "query": query,
                    "source": source,
                    "execution_path": "mcp_vector_search"
                }
                return json.dumps(error_response, indent=2)
    
    @mcp.tool()
    async def delete_source_tool(ctx: Context, source_id: str) -> str:
        """
        Delete a source and all associated crawled pages and code examples from the database.
        
        Args:
            source_id: The source ID to delete
        
        Returns:
            JSON string with deletion results
        """
        # Call the standalone function
        return await delete_source(ctx, source_id)
    
    @mcp.tool()
    async def search_code_examples(ctx: Context, query: str, source_id: str = None, match_count: int = 5) -> str:
        """
        Search for code examples relevant to the query.
        
        This tool searches the vector database for code examples relevant to the query and returns
        the matching examples with their summaries. Optionally filter by source_id.
        Get the source_id by using the get_available_sources tool before calling this search!

        Use the get_available_sources tool first to see what sources are available for filtering.
        
        Args:
            query: The search query
            source_id: Optional source ID to filter results (e.g., 'example.com')
            match_count: Maximum number of results to return (default: 5)
        
        Returns:
            JSON string with search results
        """
        # Check if code example extraction is enabled
        extract_code_examples_enabled = get_bool_setting("USE_AGENTIC_RAG", False)
        if not extract_code_examples_enabled:
            return json.dumps({
                "success": False,
                "error": "Code example extraction is disabled. Perform a normal RAG search."
            }, indent=2)
        
        try:
            # Get the Supabase client from the context
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            # Check if hybrid search is enabled
            use_hybrid_search = get_bool_setting("USE_HYBRID_SEARCH", False)
            
            # Prepare filter if source is provided and not empty
            filter_metadata = None
            if source_id and source_id.strip():
                filter_metadata = {"source": source_id}  # Use "source" to match original
            
            if use_hybrid_search:
                # Hybrid search: combine vector and keyword search
                
                # Import the search function from utils
                from src.utils import search_code_examples as search_code_examples_impl
                
                # 1. Get vector search results (get more to account for filtering)
                vector_results = search_code_examples_impl(
                    client=supabase_client,
                    query=query,
                    match_count=match_count * 2,  # Get double to have room for filtering
                    filter_metadata=filter_metadata
                )
                
                # 2. Get keyword search results using ILIKE on both content and summary
                keyword_query = supabase_client.from_('code_examples')\
                    .select('id, url, chunk_number, content, summary, metadata, source_id')\
                    .or_(f'content.ilike.%{query}%,summary.ilike.%{query}%')
                
                # Apply source filter if provided
                if source_id and source_id.strip():
                    keyword_query = keyword_query.eq('source_id', source_id)
                
                # Execute keyword search
                keyword_response = keyword_query.limit(match_count * 2).execute()
                keyword_results = keyword_response.data if keyword_response.data else []
                
                # 3. Combine results with preference for items appearing in both
                seen_ids = set()
                combined_results = []
                
                # First, add items that appear in both searches (these are the best matches)
                vector_ids = {r.get('id') for r in vector_results if r.get('id')}
                for kr in keyword_results:
                    if kr['id'] in vector_ids and kr['id'] not in seen_ids:
                        # Find the vector result to get similarity score
                        for vr in vector_results:
                            if vr.get('id') == kr['id']:
                                # Boost similarity score for items in both results
                                vr['similarity'] = min(1.0, vr.get('similarity', 0) * 1.2)
                                combined_results.append(vr)
                                seen_ids.add(kr['id'])
                                break
                
                # Then add remaining vector results (semantic matches without exact keyword)
                for vr in vector_results:
                    if vr.get('id') and vr['id'] not in seen_ids and len(combined_results) < match_count:
                        combined_results.append(vr)
                        seen_ids.add(vr['id'])
                
                # Finally, add pure keyword matches if we still need more results
                for kr in keyword_results:
                    if kr['id'] not in seen_ids and len(combined_results) < match_count:
                        # Convert keyword result to match vector result format
                        combined_results.append({
                            'id': kr['id'],
                            'url': kr['url'],
                            'chunk_number': kr['chunk_number'],
                            'content': kr['content'],
                            'summary': kr['summary'],
                            'metadata': kr['metadata'],
                            'source_id': kr['source_id'],
                            'similarity': 0.5  # Default similarity for keyword-only matches
                        })
                        seen_ids.add(kr['id'])
                
                # Use combined results
                results = combined_results[:match_count]
                
            else:
                # Standard vector search only
                from src.utils import search_code_examples as search_code_examples_impl
                
                results = search_code_examples_impl(
                    client=supabase_client,
                    query=query,
                    match_count=match_count,
                    filter_metadata=filter_metadata
                )
            
            # Apply reranking if enabled
            use_reranking = get_bool_setting("USE_RERANKING", False)
            if use_reranking and ctx.request_context.lifespan_context.reranking_model:
                results = rerank_results(ctx.request_context.lifespan_context.reranking_model, query, results, content_key="content")
            
            # Format the results
            formatted_results = []
            for result in results:
                formatted_result = {
                    "url": result.get("url"),
                    "code": result.get("content"),
                    "summary": result.get("summary"),
                    "metadata": result.get("metadata"),
                    "source_id": result.get("source_id"),
                    "similarity": result.get("similarity")
                }
                # Include rerank score if available
                if "rerank_score" in result:
                    formatted_result["rerank_score"] = result["rerank_score"]
                formatted_results.append(formatted_result)
            
            return json.dumps({
                "success": True,
                "query": query,
                "source_filter": source_id,
                "search_mode": "hybrid" if use_hybrid_search else "vector",
                "reranking_applied": use_reranking and ctx.request_context.lifespan_context.reranking_model is not None,
                "results": formatted_results,
                "count": len(formatted_results)
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "success": False,
                "query": query,
                "error": str(e)
            }, indent=2)
    
    @mcp.tool()
    async def upload_document(ctx: Context,
        file_content: str, 
        filename: str, 
        knowledge_type: str = "technical", 
        tags: List[str] = [], 
        chunk_size: int = 5000
    ) -> str:
        """
        Upload and process a document for RAG.
        
        Takes document content and stores it in the knowledge base with proper chunking and embeddings.
        
        Args:
            file_content: The content of the document
            filename: Name of the file
            knowledge_type: Type of knowledge (default: "technical")
            tags: List of tags for the document
            chunk_size: Maximum size of each chunk (default: 5000)
        
        Returns:
            JSON string with upload results
        """
        try:
            # Get the Supabase client from the context
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            # Create a pseudo-URL for the uploaded document
            doc_url = f"upload://{filename}"
            
            # Chunk the content
            chunks = smart_chunk_markdown(file_content, chunk_size)
            
            # Create documents for storage
            documents = []
            total_word_count = 0
            
            for i, chunk in enumerate(chunks):
                section_info = extract_section_info(chunk)
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
            update_source_info(supabase_client, source_id, source_summary, total_word_count, file_content[:5000], knowledge_type, tags, 0)  # File uploads default to never update
            
            # Store in Supabase - prepare data for the function
            urls = [doc['url'] for doc in documents]
            chunk_numbers = [doc['chunk_index'] for doc in documents]  # Keep 0-based indexing like original
            contents = [doc['content'] for doc in documents]
            metadatas = [doc['metadata'] for doc in documents]
            url_to_full_document = {doc_url: file_content}  # Document upload mapping
            
            add_documents_to_supabase(
                client=supabase_client,
                urls=urls,
                chunk_numbers=chunk_numbers,
                contents=contents,
                metadatas=metadatas,
                url_to_full_document=url_to_full_document
            )
            chunks_stored = len(documents)
            
            return json.dumps({
                "success": True,
                "filename": filename,
                "chunks_stored": chunks_stored,
                "content_length": len(file_content),
                "total_word_count": total_word_count,
                "knowledge_type": knowledge_type,
                "tags": tags
            })
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error uploading document: {str(e)}"
            }) 

async def store_documents_with_progress(
    supabase_client, 
    urls: List[str], 
    chunk_numbers: List[int],
    contents: List[str], 
    metadatas: List[Dict[str, Any]],
    url_to_full_document: Dict[str, str],
    progress_callback=None,
    batch_size: int = 20
) -> None:
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
    
    await report_progress_internal(0, f'Deleting {len(unique_urls)} existing URL records...')
    
    # Delete existing records for these URLs in a single operation
    try:
        if unique_urls:
            supabase_client.table("crawled_pages").delete().in_("url", unique_urls).execute()
    except Exception as e:
        await report_progress_internal(0, f'Batch delete failed, using fallback: {str(e)[:50]}...')
        # Fallback: delete records one by one
        for i, url in enumerate(unique_urls):
            try:
                supabase_client.table("crawled_pages").delete().eq("url", url).execute()
                if i % 10 == 0:  # Progress every 10 deletions
                    await report_progress_internal(0 + (i / len(unique_urls)) * 5, f'Deleting records: {i+1}/{len(unique_urls)}')
            except Exception:
                pass  # Continue with next URL
    
    await report_progress_internal(5, 'Preparing document batches...')
    
    # Check if contextual embeddings are enabled
    use_contextual_embeddings = os.getenv("USE_CONTEXTUAL_EMBEDDINGS", "false") == "true"
    max_workers = int(os.getenv("CONTEXTUAL_EMBEDDINGS_MAX_WORKERS", "3"))
    
    # Process in batches to avoid memory issues
    total_batches = (len(contents) + batch_size - 1) // batch_size
    
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
        
        # Apply contextual embedding if enabled (sequential processing to avoid progress conflicts)
        if use_contextual_embeddings:
            current_progress += progress_per_batch * 0.1  # 10% of batch progress
            await report_progress_internal(current_progress, f'Applying contextual embeddings to batch {current_batch}...')
            # Process sequentially to maintain accurate progress reporting
            contextual_contents = []
            for j, content in enumerate(batch_contents):
                url = batch_urls[j]
                full_document = url_to_full_document.get(url, "")
                
                try:
                    result, success = process_chunk_with_context((url, content, full_document))
                    contextual_contents.append(result)
                    if success:
                        batch_metadatas[j]["contextual_embedding"] = True
                except Exception as e:
                    print(f"Error processing chunk {j}: {e}")
                    contextual_contents.append(content)
                
                # Report progress every 5 chunks within this 40% of batch progress
                if j % 5 == 0 or j == len(batch_contents) - 1:
                    chunk_progress = (j + 1) / len(batch_contents) * (progress_per_batch * 0.4)
                    await report_progress_internal(current_progress + chunk_progress, f'Processed {j+1}/{len(batch_contents)} contextual embeddings')
            
            current_progress += progress_per_batch * 0.4  # 40% of batch progress for contextual embeddings
        else:
            contextual_contents = batch_contents
            current_progress += progress_per_batch * 0.5  # Skip contextual processing, move to embeddings
        
        await report_progress_internal(current_progress, f'Creating embeddings for batch {current_batch}...')
        
        # Create embeddings for the entire batch at once - this is another slow operation
        from src.utils import create_embeddings_batch
        batch_embeddings = create_embeddings_batch(contextual_contents)
        
        current_progress += progress_per_batch * 0.2  # 20% of batch progress for embeddings
        await report_progress_internal(current_progress, f'Preparing batch {current_batch} for database insertion...')
        
        # Prepare batch data
        batch_data = []
        for j in range(len(contextual_contents)):
            from urllib.parse import urlparse
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
        await report_progress_internal(current_progress, f'Inserting batch {current_batch} into database...')
        
        # Insert batch into Supabase with retry logic
        max_retries = 3
        retry_delay = 1.0
        
        for retry in range(max_retries):
            try:
                supabase_client.table("crawled_pages").insert(batch_data).execute()
                break  # Success
            except Exception as e:
                if retry < max_retries - 1:
                    await report_progress_internal(current_progress, f'Retry {retry + 1}/{max_retries} for batch {current_batch}...')
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    # Final attempt failed, try individual inserts
                    await report_progress_internal(current_progress, f'Batch insert failed, trying individual records...')
                    successful_inserts = 0
                    for record in batch_data:
                        try:
                            supabase_client.table("crawled_pages").insert(record).execute()
                            successful_inserts += 1
                        except:
                            pass
                    
                    if successful_inserts == 0:
                        raise Exception(f"Failed to insert batch {current_batch}: {str(e)}")
        
        current_progress += progress_per_batch * 0.2  # 20% of batch progress for database insertion
        await report_progress_internal(current_progress, f'Completed batch {current_batch}/{total_batches}')
    
    await report_progress_internal(100, f'All {len(contents)} document chunks stored successfully') 
