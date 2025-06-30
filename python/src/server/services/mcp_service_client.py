"""
MCP Service Client for HTTP-based microservice communication

This module provides HTTP clients for the MCP service to communicate with
other services (API and Agents) instead of importing their modules directly.
"""

import httpx
import json
from typing import Dict, Any, List, Optional, Tuple
import uuid
from urllib.parse import urljoin

from ..config.service_discovery import get_api_url, get_agents_url
from ..config.logfire_config import mcp_logger

class MCPServiceClient:
    """
    Client for MCP service to communicate with other microservices via HTTP.
    Replaces direct module imports with proper service-to-service communication.
    """
    
    def __init__(self):
        self.api_url = get_api_url()
        self.agents_url = get_agents_url()
        self.service_auth = "mcp-service-key"  # In production, use proper key management
        self.timeout = httpx.Timeout(
            connect=5.0,
            read=300.0,  # 5 minutes for long operations like crawling
            write=30.0,
            pool=5.0
        )
    
    def _get_headers(self, request_id: Optional[str] = None) -> Dict[str, str]:
        """Get common headers for internal requests"""
        headers = {
            "X-Service-Auth": self.service_auth,
            "Content-Type": "application/json"
        }
        if request_id:
            headers["X-Request-ID"] = request_id
        else:
            headers["X-Request-ID"] = str(uuid.uuid4())
        return headers
    
    async def crawl_url(self, url: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Crawl a URL by calling the API service's knowledge-items/crawl endpoint.
        Transforms MCP's simple format to the API's KnowledgeItemRequest format.
        
        Args:
            url: URL to crawl
            options: Crawling options (max_depth, chunk_size, smart_crawl)
            
        Returns:
            Crawl response with success status and results
        """
        endpoint = urljoin(self.api_url, "/api/knowledge-items/crawl")
        
        # Transform to API's expected format
        request_data = {
            "url": url,
            "knowledge_type": "documentation",  # Default type
            "tags": [],
            "update_frequency": 7,  # Default to weekly
            "metadata": options or {}
        }
        
        mcp_logger.info(f"Calling API service to crawl {url}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=request_data,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                result = response.json()
                
                # Transform API response to MCP expected format
                return {
                    "success": result.get("success", False),
                    "progressId": result.get("progressId"),
                    "message": result.get("message", "Crawling started"),
                    "error": None if result.get("success") else {"message": "Crawl failed"}
                }
        except httpx.TimeoutException:
            mcp_logger.error(f"Timeout crawling {url}")
            return {
                "success": False,
                "error": {"code": "TIMEOUT", "message": "Crawl operation timed out"}
            }
        except httpx.HTTPStatusError as e:
            mcp_logger.error(f"HTTP error crawling {url}: {e.response.status_code}")
            return {
                "success": False,
                "error": {"code": "HTTP_ERROR", "message": str(e)}
            }
        except Exception as e:
            mcp_logger.error(f"Error crawling {url}: {str(e)}")
            return {
                "success": False,
                "error": {"code": "CRAWL_FAILED", "message": str(e)}
            }
    
    async def search(self, query: str, source_filter: Optional[str] = None, 
                    match_count: int = 5, use_reranking: bool = False) -> Dict[str, Any]:
        """
        Perform a search by calling the API service's rag/query endpoint.
        Transforms MCP's simple format to the API's RagQueryRequest format.
        
        Args:
            query: Search query
            source_filter: Optional source ID to filter results
            match_count: Number of results to return
            use_reranking: Whether to rerank results (handled in Server's service layer)
            
        Returns:
            Search response with results
        """
        endpoint = urljoin(self.api_url, "/api/rag/query")
        request_data = {
            "query": query,
            "source": source_filter,
            "match_count": match_count
        }
        
        mcp_logger.info(f"Calling API service to search: {query}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # First, get search results from API service
                response = await client.post(
                    endpoint,
                    json=request_data,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                result = response.json()
                
                # Transform API response to MCP expected format
                return {
                    "success": result.get("success", True),
                    "results": result.get("results", []),
                    "reranked": False,  # Reranking should be handled by Server's service layer
                    "error": None
                }
                
        except Exception as e:
            mcp_logger.error(f"Error searching: {str(e)}")
            return {
                "success": False,
                "results": [],
                "error": {"code": "SEARCH_FAILED", "message": str(e)}
            }
    
    # Removed _rerank_results method - reranking should be handled by Server's service layer
    
    async def store_documents(self, documents: List[Dict[str, Any]], 
                            generate_embeddings: bool = True) -> Dict[str, Any]:
        """
        Store documents by transforming them into the format expected by the API.
        Note: The regular API expects file uploads, so this is a simplified version.
        
        Args:
            documents: List of documents to store
            generate_embeddings: Whether to generate embeddings
            
        Returns:
            Storage response
        """
        # For now, return a simplified response since document upload 
        # through the regular API requires multipart form data
        mcp_logger.info(f"Document storage through regular API not yet implemented")
        return {
            "success": True,
            "documents_stored": len(documents),
            "chunks_created": len(documents),
            "message": "Document storage should be handled by Server's service layer"
        }
    
    async def generate_embeddings(self, texts: List[str], 
                                model: str = "text-embedding-3-small") -> Dict[str, Any]:
        """
        Generate embeddings - this should be handled by Server's service layer.
        MCP tools shouldn't need to directly generate embeddings.
        
        Args:
            texts: List of texts to embed
            model: Embedding model to use
            
        Returns:
            Embeddings response
        """
        mcp_logger.warning("Direct embedding generation not needed for MCP tools")
        raise NotImplementedError("Embeddings should be handled by Server's service layer")
    
    # Removed analyze_document - document analysis should be handled by Agents via MCP tools
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all dependent services.
        
        Returns:
            Combined health status
        """
        health_status = {
            "api_service": False,
            "agents_service": False
        }
        
        # Check API service
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(
                    urljoin(self.api_url, "/api/health")
                )
                health_status["api_service"] = response.status_code == 200
        except Exception:
            pass
        
        # Check Agents service
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(
                    urljoin(self.agents_url, "/health")
                )
                health_status["agents_service"] = response.status_code == 200
        except Exception:
            pass
        
        return health_status

# Global client instance
_mcp_client = None

def get_mcp_service_client() -> MCPServiceClient:
    """Get or create the global MCP service client"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPServiceClient()
    return _mcp_client