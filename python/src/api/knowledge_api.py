"""
Knowledge Management API Module

This module handles all knowledge base operations including:
- Crawling and indexing web content
- Document upload and processing  
- RAG (Retrieval Augmented Generation) queries
- Knowledge item management and search
- Real-time progress tracking via WebSockets
"""

import asyncio
import json
import secrets
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Request
from pydantic import BaseModel, HttpUrl

from ..utils import get_supabase_client

# Create router
router = APIRouter(prefix="/api", tags=["knowledge"])

# Get the global crawling context from main.py
def get_crawling_context():
    """Get the global crawling context from the app state."""
    from fastapi import Request
    import inspect
    
    # Try to get the context from the current request
    frame = inspect.currentframe()
    try:
        # Walk up the call stack to find the app instance
        while frame:
            if 'app' in frame.f_locals and hasattr(frame.f_locals['app'], 'state'):
                app = frame.f_locals['app']
                if hasattr(app.state, 'crawling_context'):
                    return app.state.crawling_context
            frame = frame.f_back
    finally:
        del frame
    
    # Fallback - import directly from main
    try:
        from ..main import crawling_context
        return crawling_context
    except ImportError:
        # Create a minimal context if we can't get the global one
        class MinimalContext:
            def __init__(self):
                self._initialized = False
                self.supabase_client = get_supabase_client()
        return MinimalContext()

# Connection Manager for WebSocket management
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

# Global connection manager
manager = ConnectionManager()

# Request Models
class KnowledgeItemRequest(BaseModel):
    url: str
    knowledge_type: str = 'technical'
    tags: List[str] = []
    update_frequency: int = 7

class CrawlRequest(BaseModel):
    url: str
    knowledge_type: str = 'general'
    tags: List[str] = []
    update_frequency: int = 7

# Progress Manager for crawling operations
class CrawlProgressManager:
    """Manages crawling progress tracking and WebSocket streaming."""
    
    def __init__(self):
        self.active_crawls: Dict[str, Dict[str, Any]] = {}
        self.progress_websockets: Dict[str, List[WebSocket]] = {}
    
    def start_crawl(self, progress_id: str, initial_data: Dict[str, Any]) -> None:
        """Start tracking a new crawl operation."""
        self.active_crawls[progress_id] = {
            'status': 'starting',
            'percentage': 0,
            'start_time': datetime.now(),
            'logs': ['Starting crawl...'],
            **initial_data
        }
        
    async def update_progress(self, progress_id: str, update_data: Dict[str, Any]) -> None:
        """Update crawling progress and notify connected clients."""
        if progress_id not in self.active_crawls:
            return
        
        # Update progress data
        self.active_crawls[progress_id].update(update_data)
        self.active_crawls[progress_id]['updated_at'] = datetime.now()
        
        # Add to logs if message provided
        if 'log' in update_data:
            self.active_crawls[progress_id]['logs'].append(update_data['log'])
        
        # Broadcast to connected clients
        await self._broadcast_progress(progress_id)
    
    async def complete_crawl(self, progress_id: str, completion_data: Dict[str, Any]) -> None:
        """Mark crawl as completed and notify clients."""
        if progress_id not in self.active_crawls:
            return
        
        self.active_crawls[progress_id].update({
            'status': 'completed',
            'percentage': 100,
            'completed_at': datetime.now(),
            **completion_data
        })
        
        if 'log' in completion_data:
            self.active_crawls[progress_id]['logs'].append(completion_data['log'])
        
        await self._broadcast_progress(progress_id)
        
        # Clean up after 5 minutes
        await asyncio.sleep(300)
        if progress_id in self.active_crawls:
            del self.active_crawls[progress_id]
    
    async def error_crawl(self, progress_id: str, error_message: str) -> None:
        """Mark crawl as failed and notify clients."""
        if progress_id not in self.active_crawls:
            return
        
        self.active_crawls[progress_id].update({
            'status': 'error',
            'error': error_message,
            'completed_at': datetime.now()
        })
        
        self.active_crawls[progress_id]['logs'].append(f"Error: {error_message}")
        
        await self._broadcast_progress(progress_id)
    
    async def add_websocket(self, progress_id: str, websocket: WebSocket) -> None:
        """Add WebSocket to progress tracking."""
        await websocket.accept()
        
        if progress_id not in self.progress_websockets:
            self.progress_websockets[progress_id] = []
        
        self.progress_websockets[progress_id].append(websocket)
        
        # Send current progress immediately if available
        if progress_id in self.active_crawls:
            progress_data = self.active_crawls[progress_id].copy()
            progress_data['progressId'] = progress_id
            
            if 'start_time' in progress_data and hasattr(progress_data['start_time'], 'isoformat'):
                progress_data['start_time'] = progress_data['start_time'].isoformat()
            
            try:
                await websocket.send_json({
                    "type": "crawl_progress",
                    "data": progress_data
                })
            except Exception:
                self.remove_websocket(progress_id, websocket)
    
    def remove_websocket(self, progress_id: str, websocket: WebSocket) -> None:
        """Remove WebSocket from progress tracking."""
        if progress_id in self.progress_websockets:
            try:
                self.progress_websockets[progress_id].remove(websocket)
                if not self.progress_websockets[progress_id]:
                    del self.progress_websockets[progress_id]
            except ValueError:
                pass
    
    async def _broadcast_progress(self, progress_id: str) -> None:
        """Broadcast progress update to all connected clients."""
        if progress_id not in self.progress_websockets:
            return
        
        progress_data = self.active_crawls.get(progress_id, {}).copy()
        progress_data['progressId'] = progress_id
        
        if 'start_time' in progress_data and hasattr(progress_data['start_time'], 'isoformat'):
            progress_data['start_time'] = progress_data['start_time'].isoformat()
        
        message = {
            "type": "crawl_progress" if progress_data.get('status') != 'completed' else "crawl_completed",
            "data": progress_data
        }
        
        # Send to all connected WebSocket clients
        disconnected = []
        for websocket in self.progress_websockets[progress_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)
        
        # Clean up disconnected WebSockets
        for ws in disconnected:
            self.remove_websocket(progress_id, ws)

# Global progress manager
progress_manager = CrawlProgressManager()

async def get_available_sources_direct() -> Dict[str, Any]:
    """Get all available sources from the sources table directly."""
    try:
        supabase_client = get_supabase_client()
        
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
                    "total_words": source.get("total_words", source.get("total_word_count", 0)),
                    "created_at": source.get("created_at"),
                    "updated_at": source.get("updated_at", source.get("created_at"))
                })
        
        return {
            "success": True,
            "sources": sources,
            "count": len(sources)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/knowledge-items")
async def get_knowledge_items(
    page: int = 1,
    per_page: int = 20,
    knowledge_type: Optional[str] = None,
    search: Optional[str] = None
):
    """Get knowledge items with pagination and filtering."""
    try:
        # Ensure crawling context is initialized once  
        crawling_context = get_crawling_context()
        if not crawling_context._initialized:
            await crawling_context.initialize()
        
        # Get all sources directly 
        sources_result = await get_available_sources_direct()
        
        # Parse the JSON response
        if isinstance(sources_result, str):
            sources_data = json.loads(sources_result)
        else:
            sources_data = sources_result
        
        # Transform the data to match frontend expectations
        items = []
        for source in sources_data.get('sources', []):
            # Use title and metadata from sources table
            source_metadata = source.get('metadata', {})
            
            # Get first page URL if available
            supabase_client = crawling_context.supabase_client or get_supabase_client()
            pages_response = supabase_client.from_('crawled_pages')\
                .select('url')\
                .eq('source_id', source['source_id'])\
                .limit(1)\
                .execute()
            
            first_page = pages_response.data[0] if pages_response.data else {}
            
            # Determine source type - if metadata has source_type='file', use it; otherwise check URL pattern
            stored_source_type = source_metadata.get('source_type')
            if stored_source_type:
                source_type = stored_source_type
            else:
                # Legacy fallback - check URL pattern
                first_page_url = first_page.get('url', f"source://{source['source_id']}")
                source_type = 'file' if first_page_url.startswith('file://') else 'url'
            
            item = {
                'id': source['source_id'],
                'title': source.get('title', source.get('summary', 'Untitled')),
                'url': first_page.get('url', f"source://{source['source_id']}"),
                'source_id': source['source_id'],
                'metadata': {
                    'knowledge_type': source_metadata.get('knowledge_type', 'technical'),
                    'tags': source_metadata.get('tags', []),
                    'source_type': source_type,
                    'status': 'active',
                    'description': source_metadata.get('description', source.get('summary', '')),
                    'chunks_count': source.get('total_words', 0),
                    'word_count': source.get('total_words', 0),
                    'last_scraped': source.get('updated_at'),
                    'file_name': source_metadata.get('file_name'),
                    'file_type': source_metadata.get('file_type'),
                    **source_metadata
                },
                'created_at': source.get('created_at'),
                'updated_at': source.get('updated_at')
            }
            items.append(item)
        
        # Filter by search term if provided
        if search:
            search_lower = search.lower()
            items = [
                item for item in items 
                if search_lower in item['title'].lower() 
                or search_lower in item['metadata'].get('description', '').lower()
                or any(search_lower in tag.lower() for tag in item['metadata'].get('tags', []))
            ]
        
        # Filter by knowledge type if provided
        if knowledge_type:
            items = [
                item for item in items 
                if item['metadata'].get('knowledge_type') == knowledge_type
            ]
        
        # Apply pagination
        total = len(items)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_items = items[start_idx:end_idx]
        
        return {
            'items': paginated_items,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.delete("/knowledge-items/{source_id}")
async def delete_knowledge_item(source_id: str):
    """Delete a knowledge item and all associated content."""
    try:
        supabase_client = get_supabase_client()
        
        # Delete from sources table (this should cascade to related tables)
        response = supabase_client.table("sources").delete().eq("source_id", source_id).execute()
        
        # Also delete from crawled_pages table if needed
        supabase_client.table("crawled_pages").delete().eq("source_id", source_id).execute()
        
        return {"message": "Knowledge item deleted successfully", "source_id": source_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/knowledge-items/crawl")
async def crawl_knowledge_item(request: KnowledgeItemRequest):
    """Crawl a URL and add it to the knowledge base with progress tracking."""
    try:
        # Generate unique progress ID
        progress_id = str(uuid.uuid4())
        
        # Start progress tracking
        progress_manager.start_crawl(progress_id, {
            'progressId': progress_id,
            'currentUrl': str(request.url),
            'totalPages': 0,
            'processedPages': 0,
            'percentage': 0,
            'log': f'Starting crawl of {request.url}'
        })
        
        # Start background task
        asyncio.create_task(_perform_crawl_with_progress(progress_id, request))
        
        return {
            "progressId": progress_id,
            "status": "started",
            "message": "Crawling started. Connect to WebSocket for progress updates."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

async def _perform_crawl_with_progress(progress_id: str, request: KnowledgeItemRequest):
    """Perform the actual crawl operation with progress tracking."""
    try:
        # Create a progress callback that will be called by the crawling function
        async def progress_callback(status: str, percentage: int, message: str, **kwargs):
            """Callback function to receive real-time progress updates from crawling."""
            await progress_manager.update_progress(progress_id, {
                'status': status,
                'percentage': percentage,
                'currentUrl': kwargs.get('currentUrl', str(request.url)),
                'totalPages': kwargs.get('totalPages', 0),
                'processedPages': kwargs.get('processedPages', 0),
                'log': message,
                **kwargs
            })
        
        # Initial progress update
        await progress_callback('starting', 0, f'Starting crawl of {request.url}')
        
        # Simulate crawling process (in real implementation, you'd use MCP server here)
        await progress_callback('crawling', 25, 'Analyzing page structure...')
        await asyncio.sleep(1)
        
        await progress_callback('processing', 50, 'Extracting content...')
        await asyncio.sleep(1)
        
        await progress_callback('storing', 75, 'Processing and storing content...')
        await asyncio.sleep(1)
        
        # Store dummy data for demo
        supabase_client = get_supabase_client()
        
        # Create source entry
        source_data = {
            "source_id": f"crawl_{int(datetime.now().timestamp())}",
            "title": f"Page from {request.url}",
            "summary": f"Crawled content from {request.url}",
            "metadata": {
                "knowledge_type": request.knowledge_type,
                "tags": request.tags,
                "source_type": "url",
                "update_frequency": request.update_frequency
            },
                         "total_words": 100
        }
        
        sources_response = supabase_client.table("sources").insert(source_data).execute()
        
        # Create crawled page entry
        page_data = {
            "url": str(request.url),
            "title": f"Page from {request.url}",
            "content": f"Sample content from {request.url}",
            "source_id": source_data["source_id"],
            "word_count": 100,
            "chunk_index": 0
        }
        
        pages_response = supabase_client.table("crawled_pages").insert(page_data).execute()
        
        # Final completion update
        completion_data = {
            'chunksStored': 1,
            'wordCount': 100,
            'log': 'Crawling completed successfully'
        }
        await progress_manager.complete_crawl(progress_id, completion_data)
        
        # Broadcast final update to general WebSocket clients
        await manager.broadcast({
            "type": "crawl_completed",
            "data": {
                "url": str(request.url),
                "success": True,
                "message": f'Crawling completed for {request.url}',
                "progressId": progress_id
            }
        })
        
    except Exception as e:
        error_message = f'Crawling failed: {str(e)}'
        await progress_manager.error_crawl(progress_id, error_message)

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
    knowledge_type: Optional[str] = Form("technical")
):
    """Upload and process a document."""
    try:
        # Parse tags
        tag_list = json.loads(tags) if tags else []
        
        # Read file content
        content = await file.read()
        
        # Store in database
        supabase_client = get_supabase_client()
        
        # Create source entry
        source_id = f"upload_{int(datetime.now().timestamp())}"
        source_data = {
            "source_id": source_id,
            "title": file.filename,
            "summary": f"Uploaded document: {file.filename}",
            "metadata": {
                "knowledge_type": knowledge_type,
                "tags": tag_list,
                "source_type": "file",
                "file_name": file.filename,
                "file_type": file.content_type,
                "file_size": len(content)
            },
                         "total_words": len(content.decode('utf-8', errors='ignore').split())
        }
        
        sources_response = supabase_client.table("sources").insert(source_data).execute()
        
        # Create crawled page entry
        content_data = {
            "url": f"file://{file.filename}",
            "title": file.filename,
            "content": content.decode('utf-8', errors='ignore'),
            "source_id": source_id,
            "word_count": len(content.decode('utf-8', errors='ignore').split()),
            "chunk_index": 0
        }
        
        pages_response = supabase_client.table("crawled_pages").insert(content_data).execute()
        
        return {"message": "Document uploaded successfully", "source_id": source_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/rag/query")
async def perform_rag_query(
    query: str, 
    source: Optional[str] = None, 
    match_count: int = 5
):
    """Perform a RAG query on the knowledge base."""
    try:
        supabase_client = get_supabase_client()
        
        # Simple search implementation (in production, you'd use vector search)
        query_builder = supabase_client.table("crawled_pages").select("*")
        
        if source:
            query_builder = query_builder.eq("source_id", source)
        
        response = query_builder.limit(match_count).execute()
        
        # Filter results by query relevance (simple text matching)
        results = []
        for item in response.data:
            content = item.get("content", "")
            if query.lower() in content.lower():
                results.append({
                    "id": item["id"],
                    "title": item.get("title", ""),
                    "content": content[:500] + "..." if len(content) > 500 else content,
                    "url": item.get("url", ""),
                    "source_id": item.get("source_id", ""),
                    "relevance_score": 0.8  # Dummy score
                })
        
        return {
            "results": results[:match_count],
            "query": query,
            "total_results": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/rag/sources")
async def get_available_sources():
    """Get all available sources for RAG queries."""
    try:
        return await get_available_sources_direct()
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

# WebSocket Endpoints
@router.websocket("/knowledge-items/stream")
async def websocket_knowledge_items(websocket: WebSocket):
    """WebSocket endpoint for real-time knowledge items updates."""
    await manager.connect(websocket)
    try:
        # Ensure crawling context is initialized once  
        crawling_context = get_crawling_context()
        if not crawling_context._initialized:
            await crawling_context.initialize()
        
        # Send initial data
        sources_result = await get_available_sources_direct()
        
        if isinstance(sources_result, str):
            sources_data = json.loads(sources_result)
        else:
            sources_data = sources_result
        
        # Transform data for frontend (use same mapping as REST API)
        items = []
        for source in sources_data.get('sources', []):
            # Use metadata from sources table
            source_metadata = source.get('metadata', {})
            
            # Get first page URL if available
            supabase_client = crawling_context.supabase_client or get_supabase_client()
            pages_response = supabase_client.from_('crawled_pages')\
                .select('url')\
                .eq('source_id', source['source_id'])\
                .limit(1)\
                .execute()
            
            first_page = pages_response.data[0] if pages_response.data else {}
            
            # Determine source type - if metadata has source_type='file', use it; otherwise check URL pattern
            stored_source_type = source_metadata.get('source_type')
            if stored_source_type:
                source_type = stored_source_type
            else:
                # Legacy fallback - check URL pattern
                first_page_url = first_page.get('url', f"source://{source['source_id']}")
                source_type = 'file' if first_page_url.startswith('file://') else 'url'
            
            item = {
                'id': source['source_id'],
                'title': source.get('title', source.get('summary', 'Untitled')),
                'url': first_page.get('url', f"source://{source['source_id']}"),
                'source_id': source['source_id'],
                'metadata': {
                    'knowledge_type': source_metadata.get('knowledge_type', 'technical'),
                    'tags': source_metadata.get('tags', []),
                    'source_type': source_type,
                    'status': 'active',
                    'description': source_metadata.get('description', source.get('summary', '')),
                    'chunks_count': source.get('total_words', 0),
                    'word_count': source.get('total_words', 0),
                    'last_scraped': source.get('updated_at'),
                    'file_name': source_metadata.get('file_name'),
                    'file_type': source_metadata.get('file_type'),
                    **source_metadata
                },
                'created_at': source.get('created_at'),
                'updated_at': source.get('updated_at')
            }
            items.append(item)
        
        await websocket.send_json({
            "type": "knowledge_items_update",
            "data": {
                "items": items,
                "total": len(items),
                "page": 1,
                "per_page": 20,
                "pages": 1
            }
        })
        
        # Keep connection alive and listen for updates
        while True:
            await asyncio.sleep(5)  # Check for updates every 5 seconds
            # Send heartbeat
            await websocket.send_json({"type": "heartbeat"})
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

@router.websocket("/crawl-progress/{progress_id}")
async def websocket_crawl_progress(websocket: WebSocket, progress_id: str):
    """WebSocket endpoint for tracking specific crawl progress."""
    # Add WebSocket to progress manager (now handles accept internally)
    await progress_manager.add_websocket(progress_id, websocket)
    
    try:
        while True:
            # Keep connection alive with ping
            await asyncio.sleep(1)
            await websocket.send_json({"type": "ping"})
            
    except WebSocketDisconnect:
        progress_manager.remove_websocket(progress_id, websocket)
    except Exception as e:
        progress_manager.remove_websocket(progress_id, websocket)
        try:
            await websocket.close()
        except:
            pass

@router.get("/database/metrics")
async def get_database_metrics():
    """Get database metrics and statistics."""
    try:
        supabase_client = get_supabase_client()
        
        # Get counts from various tables
        sources_count = supabase_client.table("sources").select("*", count="exact").execute()
        pages_count = supabase_client.table("crawled_pages").select("*", count="exact").execute()
        
        return {
            "sources_count": sources_count.count if sources_count.count else 0,
            "pages_count": pages_count.count if pages_count.count else 0,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/health")
async def knowledge_health():
    """Knowledge API health check."""
    return {
        "status": "healthy",
        "service": "knowledge-api",
        "timestamp": datetime.now().isoformat()
    } 