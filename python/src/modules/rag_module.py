"""
RAG Module for Archon MCP Server

This module provides tools for:
- Web crawling (single pages, smart crawling, recursive crawling)
- Document upload and processing
- RAG query and search
- Source management
- Code example extraction and search

All tools in this module work with web content and document storage/retrieval.

Refactored to use service-based architecture for better maintainability.
"""

from mcp.server.fastmcp import FastMCP, Context
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import json
import logging
import os

# Import services
from ..services.rag.crawling_service import CrawlingService
from ..services.rag.document_storage_service import DocumentStorageService
from ..services.rag.search_service import SearchService
from ..services.rag.source_management_service import SourceManagementService

# Import utils
from src.utils import (
    get_supabase_client,
    update_source_info,
    extract_source_summary
)

# Import utils for code processing
from src.utils import (
    extract_code_blocks,
    generate_code_example_summary
)

# Import Logfire
from ..logfire_config import rag_logger, mcp_logger, search_logger

logger = logging.getLogger(__name__)


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


async def smart_crawl_url_direct(ctx, url: str, max_depth: int = 3, max_concurrent: int = 10, chunk_size: int = 5000) -> str:
    """
    Standalone function for smart crawling that can be imported directly.
    
    Intelligently crawl a URL based on its type (sitemap, text file, or webpage).
    """
    try:
        crawler = ctx.request_context.lifespan_context.crawler
        supabase_client = ctx.request_context.lifespan_context.supabase_client
        reranking_model = getattr(ctx.request_context.lifespan_context, 'reranking_model', None)
        
        # Initialize services
        crawling_service = CrawlingService(crawler, supabase_client)
        storage_service = DocumentStorageService(supabase_client)
        source_service = SourceManagementService(supabase_client)
        
        # Get progress callback if available
        progress_callback = getattr(ctx, 'progress_callback', None)
        
        async def report_progress(status: str, percentage: int, message: str, **kwargs):
            """Helper to report progress if callback available"""
            if progress_callback:
                step_info = {
                    'currentStep': status,
                    'stepMessage': message,
                    **kwargs
                }
                await progress_callback(status, percentage, message, **step_info)
        
        await report_progress('analyzing', 2, f'Analyzing URL type: {url}')
        
        # Determine crawl strategy based on URL type
        if crawling_service.is_sitemap(url):
            await report_progress('sitemap', 4, 'Detected sitemap, extracting URLs...')
            
            # Parse sitemap and get URLs
            urls = crawling_service.parse_sitemap(url)
            if not urls:
                return json.dumps({
                    "success": False,
                    "error": "Failed to extract URLs from sitemap"
                })
            
            await report_progress('sitemap', 6, f'Found {len(urls)} URLs in sitemap')
            
            # Batch crawl the sitemap URLs
            results = await crawling_service.crawl_batch_with_progress(
                urls, max_concurrent, progress_callback, 6, 22
            )
            crawl_type = "sitemap"
            
        elif crawling_service.is_txt(url):
            await report_progress('text_file', 4, 'Detected text file, downloading...')
            
            # Crawl the text file directly
            results = await crawling_service.crawl_markdown_file(url)
            crawl_type = "text_file"
            
            await report_progress('text_file', 22, f'Downloaded text file: {len(results)} file processed')
            
        else:
            await report_progress('webpage', 4, 'Detected webpage, starting recursive crawl...')
            
            # Recursive crawling for regular webpages
            results = await crawling_service.crawl_recursive_with_progress(
                [url], max_depth, max_concurrent, progress_callback, 4, 22
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
            chunks = storage_service.smart_chunk_markdown(markdown_content, chunk_size)
            
            # Process each chunk
            for j, chunk in enumerate(chunks):
                section_info = storage_service.extract_section_info(chunk)
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
            
            # Extract code blocks (but don't process summaries yet)
            if get_bool_setting("USE_AGENTIC_RAG", False):
                code_blocks = extract_code_blocks(markdown_content)
                if code_blocks:
                    # Just collect the code blocks for now
                    for code_block in code_blocks:
                        all_code_examples.append({
                            'code_block': code_block,
                            'summary': None,  # Will generate later
                            'url': page_url
                        })
            
            # Report progress during processing
            progress_pct = 24 + int((i + 1) / len(results) * 6)  # 24-30%
            await report_progress('processing', progress_pct, f'Processed {i + 1}/{len(results)} pages')
        
        await report_progress('storing', 30, 'Storing content in database...')
        
        # Prepare data for Supabase insertion
        urls = [doc['url'] for doc in all_documents]
        chunk_numbers = [doc['chunk_index'] for doc in all_documents]
        contents = [doc['content'] for doc in all_documents]
        metadatas = [doc['metadata'] for doc in all_documents]
        url_to_full_document = {}
        
        # Build url_to_full_document mapping from results
        for page_result in results:
            url_to_full_document[page_result['url']] = page_result['markdown']
        
        await report_progress('storing', 35, 'Preparing source information...')
        
        # Track sources and their content for source info creation
        source_content_map = {}
        source_word_counts = {}
        
        # Calculate word counts per source
        for doc in all_documents:
            source_id = doc['metadata']['source']
            word_count = doc['metadata']['word_count']
            
            if source_id not in source_word_counts:
                source_word_counts[source_id] = 0
                # Store content for summary generation
                for page_result in results:
                    if urlparse(page_result['url']).netloc == source_id:
                        source_content_map[source_id] = page_result['markdown'][:5000]
                        break
            
            source_word_counts[source_id] += word_count
        
        # Create source records FIRST
        await report_progress('source_creation', 0, f'Creating source records for {len(source_content_map)} sources...')
        
        for i, (source_id, content) in enumerate(source_content_map.items()):
            word_count = source_word_counts.get(source_id, 0)
            knowledge_metadata = getattr(ctx, 'knowledge_metadata', {})
            update_frequency = knowledge_metadata.get('update_frequency', 7)
            
            success, result = source_service.create_source_info(
                source_id, content, word_count, "technical", [], update_frequency
            )
            
            progress_pct = int((i + 1) / len(source_content_map) * 100)
            await report_progress('source_creation', progress_pct, f'Created source {i+1}/{len(source_content_map)}: {source_id}')
        
        # Store documents with detailed progress reporting
        try:
            await report_progress('document_storage', 0, f'Preparing to store {len(all_documents)} chunks...')
            
            # Import the function we need
            from src.utils import add_documents_to_supabase
            
            # We'll call the function but add progress reporting around it
            # Since add_documents_to_supabase processes in batches, we can estimate progress
            batch_size = 15
            total_batches = (len(all_documents) + batch_size - 1) // batch_size
            
            # Report that we're starting the storage
            await report_progress('document_storage', 10, f'Storing {len(all_documents)} chunks in {total_batches} batches...')
            
            # Call the storage function with progress callback
            await add_documents_to_supabase(
                client=storage_service.supabase_client,
                urls=urls,
                chunk_numbers=chunk_numbers,
                contents=contents,
                metadatas=metadatas,
                url_to_full_document=url_to_full_document,
                batch_size=batch_size,
                progress_callback=progress_callback
            )
            
            await report_progress('document_storage', 100, f'Successfully stored {len(all_documents)} document chunks')
        except Exception as e:
            error_msg = f"Failed to store documents: {str(e)}"
            await report_progress('error', 0, error_msg)
            raise Exception(error_msg)
            
        chunks_stored = len(all_documents)
        
        # Process and store code examples as a separate step
        code_examples_stored = 0
        if all_code_examples and get_bool_setting("USE_AGENTIC_RAG", False):
            await report_progress('code_storage', 0, f'Processing {len(all_code_examples)} code examples...')
            
            # Generate summaries for code examples with progress
            for i, example in enumerate(all_code_examples):
                # Generate summary for this code example
                example['summary'] = storage_service.process_code_example(example['code_block'])
                
                # Report progress every 5 examples or at the end
                if (i + 1) % 5 == 0 or i == len(all_code_examples) - 1:
                    progress_pct = int((i + 1) / len(all_code_examples) * 70)  # 0-70% for processing
                    await report_progress('code_storage', progress_pct, f'Processed {i+1}/{len(all_code_examples)} code summaries')
            
            # Now store the code examples
            await report_progress('code_storage', 70, f'Storing {len(all_code_examples)} code examples in database...')
            
            success, result = storage_service.store_code_examples(all_code_examples)
            if success:
                code_examples_stored = result.get("code_examples_stored", 0)
                await report_progress('code_storage', 100, f'Successfully stored {code_examples_stored} code examples')
            else:
                await report_progress('code_storage', 100, f'Failed to store code examples: {result.get("error", "Unknown error")}')
        
        # Finalization
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


async def delete_source_standalone(ctx, source_id: str) -> str:
    """
    Delete a source and all associated crawled pages and code examples from the database.
    """
    try:
        supabase_client = ctx.request_context.lifespan_context.supabase_client
        source_service = SourceManagementService(supabase_client)
        
        success, result = source_service.delete_source(source_id)
        return json.dumps({"success": success, **result})
        
    except Exception as e:
        logger.error(f"Error in delete_source_standalone: {e}")
        return json.dumps({
            "success": False,
            "error": f"Error deleting source: {str(e)}"
        })


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
            # Get services
            crawler = ctx.request_context.lifespan_context.crawler
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            crawling_service = CrawlingService(crawler, supabase_client)
            storage_service = DocumentStorageService(supabase_client)
            source_service = SourceManagementService(supabase_client)
            
            # Crawl the page
            result = await crawling_service.crawl_single_page(url)
            
            if not result["success"]:
                return json.dumps(result)
            
            # Process the content
            markdown_content = result["markdown"]
            chunks = storage_service.smart_chunk_markdown(markdown_content, chunk_size=5000)
            
            # Create documents for Supabase
            documents = []
            total_word_count = 0
            
            for i, chunk in enumerate(chunks):
                section_info = storage_service.extract_section_info(chunk)
                total_word_count += section_info["word_count"]
                
                documents.append({
                    "content": chunk,
                    "url": url,
                    "chunk_index": i,
                    "metadata": {
                        "source_id": urlparse(url).netloc,
                        "title": result.get("title", "Untitled"),
                        "headers": section_info["headers"],
                        "char_count": section_info["char_count"],
                        "word_count": section_info["word_count"]
                    }
                })
            
            # Create source info
            source_id = urlparse(url).netloc
            success, source_result = source_service.create_source_info(
                source_id, markdown_content[:5000], total_word_count, "technical", [], 0
            )
            
            # Store documents
            urls = [doc['url'] for doc in documents]
            chunk_numbers = [doc['chunk_index'] for doc in documents]
            contents = [doc['content'] for doc in documents]
            metadatas = [doc['metadata'] for doc in documents]
            url_to_full_document = {url: markdown_content}
            
            # Use the original working function from utils.py with proper parallel processing
            from src.utils import add_documents_to_supabase
            await add_documents_to_supabase(
                client=storage_service.supabase_client,
                urls=urls,
                chunk_numbers=chunk_numbers,
                contents=contents,
                metadatas=metadatas,
                url_to_full_document=url_to_full_document,
                batch_size=15,
                progress_callback=None  # No progress callback for single page crawl
            )
            chunks_stored = len(documents)
            
            # Process code examples if enabled
            code_examples_stored = 0
            if get_bool_setting("USE_AGENTIC_RAG", False):
                code_blocks = extract_code_blocks(markdown_content)
                if code_blocks:
                    code_examples = []
                    for i, code_block in enumerate(code_blocks):
                        summary = storage_service.process_code_example(code_block)
                        code_examples.append({
                            'code_block': code_block,
                            'summary': summary,
                            'url': url
                        })
                    
                    success, code_result = storage_service.store_code_examples(code_examples)
                    if success:
                        code_examples_stored = code_result.get("code_examples_stored", 0)
            
            return json.dumps({
                "success": True,
                "url": url,
                "chunks_stored": chunks_stored,
                "code_examples_stored": code_examples_stored,
                "content_length": len(markdown_content),
                "total_word_count": total_word_count,
                "source_id": source_id,
                "links_count": {
                    "internal": len(result.get("links", {}).get("internal", [])),
                    "external": len(result.get("links", {}).get("external", []))
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
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            source_service = SourceManagementService(supabase_client)
            
            success, result = source_service.get_available_sources()
            return json.dumps({"success": success, **result})
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error retrieving sources: {str(e)}"
            })
    
    @mcp.tool()
    async def perform_rag_query(ctx: Context, query: str, source: str = None, match_count: int = 5) -> str:
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
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            reranking_model = getattr(ctx.request_context.lifespan_context, 'reranking_model', None)
            
            search_service = SearchService(supabase_client, reranking_model)
            
            success, result = search_service.perform_rag_query(query, source, match_count)
            return json.dumps({"success": success, **result}, indent=2)
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "query": query,
                "source": source,
                "execution_path": "mcp_vector_search"
            }, indent=2)
    
    @mcp.tool()
    async def delete_source(ctx: Context, source_id: str) -> str:
        """
        Delete a source and all associated crawled pages and code examples from the database.
        
        Args:
            source_id: The source ID to delete
        
        Returns:
            JSON string with deletion results
        """
        return await delete_source_standalone(ctx, source_id)
    
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
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            reranking_model = getattr(ctx.request_context.lifespan_context, 'reranking_model', None)
            
            search_service = SearchService(supabase_client, reranking_model)
            
            success, result = search_service.search_code_examples_service(query, source_id, match_count)
            return json.dumps({"success": success, **result}, indent=2)
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "query": query,
                "error": str(e)
            }, indent=2)
    
    @mcp.tool()
    async def upload_document(ctx: Context, file_content: str, filename: str, 
                             knowledge_type: str = "technical", tags: List[str] = [], 
                             chunk_size: int = 5000) -> str:
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
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            storage_service = DocumentStorageService(supabase_client)
            
            success, result = await storage_service.upload_document(
                file_content, filename, knowledge_type, tags, chunk_size
            )
            
            return json.dumps({"success": success, **result})
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error uploading document: {str(e)}"
            })

    logger.info("✓ RAG Module registered with 7 refactored tools")