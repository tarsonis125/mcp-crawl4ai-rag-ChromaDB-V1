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

class CreateTaskRequest(BaseModel):
    project_id: str
    parent_task_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: Optional[str] = 'todo'

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
            projects.append({
                "id": project["id"],
                "title": project["title"],
                "github_repo": project.get("github_repo"),
                "created_at": project["created_at"],
                "updated_at": project["updated_at"],
                "prd": project.get("prd", {}),
                "docs": project.get("docs", []),
                "features": project.get("features", []),
                "data": project.get("data", [])
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
        generated_docs = []
        
        try:
            # Import DocsAgent (lazy import to avoid startup issues)
            from ..agents.docs_agent import DocsAgent, DocumentProcessingRequest
            
            await project_creation_manager.update_progress(progress_id, {
                'percentage': 50,
                'step': 'processing_requirements',
                'log': '🧠 AI is analyzing project requirements...'
            })
            
            # Initialize and use DocsAgent
            docs_agent = DocsAgent()
            processing_request = DocumentProcessingRequest(
                title=request.title,
                description=request.description or '',
                mode="create_comprehensive",
                requirements={
                    "title": request.title,
                    "basic_description": request.description or '',
                    "github_repo": request.github_repo
                }
            )
            
            await project_creation_manager.update_progress(progress_id, {
                'percentage': 70,
                'step': 'ai_generation',
                'log': '✨ AI is creating project documentation...'
            })
            
            # Generate documentation
            agent_result = await docs_agent.process_document(processing_request)
            generated_prd = agent_result.prd if hasattr(agent_result, 'prd') else {}
            generated_docs = agent_result.documents if hasattr(agent_result, 'documents') else []
            
            await project_creation_manager.update_progress(progress_id, {
                'percentage': 85,
                'step': 'finalizing_docs',
                'log': f'📋 Generated {len(generated_docs)} documents and comprehensive PRD'
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
            "docs": generated_docs or [],
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
                    "data": project.get("data", [])
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
            return {
                "id": project["id"],
                "title": project["title"],
                "github_repo": project.get("github_repo"),
                "created_at": project["created_at"],
                "updated_at": project["updated_at"],
                "prd": project.get("prd", {}),
                "docs": project.get("docs", []),
                "features": project.get("features", []),
                "data": project.get("data", [])
            }
        else:
            raise HTTPException(status_code=404, detail={'error': f'Project with ID {project_id} not found'})
                
    except HTTPException:
        raise
    except Exception as e:
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

@router.get("/projects/{project_id}/tasks")
async def list_project_tasks(project_id: str):
    """List all tasks for a specific project."""
    try:
        supabase_client = get_supabase_client()
        
        response = supabase_client.table("tasks").select("*").eq("project_id", project_id).order("created_at", desc=True).execute()
        
        return response.data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/tasks")
async def create_task(request: CreateTaskRequest):
    """Create a new task."""
    try:
        supabase_client = get_supabase_client()
        
        task_data = {
            "project_id": request.project_id,
            "title": request.title,
            "description": request.description or "",
            "status": request.status,
            "sources": [],
            "code_examples": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        if request.parent_task_id:
            task_data["parent_task_id"] = request.parent_task_id
        
        response = supabase_client.table("tasks").insert(task_data).execute()
        
        if response.data:
            return response.data[0]
        else:
            raise HTTPException(status_code=500, detail={'error': 'Failed to create task'})
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.put("/tasks/{task_id}")
async def update_task(task_id: str, title: Optional[str] = None, description: Optional[str] = None, status: Optional[str] = None):
    """Update a task."""
    try:
        supabase_client = get_supabase_client()
        
        update_data = {"updated_at": datetime.now().isoformat()}
        
        if title is not None:
            update_data["title"] = title
        if description is not None:
            update_data["description"] = description
        if status is not None:
            update_data["status"] = status
        
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
