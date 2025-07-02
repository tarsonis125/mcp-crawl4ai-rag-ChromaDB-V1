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
import httpx

# Import the service client for HTTP communication
from src.server.services.mcp_service_client import get_mcp_service_client

# MCP should use HTTP calls only - no direct database access
# from src.server.utils import get_supabase_client

logger = logging.getLogger(__name__)


def get_setting(key: str, default: str = "false") -> str:
    """Get a setting from the credential service or fall back to environment variable."""
    try:
        # MCP should not access credential service directly
        # from src.server.services.credential_service import credential_service
        credential_service = None
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

# OLD CODE BLOCK REMOVED - Lines 64-378 contained old implementation
# Now using HTTP-based communication via get_mcp_service_client()


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
        logger.info(f"Crawling single page via HTTP: {url}")
        
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
        logger.info(f"Smart crawling via HTTP: {url}")
        
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
            # MCP should use HTTP to get sources - commenting out direct DB access
            # supabase_client = get_supabase_client()
            # response = supabase_client.table("documents").select("source").execute()
            
            # TODO: Implement HTTP call to server API to get sources
            # For now, return empty list to allow MCP to start
            response = type('obj', (object,), {'data': []})
            
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
            logger.error(f"Error getting sources: {e}")
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
        logger.info(f"Performing RAG query via HTTP: {query}")
        
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
            # Use HTTP call to server API to delete source
            client = get_mcp_service_client()
            logger.info(f"Deleting source via HTTP: {source}")
            
            # Call the delete source endpoint
            async with httpx.AsyncClient() as http_client:
                response = await http_client.delete(
                    f"{client.api_url}/api/sources/{source}",
                    headers=client._get_headers()
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return json.dumps({
                        "success": True,
                        "source": source,
                        "message": result.get("message", f"Deleted all documents from source: {source}")
                    }, indent=2)
                else:
                    error_detail = response.json() if response.content else {"error": f"HTTP {response.status_code}"}
                    return json.dumps({
                        "success": False,
                        "source": source,
                        "error": error_detail.get("error", "Failed to delete source")
                    }, indent=2)
            
        except Exception as e:
            logger.error(f"Error deleting source: {e}")
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
        logger.info(f"Searching code examples via HTTP: {query}")
        
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
        logger.info(f"Uploading document via HTTP: {filename}")
        
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
    logger.info("✓ RAG tools registered (HTTP-based version)")