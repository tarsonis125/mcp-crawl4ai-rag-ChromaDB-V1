"""
Knowledge API endpoints for Archon

Handles:
- Knowledge base management (CRUD operations)
- Web crawling with progress streaming
- RAG (Retrieval Augmented Generation) queries
- Document upload and processing
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import asyncio
import secrets
from datetime import datetime
import json
from urllib.parse import urlparse

from ..utils import get_supabase_client

router = APIRouter(prefix="/api", tags=["knowledge"])

class CrawlRequest(BaseModel):
    url: str
    knowledge_type: str = 'general'
    tags: List[str] = []
    update_frequency: int = 7

class CrawlProgressData(BaseModel):
    progressId: str
    status: str
    percentage: int
    currentUrl: Optional[str] = None
    eta: Optional[str] = None
    totalPages: Optional[int] = None
    processedPages: Optional[int] = None
    chunksStored: Optional[int] = None
    wordCount: Optional[int] = None
    duration: Optional[str] = None
    error: Optional[str] = None
    logs: List[str] = []

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
        
        # Add log if provided
        if 'log' in update_data:
            self.active_crawls[progress_id]['logs'].append(update_data['log'])
            # Keep only last 50 logs
            if len(self.active_crawls[progress_id]['logs']) > 50:
                self.active_crawls[progress_id]['logs'] = self.active_crawls[progress_id]['logs'][-50:]
        
        # Broadcast to connected WebSocket clients
        await self._broadcast_progress(progress_id)
    
    async def complete_crawl(self, progress_id: str, completion_data: Dict[str, Any]) -> None:
        """Mark a crawl as completed and send final update."""
        if progress_id not in self.active_crawls:
            return
        
        completion_data.update({
            'status': 'completed',
            'percentage': 100,
            'log': 'Crawling completed successfully!',
            'duration': str(datetime.now() - self.active_crawls[progress_id]['start_time'])
        })
        
        self.active_crawls[progress_id].update(completion_data)
        await self._broadcast_progress(progress_id)
        
        # Clean up after a delay
        await asyncio.sleep(5)
        if progress_id in self.active_crawls:
            del self.active_crawls[progress_id]
    
    async def error_crawl(self, progress_id: str, error_message: str) -> None:
        """Mark a crawl as failed and send error update."""
        if progress_id not in self.active_crawls:
            return
        
        self.active_crawls[progress_id].update({
            'status': 'error',
            'error': error_message,
            'log': f'Error: {error_message}'
        })
        
        await self._broadcast_progress(progress_id)
    
    async def add_websocket(self, progress_id: str, websocket: WebSocket) -> None:
        """Add a WebSocket connection for progress updates."""
        await websocket.accept()
        
        if progress_id not in self.progress_websockets:
            self.progress_websockets[progress_id] = []
        
        self.progress_websockets[progress_id].append(websocket)
        
        # Send current progress if available
        if progress_id in self.active_crawls:
            try:
                data = self.active_crawls[progress_id].copy()
                data['progressId'] = progress_id
                
                if 'start_time' in data and hasattr(data['start_time'], 'isoformat'):
                    data['start_time'] = data['start_time'].isoformat()
                
                message = {
                    "type": "crawl_progress",
                    "data": data
                }
                await websocket.send_json(message)
            except Exception as e:
                print(f"Error sending initial progress: {e}")
        else:
            try:
                await websocket.send_json({
                    "type": "connection_established",
                    "data": {"progressId": progress_id, "status": "waiting"}
                })
            except Exception as e:
                print(f"Error sending connection confirmation: {e}")
    
    def remove_websocket(self, progress_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
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

@router.get("/knowledge-items")
async def list_knowledge_items():
    """List all knowledge base items."""
    try:
        supabase_client = get_supabase_client()
        
        response = supabase_client.table("crawled_pages").select("*").order("created_at", desc=True).execute()
        
        knowledge_items = []
        for item in response.data:
            knowledge_items.append({
                "id": item["id"],
                "title": item.get("title", "Untitled"),
                "url": item.get("url"),
                "content": item.get("content", ""),
                "source_type": item.get("source_type", "web"),
                "knowledge_type": item.get("knowledge_type", "general"),
                "tags": item.get("tags", []),
                "metadata": item.get("metadata", {}),
                "created_at": item["created_at"],
                "updated_at": item["updated_at"]
            })
        
        return knowledge_items
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.delete("/knowledge-items/{item_id}")
async def delete_knowledge_item(item_id: int):
    """Delete a knowledge base item."""
    try:
        supabase_client = get_supabase_client()
        
        response = supabase_client.table("crawled_pages").delete().eq("id", item_id).execute()
        
        return {"message": "Knowledge item deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/crawl-url")
async def crawl_url(request: CrawlRequest):
    """Initiate URL crawling with progress tracking."""
    try:
        # Generate unique progress ID
        progress_id = secrets.token_hex(16)
        
        # Start tracking progress
        progress_manager.start_crawl(progress_id, {
            'url': request.url,
            'knowledge_type': request.knowledge_type,
            'tags': request.tags
        })
        
        # Start background crawling task
        asyncio.create_task(_crawl_url_background(progress_id, request))
        
        return {
            "progressId": progress_id,
            "status": "started",
            "message": "Crawling started. Connect to WebSocket for progress updates."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

async def _crawl_url_background(progress_id: str, request: CrawlRequest):
    """Background task to actually crawl the URL with progress updates."""
    try:
        # Update progress: Starting
        await progress_manager.update_progress(progress_id, {
            'percentage': 10,
            'currentUrl': request.url,
            'log': f'Starting crawl of {request.url}'
        })
        
        # Simulate crawling process with progress updates
        # In reality, this would use crawl4ai or similar library
        
        await progress_manager.update_progress(progress_id, {
            'percentage': 30,
            'log': 'Analyzing page structure...'
        })
        
        await asyncio.sleep(2)  # Simulate processing time
        
        await progress_manager.update_progress(progress_id, {
            'percentage': 60,
            'log': 'Extracting content...'
        })
        
        await asyncio.sleep(2)
        
        await progress_manager.update_progress(progress_id, {
            'percentage': 80,
            'log': 'Processing and storing content...'
        })
        
        # Store in database (simplified)
        supabase_client = get_supabase_client()
        
        # In reality, you'd extract actual content here
        content_data = {
            "url": request.url,
            "title": f"Page from {request.url}",
            "content": f"Sample content from {request.url}",
            "source_type": "web",
            "knowledge_type": request.knowledge_type,
            "tags": request.tags,
            "metadata": {"crawl_id": progress_id}
        }
        
        response = supabase_client.table("crawled_pages").insert(content_data).execute()
        
        await progress_manager.complete_crawl(progress_id, {
            'chunksStored': 1,
            'wordCount': 100,
            'log': 'Crawling completed successfully!'
        })
        
    except Exception as e:
        await progress_manager.error_crawl(progress_id, str(e))

@router.post("/upload-document")
async def upload_document(
    file: UploadFile = File(...),
    knowledge_type: str = Form("general"),
    tags: str = Form("[]")
):
    """Upload and process a document."""
    try:
        # Parse tags
        tag_list = json.loads(tags) if tags else []
        
        # Read file content
        content = await file.read()
        
        # Store in database
        supabase_client = get_supabase_client()
        
        content_data = {
            "url": f"file://{file.filename}",
            "title": file.filename,
            "content": content.decode('utf-8', errors='ignore'),
            "source_type": "document",
            "knowledge_type": knowledge_type,
            "tags": tag_list,
            "metadata": {"file_size": len(content), "content_type": file.content_type}
        }
        
        response = supabase_client.table("crawled_pages").insert(content_data).execute()
        
        return {"message": "Document uploaded successfully", "id": response.data[0]["id"]}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/rag-query")
async def perform_rag_query(query: str, source: Optional[str] = None, match_count: int = 5):
    """Perform a RAG query on the knowledge base."""
    try:
        supabase_client = get_supabase_client()
        
        # Simple text search for now (in reality, you'd use vector similarity)
        query_builder = supabase_client.table("crawled_pages").select("*")
        
        if source:
            query_builder = query_builder.ilike("url", f"%{source}%")
        
        # Text search in content
        query_builder = query_builder.ilike("content", f"%{query}%")
        
        response = query_builder.limit(match_count).execute()
        
        results = []
        for item in response.data:
            results.append({
                "id": item["id"],
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", "")[:500] + "..." if len(item.get("content", "")) > 500 else item.get("content", ""),
                "source_type": item.get("source_type", ""),
                "knowledge_type": item.get("knowledge_type", ""),
                "relevance_score": 0.8  # Placeholder score
            })
        
        return {
            "query": query,
            "results": results,
            "total_results": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.websocket("/crawl-progress/{progress_id}")
async def websocket_crawl_progress(websocket: WebSocket, progress_id: str):
    """WebSocket endpoint for tracking specific crawl progress."""
    await progress_manager.add_websocket(progress_id, websocket)
    
    try:
        while True:
            # Keep connection alive with ping
            await asyncio.sleep(1)
            await websocket.send_json({"type": "ping"})
            
    except WebSocketDisconnect:
        progress_manager.remove_websocket(progress_id, websocket)
    except Exception as e:
        print(f"WebSocket error for progress {progress_id}: {e}")
        progress_manager.remove_websocket(progress_id, websocket)
        try:
            await websocket.close()
        except:
            pass

@router.get("/rag/sources")
async def get_available_sources():
    """Get all available knowledge sources for filtering."""
    try:
        supabase_client = get_supabase_client()
        
        # Get unique sources
        response = supabase_client.table("crawled_pages").select("url", "knowledge_type", "tags", "source_type").execute()
        
        sources = set()
        knowledge_types = set()
        all_tags = set()
        source_types = set()
        
        for item in response.data:
            if item.get("url"):
                from urllib.parse import urlparse
                domain = urlparse(item["url"]).netloc
                if domain:
                    sources.add(domain)
            
            if item.get("knowledge_type"):
                knowledge_types.add(item["knowledge_type"])
            
            if item.get("source_type"):
                source_types.add(item["source_type"])
            
            if item.get("tags"):
                all_tags.update(item["tags"])
        
        return {
            "sources": {
                "domains": sorted(list(sources)),
                "knowledge_types": sorted(list(knowledge_types)),
                "tags": sorted(list(all_tags)),
                "source_types": sorted(list(source_types))
            },
            "statistics": {
                "total_items": len(response.data),
                "total_sources": len(sources),
                "last_updated": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/health")
async def knowledge_health():
    """Health check for knowledge API."""
    return {"status": "healthy", "service": "knowledge"} 