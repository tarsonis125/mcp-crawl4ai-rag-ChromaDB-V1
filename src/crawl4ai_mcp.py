"""
MCP (Model Context Protocol) server for web crawling with Crawl4AI.

This server provides tools to crawl websites using Crawl4AI, automatically detecting
the appropriate crawl method based on URL type (sitemap, txt file, or regular webpage).

The server supports two transport modes:
- SSE (Server-Sent Events): For web-based integrations and dashboard control
- stdio: For standard MCP clients like Cursor, Claude Desktop, etc.

Key Features:
- Intelligent URL detection (sitemaps, text files, regular pages)
- Recursive crawling with depth control
- Smart content chunking preserving code blocks and paragraphs
- Vector database storage with Supabase pgvector
- Advanced RAG strategies (contextual embeddings, hybrid search, reranking)
- Code example extraction and summarization (when enabled)
- Source management and organization

Environment Variables:
- TRANSPORT: Transport mode ('sse' or 'stdio'), defaults to 'sse'
- HOST: Server host address, defaults to 'localhost'
- PORT: Server port number, defaults to 8051
- OPENAI_API_KEY: OpenAI API key for embeddings
- SUPABASE_URL: Supabase project URL
- SUPABASE_SERVICE_KEY: Supabase service key
- MODEL_CHOICE: OpenAI model for embeddings, defaults to 'gpt-4o-mini'
- USE_CONTEXTUAL_EMBEDDINGS: Enable contextual embeddings (true/false)
- USE_HYBRID_SEARCH: Enable hybrid search combining vector and keyword (true/false)
- USE_AGENTIC_RAG: Enable code example extraction (true/false)
- USE_RERANKING: Enable result reranking with cross-encoder (true/false)
"""
from mcp.server.fastmcp import FastMCP, Context
from sentence_transformers import CrossEncoder
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urldefrag
from xml.etree import ElementTree
from dotenv import load_dotenv
from supabase import Client
from pathlib import Path
import requests
import asyncio
import json
import os
import re
import sys
import concurrent.futures

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, MemoryAdaptiveDispatcher

# Add the project root to Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils import (
    get_supabase_client, 
    add_documents_to_supabase, 
    search_documents,
    extract_code_blocks,
    generate_code_example_summary,
    add_code_examples_to_supabase,
    update_source_info,
    extract_source_summary,
    search_code_examples
)

# Load environment variables from the project root .env file
project_root = Path(__file__).resolve().parent.parent
dotenv_path = project_root / '.env'

# Force override of existing environment variables
load_dotenv(dotenv_path, override=True)

# Create a dataclass for our application context
@dataclass
class Crawl4AIContext:
    """
    Context for the Crawl4AI MCP server.
    
    This context holds all the necessary resources for the MCP server to operate:
    - AsyncWebCrawler instance for web crawling operations
    - Supabase client for database operations
    - Optional reranking model for improving search results
    
    The context is managed by the FastMCP lifespan and is available to all MCP tools.
    """
    crawler: AsyncWebCrawler
    supabase_client: Client
    reranking_model: Optional[CrossEncoder] = None

@asynccontextmanager
async def crawl4ai_lifespan(server: FastMCP) -> AsyncIterator[Crawl4AIContext]:
    """
    Manages the Crawl4AI client lifecycle.
    
    This context manager handles the initialization and cleanup of resources:
    1. Creates and initializes the AsyncWebCrawler with headless browser
    2. Establishes connection to Supabase database
    3. Optionally loads the cross-encoder model for reranking
    4. Ensures proper cleanup when the server shuts down
    
    The resources are made available to all MCP tools through the context.
    
    Args:
        server: The FastMCP server instance
        
    Yields:
        Crawl4AIContext: The context containing the Crawl4AI crawler and Supabase client
        
    Environment Dependencies:
        - SUPABASE_URL: Must be set for database connection
        - SUPABASE_SERVICE_KEY: Must be set for database authentication
        - USE_RERANKING: If 'true', loads the cross-encoder model
    """
    # Create browser configuration
    browser_config = BrowserConfig(
        headless=True,
        verbose=False
    )
    
    # Initialize the crawler
    crawler = AsyncWebCrawler(config=browser_config)
    await crawler.__aenter__()
    
    # Initialize Supabase client
    supabase_client = get_supabase_client()
    
    # Initialize cross-encoder model for reranking if enabled
    reranking_model = None
    if os.getenv("USE_RERANKING", "false") == "true":
        try:
            reranking_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception as e:
            print(f"Failed to load reranking model: {e}")
            reranking_model = None
    
    try:
        yield Crawl4AIContext(
            crawler=crawler,
            supabase_client=supabase_client,
            reranking_model=reranking_model
        )
    finally:
        # Clean up the crawler
        await crawler.__aexit__(None, None, None)

# Initialize FastMCP server
mcp = FastMCP(
    "mcp-crawl4ai-rag",
    description="MCP server for RAG and web crawling with Crawl4AI",
    lifespan=crawl4ai_lifespan,
    host=os.getenv("HOST", "0.0.0.0"),
    port=os.getenv("PORT", "8051")
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
    """
    Check if a URL is a sitemap.
    
    Args:
        url: URL to check
        
    Returns:
        True if the URL is a sitemap, False otherwise
    """
    return url.endswith('sitemap.xml') or 'sitemap' in urlparse(url).path

def is_txt(url: str) -> bool:
    """
    Check if a URL is a text file.
    
    Args:
        url: URL to check
        
    Returns:
        True if the URL is a text file, False otherwise
    """
    return url.endswith('.txt')

def parse_sitemap(sitemap_url: str) -> List[str]:
    """
    Parse a sitemap and extract URLs.
    
    Args:
        sitemap_url: URL of the sitemap
        
    Returns:
        List of URLs found in the sitemap
    """
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
        
    Algorithm:
        1. Start from position 0
        2. Look ahead chunk_size characters
        3. Search backwards for the best split point:
           - First priority: Code block boundary (```)
           - Second priority: Paragraph break (\\n\\n)
           - Third priority: Sentence end (. )
        4. Only use the split point if it's after 30% of chunk_size
        5. Clean up and store the chunk
        6. Move to the next position and repeat
        
    Example:
        >>> text = "# Title\\n\\nParagraph 1.\\n\\n```python\\ncode\\n```\\n\\nParagraph 2."
        >>> chunks = smart_chunk_markdown(text, chunk_size=50)
        >>> len(chunks) == 2  # Split preserves code block
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

def process_code_example(args):
    """
    Process a single code example to generate its summary.
    This function is designed to be used with concurrent.futures.
    
    Args:
        args: Tuple containing (code, context_before, context_after)
        
    Returns:
        The generated summary
    """
    code, context_before, context_after = args
    return generate_code_example_summary(code, context_before, context_after)

@mcp.tool()
async def crawl_single_page(ctx: Context, url: str) -> str:
    """
    Crawl a single web page and store its content in Supabase.
    
    This tool is ideal for quickly retrieving content from a specific URL without following links.
    The content is stored in Supabase for later retrieval and querying.
    
    The tool performs the following operations:
    1. Crawls the specified URL using a headless browser
    2. Extracts and converts content to markdown format
    3. Chunks the content intelligently preserving structure
    4. Generates embeddings for each chunk (using OpenAI)
    5. Stores chunks in Supabase with vector embeddings
    6. Updates source metadata with title and summary
    7. Optionally extracts and processes code examples
    
    Args:
        ctx: The MCP server provided context containing crawler and database clients
        url: URL of the web page to crawl (must be a valid HTTP/HTTPS URL)
    
    Returns:
        JSON string with the operation results including:
        - success: Boolean indicating if crawl succeeded
        - url: The crawled URL
        - chunks_stored: Number of content chunks created
        - code_examples_stored: Number of code examples extracted (if enabled)
        - content_length: Total characters in the crawled content
        - total_word_count: Total word count across all chunks
        - source_id: The domain/source identifier
        - links_count: Count of internal and external links found
        - error: Error message if crawl failed
        
    Example Response:
        {
            "success": true,
            "url": "https://docs.example.com/guide",
            "chunks_stored": 5,
            "code_examples_stored": 3,
            "content_length": 15000,
            "total_word_count": 2500,
            "source_id": "docs.example.com",
            "links_count": {
                "internal": 10,
                "external": 5
            }
        }
        
    Notes:
        - Uses CacheMode.BYPASS to always fetch fresh content
        - Automatically extracts source_id from URL domain
        - Respects USE_AGENTIC_RAG env var for code extraction
        - All database operations are transactional
    """
    try:
        # Get the crawler from the context
        crawler = ctx.request_context.lifespan_context.crawler
        supabase_client = ctx.request_context.lifespan_context.supabase_client
        
        # Configure the crawl
        run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, stream=False)
        
        # Crawl the page
        result = await crawler.arun(url=url, config=run_config)
        
        if result.success and result.markdown:
            # Extract source_id
            parsed_url = urlparse(url)
            source_id = parsed_url.netloc or parsed_url.path
            
            # Chunk the content
            chunks = smart_chunk_markdown(result.markdown)
            
            # Prepare data for Supabase
            urls = []
            chunk_numbers = []
            contents = []
            metadatas = []
            total_word_count = 0
            
            for i, chunk in enumerate(chunks):
                urls.append(url)
                chunk_numbers.append(i)
                contents.append(chunk)
                
                # Extract metadata
                meta = extract_section_info(chunk)
                meta["chunk_index"] = i
                meta["url"] = url
                meta["source"] = source_id
                meta["crawl_time"] = str(asyncio.current_task().get_coro().__name__)
                metadatas.append(meta)
                
                # Accumulate word count
                total_word_count += meta.get("word_count", 0)
            
            # Create url_to_full_document mapping
            url_to_full_document = {url: result.markdown}
            
            # Extract metadata from context if available
            knowledge_type = "technical"
            tags = []
            if hasattr(ctx, 'knowledge_metadata'):
                knowledge_type = ctx.knowledge_metadata.get('knowledge_type', 'technical')
                tags = ctx.knowledge_metadata.get('tags', [])
            
            # Update source information FIRST (before inserting documents)
            source_summary = extract_source_summary(source_id, result.markdown[:5000])  # Use first 5000 chars for summary
            update_source_info(supabase_client, source_id, source_summary, total_word_count, result.markdown, knowledge_type, tags)
            
            # Add documentation chunks to Supabase (AFTER source exists)
            add_documents_to_supabase(supabase_client, urls, chunk_numbers, contents, metadatas, url_to_full_document)
            
            # Extract and process code examples only if enabled
            extract_code_examples = os.getenv("USE_AGENTIC_RAG", "false") == "true"
            if extract_code_examples:
                code_blocks = extract_code_blocks(result.markdown)
                if code_blocks:
                    code_urls = []
                    code_chunk_numbers = []
                    code_examples = []
                    code_summaries = []
                    code_metadatas = []
                    
                    # Process code examples in parallel
                    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                        # Prepare arguments for parallel processing
                        summary_args = [(block['code'], block['context_before'], block['context_after']) 
                                        for block in code_blocks]
                        
                        # Generate summaries in parallel
                        summaries = list(executor.map(process_code_example, summary_args))
                    
                    # Prepare code example data
                    for i, (block, summary) in enumerate(zip(code_blocks, summaries)):
                        code_urls.append(url)
                        code_chunk_numbers.append(i)
                        code_examples.append(block['code'])
                        code_summaries.append(summary)
                        
                        # Create metadata for code example
                        code_meta = {
                            "chunk_index": i,
                            "url": url,
                            "source": source_id,
                            "char_count": len(block['code']),
                            "word_count": len(block['code'].split())
                        }
                        code_metadatas.append(code_meta)
                    
                    # Add code examples to Supabase
                    add_code_examples_to_supabase(
                        supabase_client, 
                        code_urls, 
                        code_chunk_numbers, 
                        code_examples, 
                        code_summaries, 
                        code_metadatas
                    )
            
            return json.dumps({
                "success": True,
                "url": url,
                "chunks_stored": len(chunks),
                "code_examples_stored": len(code_blocks) if code_blocks else 0,
                "content_length": len(result.markdown),
                "total_word_count": total_word_count,
                "source_id": source_id,
                "links_count": {
                    "internal": len(result.links.get("internal", [])),
                    "external": len(result.links.get("external", []))
                }
            }, indent=2)
        else:
            return json.dumps({
                "success": False,
                "url": url,
                "error": result.error_message
            }, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "url": url,
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def smart_crawl_url(ctx: Context, url: str, max_depth: int = 3, max_concurrent: int = 10, chunk_size: int = 5000) -> str:
    """
    Intelligently crawl a URL based on its type and store content in Supabase.
    
    This tool automatically detects the URL type and applies the appropriate crawling method:
    - For sitemaps: Extracts and crawls all URLs in parallel
    - For text files (llms.txt): Directly retrieves the content
    - For regular webpages: Recursively crawls internal links up to the specified depth
    
    All crawled content is chunked and stored in Supabase for later retrieval and querying.
    
    Args:
        ctx: The MCP server provided context
        url: URL to crawl (can be a regular webpage, sitemap.xml, or .txt file)
        max_depth: Maximum recursion depth for regular URLs (default: 3)
        max_concurrent: Maximum number of concurrent browser sessions (default: 10)
        chunk_size: Maximum size of each content chunk in characters (default: 1000)
    
    Returns:
        JSON string with crawl summary and storage information
    """
    try:
        # Get the crawler from the context
        crawler = ctx.request_context.lifespan_context.crawler
        supabase_client = ctx.request_context.lifespan_context.supabase_client
        
        # Determine the crawl strategy
        crawl_results = []
        crawl_type = None
        
        if is_txt(url):
            # For text files, use simple crawl
            crawl_results = await crawl_markdown_file(crawler, url)
            crawl_type = "text_file"
        elif is_sitemap(url):
            # For sitemaps, extract URLs and crawl in parallel
            sitemap_urls = parse_sitemap(url)
            if not sitemap_urls:
                return json.dumps({
                    "success": False,
                    "url": url,
                    "error": "No URLs found in sitemap"
                }, indent=2)
            crawl_results = await crawl_batch(crawler, sitemap_urls, max_concurrent=max_concurrent)
            crawl_type = "sitemap"
        else:
            # For regular URLs, use recursive crawl
            crawl_results = await crawl_recursive_internal_links(crawler, [url], max_depth=max_depth, max_concurrent=max_concurrent)
            crawl_type = "webpage"
        
        if not crawl_results:
            return json.dumps({
                "success": False,
                "url": url,
                "error": "No content found"
            }, indent=2)
        
        # Process results and store in Supabase
        urls = []
        chunk_numbers = []
        contents = []
        metadatas = []
        chunk_count = 0
        
        # Track sources and their content
        source_content_map = {}
        source_word_counts = {}
        
        # Process documentation chunks
        for doc in crawl_results:
            source_url = doc['url']
            md = doc['markdown']
            chunks = smart_chunk_markdown(md, chunk_size=chunk_size)
            
            # Extract source_id
            parsed_url = urlparse(source_url)
            source_id = parsed_url.netloc or parsed_url.path
            
            # Store content for source summary generation
            if source_id not in source_content_map:
                source_content_map[source_id] = md[:5000]  # Store first 5000 chars
                source_word_counts[source_id] = 0
            
            for i, chunk in enumerate(chunks):
                urls.append(source_url)
                chunk_numbers.append(i)
                contents.append(chunk)
                
                # Extract metadata
                meta = extract_section_info(chunk)
                meta["chunk_index"] = i
                meta["url"] = source_url
                meta["source"] = source_id
                meta["crawl_type"] = crawl_type
                meta["crawl_time"] = str(asyncio.current_task().get_coro().__name__)
                metadatas.append(meta)
                
                # Accumulate word count
                source_word_counts[source_id] += meta.get("word_count", 0)
                
                chunk_count += 1
        
        # Create url_to_full_document mapping
        url_to_full_document = {}
        for doc in crawl_results:
            url_to_full_document[doc['url']] = doc['markdown']
        
        # Update source information for each unique source FIRST (before inserting documents)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            source_summary_args = [(source_id, content) for source_id, content in source_content_map.items()]
            source_summaries = list(executor.map(lambda args: extract_source_summary(args[0], args[1]), source_summary_args))
        
        # Extract metadata from context if available
        knowledge_type = "technical"
        tags = []
        if hasattr(ctx, 'knowledge_metadata'):
            knowledge_type = ctx.knowledge_metadata.get('knowledge_type', 'technical')
            tags = ctx.knowledge_metadata.get('tags', [])
        
        for (source_id, content), summary in zip(source_summary_args, source_summaries):
            word_count = source_word_counts.get(source_id, 0)
            update_source_info(supabase_client, source_id, summary, word_count, content, knowledge_type, tags)
        
        # Add documentation chunks to Supabase (AFTER sources exist)
        batch_size = 20
        add_documents_to_supabase(supabase_client, urls, chunk_numbers, contents, metadatas, url_to_full_document, batch_size=batch_size)
        
        # Extract and process code examples from all documents only if enabled
        extract_code_examples_enabled = os.getenv("USE_AGENTIC_RAG", "false") == "true"
        code_examples = []  # Initialize empty list
        if extract_code_examples_enabled:
            all_code_blocks = []
            code_urls = []
            code_chunk_numbers = []
            code_examples = []
            code_summaries = []
            code_metadatas = []
            
            # Extract code blocks from all documents
            for doc in crawl_results:
                source_url = doc['url']
                md = doc['markdown']
                code_blocks = extract_code_blocks(md)
                
                if code_blocks:
                    # Process code examples in parallel
                    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                        # Prepare arguments for parallel processing
                        summary_args = [(block['code'], block['context_before'], block['context_after']) 
                                        for block in code_blocks]
                        
                        # Generate summaries in parallel
                        summaries = list(executor.map(process_code_example, summary_args))
                    
                    # Prepare code example data
                    parsed_url = urlparse(source_url)
                    source_id = parsed_url.netloc or parsed_url.path
                    
                    for i, (block, summary) in enumerate(zip(code_blocks, summaries)):
                        code_urls.append(source_url)
                        code_chunk_numbers.append(len(code_examples))  # Use global code example index
                        code_examples.append(block['code'])
                        code_summaries.append(summary)
                        
                        # Create metadata for code example
                        code_meta = {
                            "chunk_index": len(code_examples) - 1,
                            "url": source_url,
                            "source": source_id,
                            "char_count": len(block['code']),
                            "word_count": len(block['code'].split())
                        }
                        code_metadatas.append(code_meta)
            
            # Add all code examples to Supabase
            if code_examples:
                add_code_examples_to_supabase(
                    supabase_client, 
                    code_urls, 
                    code_chunk_numbers, 
                    code_examples, 
                    code_summaries, 
                    code_metadatas,
                    batch_size=batch_size
                )
        
        return json.dumps({
            "success": True,
            "url": url,
            "crawl_type": crawl_type,
            "pages_crawled": len(crawl_results),
            "chunks_stored": chunk_count,
            "code_examples_stored": len(code_examples) if 'code_examples' in locals() else 0,
            "sources_updated": len(source_content_map),
            "urls_crawled": [doc['url'] for doc in crawl_results][:5] + (["..."] if len(crawl_results) > 5 else [])
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "url": url,
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def get_available_sources(ctx: Context) -> str:
    """
    Get all available sources from the sources table.
    
    This tool returns a list of all unique sources (domains) that have been crawled and stored
    in the database, along with their summaries and statistics. This is useful for discovering 
    what content is available for querying.

    Always use this tool before calling the RAG query or code example query tool
    with a specific source filter!
    
    Args:
        ctx: The MCP server provided context
    
    Returns:
        JSON string with the list of available sources and their details
    """
    try:
        # Get the Supabase client from the context
        supabase_client = ctx.request_context.lifespan_context.supabase_client
        
        # Query the sources table directly
        result = supabase_client.from_('sources')\
            .select('*')\
            .order('source_id')\
            .execute()
        
        # Format the sources with their details
        sources = []
        if result.data:
            for source in result.data:
                sources.append({
                    "source_id": source.get("source_id"),
                    "title": source.get("title", source.get("summary", "Untitled")),
                    "summary": source.get("summary"),
                    "metadata": source.get("metadata", {}),
                    "total_words": source.get("total_word_count", 0),
                    "created_at": source.get("created_at"),
                    "updated_at": source.get("updated_at")
                })
        
        return json.dumps({
            "success": True,
            "sources": sources,
            "count": len(sources)
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def perform_rag_query(ctx: Context, query: str, source: str = None, match_count: int = 5) -> str:
    """
    Perform a RAG (Retrieval Augmented Generation) query on the stored content.
    
    This tool searches the vector database for content relevant to the query and returns
    the matching documents. Optionally filter by source domain.
    Get the source by using the get_available_sources tool before calling this search!
    
    Args:
        ctx: The MCP server provided context
        query: The search query
        source: Optional source domain to filter results (e.g., 'example.com')
        match_count: Maximum number of results to return (default: 5)
    
    Returns:
        JSON string with the search results
    """
    try:
        # Get the Supabase client from the context
        supabase_client = ctx.request_context.lifespan_context.supabase_client
        
        # Check if hybrid search is enabled
        use_hybrid_search = os.getenv("USE_HYBRID_SEARCH", "false") == "true"
        
        # Prepare filter if source is provided and not empty
        filter_metadata = None
        if source and source.strip():
            filter_metadata = {"source": source}
        
        if use_hybrid_search:
            # Hybrid search: combine vector and keyword search
            
            # 1. Get vector search results (get more to account for filtering)
            vector_results = search_documents(
                client=supabase_client,
                query=query,
                match_count=match_count * 2,  # Get double to have room for filtering
                filter_metadata=filter_metadata
            )
            
            # 2. Get keyword search results using ILIKE
            keyword_query = supabase_client.from_('crawled_pages')\
                .select('id, url, chunk_number, content, metadata, source_id')\
                .ilike('content', f'%{query}%')
            
            # Apply source filter if provided
            if source and source.strip():
                keyword_query = keyword_query.eq('source_id', source)
            
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
                        'metadata': kr['metadata'],
                        'source_id': kr['source_id'],
                        'similarity': 0.5  # Default similarity for keyword-only matches
                    })
                    seen_ids.add(kr['id'])
            
            # Use combined results
            results = combined_results[:match_count]
            
        else:
            # Standard vector search only
            results = search_documents(
                client=supabase_client,
                query=query,
                match_count=match_count,
                filter_metadata=filter_metadata
            )
        
        # Apply reranking if enabled
        use_reranking = os.getenv("USE_RERANKING", "false") == "true"
        if use_reranking and ctx.request_context.lifespan_context.reranking_model:
            results = rerank_results(ctx.request_context.lifespan_context.reranking_model, query, results, content_key="content")
        
        # Format the results
        formatted_results = []
        for result in results:
            formatted_result = {
                "url": result.get("url"),
                "content": result.get("content"),
                "metadata": result.get("metadata"),
                "similarity": result.get("similarity")
            }
            # Include rerank score if available
            if "rerank_score" in result:
                formatted_result["rerank_score"] = result["rerank_score"]
            formatted_results.append(formatted_result)
        
        return json.dumps({
            "success": True,
            "query": query,
            "source_filter": source,
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
async def delete_source(ctx: Context, source_id: str) -> str:
    """
    Delete a source and all associated crawled pages and code examples.
    
    Args:
        source_id: The source ID to delete
        
    Returns:
        JSON string with success status and details
    """
    try:
        context = ctx.state
        supabase = context.supabase_client
        
        # Delete all crawled pages for this source
        pages_result = supabase.table("crawled_pages").delete().eq("source_id", source_id).execute()
        
        # Delete all code examples for this source
        examples_result = supabase.table("code_examples").delete().eq("source_id", source_id).execute()
        
        # Delete the source itself
        source_result = supabase.table("sources").delete().eq("source_id", source_id).execute()
        
        return json.dumps({
            "success": True,
            "source_id": source_id,
            "message": f"Source {source_id} and all associated content deleted successfully",
            "deleted": {
                "pages": len(pages_result.data) if pages_result.data else 0,
                "examples": len(examples_result.data) if examples_result.data else 0,
                "source": len(source_result.data) if source_result.data else 0
            }
        })
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to delete source: {str(e)}"
        })


@mcp.tool()
async def search_code_examples(ctx: Context, query: str, source_id: str = None, match_count: int = 5) -> str:
    """
    Search for code examples relevant to the query.
    
    This tool searches the vector database for code examples relevant to the query and returns
    the matching examples with their summaries. Optionally filter by source_id.
    Get the source_id by using the get_available_sources tool before calling this search!

    Use the get_available_sources tool first to see what sources are available for filtering.
    
    Args:
        ctx: The MCP server provided context
        query: The search query
        source_id: Optional source ID to filter results (e.g., 'example.com')
        match_count: Maximum number of results to return (default: 5)
    
    Returns:
        JSON string with the search results
    """
    # Check if code example extraction is enabled
    extract_code_examples_enabled = os.getenv("USE_AGENTIC_RAG", "false") == "true"
    if not extract_code_examples_enabled:
        return json.dumps({
            "success": False,
            "error": "Code example extraction is disabled. Perform a normal RAG search."
        }, indent=2)
    
    try:
        # Get the Supabase client from the context
        supabase_client = ctx.request_context.lifespan_context.supabase_client
        
        # Check if hybrid search is enabled
        use_hybrid_search = os.getenv("USE_HYBRID_SEARCH", "false") == "true"
        
        # Prepare filter if source is provided and not empty
        filter_metadata = None
        if source_id and source_id.strip():
            filter_metadata = {"source": source_id}
        
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
        use_reranking = os.getenv("USE_RERANKING", "false") == "true"
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
async def upload_document(
    ctx: Context, 
    file_content: str, 
    filename: str, 
    knowledge_type: str = "technical", 
    tags: List[str] = [], 
    chunk_size: int = 5000
) -> str:
    """
    Upload and process a document to add it to the knowledge base.
    
    This tool processes uploaded documents (PDF, DOC, MD, TXT) and adds them to the knowledge base.
    It extracts text content, chunks it appropriately, generates embeddings, and stores everything
    in the Supabase database with proper metadata and AI-generated titles/descriptions.
    
    Supported formats:
    - PDF (.pdf): Extracted using PyPDF2 and pdfplumber
    - Word Documents (.doc, .docx): Extracted using python-docx 
    - Markdown (.md): Processed directly
    - Text (.txt): Processed directly
    
    The document is processed similar to web crawling:
    - Text is chunked preserving structure (paragraphs, code blocks)
    - Embeddings are generated for each chunk
    - AI-generated title and description are created
    - Code examples are extracted if Agentic RAG is enabled
    - All chunks are stored with proper metadata
    
    Args:
        ctx: The MCP server provided context
        file_content: Base64 encoded file content or raw text content  
        filename: Original filename with extension
        knowledge_type: Type of knowledge ("technical" or "business")
        tags: List of tags to associate with the document
        chunk_size: Size of each text chunk (default: 5000)
    
    Returns:
        JSON string with upload results including success status, chunks created, and metadata
    """
    try:
        import base64
        import tempfile
        import os
        from pathlib import Path
        
        # Import document processing libraries
        try:
            import PyPDF2
            import pdfplumber
            from docx import Document as DocxDocument
        except ImportError as e:
            return json.dumps({
                "success": False,
                "error": f"Missing document processing library: {e}. Please install required dependencies."
            }, indent=2)
        
        # Get the Supabase client from the context
        supabase_client = ctx.request_context.lifespan_context.supabase_client
        
        # Determine file type from extension
        file_ext = Path(filename).suffix.lower()
        supported_extensions = {'.pdf', '.doc', '.docx', '.md', '.txt'}
        
        if file_ext not in supported_extensions:
            return json.dumps({
                "success": False,
                "error": f"Unsupported file type: {file_ext}. Supported: {', '.join(supported_extensions)}"
            }, indent=2)
        
        # Extract text content based on file type
        text_content = ""
        
        if file_ext in ['.md', '.txt']:
            # For text files, assume file_content is already text
            if file_content.startswith('data:') or len(file_content) % 4 == 0:
                try:
                    # Try to decode as base64 first
                    decoded_content = base64.b64decode(file_content)
                    text_content = decoded_content.decode('utf-8')
                except:
                    # Fallback to treating as raw text
                    text_content = file_content
            else:
                text_content = file_content
                
        else:
            # For binary files, decode base64 and process with appropriate library
            try:
                file_data = base64.b64decode(file_content)
            except Exception as e:
                return json.dumps({
                    "success": False,
                    "error": f"Failed to decode file content: {e}"
                }, indent=2)
            
            # Create temporary file for processing
            with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as temp_file:
                temp_file.write(file_data)
                temp_file_path = temp_file.name
            
            try:
                if file_ext == '.pdf':
                    # Extract text from PDF using both PyPDF2 and pdfplumber for best results
                    text_parts = []
                    
                    # Try pdfplumber first (better for complex layouts)
                    try:
                        with pdfplumber.open(temp_file_path) as pdf:
                            for page in pdf.pages:
                                text = page.extract_text()
                                if text:
                                    text_parts.append(text)
                    except Exception as plumber_error:
                        print(f"pdfplumber failed: {plumber_error}, trying PyPDF2")
                        
                        # Fallback to PyPDF2
                        with open(temp_file_path, 'rb') as pdf_file:
                            pdf_reader = PyPDF2.PdfReader(pdf_file)
                            for page in pdf_reader.pages:
                                text = page.extract_text()
                                if text:
                                    text_parts.append(text)
                    
                    text_content = '\n\n'.join(text_parts)
                    
                elif file_ext in ['.doc', '.docx']:
                    # Extract text from Word document
                    doc = DocxDocument(temp_file_path)
                    text_parts = []
                    for paragraph in doc.paragraphs:
                        if paragraph.text.strip():
                            text_parts.append(paragraph.text)
                    text_content = '\n\n'.join(text_parts)
                    
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
        
        # Validate extracted content
        if not text_content.strip():
            return json.dumps({
                "success": False,
                "error": "No text content could be extracted from the document"
            }, indent=2)
        
        # Generate document URL (use file:// scheme for uploaded documents)
        document_url = f"file://{filename}"
        
        # Generate AI title and description for the document
        try:
            # Get credentials from database for OpenAI API
            from src.credential_service import get_credential_value
            
            openai_api_key = await get_credential_value("OPENAI_API_KEY", decrypt=True)
            if not openai_api_key:
                raise Exception("OpenAI API key not found in credentials")
            
            # Generate title and description using OpenAI
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            
            # Prepare content sample for AI analysis (first 2000 chars)
            content_sample = text_content[:2000] + ("..." if len(text_content) > 2000 else "")
            
            title_prompt = f"""Based on this document content, generate a clear, descriptive title (max 100 characters):

{content_sample}

Title:"""
            
            title_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": title_prompt}],
                max_tokens=50,
                temperature=0.3
            )
            
            ai_title = title_response.choices[0].message.content.strip()
            if len(ai_title) > 100:
                ai_title = ai_title[:97] + "..."
            
            description_prompt = f"""Based on this document content, generate a helpful 2-3 sentence description:

{content_sample}

Description:"""
            
            description_response = client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[{"role": "user", "content": description_prompt}],
                max_tokens=150,
                temperature=0.3
            )
            
            ai_description = description_response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Failed to generate AI title/description: {e}")
            # Fallback to filename-based title
            ai_title = Path(filename).stem.replace('_', ' ').replace('-', ' ').title()
            ai_description = f"Uploaded document: {filename}"
        
        # Chunk the text content
        chunks = smart_chunk_markdown(text_content, chunk_size)
        
        # Calculate document stats
        word_count = len(text_content.split())
        chunk_count = len(chunks)
        
        # Prepare metadata for storage
        base_metadata = {
            'knowledge_type': knowledge_type,
            'tags': tags,
            'source_type': 'file',
            'file_name': filename,
            'file_type': file_ext,
            'word_count': word_count,
            'chunks_count': chunk_count,
            'upload_date': None,  # Will be set by database
            'title': ai_title,
            'description': ai_description
        }
        
        # Get metadata from context if available
        context_metadata = getattr(ctx, 'knowledge_metadata', {})
        base_metadata.update(context_metadata)
        
        # Prepare data for batch insertion
        urls = [document_url] * len(chunks)
        chunk_numbers = list(range(1, len(chunks) + 1))
        contents = chunks
        metadatas = [base_metadata.copy() for _ in chunks]
        
        # Add chunk-specific metadata
        for i, metadata in enumerate(metadatas):
            chunk_content = contents[i]
            section_info = extract_section_info(chunk_content)
            metadata.update(section_info)
            metadata['chunk_index'] = i + 1
            metadata['total_chunks'] = len(chunks)
        
        # Create URL to full document mapping for contextual embeddings
        url_to_full_document = {document_url: text_content}
        
        # First, create/update source information to ensure it exists
        source_id = urlparse(document_url).netloc or Path(filename).stem
        try:
            update_source_info(
                client=supabase_client,
                source_id=source_id,
                summary=ai_description,
                word_count=word_count,
                content=text_content[:500],  # First 500 chars as preview
                knowledge_type=knowledge_type,
                tags=tags
            )
        except Exception as e:
            print(f"Failed to update source info: {e}")
            return json.dumps({
                "success": False,
                "filename": filename,
                "error": f"Failed to create source entry: {e}"
            }, indent=2)
        
        # Store document chunks in Supabase
        add_documents_to_supabase(
            client=supabase_client,
            urls=urls,
            chunk_numbers=chunk_numbers,
            contents=contents,
            metadatas=metadatas,
            url_to_full_document=url_to_full_document
        )
        
        # Extract and store code examples if Agentic RAG is enabled
        code_examples_count = 0
        if os.getenv("USE_AGENTIC_RAG", "false") == "true":
            try:
                all_code_examples = []
                
                # Process code examples in parallel
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    future_to_chunk = {
                        executor.submit(process_code_example, (document_url, chunk, i + 1)): i 
                        for i, chunk in enumerate(chunks)
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_chunk):
                        try:
                            code_examples = future.result()
                            if code_examples:
                                all_code_examples.extend(code_examples)
                        except Exception as e:
                            print(f"Error processing code examples: {e}")
                
                # Store code examples if any were found
                if all_code_examples:
                    add_code_examples_to_supabase(supabase_client, all_code_examples)
                    code_examples_count = len(all_code_examples)
                    
            except Exception as e:
                print(f"Error in code example extraction: {e}")
        
        return json.dumps({
            "success": True,
            "filename": filename,
            "title": ai_title,
            "description": ai_description,
            "source_id": source_id,
            "chunks_created": chunk_count,
            "word_count": word_count,
            "code_examples_extracted": code_examples_count,
            "knowledge_type": knowledge_type,
            "tags": tags,
            "file_type": file_ext,
            "message": f"Successfully uploaded and processed {filename}"
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "filename": filename,
            "error": str(e)
        }, indent=2)

async def crawl_markdown_file(crawler: AsyncWebCrawler, url: str) -> List[Dict[str, Any]]:
    """
    Crawl a .txt or markdown file.
    
    Args:
        crawler: AsyncWebCrawler instance
        url: URL of the file
        
    Returns:
        List of dictionaries with URL and markdown content
    """
    crawl_config = CrawlerRunConfig()

    result = await crawler.arun(url=url, config=crawl_config)
    if result.success and result.markdown:
        return [{'url': url, 'markdown': result.markdown}]
    else:
        print(f"Failed to crawl {url}: {result.error_message}")
        return []

async def crawl_batch(crawler: AsyncWebCrawler, urls: List[str], max_concurrent: int = 10) -> List[Dict[str, Any]]:
    """
    Batch crawl multiple URLs in parallel.
    
    Args:
        crawler: AsyncWebCrawler instance
        urls: List of URLs to crawl
        max_concurrent: Maximum number of concurrent browser sessions
        
    Returns:
        List of dictionaries with URL and markdown content
    """
    crawl_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, stream=False)
    dispatcher = MemoryAdaptiveDispatcher(
        memory_threshold_percent=70.0,
        check_interval=1.0,
        max_session_permit=max_concurrent
    )

    results = await crawler.arun_many(urls=urls, config=crawl_config, dispatcher=dispatcher)
    return [{'url': r.url, 'markdown': r.markdown} for r in results if r.success and r.markdown]

async def crawl_recursive_internal_links(crawler: AsyncWebCrawler, start_urls: List[str], max_depth: int = 3, max_concurrent: int = 10) -> List[Dict[str, Any]]:
    """
    Recursively crawl internal links from start URLs up to a maximum depth.
    
    Args:
        crawler: AsyncWebCrawler instance
        start_urls: List of starting URLs
        max_depth: Maximum recursion depth
        max_concurrent: Maximum number of concurrent browser sessions
        
    Returns:
        List of dictionaries with URL and markdown content
    """
    run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, stream=False)
    dispatcher = MemoryAdaptiveDispatcher(
        memory_threshold_percent=70.0,
        check_interval=1.0,
        max_session_permit=max_concurrent
    )

    visited = set()

    def normalize_url(url):
        return urldefrag(url)[0]

    current_urls = set([normalize_url(u) for u in start_urls])
    results_all = []

    for depth in range(max_depth):
        urls_to_crawl = [normalize_url(url) for url in current_urls if normalize_url(url) not in visited]
        if not urls_to_crawl:
            break

        results = await crawler.arun_many(urls=urls_to_crawl, config=run_config, dispatcher=dispatcher)
        next_level_urls = set()

        for result in results:
            norm_url = normalize_url(result.url)
            visited.add(norm_url)

            if result.success and result.markdown:
                results_all.append({'url': result.url, 'markdown': result.markdown})
                for link in result.links.get("internal", []):
                    next_url = normalize_url(link["href"])
                    if next_url not in visited:
                        next_level_urls.add(next_url)

        current_urls = next_level_urls

    return results_all

async def main():
    transport = os.getenv("TRANSPORT", "sse")
    host = os.getenv("HOST", "localhost")
    port = int(os.getenv("PORT", "8051"))
    
    print(f"Starting MCP server with transport: {transport}")
    
    if transport == 'sse':
        # Run the MCP server with SSE transport (host/port already set in FastMCP constructor)
        print(f"SSE server will be available at: http://{host}:{port}/sse")
        await mcp.run_sse_async()
    elif transport == 'stdio':
        # Run the MCP server with stdio transport
        print("Stdio server ready for MCP client connections")
        await mcp.run_stdio_async()
    else:
        raise ValueError(f"Unsupported transport: {transport}. Use 'sse' or 'stdio'")

if __name__ == "__main__":
    asyncio.run(main())