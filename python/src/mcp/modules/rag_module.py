"""
RAG Module for Archon MCP Server (HTTP-based version)

This module provides tools for:
- Web crawling (single pages, smart crawling, recursive crawling)
- Document upload and processing
- RAG query and search
- Source management
- Code example extraction and search

This version uses HTTP calls to the server service instead of importing
service modules directly, enabling true microservices architecture.
"""

from mcp.server.fastmcp import FastMCP, Context
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import json
import logging
import os
from datetime import datetime

# Import the service client for HTTP communication
from src.server.services.mcp_service_client import get_mcp_service_client

# Import lightweight utilities only
from src.server.utils import get_supabase_client

# Import Logfire
from src.server.config.logfire_config import rag_logger, mcp_logger, search_logger

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


# Note: Old direct service functions removed - now using HTTP-based communication

def register_rag_tools(mcp: FastMCP):
    """
    Register all RAG-related tools with the MCP server.
    These tools now use HTTP calls to other services.
    """
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
        
        # Create a mock WebSocket that uses the progress callback
        class MockWebSocket:
            async def send_json(self, data):
                """Convert WebSocket messages to progress callback calls"""
                if progress_callback:
                    msg_type = data.get('type', '')
                    if msg_type == 'worker_progress':
                        # Don't send worker progress through main callback, it's handled separately
                        pass
                    elif msg_type == 'document_storage_progress':
                        # Pass the worker data through the progress callback
                        await progress_callback(
                            'document_storage',
                            data.get('percentage', 0),
                            data.get('message', ''),
                            completed_batches=data.get('completed_batches', 0),
                            total_batches=data.get('total_batches', 0),
                            workers=data.get('workers', []),
                            parallelWorkers=data.get('parallelWorkers', 0),
                            totalJobs=data.get('totalJobs', 0)
                        )
                    else:
                        # Generic progress
                        await progress_callback(
                            data.get('status', 'processing'),
                            data.get('percentage', 0),
                            data.get('message', '')
                        )
        
        # Create mock websocket if we have a progress callback
        websocket = MockWebSocket() if progress_callback else None
        
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
        # Source creation phase: 35-45% of overall progress
        await report_progress('source_creation', 35, f'Creating source records for {len(source_content_map)} sources...')
        
        for i, (source_id, content) in enumerate(source_content_map.items()):
            word_count = source_word_counts.get(source_id, 0)
            knowledge_metadata = getattr(ctx, 'knowledge_metadata', {})
            update_frequency = knowledge_metadata.get('update_frequency', 7)
            
            success, result = source_service.create_source_info(
                source_id, content, word_count, "technical", [], update_frequency
            )
            
            # Scale progress from 0-100% to 35-45%
            phase_progress = int((i + 1) / len(source_content_map) * 100)
            overall_progress = 35 + int(phase_progress * 0.1)  # 0.1 = 10% range / 100%
            await report_progress('source_creation', overall_progress, f'Created source {i+1}/{len(source_content_map)}: {source_id}')
        
        # Store documents with detailed progress reporting
        try:
            # Document storage phase: 45-90% of overall progress
            await report_progress('document_storage', 45, f'Preparing to store {len(all_documents)} chunks...')
            
            # Import the function we need
            from src.server.utils import add_documents_to_supabase_parallel
            
            # We'll call the function but add progress reporting around it
            # Since add_documents_to_supabase_parallel processes in batches, we can estimate progress
            batch_size = 15
            max_workers = int(os.getenv("CONTEXTUAL_EMBEDDINGS_MAX_WORKERS", "3"))
            total_batches = (len(all_documents) + batch_size - 1) // batch_size
            
            # Report that we're starting the storage
            await report_progress('document_storage', 47, f'Storing {len(all_documents)} chunks in {total_batches} batches with {max_workers} workers...')
            
            # Create a scaled progress callback for document storage
            async def scaled_document_storage_callback(status: str, percentage: int, message: str, **kwargs):
                # Scale the percentage from document storage (0-100) to overall progress (45-90)
                scaled_percentage = 45 + int((percentage / 100.0) * 45)  # 45% range
                await report_progress(status, scaled_percentage, message, **kwargs)
            
            # websocket is already created above as MockWebSocket
            
            # Call the parallel storage function with scaled progress callback and websocket
            await add_documents_to_supabase_parallel(
                client=storage_service.supabase_client,
                urls=urls,
                chunk_numbers=chunk_numbers,
                contents=contents,
                metadatas=metadatas,
                url_to_full_document=url_to_full_document,
                batch_size=batch_size,
                progress_callback=scaled_document_storage_callback,
                websocket=websocket,
                max_workers=max_workers
            )
            
            await report_progress('document_storage', 90, f'Successfully stored {len(all_documents)} document chunks')
        except Exception as e:
            error_msg = f"Failed to store documents: {str(e)}"
            await report_progress('error', 0, error_msg)
            raise Exception(error_msg)
            
        chunks_stored = len(all_documents)
        
        # Process and store code examples as a separate step
        code_examples_stored = 0
        if all_code_examples and get_bool_setting("USE_AGENTIC_RAG", False):
            # Code storage phase: 90-99% of overall progress
            await report_progress('code_storage', 90, f'Processing {len(all_code_examples)} code examples...')
            
            # Generate summaries for code examples with progress
            for i, example in enumerate(all_code_examples):
                # Generate summary for this code example
                example['summary'] = storage_service.process_code_example(example['code_block'])
                
                # Report progress every 5 examples or at the end
                if (i + 1) % 5 == 0 or i == len(all_code_examples) - 1:
                    # Scale progress from 0-70% to 90-96%
                    phase_progress = int((i + 1) / len(all_code_examples) * 70)
                    overall_progress = 90 + int(phase_progress * 0.086)  # 0.086 = 6% range / 70%
                    await report_progress('code_storage', overall_progress, f'Processed {i+1}/{len(all_code_examples)} code summaries')
            
            # Now store the code examples
            await report_progress('code_storage', 96, f'Storing {len(all_code_examples)} code examples in database...')
            
            success, result = storage_service.store_code_examples(all_code_examples)
            if success:
                code_examples_stored = result.get("code_examples_stored", 0)
                await report_progress('code_storage', 99, f'Successfully stored {code_examples_stored} code examples')
            else:
                await report_progress('code_storage', 99, f'Failed to store code examples: {result.get("error", "Unknown error")}')
        
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
    async def crawl_single_page(ctx: Context, url: str, chunk_size: int = 5000) -> str:
        """
        Crawl a single web page and store its content.
        
        This tool delegates to the API service via HTTP.
        
        Args:
            url: The URL to crawl
            chunk_size: Maximum size of each content chunk (default: 5000 characters)
        
        Returns:
            JSON string with success status and metadata
        """
        client = get_mcp_service_client()
        rag_logger.info(f"Crawling single page via HTTP: {url}")
        
        result = await client.crawl_url(
            url,
            options={
                "max_depth": 1,
                "chunk_size": chunk_size,
                "smart_crawl": False
            }
        )
        
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    async def smart_crawl_url(ctx: Context, url: str, max_depth: int = 3, chunk_size: int = 5000) -> str:
        """
        Intelligently crawl a URL based on its type (sitemap, text file, or webpage).
        
        This tool delegates to the API service via HTTP.
        
        Args:
            url: The URL to crawl
            max_depth: Maximum crawl depth for recursive crawling (default: 3)
            chunk_size: Maximum size of each content chunk (default: 5000 characters)
        
        Returns:
            JSON string with crawl results
        """
        client = get_mcp_service_client()
        rag_logger.info(f"Smart crawling via HTTP: {url}")
        
        result = await client.crawl_url(
            url,
            options={
                "max_depth": max_depth,
                "chunk_size": chunk_size,
                "smart_crawl": True
            }
        )
        
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    async def get_available_sources(ctx: Context) -> str:
        """
        Get list of available sources in the knowledge base.
        
        This tool uses direct database access for simple read operations.
        
        Returns:
            JSON string with list of sources
        """
        try:
            supabase_client = get_supabase_client()
            
            # Get unique sources from documents table
            response = supabase_client.table("documents").select("source").execute()
            
            if response.data:
                # Extract unique sources
                sources = list(set(doc["source"] for doc in response.data if doc.get("source")))
                sources.sort()
                
                return json.dumps({
                    "success": True,
                    "sources": sources,
                    "count": len(sources)
                }, indent=2)
            else:
                return json.dumps({
                    "success": True,
                    "sources": [],
                    "count": 0
                }, indent=2)
                
        except Exception as e:
            search_logger.error(f"Error getting sources: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
    
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
        client = get_mcp_service_client()
        rag_logger.info(f"Performing RAG query via HTTP: {query}")
        
        # Check if reranking is enabled
        use_reranking = get_bool_setting("USE_RERANKING", False)
        
        result = await client.search(
            query,
            source_filter=source,
            match_count=match_count,
            use_reranking=use_reranking
        )
        
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    async def delete_source(ctx: Context, source: str) -> str:
        """
        Delete all documents from a specific source.
        
        This tool uses direct database access for simple operations.
        
        Args:
            source: The source domain to delete
        
        Returns:
            JSON string with deletion results
        """
        try:
            supabase_client = get_supabase_client()
            
            # Delete documents from the source
            response = supabase_client.table("documents").delete().eq("source", source).execute()
            
            return json.dumps({
                "success": True,
                "source": source,
                "message": f"Deleted all documents from source: {source}"
            }, indent=2)
            
        except Exception as e:
            search_logger.error(f"Error deleting source: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2)
    
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
        # For now, use the same search endpoint with enhanced query
        client = get_mcp_service_client()
        search_logger.info(f"Searching code examples via HTTP: {query}")
        
        result = await client.search(
            f"code example {query}",  # Enhance query for code search
            source_filter=source_id,
            match_count=match_count,
            use_reranking=True  # Code search benefits from reranking
        )
        
        return json.dumps(result, indent=2)
    
    @mcp.tool()
    async def upload_document(ctx: Context, filename: str, content: str, doc_type: str = "general") -> str:
        """
        Upload a document's content to the knowledge base.
        
        This tool delegates to the API service via HTTP.
        
        Args:
            filename: Name of the document
            content: Document content as text
            doc_type: Type of document (general, technical, business)
        
        Returns:
            JSON string with upload results
        """
        client = get_mcp_service_client()
        rag_logger.info(f"Uploading document via HTTP: {filename}")
        
        # Prepare document for storage
        document = {
            "content": content,
            "metadata": {
                "filename": filename,
                "doc_type": doc_type,
                "source": "upload",
                "upload_timestamp": str(datetime.now())
            }
        }
        
        result = await client.store_documents([document])
        
        return json.dumps(result, indent=2)

    # Log successful registration
    mcp_logger.info("✓ RAG tools registered (HTTP-based version)")