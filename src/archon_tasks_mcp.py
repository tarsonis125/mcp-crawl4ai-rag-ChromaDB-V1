"""
MCP tool definitions for Archon Task Management
"""
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class TaskLookup(BaseModel):
    """Retrieve a single task."""
    task_id: str = Field(..., description="UUID of the task")


class TasksByProject(BaseModel):
    """List tasks under a project."""
    project_id: str = Field(..., description="UUID of the project")


class CreateTask(BaseModel):
    """Create a new task under a project."""
    project_id: str = Field(..., description="UUID of the parent project")
    title: str = Field(..., description="Title of the task")
    description: Optional[str] = Field(None, description="Optional detailed description")
    parent_task_id: Optional[str] = Field(None, description="UUID of a parent task, if subtask")
    sources: Optional[List[Dict]] = Field(None, description="List of source metadata dicts")
    code_examples: Optional[List[Dict]] = Field(None, description="List of code example dicts")


class UpdateTaskStatus(BaseModel):
    """Update a task's status."""
    task_id: str = Field(..., description="UUID of the task to update")
    status: str = Field(..., description="New status: one of 'todo','doing','blocked','done'")


TOOL_REGISTRY = {
    "task_lookup": {"schema": TaskLookup, "endpoint": "/tasks/{task_id}"},
    "list_tasks": {"schema": TasksByProject, "endpoint": "/tasks/by_project/{project_id}"},
    "create_task": {"schema": CreateTask, "endpoint": "/tasks"},
    "update_task_status": {"schema": UpdateTaskStatus, "endpoint": "/tasks/{task_id}/status"}
}
