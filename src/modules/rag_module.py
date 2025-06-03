"""
RAG Module for Archon MCP Server

This module provides tools for:
- Web crawling (single pages, smart crawling, recursive crawling)
- Document upload and processing
- RAG query and search
- Source management
- Code example extraction and search

All tools in this module work with web content and document storage/retrieval.
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

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, MemoryAdaptiveDispatcher

from src.utils import (
    add_documents_to_supabase, 
    search_documents,
    extract_code_blocks,
    generate_code_example_summary,
    add_code_examples_to_supabase,
    update_source_info,
    extract_source_summary,
    search_code_examples
)


def rerank_results(model: CrossEncoder, query: str, results: List[Dict[str, Any]], content_key: str = "content") -> List[Dict[str, Any]]:
    """
    Rerank search results using a cross-encoder model for improved relevance.
    
    This function takes search results from vector/keyword search and re-scores them
    using a cross-encoder model that directly compares the query with each result.
    Cross-encoders typically provide better relevance scoring than bi-encoders used
    in vector search, at the cost of higher computational requirements.
    
    The function adds a 'rerank_score' field to each result and sorts by this score.
    
    Args:
        model: The cross-encoder model to use for reranking (e.g., ms-marco-MiniLM)
        query: The search query to compare against
        results: List of search results, each containing at least the content_key field
        content_key: The key in each result dict that contains the text content
        
    Returns:
        Reranked list of results sorted by relevance (highest score first)
        
    Note:
        - Falls back gracefully to original results if reranking fails
        - Preserves all original fields in results
        - Adds 'rerank_score' field with float values
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
    """Check if a URL is a sitemap."""
    return url.endswith('sitemap.xml') or 'sitemap' in urlparse(url).path


def is_txt(url: str) -> bool:
    """Check if a URL is a text file."""
    return url.endswith('.txt')


def parse_sitemap(sitemap_url: str) -> List[str]:
    """Parse a sitemap and extract URLs."""
    resp = requests.get(sitemap_url)
    urls = []

    if resp.status_code == 200:
        try:
            tree = ElementTree.fromstring(resp.content)
            urls = [loc.text for loc in tree.findall('.//{*}loc')]
        except Exception as e:
            print(f"Error parsing sitemap XML: {e}")

    return urls


def smart_chunk_markdown(text: str, chunk_size: int = 5000) -> List[str]:
    """
    Split text into chunks intelligently, respecting code blocks and paragraphs.
    
    This function implements a context-aware chunking strategy that:
    1. Preserves code blocks (```) as complete units when possible
    2. Prefers to break at paragraph boundaries (\\n\\n)
    3. Falls back to sentence boundaries (. ) if needed
    4. Only splits mid-content when absolutely necessary
    
    The algorithm ensures that important semantic units like code examples
    remain intact, improving the quality of RAG retrieval.
    
    Args:
        text: The markdown text to chunk
        chunk_size: Maximum size of each chunk in characters (default: 5000)
        
    Returns:
        List of text chunks, each no larger than chunk_size
    """
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        # Calculate end position
        end = start + chunk_size

        # If we're at the end of the text, just take what's left
        if end >= text_length:
            chunks.append(text[start:].strip())
            break

        # Try to find a code block boundary first (```)
        chunk = text[start:end]
        code_block = chunk.rfind('```')
        if code_block != -1 and code_block > chunk_size * 0.3:
            end = start + code_block

        # If no code block, try to break at a paragraph
        elif '\n\n' in chunk:
            # Find the last paragraph break
            last_break = chunk.rfind('\n\n')
            if last_break > chunk_size * 0.3:  # Only break if we're past 30% of chunk_size
                end = start + last_break

        # If no paragraph break, try to break at a sentence
        elif '. ' in chunk:
            # Find the last sentence break
            last_period = chunk.rfind('. ')
            if last_period > chunk_size * 0.3:  # Only break if we're past 30% of chunk_size
                end = start + last_period + 1

        # Extract chunk and clean it up
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start position for next chunk
        start = end

    return chunks


def extract_section_info(chunk: str) -> Dict[str, Any]:
    """Extracts headers and stats from a chunk."""
    headers = re.findall(r'^(#+)\s+(.+)$', chunk, re.MULTILINE)
    header_str = '; '.join([f'{h[0]} {h[1]}' for h in headers]) if headers else ''

    return {
        "headers": header_str,
        "char_count": len(chunk),
        "word_count": len(chunk.split())
    }


def process_code_example(args):
    """Process a single code example to generate its summary."""
    code, context_before, context_after = args
    return generate_code_example_summary(code, context_before, context_after)


# Helper functions for crawling
async def crawl_markdown_file(crawler: AsyncWebCrawler, url: str) -> List[Dict[str, Any]]:
    """Crawl a .txt or markdown file."""
    crawl_config = CrawlerRunConfig()

    result = await crawler.arun(url=url, config=crawl_config)
    if result.success and result.markdown:
        return [{'url': url, 'markdown': result.markdown}]
    else:
        print(f"Failed to crawl {url}: {result.error_message}")
        return []


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
            await progress_callback('crawling', percentage, message, **kwargs)

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
                await progress_callback(status, percentage, message, **kwargs)
        
        await report_progress('analyzing', 5, f'Analyzing URL type: {url}')
        
        # Determine crawl strategy based on URL type
        if is_sitemap(url):
            await report_progress('sitemap', 10, 'Detected sitemap, extracting URLs...')
            
            # Parse sitemap and get URLs
            urls = parse_sitemap(url)
            if not urls:
                return json.dumps({
                    "success": False,
                    "error": "Failed to extract URLs from sitemap"
                })
            
            await report_progress('sitemap', 15, f'Found {len(urls)} URLs in sitemap')
            
            # Batch crawl the sitemap URLs
            results = await crawl_batch_with_progress(
                crawler, urls, max_concurrent, progress_callback, 15, 60
            )
            crawl_type = "sitemap"
            
        elif is_txt(url):
            await report_progress('text_file', 10, 'Detected text file, downloading...')
            
            # Crawl the text file directly
            results = await crawl_markdown_file(crawler, url)
            crawl_type = "text_file"
            
            await report_progress('text_file', 60, f'Downloaded text file: {len(results)} file processed')
            
        else:
            await report_progress('webpage', 10, 'Detected webpage, starting recursive crawl...')
            
            # Recursive crawling for regular webpages
            results = await crawl_recursive_with_progress(
                crawler, [url], max_depth, max_concurrent, progress_callback, 10, 60
            )
            crawl_type = "webpage"
        
        if not results:
            return json.dumps({
                "success": False,
                "error": "No content retrieved from crawling"
            })
        
        await report_progress('processing', 65, f'Processing {len(results)} pages into chunks...')
        
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
                    "source_id": urlparse(page_url).netloc,
                    "title": f"Page {i+1} from {crawl_type}",
                    "headers": section_info["headers"],
                    "char_count": section_info["char_count"],
                    "word_count": section_info["word_count"],
                    "crawl_type": crawl_type,
                    "source_type": "url",
                    **knowledge_metadata  # Add any additional metadata from context
                }
                
                all_documents.append({
                    "content": chunk,
                    "url": page_url,
                    "chunk_index": j,
                    "metadata": document_metadata
                })
            
            # Extract code examples if enabled
            if os.getenv("USE_AGENTIC_RAG", "false") == "true":
                code_blocks = extract_code_blocks(markdown_content)
                if code_blocks:
                    # Process code examples in parallel
                    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                        code_summaries = list(executor.map(process_code_example, code_blocks))
                    
                    for code_block, summary in zip(code_blocks, code_summaries):
                        all_code_examples.append({
                            'code_block': code_block,
                            'summary': summary,
                            'url': page_url
                        })
            
            # Report progress during processing
            progress_pct = 65 + int((i + 1) / len(results) * 15)  # 65-80%
            await report_progress('processing', progress_pct, f'Processed {i + 1}/{len(results)} pages')
        
        await report_progress('storing', 80, 'Storing content in database...')
        
        # Store documents in Supabase
        chunks_stored = await add_documents_to_supabase(supabase_client, all_documents)
        
        # Store code examples if any
        code_examples_stored = 0
        if all_code_examples:
            code_examples_stored = await add_code_examples_to_supabase(
                supabase_client, 
                [ex['code_block'] for ex in all_code_examples],
                [ex['summary'] for ex in all_code_examples],
                url  # Use the original URL as source
            )
        
        await report_progress('storing', 90, 'Updating source information...')
        
        # Update source information
        source_id = urlparse(url).netloc
        source_summary = f"Crawled via {crawl_type}: {len(results)} pages processed"
        
        await update_source_info(supabase_client, source_id, source_summary)
        
        await report_progress('completed', 100, f'Successfully crawled {len(results)} pages with {chunks_stored} chunks stored')
        
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
        supabase_client = ctx.request_context.lifespan_context.supabase_client
        
        # Delete from crawled_pages table
        pages_response = supabase_client.table("crawled_pages").delete().eq("source_id", source_id).execute()
        pages_deleted = len(pages_response.data) if pages_response.data else 0
        
        # Delete from code_examples table
        code_response = supabase_client.table("code_examples").delete().eq("source_id", source_id).execute()
        code_deleted = len(code_response.data) if code_response.data else 0
        
        # Delete from sources table
        source_response = supabase_client.table("sources").delete().eq("source_id", source_id).execute()
        source_deleted = len(source_response.data) if source_response.data else 0
        
        return json.dumps({
            "success": True,
            "source_id": source_id,
            "pages_deleted": pages_deleted,
            "code_examples_deleted": code_deleted,
            "source_records_deleted": source_deleted
        })
        
    except Exception as e:
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
            ctx: The MCP server provided context containing crawler and database clients
            url: URL of the web page to crawl (must be a valid HTTP/HTTPS URL)
        
        Returns:
            JSON string with the operation results including success status, content metrics, and any errors
        """
        try:
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
            
            # Store in Supabase
            chunks_stored = await add_documents_to_supabase(supabase_client, documents)
            
            # Process code examples if enabled
            code_examples_stored = 0
            if os.getenv("USE_AGENTIC_RAG", "false") == "true":
                code_blocks = extract_code_blocks(markdown_content)
                if code_blocks:
                    # Process code examples in parallel
                    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                        code_summaries = list(executor.map(process_code_example, code_blocks))
                    
                    code_examples_stored = await add_code_examples_to_supabase(
                        supabase_client, code_blocks, code_summaries, url
                    )
            
            # Update source information
            await update_source_info(
                supabase_client,
                urlparse(url).netloc,
                extract_source_summary(result.title or "Untitled", markdown_content[:500])
            )
            
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
            ctx: The MCP server provided context
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
        
        Args:
            ctx: The MCP server provided context
        
        Returns:
            JSON string with list of sources and their metadata
        """
        try:
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
    async def perform_rag_query(ctx: Context, query: str, source: str = None, match_count: int = 5) -> str:
        """
        Perform a RAG (Retrieval Augmented Generation) query on stored content.
        
        Searches the vector database for content relevant to the query.
        
        Args:
            ctx: The MCP server provided context
            query: The search query
            source: Optional source domain to filter results
            match_count: Maximum number of results to return (default: 5)
        
        Returns:
            JSON string with search results and metadata
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            reranking_model = ctx.request_context.lifespan_context.reranking_model
            
            # Perform the search
            results = await search_documents(
                supabase_client, 
                query, 
                source_filter=source, 
                match_count=match_count
            )
            
            # Apply reranking if available
            if reranking_model and results:
                results = rerank_results(reranking_model, query, results, "content")
            
            return json.dumps({
                "success": True,
                "query": query,
                "source_filter": source,
                "results": results,
                "count": len(results)
            })
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error performing RAG query: {str(e)}"
            })
    
    @mcp.tool()
    async def delete_source_tool(ctx: Context, source_id: str) -> str:
        """
        Delete a source and all associated crawled pages and code examples from the database.
        
        Args:
            ctx: The MCP server provided context
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
        
        Searches the vector database for code examples with their summaries.
        
        Args:
            ctx: The MCP server provided context
            query: The search query
            source_id: Optional source ID to filter results
            match_count: Maximum number of results to return (default: 5)
        
        Returns:
            JSON string with search results
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            results = await search_code_examples(
                supabase_client,
                query,
                source_id=source_id,
                match_count=match_count
            )
            
            return json.dumps({
                "success": True,
                "query": query,
                "source_filter": source_id,
                "results": results,
                "count": len(results)
            })
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error searching code examples: {str(e)}"
            })
    
    @mcp.tool()
    async def upload_document(
        ctx: Context, 
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
            ctx: The MCP server provided context
            file_content: The content of the document
            filename: Name of the file
            knowledge_type: Type of knowledge (default: "technical")
            tags: List of tags for the document
            chunk_size: Maximum size of each chunk (default: 5000)
        
        Returns:
            JSON string with upload results
        """
        try:
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
            
            # Store in Supabase
            chunks_stored = await add_documents_to_supabase(supabase_client, documents)
            
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