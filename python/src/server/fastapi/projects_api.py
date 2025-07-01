"""
Projects API endpoints for Archon

Handles:
- Project management (CRUD operations)
- Task management with hierarchical structure
- Streaming project creation with DocumentAgent integration
- Socket.IO progress updates for project creation
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional, Set
import asyncio
import secrets
from datetime import datetime, timedelta
import json
import uuid

from ..utils import get_supabase_client
# Removed direct logging import - using unified config
from ..config.logfire_config import logfire

# Set up standard logger for background tasks
from ..config.logfire_config import get_logger

logger = get_logger(__name__)

# Service imports
from ..services.projects import (
    ProjectService, 
    TaskService,
    progress_service,
    ProjectCreationService,
    SourceLinkingService
)

# Import Socket.IO broadcast functions from socketio_handlers
from .socketio_handlers import broadcast_project_update

router = APIRouter(prefix="/api", tags=["projects"])

class CreateProjectRequest(BaseModel):
    title: str
    description: Optional[str] = None
    github_repo: Optional[str] = None
    docs: Optional[List[Any]] = None
    features: Optional[List[Any]] = None
    data: Optional[List[Any]] = None
    technical_sources: Optional[List[str]] = None  # List of knowledge source IDs
    business_sources: Optional[List[str]] = None   # List of knowledge source IDs
    pinned: Optional[bool] = None  # Whether this project should be pinned to top

class UpdateProjectRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None  # Add description field
    github_repo: Optional[str] = None
    docs: Optional[List[Any]] = None
    features: Optional[List[Any]] = None
    data: Optional[List[Any]] = None
    technical_sources: Optional[List[str]] = None  # List of knowledge source IDs
    business_sources: Optional[List[str]] = None   # List of knowledge source IDs
    pinned: Optional[bool] = None  # Whether this project is pinned to top

class CreateTaskRequest(BaseModel):
    project_id: str
    parent_task_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: Optional[str] = 'todo'
    assignee: Optional[str] = 'User'
    task_order: Optional[int] = 0
    feature: Optional[str] = None



@router.get("/projects")
async def list_projects():
    """List all projects."""
    try:
        logfire.info("Listing all projects")
        
        # Use ProjectService to get projects
        project_service = ProjectService()
        success, result = project_service.list_projects()
        
        if not success:
            raise HTTPException(status_code=500, detail=result)
        
        # Use SourceLinkingService to format projects with sources
        source_service = SourceLinkingService()
        formatted_projects = source_service.format_projects_with_sources(result["projects"])
        
        logfire.info(f"Projects listed successfully | count={len(formatted_projects)}")
        
        return formatted_projects
        
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to list projects | error={str(e)}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/projects")
async def create_project(request: CreateProjectRequest):
    """Create a new project with streaming progress."""
    try:
        logfire.info(f"Creating new project | title={request.title} | github_repo={request.github_repo}")
        
        # Generate unique progress ID for this creation
        progress_id = secrets.token_hex(16)
        
        # Start tracking creation progress
        progress_service.start_operation(progress_id, 'project_creation', {
            'title': request.title,
            'description': request.description or '',
            'github_repo': request.github_repo
        })
        
        # Start background task to create the project with AI assistance
        asyncio.create_task(_create_project_with_ai(progress_id, request))
        
        logfire.info(f"Project creation started | progress_id={progress_id} | title={request.title}")
        
        # Return progress_id immediately so frontend can connect to Socket.IO
        return {
            "progress_id": progress_id,
            "status": "started",
            "message": "Project creation started. Connect to Socket.IO for progress updates."
        }
        
    except Exception as e:
        logfire.error(f"Failed to start project creation | error={str(e)} | title={request.title}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

async def _create_project_with_ai(progress_id: str, request: CreateProjectRequest):
    """Background task to create project with AI assistance using ProjectCreationService."""
    try:
        # Prepare kwargs for additional project fields
        kwargs = {}
        if request.pinned is not None:
            kwargs['pinned'] = request.pinned
        if request.features:
            kwargs['features'] = request.features
        if request.data:
            kwargs['data'] = request.data
        
        # Use ProjectCreationService to handle the entire workflow
        creation_service = ProjectCreationService()
        success, result = await creation_service.create_project_with_ai(
            progress_id=progress_id,
            title=request.title,
            description=request.description,
            github_repo=request.github_repo,
            **kwargs
        )
        
        if success:
            # Broadcast project list update
            await broadcast_project_update()
            
            # Complete the operation
            await progress_service.complete_operation(progress_id, {
                'project_id': result['project_id']
            })
        else:
            # Error occurred
            await progress_service.error_operation(progress_id, result.get('error', 'Unknown error'))
        
    except Exception as e:
        logfire.error(f"Project creation failed: {str(e)}")
        await progress_service.error_operation(progress_id, str(e))

@router.get("/projects/health")
async def projects_health():
    """Health check for projects API and database schema validation."""
    try:
        logfire.info("Projects health check requested")
        supabase_client = get_supabase_client()
        
        # Check if projects table exists by testing ProjectService
        try:
            project_service = ProjectService(supabase_client)
            # Try to list projects with limit 1 to test table access
            success, _ = project_service.list_projects()
            projects_table_exists = success
            if success:
                logfire.info("Projects table detected successfully")
            else:
                logfire.warning("Projects table access failed")
        except Exception as e:
            projects_table_exists = False
            logfire.warning(f"Projects table not found | error={str(e)}")
        
        # Check if tasks table exists by testing TaskService
        try:
            task_service = TaskService(supabase_client)
            # Try to list tasks with limit 1 to test table access
            success, _ = task_service.list_tasks(include_closed=True)
            tasks_table_exists = success
            if success:
                logfire.info("Tasks table detected successfully")
            else:
                logfire.warning("Tasks table access failed")
        except Exception as e:
            tasks_table_exists = False
            logfire.warning(f"Tasks table not found | error={str(e)}")
        
        schema_valid = projects_table_exists and tasks_table_exists
        
        result = {
            "status": "healthy" if schema_valid else "schema_missing",
            "service": "projects",
            "schema": {
                "projects_table": projects_table_exists,
                "tasks_table": tasks_table_exists,
                "valid": schema_valid
            }
        }
        
        logfire.info(f"Projects health check completed | status={result['status']} | schema_valid={schema_valid}")
        
        return result
        
    except Exception as e:
        logfire.error(f"Projects health check failed | error={str(e)}")
        return {
            "status": "error",
            "service": "projects",
            "error": str(e),
            "schema": {
                "projects_table": False,
                "tasks_table": False,
                "valid": False
            }
        }

@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get a specific project."""
    try:
        logfire.info(f"Getting project | project_id={project_id}")
        
        # Use ProjectService to get the project
        project_service = ProjectService()
        success, result = project_service.get_project(project_id)
        
        if not success:
            if "not found" in result.get("error", "").lower():
                logfire.warning(f"Project not found | project_id={project_id}")
                raise HTTPException(status_code=404, detail=result)
            else:
                raise HTTPException(status_code=500, detail=result)
        
        project = result["project"]
        
        logfire.info(f"Project retrieved successfully | project_id={project_id} | title={project['title']}")
        
        # The ProjectService already includes sources, so just add any missing fields
        return {
            **project,
            "description": project.get("description", ""),
            "docs": project.get("docs", []),
            "features": project.get("features", []),
            "data": project.get("data", []),
            "pinned": project.get("pinned", False)
        }
                    
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to get project | error={str(e)} | project_id={project_id}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.put("/projects/{project_id}")
async def update_project(project_id: str, request: UpdateProjectRequest):
    """Update a project with comprehensive Logfire monitoring."""
    try:
            supabase_client = get_supabase_client()
            
            # Build update fields from request
            update_fields = {}
            if request.title is not None:
                update_fields["title"] = request.title
            if request.description is not None:
                update_fields["description"] = request.description
            if request.github_repo is not None:
                update_fields["github_repo"] = request.github_repo
            if request.docs is not None:
                update_fields["docs"] = request.docs
            if request.features is not None:
                update_fields["features"] = request.features
            if request.data is not None:
                update_fields["data"] = request.data
            if request.pinned is not None:
                update_fields["pinned"] = request.pinned
            
            
            # Create version snapshots for JSONB fields before updating
            if update_fields:
                try:
                    from ..services.projects.versioning_service import VersioningService
                    versioning_service = VersioningService(supabase_client)
                    
                    # Get current project for comparison
                    project_service = ProjectService(supabase_client)
                    success, current_result = project_service.get_project(project_id)
                    
                    if success and current_result.get("project"):
                        current_project = current_result["project"]
                        version_count = 0
                        
                        # Create versions for updated JSONB fields
                        for field_name in ['docs', 'features', 'data']:
                            if field_name in update_fields:
                                current_content = current_project.get(field_name, {})
                                new_content = update_fields[field_name]
                                
                                # Only create version if content actually changed
                                if current_content != new_content:
                                    v_success, _ = versioning_service.create_version(
                                        project_id=project_id,
                                        field_name=field_name,
                                        content=current_content,
                                        change_summary=f"Updated {field_name} via API",
                                        change_type="update",
                                        created_by="api_user"
                                    )
                                    if v_success:
                                        version_count += 1
                        
                        logfire.info(f"Created {version_count} version snapshots before update")
                except ImportError:
                    logfire.warning("VersioningService not available - skipping version snapshots")
                except Exception as e:
                    logfire.warning(f"Failed to create version snapshots: {e}")
                    # Don't fail the update, just log the warning
            
            # Use ProjectService to update the project
            project_service = ProjectService(supabase_client)
            success, result = project_service.update_project(project_id, update_fields)
            
            if not success:
                if "not found" in result.get("error", "").lower():
                    raise HTTPException(status_code=404, detail={'error': f'Project with ID {project_id} not found'})
                else:
                    raise HTTPException(status_code=500, detail=result)
            
            project = result["project"]
            
            # Handle source updates using SourceLinkingService
            source_service = SourceLinkingService(supabase_client)
            
            if request.technical_sources is not None or request.business_sources is not None:
                source_success, source_result = source_service.update_project_sources(
                    project_id=project_id,
                    technical_sources=request.technical_sources,
                    business_sources=request.business_sources
                )
                
                if source_success:
                    logfire.info(f"Project sources updated | project_id={project_id} | technical_success={source_result.get('technical_success', 0)} | technical_failed={source_result.get('technical_failed', 0)} | business_success={source_result.get('business_success', 0)} | business_failed={source_result.get('business_failed', 0)}")
                else:
                    logfire.warning(f"Failed to update some sources: {source_result}")
            
            # Format project response with sources using SourceLinkingService
            formatted_project = source_service.format_project_with_sources(project)
            
            # Broadcast project list update to Socket.IO clients
            await broadcast_project_update()
            
            logfire.info(f"Project updated successfully | project_id={project_id} | title={project.get('title')} | technical_sources={len(formatted_project.get('technical_sources', []))} | business_sources={len(formatted_project.get('business_sources', []))}")
            
            return formatted_project
                
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Project update failed | project_id={project_id} | error={str(e)}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and all its tasks."""
    try:
        logfire.info(f"Deleting project | project_id={project_id}")
        
        # Use ProjectService to delete the project
        project_service = ProjectService()
        success, result = project_service.delete_project(project_id)
        
        if not success:
            if "not found" in result.get("error", "").lower():
                raise HTTPException(status_code=404, detail=result)
            else:
                raise HTTPException(status_code=500, detail=result)
        
        # Broadcast project list update to Socket.IO clients
        await broadcast_project_update()
        
        logfire.info(f"Project deleted successfully | project_id={project_id} | deleted_tasks={result.get('deleted_tasks', 0)}")
        
        return {"message": "Project deleted successfully", 
               "deleted_tasks": result.get("deleted_tasks", 0)}
            
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to delete project | error={str(e)} | project_id={project_id}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/projects/{project_id}/features")
async def get_project_features(project_id: str):
    """Get features from a project's features JSONB field."""
    try:
        logfire.info(f"Getting project features | project_id={project_id}")
        
        # Use ProjectService to get features
        project_service = ProjectService()
        success, result = project_service.get_project_features(project_id)
        
        if not success:
            if "not found" in result.get("error", "").lower():
                logfire.warning(f"Project not found for features | project_id={project_id}")
                raise HTTPException(status_code=404, detail=result)
            else:
                raise HTTPException(status_code=500, detail=result)
        
        logfire.info(f"Project features retrieved | project_id={project_id} | feature_count={result.get('count', 0)}")
        
        return result
            
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to get project features | error={str(e)} | project_id={project_id}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/projects/{project_id}/tasks")
async def list_project_tasks(project_id: str, include_archived: bool = False, include_subtasks: bool = False):
    """List all tasks for a specific project. By default, filters out archived tasks and subtasks."""
    try:
        logfire.info(f"Listing project tasks | project_id={project_id} | include_archived={include_archived} | include_subtasks={include_subtasks}")
        
        # Use TaskService to list tasks
        task_service = TaskService()
        success, result = task_service.list_tasks(
            project_id=project_id,
            include_closed=True  # Get all tasks, we'll filter archived separately
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=result)
        
        tasks = result.get("tasks", [])
        
        # Apply filters
        filtered_tasks = []
        for task in tasks:
            # Skip archived tasks if not including them (handle None as False)
            if not include_archived and task.get("archived", False):
                continue
            
            # Skip subtasks if not including them
            if not include_subtasks and task.get("parent_task_id"):
                continue
            
            filtered_tasks.append(task)
        
        logfire.info(f"Project tasks retrieved | project_id={project_id} | task_count={len(filtered_tasks)}")
        
        return filtered_tasks
            
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to list project tasks | error={str(e)} | project_id={project_id}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/tasks")
async def create_task(request: CreateTaskRequest):
    """Create a new task with automatic reordering and real-time Socket.IO broadcasting."""
    try:
            # Use TaskService to create the task
            task_service = TaskService()
            success, result = await task_service.create_task(
                project_id=request.project_id,
                title=request.title,
                description=request.description or "",
                assignee=request.assignee or "User",
                task_order=request.task_order or 0,
                feature=request.feature,
                parent_task_id=request.parent_task_id
            )
            
            if not success:
                raise HTTPException(status_code=400, detail=result)
            
            created_task = result["task"]
            
            logfire.info(f"Task created successfully | task_id={created_task['id']} | project_id={request.project_id}")
            
            return {"message": "Task created successfully", "task": created_task}
                
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to create task | error={str(e)} | project_id={request.project_id}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get a specific task by ID."""
    try:
            # Use TaskService to get the task
            task_service = TaskService()
            success, result = task_service.get_task(task_id)
            
            if not success:
                if "not found" in result.get("error", "").lower():
                    raise HTTPException(status_code=404, detail=result.get("error"))
                else:
                    raise HTTPException(status_code=500, detail=result)
            
            task = result["task"]
            
            logfire.info(f"Task retrieved successfully | task_id={task_id} | project_id={task.get('project_id')}")
            
            return task
            
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to get task | error={str(e)} | task_id={task_id}")
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
    """Update a task with real-time Socket.IO broadcasting."""
    try:
        # Build update fields dictionary
        update_fields = {}
        if request.title is not None:
            update_fields["title"] = request.title
        if request.description is not None:
            update_fields["description"] = request.description
        if request.status is not None:
            update_fields["status"] = request.status
        if request.assignee is not None:
            update_fields["assignee"] = request.assignee
        if request.task_order is not None:
            update_fields["task_order"] = request.task_order
        if request.feature is not None:
            update_fields["feature"] = request.feature
            
            # Use TaskService to update the task
            task_service = TaskService()
            success, result = await task_service.update_task(task_id, update_fields)
            
            if not success:
                if "not found" in result.get("error", "").lower():
                    raise HTTPException(status_code=404, detail=result.get("error"))
                else:
                    raise HTTPException(status_code=500, detail=result)
            
            updated_task = result["task"]
            
            logfire.info(f"Task updated successfully | task_id={task_id} | project_id={updated_task.get('project_id')} | updated_fields={list(update_fields.keys())}")
            
            return {"message": "Task updated successfully", "task": updated_task}
                
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to update task | error={str(e)} | task_id={task_id}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Archive a task (soft delete) with real-time Socket.IO broadcasting."""
    try:
            # Use TaskService to archive the task
            task_service = TaskService()
            success, result = await task_service.archive_task(task_id, archived_by="api")
            
            if not success:
                if "not found" in result.get("error", "").lower():
                    raise HTTPException(status_code=404, detail=result.get("error"))
                elif "already archived" in result.get("error", "").lower():
                    raise HTTPException(status_code=409, detail=result.get("error"))
                else:
                    raise HTTPException(status_code=500, detail=result)
            
            logfire.info(f"Task archived successfully | task_id={task_id} | subtasks_archived={result.get('archived_subtasks', 0)}")
            
            return {
                "message": result.get("message", "Task archived successfully"),
                "subtasks_archived": result.get("archived_subtasks", 0)
            }
                
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to archive task | error={str(e)} | task_id={task_id}")
        raise HTTPException(status_code=500, detail={'error': str(e)})


# WebSocket endpoints removed - use Socket.IO events instead


# MCP endpoints now emit Socket.IO directly - no context manager needed

@router.get("/tasks/subtasks/{parent_task_id}")
async def get_task_subtasks(parent_task_id: str, include_closed: bool = False):
    """Get all subtasks of a specific task."""
    try:
            # Use TaskService to list subtasks
            task_service = TaskService()
            success, result = task_service.list_tasks(
                parent_task_id=parent_task_id,
                include_closed=include_closed
            )
            
            if not success:
                raise HTTPException(status_code=500, detail=result)
            
            tasks = result.get("tasks", [])
            
            logfire.info(f"Retrieved subtasks successfully | parent_task_id={parent_task_id} | subtask_count={len(tasks)} | include_closed={include_closed}")
            
            return {"tasks": tasks}
                
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to get subtasks | error={str(e)} | parent_task_id={parent_task_id}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/mcp/tasks/{task_id}/status")
async def mcp_update_task_status_with_socketio(task_id: str, status: str):
    """Update task status via MCP tools with Socket.IO broadcasting using RAG pattern."""
    try:
        logfire.info(f"MCP task status update | task_id={task_id} | status={status}")
        
        # Use TaskService to update the task
        task_service = TaskService()
        success, result = await task_service.update_task(
            task_id=task_id,
            update_fields={"status": status}
        )
        
        if not success:
            if "not found" in result.get("error", "").lower():
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            else:
                raise HTTPException(status_code=500, detail=result)
        
        updated_task = result["task"]
        project_id = updated_task["project_id"]
        
        logfire.info(f"Task status updated with Socket.IO broadcast | task_id={task_id} | project_id={project_id} | status={status}")
        
        return {"message": "Task status updated successfully", "task": updated_task}
            
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Failed to update task status with Socket.IO | error={str(e)} | task_id={task_id}")
        raise HTTPException(status_code=500, detail=str(e))

# Socket.IO Event Handlers moved to socketio_handlers.py
# The handlers are automatically registered when socketio_handlers is imported above
