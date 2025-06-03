"""
Project Module for Archon MCP Server

This module provides tools for:
- Project management (create, list, get, delete projects)
- Task management (create, list, update, delete tasks)
- Task status workflow (todo → doing → blocked → done)
- Task hierarchy (subtasks with parent relationships)

All tools work with the Supabase tasks and projects tables.
"""
from mcp.server.fastmcp import FastMCP, Context
from typing import List, Dict, Any, Optional
import json
import uuid
from datetime import datetime


def register_project_tools(mcp: FastMCP):
    """Register all project and task management tools with the MCP server."""
    
    @mcp.tool()
    async def create_project(ctx: Context, title: str, prd: Dict[str, Any] = None, github_repo: str = None) -> str:
        """
        Create a new project.
        
        Args:
            ctx: The MCP server provided context
            title: Title of the project
            prd: Optional product requirements document as JSON
            github_repo: Optional GitHub repository URL
        
        Returns:
            JSON string with the created project information
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            project_data = {
                "title": title,
                "prd": prd or {},
                "docs": [],
                "features": [],
                "data": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            if github_repo:
                project_data["github_repo"] = github_repo
            
            response = supabase_client.table("projects").insert(project_data).execute()
            
            if response.data:
                project = response.data[0]
                return json.dumps({
                    "success": True,
                    "project": {
                        "id": project["id"],
                        "title": project["title"],
                        "github_repo": project.get("github_repo"),
                        "created_at": project["created_at"]
                    }
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": "Failed to create project"
                })
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error creating project: {str(e)}"
            })
    
    @mcp.tool()
    async def list_projects(ctx: Context) -> str:
        """
        List all projects.
        
        Args:
            ctx: The MCP server provided context
        
        Returns:
            JSON string with list of all projects
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            response = supabase_client.table("projects").select("*").order("created_at", desc=True).execute()
            
            projects = []
            for project in response.data:
                projects.append({
                    "id": project["id"],
                    "title": project["title"],
                    "github_repo": project.get("github_repo"),
                    "created_at": project["created_at"],
                    "updated_at": project["updated_at"]
                })
            
            return json.dumps({
                "success": True,
                "projects": projects,
                "total_count": len(projects)
            })
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error listing projects: {str(e)}"
            })
    
    @mcp.tool()
    async def get_project(ctx: Context, project_id: str) -> str:
        """
        Get a specific project by ID.
        
        Args:
            ctx: The MCP server provided context
            project_id: UUID of the project
        
        Returns:
            JSON string with project details
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            response = supabase_client.table("projects").select("*").eq("id", project_id).execute()
            
            if response.data:
                project = response.data[0]
                return json.dumps({
                    "success": True,
                    "project": project
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Project with ID {project_id} not found"
                })
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error getting project: {str(e)}"
            })
    
    @mcp.tool()
    async def delete_project(ctx: Context, project_id: str) -> str:
        """
        Delete a project and all its associated tasks.
        
        Args:
            ctx: The MCP server provided context
            project_id: UUID of the project to delete
        
        Returns:
            JSON string with deletion results
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            # First, get task count for reporting
            tasks_response = supabase_client.table("tasks").select("id").eq("project_id", project_id).execute()
            tasks_count = len(tasks_response.data) if tasks_response.data else 0
            
            # Delete the project (tasks will be deleted by cascade)
            response = supabase_client.table("projects").delete().eq("id", project_id).execute()
            
            if response.data:
                return json.dumps({
                    "success": True,
                    "project_id": project_id,
                    "deleted_tasks": tasks_count
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Project with ID {project_id} not found"
                })
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error deleting project: {str(e)}"
            })
    
    @mcp.tool()
    async def create_task(ctx: Context, project_id: str, title: str, description: str = "", parent_task_id: str = None, sources: List[Dict[str, Any]] = None, code_examples: List[Dict[str, Any]] = None) -> str:
        """
        Create a new task under a project.
        
        Args:
            ctx: The MCP server provided context
            project_id: UUID of the parent project
            title: Title of the task
            description: Optional detailed description
            parent_task_id: Optional UUID of parent task for subtasks
            sources: Optional list of source metadata dicts
            code_examples: Optional list of code example dicts
        
        Returns:
            JSON string with the created task information
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            task_data = {
                "project_id": project_id,
                "title": title,
                "description": description,
                "status": "todo",
                "sources": sources or [],
                "code_examples": code_examples or [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            if parent_task_id:
                task_data["parent_task_id"] = parent_task_id
            
            response = supabase_client.table("tasks").insert(task_data).execute()
            
            if response.data:
                task = response.data[0]
                return json.dumps({
                    "success": True,
                    "task": {
                        "id": task["id"],
                        "project_id": task["project_id"],
                        "parent_task_id": task.get("parent_task_id"),
                        "title": task["title"],
                        "description": task["description"],
                        "status": task["status"],
                        "created_at": task["created_at"]
                    }
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": "Failed to create task"
                })
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error creating task: {str(e)}"
            })
    
    @mcp.tool()
    async def list_tasks_by_project(ctx: Context, project_id: str) -> str:
        """
        List all tasks under a specific project.
        
        Args:
            ctx: The MCP server provided context
            project_id: UUID of the project
        
        Returns:
            JSON string with list of tasks for the project
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            response = supabase_client.table("tasks").select("*").eq("project_id", project_id).order("created_at", desc=False).execute()
            
            tasks = []
            for task in response.data:
                tasks.append({
                    "id": task["id"],
                    "project_id": task["project_id"],
                    "parent_task_id": task.get("parent_task_id"),
                    "title": task["title"],
                    "description": task["description"],
                    "status": task["status"],
                    "created_at": task["created_at"],
                    "updated_at": task["updated_at"]
                })
            
            return json.dumps({
                "success": True,
                "project_id": project_id,
                "tasks": tasks,
                "total_count": len(tasks)
            })
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error listing tasks: {str(e)}"
            })
    
    @mcp.tool()
    async def get_task(ctx: Context, task_id: str) -> str:
        """
        Get a specific task by ID.
        
        Args:
            ctx: The MCP server provided context
            task_id: UUID of the task
        
        Returns:
            JSON string with task details
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            response = supabase_client.table("tasks").select("*").eq("id", task_id).execute()
            
            if response.data:
                task = response.data[0]
                return json.dumps({
                    "success": True,
                    "task": task
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Task with ID {task_id} not found"
                })
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error getting task: {str(e)}"
            })
    
    @mcp.tool()
    async def update_task_status(ctx: Context, task_id: str, status: str) -> str:
        """
        Update a task's status.
        
        Args:
            ctx: The MCP server provided context
            task_id: UUID of the task to update
            status: New status - one of 'todo', 'doing', 'blocked', 'done'
        
        Returns:
            JSON string with update results
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            # Validate status
            valid_statuses = ['todo', 'doing', 'blocked', 'done']
            if status not in valid_statuses:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}"
                })
            
            response = supabase_client.table("tasks").update({
                "status": status,
                "updated_at": datetime.now().isoformat()
            }).eq("id", task_id).execute()
            
            if response.data:
                task = response.data[0]
                return json.dumps({
                    "success": True,
                    "task": {
                        "id": task["id"],
                        "title": task["title"],
                        "status": task["status"],
                        "updated_at": task["updated_at"]
                    }
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Task with ID {task_id} not found"
                })
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error updating task status: {str(e)}"
            })
    
    @mcp.tool()
    async def update_task(ctx: Context, task_id: str, title: str = None, description: str = None, status: str = None) -> str:
        """
        Update task details.
        
        Args:
            ctx: The MCP server provided context
            task_id: UUID of the task to update
            title: Optional new title
            description: Optional new description  
            status: Optional new status - one of 'todo', 'doing', 'blocked', 'done'
        
        Returns:
            JSON string with update results
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            # Build update data
            update_data = {
                "updated_at": datetime.now().isoformat()
            }
            
            if title is not None:
                update_data["title"] = title
            
            if description is not None:
                update_data["description"] = description
                
            if status is not None:
                valid_statuses = ['todo', 'doing', 'blocked', 'done']
                if status not in valid_statuses:
                    return json.dumps({
                        "success": False,
                        "error": f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}"
                    })
                update_data["status"] = status
            
            response = supabase_client.table("tasks").update(update_data).eq("id", task_id).execute()
            
            if response.data:
                task = response.data[0]
                return json.dumps({
                    "success": True,
                    "task": task
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Task with ID {task_id} not found"
                })
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error updating task: {str(e)}"
            })
    
    @mcp.tool()
    async def delete_task(ctx: Context, task_id: str) -> str:
        """
        Delete a task and all its subtasks.
        
        Args:
            ctx: The MCP server provided context
            task_id: UUID of the task to delete
        
        Returns:
            JSON string with deletion results
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            # First, get all subtasks to count them
            subtasks_response = supabase_client.table("tasks").select("id").eq("parent_task_id", task_id).execute()
            subtasks_count = len(subtasks_response.data) if subtasks_response.data else 0
            
            # Delete the task (subtasks will be deleted by cascade)
            response = supabase_client.table("tasks").delete().eq("id", task_id).execute()
            
            if response.data:
                return json.dumps({
                    "success": True,
                    "task_id": task_id,
                    "deleted_subtasks": subtasks_count
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Task with ID {task_id} not found"
                })
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error deleting task: {str(e)}"
            })
    
    @mcp.tool()
    async def get_task_subtasks(ctx: Context, parent_task_id: str) -> str:
        """
        Get all subtasks of a specific task.
        
        Args:
            ctx: The MCP server provided context
            parent_task_id: UUID of the parent task
        
        Returns:
            JSON string with list of subtasks
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            response = supabase_client.table("tasks").select("*").eq("parent_task_id", parent_task_id).order("created_at", desc=False).execute()
            
            subtasks = []
            for task in response.data:
                subtasks.append({
                    "id": task["id"],
                    "project_id": task["project_id"],
                    "parent_task_id": task["parent_task_id"],
                    "title": task["title"],
                    "description": task["description"],
                    "status": task["status"],
                    "created_at": task["created_at"],
                    "updated_at": task["updated_at"]
                })
            
            return json.dumps({
                "success": True,
                "parent_task_id": parent_task_id,
                "subtasks": subtasks,
                "total_count": len(subtasks)
            })
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error getting subtasks: {str(e)}"
            })
    
    @mcp.tool()
    async def get_tasks_by_status(ctx: Context, project_id: str, status: str) -> str:
        """
        Get all tasks in a project filtered by status.
        
        Args:
            ctx: The MCP server provided context
            project_id: UUID of the project
            status: Status to filter by - one of 'todo', 'doing', 'blocked', 'done'
        
        Returns:
            JSON string with filtered tasks
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            # Validate status
            valid_statuses = ['todo', 'doing', 'blocked', 'done']
            if status not in valid_statuses:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}"
                })
            
            response = supabase_client.table("tasks").select("*").eq("project_id", project_id).eq("status", status).order("created_at", desc=False).execute()
            
            tasks = []
            for task in response.data:
                tasks.append({
                    "id": task["id"],
                    "project_id": task["project_id"],
                    "parent_task_id": task.get("parent_task_id"),
                    "title": task["title"],
                    "description": task["description"],
                    "status": task["status"],
                    "created_at": task["created_at"],
                    "updated_at": task["updated_at"]
                })
            
            return json.dumps({
                "success": True,
                "project_id": project_id,
                "status_filter": status,
                "tasks": tasks,
                "total_count": len(tasks)
            })
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error getting tasks by status: {str(e)}"
            }) 