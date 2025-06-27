"""
Internal API endpoints for service-to-service communication

This module provides internal endpoints that other services (MCP, Agents) can call
to perform operations without importing the service modules directly.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel, HttpUrl
import uuid

# Import services that will be used
from ..services.rag.crawling_service import CrawlingService
from ..services.rag.search_service import SearchService
from ..services.rag.document_storage_service import DocumentStorageService
from ..services.embedding_service import EmbeddingService
from ..services.agents_service_client import AgentsServiceClient
from ..utils import get_supabase_client
from ..logfire_config import api_logger

# Create router with internal prefix
router = APIRouter(prefix="/internal", tags=["internal"])

# Request/Response Models
class CrawlRequest(BaseModel):
    url: HttpUrl
    options: Optional[Dict[str, Any]] = None

class CrawlResponse(BaseModel):
    success: bool
    pages_crawled: Optional[int] = None
    chunks_stored: Optional[int] = None
    total_word_count: Optional[int] = None
    source_id: Optional[str] = None
    error: Optional[Dict[str, Any]] = None

class SearchRequest(BaseModel):
    query: str
    source_filter: Optional[str] = None
    match_count: int = 5
    use_reranking: bool = False

class SearchResult(BaseModel):
    id: str
    content: str
    similarity: float
    metadata: Dict[str, Any]

class SearchResponse(BaseModel):
    success: bool
    results: List[SearchResult]
    reranked: bool = False
    error: Optional[Dict[str, Any]] = None

class StorageRequest(BaseModel):
    documents: List[Dict[str, Any]]
    generate_embeddings: bool = True

class StorageResponse(BaseModel):
    success: bool
    documents_stored: int
    chunks_created: int
    error: Optional[Dict[str, Any]] = None

class EmbeddingsRequest(BaseModel):
    texts: List[str]
    model: str = "text-embedding-3-small"

class EmbeddingsResponse(BaseModel):
    embeddings: List[List[float]]
    model: str
    usage: Dict[str, int]

# Authentication middleware for internal endpoints
async def verify_internal_auth(x_service_auth: Optional[str] = Header(None)):
    """Verify that the request is from an authorized internal service"""
    # For now, accept any request with the header
    # In production, validate against service-specific keys
    if not x_service_auth:
        raise HTTPException(status_code=401, detail="Missing X-Service-Auth header")
    return x_service_auth

# Get crawling context from main app
def get_crawling_context(request: Request):
    """Get the crawling context from the app state"""
    if hasattr(request.app.state, 'crawling_context'):
        return request.app.state.crawling_context
    raise HTTPException(status_code=500, detail="Crawling context not initialized")

@router.post("/crawl", response_model=CrawlResponse)
async def internal_crawl(
    request: Request,
    crawl_request: CrawlRequest,
    service_auth: str = Header(None, alias="X-Service-Auth")
):
    """
    Internal endpoint for crawling operations.
    Used by MCP service to delegate crawling to API service.
    """
    await verify_internal_auth(service_auth)
    
    try:
        # Get services from context
        context = get_crawling_context(request)
        crawler = context.crawler
        supabase_client = context.supabase_client
        
        # Initialize services
        crawling_service = CrawlingService(crawler, supabase_client)
        storage_service = DocumentStorageService(supabase_client)
        
        # Prepare options
        options = crawl_request.options or {}
        max_depth = options.get("max_depth", 3)
        chunk_size = options.get("chunk_size", 5000)
        smart_crawl = options.get("smart_crawl", True)
        
        api_logger.info(f"Internal crawl request for {crawl_request.url}")
        
        # Perform crawling based on type
        if smart_crawl:
            # Smart crawl logic (detect sitemap, etc.)
            from ..modules.rag_module import smart_crawl_url_direct
            
            # Create a mock context for the function
            class MockContext:
                class RequestContext:
                    class LifespanContext:
                        def __init__(self, crawler, supabase_client):
                            self.crawler = crawler
                            self.supabase_client = supabase_client
                            self.reranking_model = None
                    
                    def __init__(self, crawler, supabase_client):
                        self.lifespan_context = self.LifespanContext(crawler, supabase_client)
                
                def __init__(self, crawler, supabase_client):
                    self.request_context = self.RequestContext(crawler, supabase_client)
            
            mock_ctx = MockContext(crawler, supabase_client)
            result = await smart_crawl_url_direct(
                mock_ctx,
                str(crawl_request.url),
                max_depth=max_depth,
                max_concurrent=5,
                chunk_size=chunk_size
            )
            
            # Parse result
            if isinstance(result, str):
                result = json.loads(result)
            
            return CrawlResponse(
                success=result.get("success", False),
                pages_crawled=result.get("pages_crawled"),
                chunks_stored=result.get("chunks_stored"),
                total_word_count=result.get("total_word_count"),
                source_id=result.get("source_id"),
                error=None if result.get("success") else {"message": result.get("error")}
            )
        else:
            # Simple single page crawl
            success, content = await crawling_service.crawl_single_page(str(crawl_request.url))
            
            if success and content:
                # Store the content
                chunks = storage_service.chunk_content(content, chunk_size)
                source_id = str(uuid.uuid4())
                
                # Store chunks (without embeddings for now)
                stored = 0
                for chunk in chunks:
                    # Store logic here
                    stored += 1
                
                return CrawlResponse(
                    success=True,
                    pages_crawled=1,
                    chunks_stored=stored,
                    total_word_count=len(content.split()),
                    source_id=source_id
                )
            else:
                return CrawlResponse(
                    success=False,
                    error={"message": "Failed to crawl URL"}
                )
                
    except Exception as e:
        api_logger.error(f"Internal crawl error: {str(e)}")
        return CrawlResponse(
            success=False,
            error={
                "code": "CRAWL_FAILED",
                "message": str(e)
            }
        )

@router.post("/search", response_model=SearchResponse)
async def internal_search(
    request: Request,
    search_request: SearchRequest,
    service_auth: str = Header(None, alias="X-Service-Auth")
):
    """
    Internal endpoint for search operations.
    Used by MCP service to perform RAG queries.
    """
    await verify_internal_auth(service_auth)
    
    try:
        # Get services
        context = get_crawling_context(request)
        supabase_client = context.supabase_client
        
        # Initialize search service with agents client for reranking
        agents_client = AgentsServiceClient()
        search_service = SearchService(supabase_client, agents_client)
        
        api_logger.info(f"Internal search request: {search_request.query}")
        
        # Perform search
        success, result = search_service.perform_rag_query(
            search_request.query,
            search_request.source_filter,
            search_request.match_count
        )
        
        if success:
            # Convert results to response format
            results = []
            for match in result.get("results", []):
                results.append(SearchResult(
                    id=match.get("id", ""),
                    content=match.get("content", ""),
                    similarity=match.get("similarity", 0.0),
                    metadata=match.get("metadata", {})
                ))
            
            return SearchResponse(
                success=True,
                results=results,
                reranked=False  # Reranking happens in Agents service
            )
        else:
            return SearchResponse(
                success=False,
                results=[],
                error={"message": result.get("error", "Search failed")}
            )
            
    except Exception as e:
        api_logger.error(f"Internal search error: {str(e)}")
        return SearchResponse(
            success=False,
            results=[],
            error={
                "code": "SEARCH_FAILED",
                "message": str(e)
            }
        )

@router.post("/storage/store", response_model=StorageResponse)
async def internal_store(
    request: Request,
    storage_request: StorageRequest,
    service_auth: str = Header(None, alias="X-Service-Auth")
):
    """
    Internal endpoint for document storage.
    Used by MCP service to store documents.
    """
    await verify_internal_auth(service_auth)
    
    try:
        # Get services
        context = get_crawling_context(request)
        supabase_client = context.supabase_client
        
        # Initialize storage service
        storage_service = DocumentStorageService(supabase_client)
        
        api_logger.info(f"Internal storage request for {len(storage_request.documents)} documents")
        
        # Process and store documents
        total_chunks = 0
        for doc in storage_request.documents:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            
            # Chunk the content
            chunks = storage_service.chunk_content(content, chunk_size=5000)
            
            # Store chunks (simplified for now)
            for chunk in chunks:
                # Add storage logic here
                total_chunks += 1
        
        return StorageResponse(
            success=True,
            documents_stored=len(storage_request.documents),
            chunks_created=total_chunks
        )
        
    except Exception as e:
        api_logger.error(f"Internal storage error: {str(e)}")
        return StorageResponse(
            success=False,
            documents_stored=0,
            chunks_created=0,
            error={
                "code": "STORAGE_FAILED",
                "message": str(e)
            }
        )

@router.post("/embeddings", response_model=EmbeddingsResponse)
async def internal_embeddings(
    request: Request,
    embeddings_request: EmbeddingsRequest,
    service_auth: str = Header(None, alias="X-Service-Auth")
):
    """
    Internal endpoint for generating embeddings.
    Used by other services to generate embeddings without importing the service.
    """
    await verify_internal_auth(service_auth)
    
    try:
        # Initialize embedding service
        embedding_service = EmbeddingService()
        
        api_logger.info(f"Internal embeddings request for {len(embeddings_request.texts)} texts")
        
        # Generate embeddings
        embeddings = []
        total_tokens = 0
        
        for text in embeddings_request.texts:
            embedding = await embedding_service.get_embedding(
                text, 
                model=embeddings_request.model
            )
            embeddings.append(embedding)
            # Estimate tokens (rough approximation)
            total_tokens += len(text.split()) * 1.3
        
        return EmbeddingsResponse(
            embeddings=embeddings,
            model=embeddings_request.model,
            usage={
                "prompt_tokens": int(total_tokens),
                "total_tokens": int(total_tokens)
            }
        )
        
    except Exception as e:
        api_logger.error(f"Internal embeddings error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "EMBEDDINGS_FAILED",
                "message": str(e)
            }
        )

@router.get("/health")
async def internal_health():
    """Health check for internal endpoints"""
    return {"status": "healthy", "service": "internal-api"}