"""
Projects API endpoints for Archon

Handles:
- Project management (CRUD operations)
- Task management with hierarchical structure
- Streaming project creation with DocsAgent integration
- WebSocket progress updates for project creation
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import asyncio
import secrets
from datetime import datetime
import json

from ..utils import get_supabase_client
import logging
from ..logfire_config import get_logger

# Get logfire logger for this module - use logfire directly like MCP server does
from ..logfire_config import logfire
logfire_logger = logfire

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["projects"])

class CreateProjectRequest(BaseModel):
    title: str
    description: Optional[str] = None
    github_repo: Optional[str] = None
    color: Optional[str] = 'blue'
    icon: Optional[str] = 'Briefcase'
    prd: Optional[Dict[str, Any]] = None
    docs: Optional[List[Any]] = None
    features: Optional[List[Any]] = None
    data: Optional[List[Any]] = None
    technical_sources: Optional[List[str]] = None  # List of knowledge source IDs
    business_sources: Optional[List[str]] = None   # List of knowledge source IDs

class UpdateProjectRequest(BaseModel):
    title: Optional[str] = None
    github_repo: Optional[str] = None
    prd: Optional[Dict[str, Any]] = None
    docs: Optional[List[Any]] = None
    features: Optional[List[Any]] = None
    data: Optional[List[Any]] = None
    technical_sources: Optional[List[str]] = None  # List of knowledge source IDs
    business_sources: Optional[List[str]] = None   # List of knowledge source IDs

class CreateTaskRequest(BaseModel):
    project_id: str
    parent_task_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: Optional[str] = 'todo'
    assignee: Optional[str] = 'User'
    task_order: Optional[int] = 0
    feature: Optional[str] = None

class ProjectCreationProgressData(BaseModel):
    progressId: str
    status: str
    percentage: int
    step: Optional[str] = None
    currentStep: Optional[str] = None
    eta: Optional[str] = None
    error: Optional[str] = None
    logs: List[str] = []
    project: Optional[Dict[str, Any]] = None
    duration: Optional[str] = None

class ProjectCreationProgressManager:
    """Manages project creation progress tracking and WebSocket streaming."""
    
    def __init__(self):
        self.active_creations: Dict[str, Dict[str, Any]] = {}
        self.progress_websockets: Dict[str, List[WebSocket]] = {}
    
    def start_creation(self, progress_id: str, initial_data: Dict[str, Any]) -> None:
        """Start tracking a new project creation operation."""
        self.active_creations[progress_id] = {
            'status': 'starting',
            'percentage': 0,
            'start_time': datetime.now(),
            'logs': ['🚀 Starting project creation...'],
            'step': 'initialization',
            **initial_data
        }
        
    async def update_progress(self, progress_id: str, update_data: Dict[str, Any]) -> None:
        """Update creation progress and notify connected clients."""
        if progress_id not in self.active_creations:
            return
        
        # Update progress data
        self.active_creations[progress_id].update(update_data)
        
        # Add log if provided
        if 'log' in update_data:
            self.active_creations[progress_id]['logs'].append(update_data['log'])
            # Keep only last 50 logs
            if len(self.active_creations[progress_id]['logs']) > 50:
                self.active_creations[progress_id]['logs'] = self.active_creations[progress_id]['logs'][-50:]
        
        # Broadcast to connected WebSocket clients
        await self._broadcast_progress(progress_id)
    
    async def complete_creation(self, progress_id: str, completion_data: Dict[str, Any]) -> None:
        """Mark a project creation as completed and send final update."""
        if progress_id not in self.active_creations:
            return
        
        completion_data.update({
            'status': 'completed',
            'percentage': 100,
            'step': 'finished',
            'log': '✅ Project creation completed successfully!',
            'duration': str(datetime.now() - self.active_creations[progress_id]['start_time'])
        })
        
        self.active_creations[progress_id].update(completion_data)
        await self._broadcast_progress(progress_id)
        
        # Clean up after a delay
        await asyncio.sleep(5)
        if progress_id in self.active_creations:
            del self.active_creations[progress_id]
    
    async def error_creation(self, progress_id: str, error_message: str) -> None:
        """Mark a project creation as failed and send error update."""
        if progress_id not in self.active_creations:
            return
        
        self.active_creations[progress_id].update({
            'status': 'error',
            'error': error_message,
            'log': f'❌ Error: {error_message}',
            'step': 'failed'
        })
        
        await self._broadcast_progress(progress_id)
    
    async def add_websocket(self, progress_id: str, websocket: WebSocket) -> None:
        """Add a WebSocket connection for progress updates."""
        await websocket.accept()
        
        if progress_id not in self.progress_websockets:
            self.progress_websockets[progress_id] = []
        
        self.progress_websockets[progress_id].append(websocket)
        
        # Send current progress if available
        if progress_id in self.active_creations:
            try:
                data = self.active_creations[progress_id].copy()
                data['progressId'] = progress_id
                
                if 'start_time' in data and hasattr(data['start_time'], 'isoformat'):
                    data['start_time'] = data['start_time'].isoformat()
                
                message = {
                    "type": "project_progress",
                    "data": data
                }
                await websocket.send_json(message)
            except Exception as e:
                print(f"Error sending initial project creation progress: {e}")
        else:
            try:
                await websocket.send_json({
                    "type": "connection_established",
                    "data": {"progressId": progress_id, "status": "waiting"}
                })
            except Exception as e:
                print(f"Error sending project creation connection confirmation: {e}")
    
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
        
        progress_data = self.active_creations.get(progress_id, {}).copy()
        progress_data['progressId'] = progress_id
        
        if 'start_time' in progress_data and hasattr(progress_data['start_time'], 'isoformat'):
            progress_data['start_time'] = progress_data['start_time'].isoformat()
        
        message = {
            "type": "project_progress",
            "data": progress_data
        }
        
        if progress_data.get('status') == 'completed':
            message["type"] = "project_completed"
        elif progress_data.get('status') == 'error':
            message["type"] = "project_error"
        
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

# Global project creation progress manager
project_creation_manager = ProjectCreationProgressManager()

# WebSocket Connection Manager for Task Updates
class TaskUpdateManager:
    def __init__(self):
        self.project_connections: Dict[str, List[WebSocket]] = {}
        self.task_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect_to_project(self, websocket: WebSocket, project_id: str):
        """Connect a WebSocket to receive updates for a specific project's tasks"""
        with logfire_logger.span("task_websocket_connect") as span:
            span.set_attribute("project_id", project_id)
            
            try:
                await websocket.accept()
                logfire_logger.info("Task WebSocket connected", project_id=project_id)
                
                if project_id not in self.project_connections:
                    self.project_connections[project_id] = []
                
                self.project_connections[project_id].append(websocket)
                span.set_attribute("success", True)
                span.set_attribute("total_connections", len(self.project_connections[project_id]))
                
            except Exception as e:
                logfire_logger.error("Failed to connect task WebSocket", project_id=project_id, error=str(e))
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise
    
    def disconnect_from_project(self, websocket: WebSocket, project_id: str):
        """Disconnect a WebSocket from project task updates"""
        if project_id in self.project_connections:
            try:
                self.project_connections[project_id].remove(websocket)
                if not self.project_connections[project_id]:
                    del self.project_connections[project_id]
                logfire_logger.info("Task WebSocket disconnected", project_id=project_id)
            except ValueError:
                pass  # WebSocket not in list
    
    async def broadcast_task_update(self, project_id: str, event_type: str, task_data: Dict[str, Any]):
        """Broadcast a task update to all connected clients for a project"""
        with logfire_logger.span("task_websocket_broadcast") as span:
            span.set_attribute("project_id", project_id)
            span.set_attribute("event_type", event_type)
            span.set_attribute("task_id", task_data.get("id"))
            
            if project_id not in self.project_connections:
                span.set_attribute("connections", 0)
                return
            
            connections = self.project_connections[project_id][:]
            message = {
                "type": event_type,
                "data": task_data,
                "timestamp": datetime.now().isoformat(),
                "project_id": project_id
            }
            
            disconnected = []
            successful_broadcasts = 0
            
            for websocket in connections:
                try:
                    await websocket.send_json(message)
                    successful_broadcasts += 1
                except Exception as e:
                    logfire_logger.warning("Failed to send task update to WebSocket", error=str(e))
                    disconnected.append(websocket)
            
            # Remove disconnected WebSockets
            for ws in disconnected:
                self.disconnect_from_project(ws, project_id)
            
            logfire_logger.info("Task update broadcasted", 
                          project_id=project_id, 
                          event_type=event_type,
                          successful_broadcasts=successful_broadcasts,
                          failed_broadcasts=len(disconnected))
            
            span.set_attribute("successful_broadcasts", successful_broadcasts)
            span.set_attribute("failed_broadcasts", len(disconnected))

# Global task update manager
task_update_manager = TaskUpdateManager()

@router.get("/projects")
async def list_projects():
    """List all projects."""
    with logfire_logger.span("api_list_projects") as span:
        span.set_attribute("endpoint", "/api/projects")
        span.set_attribute("method", "GET")
        
        try:
            logfire_logger.info("Listing all projects")
            supabase_client = get_supabase_client()
            
            response = supabase_client.table("projects").select("*").order("created_at", desc=True).execute()
            
            projects = []
            for project in response.data:
                # Get linked sources for this project
                technical_sources = []
                business_sources = []
                
                try:
                    sources_response = supabase_client.table("project_sources").select("source_id, notes").eq("project_id", project["id"]).execute()
                    for source_link in sources_response.data:
                        if source_link.get("notes") == "technical":
                            technical_sources.append(source_link["source_id"])
                        elif source_link.get("notes") == "business":
                            business_sources.append(source_link["source_id"])
                except Exception as e:
                    logger.warning(f"Failed to retrieve linked sources for project {project['id']}: {e}")
                
                projects.append({
                    "id": project["id"],
                    "title": project["title"],
                    "github_repo": project.get("github_repo"),
                    "created_at": project["created_at"],
                    "updated_at": project["updated_at"],
                    "prd": project.get("prd", {}),
                    "docs": project.get("docs", []),
                    "features": project.get("features", []),
                    "data": project.get("data", []),
                    "technical_sources": technical_sources,
                    "business_sources": business_sources
                })
            
            logfire_logger.info("Projects listed successfully", count=len(projects))
            span.set_attribute("project_count", len(projects))
            
            return projects
            
        except Exception as e:
            logfire_logger.error("Failed to list projects", error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/projects")
async def create_project(request: CreateProjectRequest):
    """Create a new project with streaming progress."""
    with logfire_logger.span("api_create_project") as span:
        span.set_attribute("endpoint", "/api/projects")
        span.set_attribute("method", "POST")
        span.set_attribute("title", request.title)
        span.set_attribute("has_github_repo", request.github_repo is not None)
        span.set_attribute("has_technical_sources", request.technical_sources is not None)
        span.set_attribute("has_business_sources", request.business_sources is not None)
        
        try:
            logfire_logger.info("Creating new project", title=request.title, github_repo=request.github_repo)
            
            # Generate unique progress ID for this creation
            progress_id = secrets.token_hex(16)
            span.set_attribute("progress_id", progress_id)
            
            # Start tracking creation progress
            project_creation_manager.start_creation(progress_id, {
                'title': request.title,
                'description': request.description or '',
                'github_repo': request.github_repo
            })
            
            # Start background task to actually create the project
            asyncio.create_task(_create_project_background(progress_id, request))
            
            logfire_logger.info("Project creation started", progress_id=progress_id, title=request.title)
            span.set_attribute("success", True)
            
            # Return progress_id immediately so frontend can connect to WebSocket
            return {
                "progress_id": progress_id,
                "status": "started",
                "message": "Project creation started. Connect to WebSocket for progress updates."
            }
            
        except Exception as e:
            logfire_logger.error("Failed to start project creation", error=str(e), title=request.title)
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail={'error': str(e)})

async def _create_project_background(progress_id: str, request: CreateProjectRequest):
    """Background task to actually create the project with progress updates."""
    try:
        # Update progress: Starting
        await project_creation_manager.update_progress(progress_id, {
            'percentage': 10,
            'step': 'initializing_agents',
            'log': '🤖 Initializing DocsAgent...'
        })
        
        # Get Supabase client
        supabase_client = get_supabase_client()
        
        # Update progress: DocsAgent processing
        await project_creation_manager.update_progress(progress_id, {
            'percentage': 30,
            'step': 'generating_docs',
            'log': '📝 Generating comprehensive documentation...'
        })
        
        # Try to use DocsAgent for enhanced documentation
        generated_prd = {}
        
        try:
            # Import DocsAgent (lazy import to avoid startup issues)
            from ..agents.docs_agent import DocsAgent
            
            await project_creation_manager.update_progress(progress_id, {
                'percentage': 50,
                'step': 'processing_requirements',
                'log': '🧠 AI is analyzing project requirements...'
            })
            
            # Initialize and use DocsAgent
            docs_agent = DocsAgent()
            
            await project_creation_manager.update_progress(progress_id, {
                'percentage': 70,
                'step': 'ai_generation',
                'log': '✨ AI is creating project documentation...'
            })
            
            # Generate comprehensive PRD
            agent_result = await docs_agent.create_prd(
                project_title=request.title,
                project_description=request.description or 'A new project created in Archon',
                requirements=[
                    "User-friendly interface",
                    "Secure data handling", 
                    "Scalable architecture"
                ] if not request.description else [request.description],
                context={
                    "github_repo": request.github_repo,
                    "created_via": "archon_ui"
                }
            )
            
            # Extract PRD content from agent result
            generated_prd = agent_result.content if hasattr(agent_result, 'content') else {}
            
            await project_creation_manager.update_progress(progress_id, {
                'percentage': 85,
                'step': 'finalizing_docs',
                'log': f'📋 Generated comprehensive PRD with {len(generated_prd.keys()) if generated_prd else 0} sections'
            })
            
        except ImportError:
            await project_creation_manager.update_progress(progress_id, {
                'percentage': 60,
                'step': 'fallback_mode',
                'log': '⚠️ DocsAgent not available, using basic project structure'
            })
        except Exception as e:
            await project_creation_manager.update_progress(progress_id, {
                'percentage': 60,
                'step': 'ai_fallback',
                'log': f'⚠️ AI generation failed ({str(e)}), using basic structure'
            })
        
        # Create project data structure
        project_data = {
            "title": request.title,
            "prd": generated_prd or request.prd or {},
            "docs": [],
            "features": [],
            "data": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        if request.github_repo:
            project_data["github_repo"] = request.github_repo
        
        await project_creation_manager.update_progress(progress_id, {
            'percentage': 95,
            'step': 'saving_to_database',
            'log': '💾 Saving project to database...'
        })
        
        # Insert project into database
        response = supabase_client.table("projects").insert(project_data).execute()
        
        if response.data:
            project = response.data[0]
            project_id = project["id"]
            
            # Save technical and business sources to project_sources table
            if request.technical_sources or request.business_sources:
                await project_creation_manager.update_progress(progress_id, {
                    'percentage': 97,
                    'step': 'linking_sources',
                    'log': '🔗 Linking knowledge sources...'
                })
                
                # Insert technical sources
                if request.technical_sources:
                    for source_id in request.technical_sources:
                        try:
                            supabase_client.table("project_sources").insert({
                                "project_id": project_id,
                                "source_id": source_id,
                                "created_by": "system",
                                "notes": "technical"
                            }).execute()
                        except Exception as e:
                            logger.warning(f"Failed to link technical source {source_id}: {e}")
                
                # Insert business sources  
                if request.business_sources:
                    for source_id in request.business_sources:
                        try:
                            supabase_client.table("project_sources").insert({
                                "project_id": project_id,
                                "source_id": source_id,
                                "created_by": "system", 
                                "notes": "business"
                            }).execute()
                        except Exception as e:
                            logger.warning(f"Failed to link business source {source_id}: {e}")
            
            # Get linked sources for response
            technical_sources = []
            business_sources = []
            
            try:
                sources_response = supabase_client.table("project_sources").select("source_id, notes").eq("project_id", project_id).execute()
                for source_link in sources_response.data:
                    if source_link.get("notes") == "technical":
                        technical_sources.append(source_link["source_id"])
                    elif source_link.get("notes") == "business":
                        business_sources.append(source_link["source_id"])
            except Exception as e:
                logger.warning(f"Failed to retrieve linked sources: {e}")
            
            # Complete the creation process
            await project_creation_manager.complete_creation(progress_id, {
                'project': {
                    "id": project["id"],
                    "title": project["title"],
                    "github_repo": project.get("github_repo"),
                    "created_at": project["created_at"],
                    "updated_at": project["updated_at"],
                    "prd": project.get("prd", {}),
                    "docs": project.get("docs", []),
                    "features": project.get("features", []),
                    "data": project.get("data", []),
                    "technical_sources": technical_sources,
                    "business_sources": business_sources
                }
            })
        else:
            await project_creation_manager.error_creation(progress_id, "Failed to save project to database")
            
    except Exception as e:
        await project_creation_manager.error_creation(progress_id, str(e))

@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get a specific project."""
    with logfire_logger.span("api_get_project") as span:
        span.set_attribute("endpoint", f"/api/projects/{project_id}")
        span.set_attribute("method", "GET")
        span.set_attribute("project_id", project_id)
        
        try:
            logfire_logger.info("Getting project", project_id=project_id)
            supabase_client = get_supabase_client()
            
            response = supabase_client.table("projects").select("*").eq("id", project_id).execute()
            
            if response.data:
                project = response.data[0]
                
                # Get linked sources
                technical_sources = []
                business_sources = []
                
                try:
                    # Get source IDs from project_sources table
                    sources_response = supabase_client.table("project_sources").select("source_id, notes").eq("project_id", project["id"]).execute()
                    
                    # Collect source IDs by type
                    technical_source_ids = []
                    business_source_ids = []
                    
                    for source_link in sources_response.data:
                        if source_link.get("notes") == "technical":
                            technical_source_ids.append(source_link["source_id"])
                        elif source_link.get("notes") == "business":
                            business_source_ids.append(source_link["source_id"])
                    
                    # Fetch full source objects from sources table
                    if technical_source_ids:
                        tech_sources_response = supabase_client.table("sources").select("*").in_("source_id", technical_source_ids).execute()
                        technical_sources = tech_sources_response.data
                    
                    if business_source_ids:
                        biz_sources_response = supabase_client.table("sources").select("*").in_("source_id", business_source_ids).execute()
                        business_sources = biz_sources_response.data
                        
                except Exception as e:
                    logger.warning(f"Failed to retrieve linked sources for project {project['id']}: {e}")
                
                logfire_logger.info("Project retrieved successfully", project_id=project_id, title=project["title"])
                span.set_attribute("success", True)
                span.set_attribute("title", project["title"])
                
                return {
                    "id": project["id"],
                    "title": project["title"],
                    "github_repo": project.get("github_repo"),
                    "created_at": project["created_at"],
                    "updated_at": project["updated_at"],
                    "prd": project.get("prd", {}),
                    "docs": project.get("docs", []),
                    "features": project.get("features", []),
                    "data": project.get("data", []),
                    "technical_sources": technical_sources,
                    "business_sources": business_sources
                }
            else:
                logfire_logger.warning("Project not found", project_id=project_id)
                span.set_attribute("found", False)
                raise HTTPException(status_code=404, detail={'error': f'Project with ID {project_id} not found'})
                    
        except HTTPException:
            raise
        except Exception as e:
            logfire_logger.error("Failed to get project", error=str(e), project_id=project_id)
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail={'error': str(e)})

@router.put("/projects/{project_id}")
async def update_project(project_id: str, request: UpdateProjectRequest):
    """Update a project with comprehensive Logfire monitoring."""
    with logfire_logger.span("api_update_project") as span:
        span.set_attribute("endpoint", f"/projects/{project_id}")
        span.set_attribute("method", "PUT")
        span.set_attribute("project_id", project_id)
        span.set_attribute("has_technical_sources", request.technical_sources is not None)
        span.set_attribute("has_business_sources", request.business_sources is not None)
        
        if request.technical_sources is not None:
            span.set_attribute("technical_sources_count", len(request.technical_sources))
        if request.business_sources is not None:
            span.set_attribute("business_sources_count", len(request.business_sources))
        
        try:
            supabase_client = get_supabase_client()
            
            # Build update data with monitoring
            with logfire_logger.span("prepare_update_data") as prep_span:
                update_data = {"updated_at": datetime.now().isoformat()}
                
                if request.title is not None:
                    update_data["title"] = request.title
                if request.github_repo is not None:
                    update_data["github_repo"] = request.github_repo
                if request.prd is not None:
                    update_data["prd"] = request.prd
                if request.docs is not None:
                    update_data["docs"] = request.docs
                if request.features is not None:
                    update_data["features"] = request.features
                if request.data is not None:
                    update_data["data"] = request.data
                
                prep_span.set_attribute("update_fields_count", len(update_data) - 1)  # -1 for updated_at
            
            # Update project in database with monitoring
            with logfire_logger.span("update_project_record") as update_span:
                response = supabase_client.table("projects").update(update_data).eq("id", project_id).execute()
                
                if not response.data:
                    update_span.set_attribute("success", False)
                    raise HTTPException(status_code=404, detail={'error': f'Project with ID {project_id} not found'})
                
                project = response.data[0]
                update_span.set_attribute("success", True)
            
            # Handle technical_sources with monitoring
            if request.technical_sources is not None:
                with logfire_logger.span("update_technical_sources") as tech_span:
                    tech_span.set_attribute("source_count", len(request.technical_sources))
                    
                    # Remove existing technical sources
                    supabase_client.table("project_sources").delete().eq("project_id", project_id).eq("notes", "technical").execute()
                    
                    # Add new technical sources
                    successful_links = 0
                    failed_links = 0
                    
                    for source_id in request.technical_sources:
                        try:
                            supabase_client.table("project_sources").insert({
                                "project_id": project_id,
                                "source_id": source_id,
                                "notes": "technical"
                            }).execute()
                            successful_links += 1
                        except Exception as e:
                            failed_links += 1
                            logger.warning(f"Failed to link technical source {source_id}: {e}")
                            logfire_logger.warning(f"Technical source link failed", source_id=source_id, error=str(e))
                    
                    tech_span.set_attribute("successful_links", successful_links)
                    tech_span.set_attribute("failed_links", failed_links)
                    logfire_logger.info(f"Technical sources updated: {successful_links} success, {failed_links} failed")
            
            # Handle business_sources with monitoring
            if request.business_sources is not None:
                with logfire_logger.span("update_business_sources") as biz_span:
                    biz_span.set_attribute("source_count", len(request.business_sources))
                    
                    # Remove existing business sources
                    supabase_client.table("project_sources").delete().eq("project_id", project_id).eq("notes", "business").execute()
                    
                    # Add new business sources
                    successful_links = 0
                    failed_links = 0
                    
                    for source_id in request.business_sources:
                        try:
                            supabase_client.table("project_sources").insert({
                                "project_id": project_id,
                                "source_id": source_id,
                                "notes": "business"
                            }).execute()
                            successful_links += 1
                        except Exception as e:
                            failed_links += 1
                            logger.warning(f"Failed to link business source {source_id}: {e}")
                            logfire_logger.warning(f"Business source link failed", source_id=source_id, error=str(e))
                    
                    biz_span.set_attribute("successful_links", successful_links)
                    biz_span.set_attribute("failed_links", failed_links)
                    logfire_logger.info(f"Business sources updated: {successful_links} success, {failed_links} failed")
            
            # Get linked sources for response with monitoring
            technical_sources = []
            business_sources = []
            
            with logfire_logger.span("fetch_linked_sources_for_response") as fetch_span:
                try:
                    # Get source IDs from project_sources table
                    sources_response = supabase_client.table("project_sources").select("source_id, notes").eq("project_id", project_id).execute()
                    
                    # Collect source IDs by type
                    technical_source_ids = []
                    business_source_ids = []
                    
                    for source_link in sources_response.data:
                        if source_link.get("notes") == "technical":
                            technical_source_ids.append(source_link["source_id"])
                        elif source_link.get("notes") == "business":
                            business_source_ids.append(source_link["source_id"])
                    
                    fetch_span.set_attribute("technical_ids_found", len(technical_source_ids))
                    fetch_span.set_attribute("business_ids_found", len(business_source_ids))
                    
                    # Fetch full source objects from sources table
                    if technical_source_ids:
                        tech_sources_response = supabase_client.table("sources").select("*").in_("source_id", technical_source_ids).execute()
                        technical_sources = tech_sources_response.data
                    
                    if business_source_ids:
                        biz_sources_response = supabase_client.table("sources").select("*").in_("source_id", business_source_ids).execute()
                        business_sources = biz_sources_response.data
                    
                    fetch_span.set_attribute("technical_objects_fetched", len(technical_sources))
                    fetch_span.set_attribute("business_objects_fetched", len(business_sources))
                        
                except Exception as e:
                    fetch_span.set_attribute("success", False)
                    fetch_span.set_attribute("error", str(e))
                    logger.warning(f"Failed to retrieve linked sources: {e}")
                    logfire_logger.warning(f"Failed to fetch linked sources for response", project_id=project_id, error=str(e))
            
            span.set_attribute("success", True)
            span.set_attribute("final_technical_sources", len(technical_sources))
            span.set_attribute("final_business_sources", len(business_sources))
            
            logfire_logger.info(f"Project updated successfully", 
                              project_id=project_id, 
                              technical_sources=len(technical_sources),
                              business_sources=len(business_sources))
            
            return {
                "id": project["id"],
                "title": project["title"],
                "github_repo": project.get("github_repo"),
                "created_at": project["created_at"],
                "updated_at": project["updated_at"],
                "prd": project.get("prd", {}),
                "docs": project.get("docs", []),
                "features": project.get("features", []),
                "data": project.get("data", []),
                "technical_sources": technical_sources,
                "business_sources": business_sources
            }
                
        except HTTPException:
            span.set_attribute("success", False)
            span.set_attribute("error", "HTTP Exception")
            raise
        except Exception as e:
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            logfire_logger.error(f"Project update failed", project_id=project_id, error=str(e))
            raise HTTPException(status_code=500, detail={'error': str(e)})

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and all its tasks."""
    with logfire_logger.span("api_delete_project") as span:
        span.set_attribute("endpoint", f"/api/projects/{project_id}")
        span.set_attribute("method", "DELETE")
        span.set_attribute("project_id", project_id)
        
        try:
            logfire_logger.info("Deleting project", project_id=project_id)
            supabase_client = get_supabase_client()
            
            # Delete project (tasks will be cascade deleted due to foreign key)
            response = supabase_client.table("projects").delete().eq("id", project_id).execute()
            
            logfire_logger.info("Project deleted successfully", project_id=project_id)
            span.set_attribute("success", True)
            
            return {"message": "Project deleted successfully"}
            
        except Exception as e:
            logfire_logger.error("Failed to delete project", error=str(e), project_id=project_id)
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/projects/{project_id}/features")
async def get_project_features(project_id: str):
    """Get features from a project's features JSONB field."""
    with logfire_logger.span("api_get_project_features") as span:
        span.set_attribute("endpoint", f"/api/projects/{project_id}/features")
        span.set_attribute("method", "GET")
        span.set_attribute("project_id", project_id)
        
        try:
            logfire_logger.info("Getting project features", project_id=project_id)
            supabase_client = get_supabase_client()
            
            response = supabase_client.table("projects").select("features").eq("id", project_id).single().execute()
            
            if not response.data:
                logfire_logger.warning("Project not found for features", project_id=project_id)
                span.set_attribute("found", False)
                raise HTTPException(status_code=404, detail={'error': 'Project not found'})
            
            features = response.data.get("features", [])
            
            # Extract feature labels for dropdown options
            feature_options = []
            for feature in features:
                if isinstance(feature, dict) and "data" in feature and "label" in feature["data"]:
                    feature_options.append({
                        "id": feature.get("id", ""),
                        "label": feature["data"]["label"],
                        "type": feature["data"].get("type", ""),
                        "feature_type": feature.get("type", "page")
                    })
            
            logfire_logger.info("Project features retrieved", project_id=project_id, feature_count=len(feature_options))
            span.set_attribute("feature_count", len(feature_options))
            
            return {
                "features": feature_options,
                "count": len(feature_options)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logfire_logger.error("Failed to get project features", error=str(e), project_id=project_id)
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/projects/{project_id}/tasks")
async def list_project_tasks(project_id: str, include_archived: bool = False):
    """List all tasks for a specific project. By default, filters out archived tasks."""
    with logfire_logger.span("api_list_project_tasks") as span:
        span.set_attribute("endpoint", f"/api/projects/{project_id}/tasks")
        span.set_attribute("method", "GET")
        span.set_attribute("project_id", project_id)
        span.set_attribute("include_archived", include_archived)
        
        try:
            logfire_logger.info("Listing project tasks", project_id=project_id, include_archived=include_archived)
            supabase_client = get_supabase_client()
            
            # Build query to optionally exclude archived tasks
            query = supabase_client.table("tasks").select("*").eq("project_id", project_id)
            
            # Only include non-archived tasks by default (handle NULL as False for backwards compatibility)
            if not include_archived:
                query = query.or_("archived.is.null,archived.eq.false")
            
            response = query.order("task_order", desc=False).order("created_at", desc=False).execute()
            
            logfire_logger.info("Project tasks retrieved", project_id=project_id, task_count=len(response.data))
            span.set_attribute("task_count", len(response.data))
            
            return response.data
            
        except Exception as e:
            logfire_logger.error("Failed to list project tasks", error=str(e), project_id=project_id)
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/health")
async def projects_health():
    """Health check for projects API."""
    with logfire_logger.span("api_projects_health") as span:
        span.set_attribute("endpoint", "/api/health")
        span.set_attribute("method", "GET")
        
        logfire_logger.info("Projects health check requested")
        result = {"status": "healthy", "service": "projects"}
        span.set_attribute("status", "healthy")
        
        return result

@router.post("/tasks")
async def create_task(request: CreateTaskRequest):
    """Create a new task with automatic reordering and real-time WebSocket broadcasting."""
    with logfire_logger.span("api_create_task") as span:
        span.set_attribute("endpoint", "/tasks")
        span.set_attribute("method", "POST")
        span.set_attribute("project_id", request.project_id)
        span.set_attribute("title", request.title)
        span.set_attribute("assignee", request.assignee)
        span.set_attribute("status", request.status)
        
        try:
            supabase_client = get_supabase_client()
            
            task_status = request.status or 'todo'
            task_order = request.task_order or 0
            
            # REORDERING LOGIC: If inserting at a specific position, increment existing tasks
            if task_order > 0:
                # Get all tasks in the same project and status with task_order >= new task's order
                existing_tasks_response = supabase_client.table("tasks").select("id, task_order").eq("project_id", request.project_id).eq("status", task_status).gte("task_order", task_order).execute()
                
                if existing_tasks_response.data:
                    logfire_logger.info(f"Reordering {len(existing_tasks_response.data)} existing tasks", 
                                      project_id=request.project_id, 
                                      status=task_status, 
                                      insert_position=task_order)
                    span.set_attribute("tasks_to_reorder", len(existing_tasks_response.data))
                    
                    # Increment task_order for all affected tasks
                    for existing_task in existing_tasks_response.data:
                        new_order = existing_task["task_order"] + 1
                        supabase_client.table("tasks").update({
                            "task_order": new_order,
                            "updated_at": datetime.now().isoformat()
                        }).eq("id", existing_task["id"]).execute()
                        
                        logfire_logger.debug("Reordered task", 
                                           task_id=existing_task["id"], 
                                           old_order=existing_task["task_order"], 
                                           new_order=new_order)
            
            # Create task data
            task_data = {
                "project_id": request.project_id,
                "title": request.title,
                "description": request.description,
                "status": task_status,
                "assignee": request.assignee or 'User',
                "task_order": task_order,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            if request.parent_task_id:
                task_data["parent_task_id"] = request.parent_task_id
            if request.feature:
                task_data["feature"] = request.feature
            
            # Insert task into database
            response = supabase_client.table("tasks").insert(task_data).execute()
            
            if response.data:
                created_task = response.data[0]
                logfire_logger.info("Task created successfully with automatic reordering", 
                                  task_id=created_task["id"], 
                                  project_id=request.project_id,
                                  task_order=task_order)
                span.set_attribute("success", True)
                span.set_attribute("task_id", created_task["id"])
                span.set_attribute("final_task_order", task_order)
                
                # Broadcast real-time update to connected clients
                await task_update_manager.broadcast_task_update(
                    project_id=request.project_id,
                    event_type="task_created",
                    task_data=created_task
                )
                
                return {"message": "Task created successfully", "task": created_task}
            else:
                raise HTTPException(status_code=500, detail="Failed to create task")
                
        except Exception as e:
            logfire_logger.error("Failed to create task", error=str(e), project_id=request.project_id)
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get a specific task by ID."""
    with logfire_logger.span("api_get_task") as span:
        span.set_attribute("endpoint", f"/tasks/{task_id}")
        span.set_attribute("method", "GET")
        span.set_attribute("task_id", task_id)
        
        try:
            supabase_client = get_supabase_client()
            
            # Get task by ID - handle backwards compatibility for archived field
            response = supabase_client.table("tasks").select("*").eq("id", task_id).or_("archived.is.null,archived.eq.false").execute()
            
            if not response.data:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
            task = response.data[0]
            span.set_attribute("project_id", task.get("project_id"))
            span.set_attribute("success", True)
            
            logfire_logger.info("Task retrieved successfully", 
                              task_id=task_id, 
                              project_id=task.get("project_id"))
            
            return task
            
        except HTTPException:
            raise
        except Exception as e:
            logfire_logger.error("Failed to get task", error=str(e), task_id=task_id)
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    assignee: Optional[str] = None
    task_order: Optional[int] = None
    feature: Optional[str] = None

@router.put("/tasks/{task_id}")
async def update_task(task_id: str, request: UpdateTaskRequest):
    """Update a task with real-time WebSocket broadcasting."""
    with logfire_logger.span("api_update_task") as span:
        span.set_attribute("endpoint", f"/tasks/{task_id}")
        span.set_attribute("method", "PUT")
        span.set_attribute("task_id", task_id)
        
        try:
            supabase_client = get_supabase_client()
            
            # First get the current task to get project_id for broadcasting
            current_task_response = supabase_client.table("tasks").select("*").eq("id", task_id).execute()
            if not current_task_response.data:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
            current_task = current_task_response.data[0]
            project_id = current_task["project_id"]
            span.set_attribute("project_id", project_id)
            
            # Build update data
            update_data = {"updated_at": datetime.now().isoformat()}
            
            if request.title is not None:
                update_data["title"] = request.title
                span.set_attribute("updated_title", True)
            if request.description is not None:
                update_data["description"] = request.description
                span.set_attribute("updated_description", True)
            if request.status is not None:
                update_data["status"] = request.status
                span.set_attribute("new_status", request.status)
            if request.assignee is not None:
                update_data["assignee"] = request.assignee
                span.set_attribute("new_assignee", request.assignee)
            if request.task_order is not None:
                update_data["task_order"] = request.task_order
                span.set_attribute("new_task_order", request.task_order)
            if request.feature is not None:
                update_data["feature"] = request.feature
                span.set_attribute("updated_feature", True)
            
            # Update task in database
            response = supabase_client.table("tasks").update(update_data).eq("id", task_id).execute()
            
            if response.data:
                updated_task = response.data[0]
                logfire_logger.info("Task updated successfully", 
                                  task_id=task_id, 
                                  project_id=project_id,
                                  updated_fields=list(update_data.keys()))
                span.set_attribute("success", True)
                
                # Broadcast real-time update to connected clients
                await task_update_manager.broadcast_task_update(
                    project_id=project_id,
                    event_type="task_updated",
                    task_data=updated_task
                )
                
                return {"message": "Task updated successfully", "task": updated_task}
            else:
                raise HTTPException(status_code=500, detail="Failed to update task")
                
        except HTTPException:
            raise
        except Exception as e:
            logfire_logger.error("Failed to update task", error=str(e), task_id=task_id)
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Archive a task (soft delete) with real-time WebSocket broadcasting."""
    with logfire_logger.span("api_archive_task") as span:
        span.set_attribute("endpoint", f"/tasks/{task_id}")
        span.set_attribute("method", "DELETE")
        span.set_attribute("task_id", task_id)
        
        try:
            supabase_client = get_supabase_client()
            
            # First get the task to get project_id for broadcasting
            # Handle backwards compatibility - check for archived field and treat NULL as False
            task_response = supabase_client.table("tasks").select("*").eq("id", task_id).execute()
            if not task_response.data:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
            task_to_archive = task_response.data[0]
            # Check if task is already archived (handle NULL as False for backwards compatibility)
            if task_to_archive.get("archived") is True:
                raise HTTPException(status_code=404, detail=f"Task {task_id} is already archived")
            project_id = task_to_archive["project_id"]
            span.set_attribute("project_id", project_id)
            
            # Archive task using soft delete (set archived=true)
            from datetime import datetime
            archive_data = {
                "archived": True,
                "archived_at": datetime.now().isoformat(),
                "archived_by": "api",  # Could be enhanced to track actual user
                "updated_at": datetime.now().isoformat()
            }
            
            response = supabase_client.table("tasks").update(archive_data).eq("id", task_id).execute()
            
            if response.data:
                archived_task = response.data[0]
                
                # Also archive all subtasks - use OR condition to handle NULL values
                subtasks_response = supabase_client.table("tasks").update(archive_data).eq("parent_task_id", task_id).or_("archived.is.null,archived.eq.false").execute()
                subtasks_count = len(subtasks_response.data) if subtasks_response.data else 0
                
                logfire_logger.info("Task archived successfully", 
                                  task_id=task_id, 
                                  project_id=project_id,
                                  subtasks_archived=subtasks_count)
                span.set_attribute("success", True)
                span.set_attribute("subtasks_archived", subtasks_count)
                
                # Broadcast real-time update to connected clients
                await task_update_manager.broadcast_task_update(
                    project_id=project_id,
                    event_type="task_archived",
                    task_data=archived_task
                )
                
                return {
                    "message": "Task archived successfully", 
                    "task": archived_task,
                    "subtasks_archived": subtasks_count
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to archive task")
                
        except HTTPException:
            raise
        except Exception as e:
            logfire_logger.error("Failed to archive task", error=str(e), task_id=task_id)
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/project-creation-progress/{progress_id}")
async def websocket_project_creation_progress(websocket: WebSocket, progress_id: str):
    """WebSocket endpoint for tracking specific project creation progress."""
    await project_creation_manager.add_websocket(progress_id, websocket)
    
    try:
        while True:
            # Keep connection alive with ping
            await asyncio.sleep(1)
            await websocket.send_json({"type": "ping"})
            
    except WebSocketDisconnect:
        project_creation_manager.remove_websocket(progress_id, websocket)
    except Exception as e:
        print(f"Project creation WebSocket error for progress {progress_id}: {e}")
        project_creation_manager.remove_websocket(progress_id, websocket)
        try:
            await websocket.close()
        except:
            pass

@router.get("/health")
async def projects_health():
    """Health check for projects API."""
    with logfire_logger.span("api_projects_health") as span:
        span.set_attribute("endpoint", "/api/health")
        span.set_attribute("method", "GET")
        
        logfire_logger.info("Projects health check requested")
        result = {"status": "healthy", "service": "projects"}
        span.set_attribute("status", "healthy")
        
        return result

# WebSocket endpoint for real-time task updates
@router.websocket("/projects/{project_id}/tasks/updates")
async def task_updates_websocket(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time task updates for a specific project"""
    await task_update_manager.connect_to_project(websocket, project_id)
    
    try:
        # Send a connection confirmation message
        await websocket.send_json({
            "type": "connection_established",
            "data": {
                "project_id": project_id,
                "message": "Connected to task updates"
            },
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep connection alive - just wait for disconnection
        while True:
            await asyncio.sleep(1)  # Keep connection alive without expecting client messages
                
    except WebSocketDisconnect:
        logfire_logger.info("Task updates WebSocket disconnected during setup", project_id=project_id)
    except Exception as e:
        logfire_logger.error("Unexpected error in task updates WebSocket", project_id=project_id, error=str(e))
    finally:
        task_update_manager.disconnect_from_project(websocket, project_id) 

# MCP CONTEXT MANAGER FOR TASK UPDATES WITH WEBSOCKET BROADCASTING
# Following the same pattern as RAG module

class TaskContext:
    """Minimal context for task MCP calls with WebSocket broadcasting support."""
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.progress_callback = None

@router.put("/mcp/tasks/{task_id}/status")
async def mcp_update_task_status_with_websockets(task_id: str, status: str):
    """Update task status via MCP tools with WebSocket broadcasting using RAG pattern."""
    with logfire_logger.span("mcp_task_status_update") as span:
        span.set_attribute("endpoint", f"/api/mcp/tasks/{task_id}/status")
        span.set_attribute("method", "PUT")
        span.set_attribute("task_id", task_id)
        span.set_attribute("status", status)
        
        try:
            logfire_logger.info("MCP task status update", task_id=task_id, status=status)
            
            # Get task to determine project_id
            supabase_client = get_supabase_client()
            task_response = supabase_client.table("tasks").select("*").eq("id", task_id).execute()
            if not task_response.data:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
            current_task = task_response.data[0]
            project_id = current_task["project_id"]
            span.set_attribute("project_id", project_id)
            
            # Create context for MCP function (like RAG does)
            ctx = TaskContext(project_id)
            
            # Set progress callback for WebSocket broadcasting
            async def websocket_callback(event_type: str, task_data: dict):
                """Callback to broadcast WebSocket updates"""
                await task_update_manager.broadcast_task_update(
                    project_id=project_id,
                    event_type=event_type,
                    task_data=task_data
                )
            
            ctx.progress_callback = websocket_callback
            
            # Import and call MCP function directly with context
            from src.modules.project_module import update_task_status_direct
            result = await update_task_status_direct(ctx, task_id, status)
            
            # Parse result
            if isinstance(result, str):
                result_data = json.loads(result)
            else:
                result_data = result
            
            if not result_data.get("success"):
                raise HTTPException(status_code=500, detail=result_data.get("error", "Unknown error"))
            
            span.set_attribute("success", True)
            logfire_logger.info("Task status updated with WebSocket broadcast", 
                              task_id=task_id, 
                              project_id=project_id, 
                              status=status)
            
            return {"message": "Task status updated successfully", "task": result_data.get("task")}
            
        except HTTPException:
            raise
        except Exception as e:
            logfire_logger.error("Failed to update task status with WebSocket", error=str(e), task_id=task_id)
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e)) 
