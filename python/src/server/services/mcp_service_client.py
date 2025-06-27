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

from ..config import get_api_url, get_agents_url
from ..logfire_config import mcp_logger

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
        Crawl a URL by calling the API service's internal crawl endpoint.
        
        Args:
            url: URL to crawl
            options: Crawling options (max_depth, chunk_size, smart_crawl)
            
        Returns:
            Crawl response with success status and results
        """
        endpoint = urljoin(self.api_url, "/internal/crawl")
        request_data = {
            "url": url,
            "options": options or {}
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
                return response.json()
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
        Perform a search by calling the API service's internal search endpoint.
        If reranking is requested, also calls the Agents service.
        
        Args:
            query: Search query
            source_filter: Optional source ID to filter results
            match_count: Number of results to return
            use_reranking: Whether to rerank results using the Agents service
            
        Returns:
            Search response with results
        """
        endpoint = urljoin(self.api_url, "/internal/search")
        request_data = {
            "query": query,
            "source_filter": source_filter,
            "match_count": match_count,
            "use_reranking": use_reranking
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
                search_results = response.json()
                
                # If reranking requested and we have results, call Agents service
                if use_reranking and search_results.get("success") and search_results.get("results"):
                    mcp_logger.info("Calling Agents service for reranking")
                    rerank_results = await self._rerank_results(query, search_results["results"])
                    
                    if rerank_results.get("success"):
                        search_results["results"] = rerank_results["reranked_results"]
                        search_results["reranked"] = True
                    else:
                        mcp_logger.warning("Reranking failed, returning original results")
                
                return search_results
                
        except Exception as e:
            mcp_logger.error(f"Error searching: {str(e)}")
            return {
                "success": False,
                "results": [],
                "error": {"code": "SEARCH_FAILED", "message": str(e)}
            }
    
    async def _rerank_results(self, query: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Rerank search results by calling the Agents service.
        
        Args:
            query: Original search query
            results: Search results to rerank
            
        Returns:
            Reranking response
        """
        endpoint = urljoin(self.agents_url, "/internal/rerank")
        request_data = {
            "query": query,
            "results": results
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=request_data,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            mcp_logger.error(f"Error reranking: {str(e)}")
            return {
                "success": False,
                "error": {"code": "RERANK_FAILED", "message": str(e)}
            }
    
    async def store_documents(self, documents: List[Dict[str, Any]], 
                            generate_embeddings: bool = True) -> Dict[str, Any]:
        """
        Store documents by calling the API service's internal storage endpoint.
        
        Args:
            documents: List of documents to store
            generate_embeddings: Whether to generate embeddings
            
        Returns:
            Storage response
        """
        endpoint = urljoin(self.api_url, "/internal/storage/store")
        request_data = {
            "documents": documents,
            "generate_embeddings": generate_embeddings
        }
        
        mcp_logger.info(f"Calling API service to store {len(documents)} documents")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=request_data,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            mcp_logger.error(f"Error storing documents: {str(e)}")
            return {
                "success": False,
                "documents_stored": 0,
                "chunks_created": 0,
                "error": {"code": "STORAGE_FAILED", "message": str(e)}
            }
    
    async def generate_embeddings(self, texts: List[str], 
                                model: str = "text-embedding-3-small") -> Dict[str, Any]:
        """
        Generate embeddings by calling the API service's internal embeddings endpoint.
        
        Args:
            texts: List of texts to embed
            model: Embedding model to use
            
        Returns:
            Embeddings response
        """
        endpoint = urljoin(self.api_url, "/internal/embeddings")
        request_data = {
            "texts": texts,
            "model": model
        }
        
        mcp_logger.info(f"Calling API service to generate {len(texts)} embeddings")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=request_data,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            mcp_logger.error(f"Error generating embeddings: {str(e)}")
            raise Exception(f"Failed to generate embeddings: {str(e)}")
    
    async def analyze_document(self, document_id: str, analysis_type: str = "summarize",
                             options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze a document by calling the Agents service.
        
        Args:
            document_id: ID of document to analyze
            analysis_type: Type of analysis to perform
            options: Analysis options
            
        Returns:
            Analysis response
        """
        endpoint = urljoin(self.agents_url, "/internal/analyze")
        request_data = {
            "document_id": document_id,
            "analysis_type": analysis_type,
            "options": options or {}
        }
        
        mcp_logger.info(f"Calling Agents service to analyze document {document_id}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=request_data,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            mcp_logger.error(f"Error analyzing document: {str(e)}")
            return {
                "success": False,
                "error": {"code": "ANALYSIS_FAILED", "message": str(e)}
            }
    
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
                    urljoin(self.api_url, "/internal/health"),
                    headers=self._get_headers()
                )
                health_status["api_service"] = response.status_code == 200
        except Exception:
            pass
        
        # Check Agents service
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(
                    urljoin(self.agents_url, "/internal/health"),
                    headers=self._get_headers()
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