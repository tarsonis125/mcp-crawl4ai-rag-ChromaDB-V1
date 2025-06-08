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

# Get logfire logger for this module
logfire_logger = get_logger("projects_api", module="projects_api", service="archon-backend")

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

@router.get("/projects")
async def list_projects():
    """List all projects."""
    try:
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
        
        return projects
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/projects")
async def create_project(request: CreateProjectRequest):
    """Create a new project with streaming progress."""
    # Generate unique progress ID for this creation
    progress_id = secrets.token_hex(16)
    
    # Start tracking creation progress
    project_creation_manager.start_creation(progress_id, {
        'title': request.title,
        'description': request.description or '',
        'github_repo': request.github_repo
    })
    
    # Start background task to actually create the project
    asyncio.create_task(_create_project_background(progress_id, request))
    
    # Return progress_id immediately so frontend can connect to WebSocket
    return {
        "progress_id": progress_id,
        "status": "started",
        "message": "Project creation started. Connect to WebSocket for progress updates."
    }

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
    try:
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
            raise HTTPException(status_code=404, detail={'error': f'Project with ID {project_id} not found'})
                
    except HTTPException:
        raise
    except Exception as e:
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
    try:
        supabase_client = get_supabase_client()
        
        # Delete project (tasks will be cascade deleted due to foreign key)
        response = supabase_client.table("projects").delete().eq("id", project_id).execute()
        
        return {"message": "Project deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/projects/{project_id}/features")
async def get_project_features(project_id: str):
    """Get features from a project's features JSONB field."""
    try:
        supabase_client = get_supabase_client()
        
        response = supabase_client.table("projects").select("features").eq("id", project_id).single().execute()
        
        if not response.data:
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
        
        return {
            "features": feature_options,
            "count": len(feature_options)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/projects/{project_id}/tasks")
async def list_project_tasks(project_id: str):
    """List all tasks for a specific project."""
    try:
        supabase_client = get_supabase_client()
        
        response = supabase_client.table("tasks").select("*").eq("project_id", project_id).order("task_order", desc=False).order("created_at", desc=False).execute()
        
        return response.data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/tasks")
async def create_task(request: CreateTaskRequest):
    """Create a new task."""
    try:
        supabase_client = get_supabase_client()
        
        # Validate assignee
        valid_assignees = ['User', 'Archon', 'AI IDE Agent']
        if request.assignee not in valid_assignees:
            raise HTTPException(
                status_code=400, 
                detail={'error': f"Invalid assignee '{request.assignee}'. Must be one of: {', '.join(valid_assignees)}"}
            )
        
        # Validate status
        valid_statuses = ['todo', 'doing', 'blocked', 'done']
        if request.status not in valid_statuses:
            raise HTTPException(
                status_code=400, 
                detail={'error': f"Invalid status '{request.status}'. Must be one of: {', '.join(valid_statuses)}"}
            )
        
        task_data = {
            "project_id": request.project_id,
            "title": request.title,
            "description": request.description or "",
            "status": request.status,
            "assignee": request.assignee,
            "task_order": request.task_order,
            "sources": [],
            "code_examples": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        if request.parent_task_id:
            task_data["parent_task_id"] = request.parent_task_id
            
        if request.feature:
            task_data["feature"] = request.feature
        
        response = supabase_client.table("tasks").insert(task_data).execute()
        
        if response.data:
            return response.data[0]
        else:
            raise HTTPException(status_code=500, detail={'error': 'Failed to create task'})
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    assignee: Optional[str] = None
    task_order: Optional[int] = None
    feature: Optional[str] = None

@router.put("/tasks/{task_id}")
async def update_task(task_id: str, request: UpdateTaskRequest):
    """Update a task."""
    try:
        supabase_client = get_supabase_client()
        
        update_data = {"updated_at": datetime.now().isoformat()}
        
        if request.title is not None:
            update_data["title"] = request.title
        if request.description is not None:
            update_data["description"] = request.description
        if request.status is not None:
            valid_statuses = ['todo', 'doing', 'blocked', 'done']
            if request.status not in valid_statuses:
                raise HTTPException(
                    status_code=400, 
                    detail={'error': f"Invalid status '{request.status}'. Must be one of: {', '.join(valid_statuses)}"}
                )
            update_data["status"] = request.status
        if request.assignee is not None:
            valid_assignees = ['User', 'Archon', 'AI IDE Agent']
            if request.assignee not in valid_assignees:
                raise HTTPException(
                    status_code=400, 
                    detail={'error': f"Invalid assignee '{request.assignee}'. Must be one of: {', '.join(valid_assignees)}"}
                )
            update_data["assignee"] = request.assignee
        if request.task_order is not None:
            update_data["task_order"] = request.task_order
        if request.feature is not None:
            update_data["feature"] = request.feature
        
        response = supabase_client.table("tasks").update(update_data).eq("id", task_id).execute()
        
        if response.data:
            return response.data[0]
        else:
            raise HTTPException(status_code=404, detail={'error': f'Task with ID {task_id} not found'})
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task."""
    try:
        supabase_client = get_supabase_client()
        
        response = supabase_client.table("tasks").delete().eq("id", task_id).execute()
        
        return {"message": "Task deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

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
    return {"status": "healthy", "service": "projects"} 
