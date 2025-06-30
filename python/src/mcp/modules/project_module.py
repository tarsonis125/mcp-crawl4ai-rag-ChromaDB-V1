"""
Project Module for Archon MCP Server

This module provides consolidated tools for project and task management following
MCP best practices. Instead of many specialized tools, we provide fewer, more
flexible tools that can handle multiple operations.

Consolidated tools:
- manage_project: Handles create, list, get, delete operations
- manage_task: Handles all task operations
- manage_document: Handles all document operations
- manage_versions: Handles all versioning operations
- get_project_features: Standalone tool for feature queries
"""

from mcp.server.fastmcp import FastMCP, Context
from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime

# Import HTTP client and service discovery
import httpx
from urllib.parse import urljoin

# Import service discovery for HTTP calls
from src.server.config.service_discovery import get_api_url

# Import Logfire
from src.server.config.logfire_config import mcp_logger

logger = logging.getLogger(__name__)


def register_project_tools(mcp: FastMCP):
    """Register consolidated project and task management tools with the MCP server."""
    
    @mcp.tool()
    async def manage_project(
        ctx: Context,
        action: str,
        project_id: str = None,
        title: str = None,
        prd: Dict[str, Any] = None,
        github_repo: str = None
    ) -> str:
        """
        Unified tool for project management operations.
        
        Args:
            action: Operation to perform - "create" | "list" | "get" | "delete"
            project_id: UUID of the project (required for get/delete)
            title: Project title (required for create)
            prd: Product requirements document as JSON (optional for create)
            github_repo: GitHub repository URL (optional for create)
        
        Returns:
            JSON string with operation results
        
        Examples:
            Create: manage_project(action="create", title="My App", github_repo="https://github.com/user/repo")
            List: manage_project(action="list")
            Get: manage_project(action="get", project_id="uuid-here")
            Delete: manage_project(action="delete", project_id="uuid-here")
        """
        with mcp_logger.span("mcp_manage_project") as span:
            span.set_attribute("tool", "manage_project")
            span.set_attribute("action", action)
            
            try:
                api_url = get_api_url()
                timeout = httpx.Timeout(30.0, connect=5.0)
                
                if action == "create":
                    if not title:
                        return json.dumps({"success": False, "error": "Title is required for create action"})
                    
                    # Call Server API to create project
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(
                            urljoin(api_url, "/api/projects"),
                            json={
                                "title": title,
                                "prd": prd,
                                "github_repo": github_repo
                            }
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            span.set_attribute("success", True)
                            span.set_attribute("project_id", result.get("progress_id"))
                            return json.dumps({"success": True, "project": result})
                        else:
                            error_detail = response.json().get("detail", {}).get("error", "Unknown error")
                            return json.dumps({"success": False, "error": error_detail})
                
                elif action == "list":
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.get(urljoin(api_url, "/api/projects"))
                        
                        if response.status_code == 200:
                            projects = response.json()
                            span.set_attribute("success", True)
                            span.set_attribute("project_count", len(projects))
                            return json.dumps({"success": True, "projects": projects})
                        else:
                            return json.dumps({"success": False, "error": "Failed to list projects"})
                
                elif action == "get":
                    if not project_id:
                        return json.dumps({"success": False, "error": "project_id is required for get action"})
                    
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.get(urljoin(api_url, f"/api/projects/{project_id}"))
                        
                        if response.status_code == 200:
                            project = response.json()
                            span.set_attribute("success", True)
                            return json.dumps({"success": True, "project": project})
                        elif response.status_code == 404:
                            return json.dumps({"success": False, "error": f"Project {project_id} not found"})
                        else:
                            return json.dumps({"success": False, "error": "Failed to get project"})
                
                elif action == "delete":
                    if not project_id:
                        return json.dumps({"success": False, "error": "project_id is required for delete action"})
                    
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.delete(urljoin(api_url, f"/api/projects/{project_id}"))
                        
                        if response.status_code == 200:
                            span.set_attribute("success", True)
                            return json.dumps({"success": True, "message": "Project deleted successfully"})
                        else:
                            return json.dumps({"success": False, "error": "Failed to delete project"})
                
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Invalid action '{action}'. Must be one of: create, list, get, delete"
                    })
                
            except Exception as e:
                logger.error(f"Error in manage_project: {e}")
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                return json.dumps({"success": False, "error": str(e)})
    
    @mcp.tool()
    async def manage_task(
        ctx: Context,
        action: str,
        task_id: str = None,
        project_id: str = None,
        filter_by: str = None,
        filter_value: str = None,
        title: str = None,
        description: str = "",
        assignee: str = "User",
        task_order: int = 0,
        feature: str = None,
        parent_task_id: str = None,
        sources: List[Dict[str, Any]] = None,
        code_examples: List[Dict[str, Any]] = None,
        update_fields: Dict[str, Any] = None,
        include_closed: bool = False
    ) -> str:
        """
        Unified tool for task management operations.
        
        Args:
            action: Operation - "create" | "list" | "get" | "update" | "delete" | "archive"
            task_id: UUID of the task (required for get/update/delete/archive)
            project_id: UUID of the project (required for create, optional for list)
            filter_by: Filter type for list - "status" | "parent" | "project"
            filter_value: Value for the filter (status value or parent_task_id)
            title: Task title (required for create)
            description: Task description (for create)
            assignee: One of 'User', 'Archon', 'AI IDE Agent' (for create)
            task_order: Order/priority (for create)
            feature: Feature label (for create)
            parent_task_id: Parent task for subtasks (for create)
            sources: List of source metadata (for create)
            code_examples: List of code examples (for create)
            update_fields: Dict of fields to update (for update action)
            include_closed: Include done tasks in list (default: False)
        
        Returns:
            JSON string with operation results
        
        Examples:
            Create: manage_task(action="create", project_id="uuid", title="Implement login")
            List by project: manage_task(action="list", filter_by="project", filter_value="project-uuid")
            List by status: manage_task(action="list", filter_by="status", filter_value="todo", project_id="uuid")
            Get: manage_task(action="get", task_id="uuid")
            Update: manage_task(action="update", task_id="uuid", update_fields={"status": "doing"})
            Archive: manage_task(action="archive", task_id="uuid")
        """
        with mcp_logger.span("mcp_manage_task") as span:
            span.set_attribute("tool", "manage_task")
            span.set_attribute("action", action)
            
            try:
                api_url = get_api_url()
                timeout = httpx.Timeout(30.0, connect=5.0)
                
                if action == "create":
                    if not project_id:
                        return json.dumps({"success": False, "error": "project_id is required for create action"})
                    if not title:
                        return json.dumps({"success": False, "error": "title is required for create action"})
                    
                    # Call Server API to create task
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(
                            urljoin(api_url, "/api/tasks"),
                            json={
                                "project_id": project_id,
                                "title": title,
                                "description": description,
                                "assignee": assignee,
                                "task_order": task_order,
                                "feature": feature,
                                "parent_task_id": parent_task_id,
                                "sources": sources,
                                "code_examples": code_examples
                            }
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            span.set_attribute("success", True)
                            span.set_attribute("task_id", result.get("task", {}).get("id"))
                            return json.dumps({"success": True, "task": result.get("task"), "message": result.get("message")})
                        else:
                            error_detail = response.text
                            return json.dumps({"success": False, "error": error_detail})
                
                elif action == "list":
                    # Build URL with query parameters
                    params = {}
                    
                    if filter_by == "project" and filter_value:
                        url = urljoin(api_url, f"/api/projects/{filter_value}/tasks")
                        params["include_archived"] = False
                        params["include_subtasks"] = include_closed
                    elif filter_by == "parent" and filter_value:
                        url = urljoin(api_url, f"/api/tasks/subtasks/{filter_value}")
                        params["include_closed"] = include_closed
                    elif project_id:
                        url = urljoin(api_url, f"/api/projects/{project_id}/tasks")
                        params["include_archived"] = False
                        params["include_subtasks"] = include_closed
                    else:
                        return json.dumps({"success": False, "error": "project_id or filter_value required for list action"})
                    
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.get(url, params=params)
                        
                        if response.status_code == 200:
                            result = response.json()
                            tasks = result if isinstance(result, list) else result.get("tasks", [])
                            span.set_attribute("success", True)
                            span.set_attribute("task_count", len(tasks))
                            return json.dumps({"success": True, "tasks": tasks})
                        else:
                            return json.dumps({"success": False, "error": "Failed to list tasks"})
                
                elif action == "get":
                    if not task_id:
                        return json.dumps({"success": False, "error": "task_id is required for get action"})
                    
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.get(urljoin(api_url, f"/api/tasks/{task_id}"))
                        
                        if response.status_code == 200:
                            task = response.json()
                            span.set_attribute("success", True)
                            return json.dumps({"success": True, "task": task})
                        elif response.status_code == 404:
                            return json.dumps({"success": False, "error": f"Task {task_id} not found"})
                        else:
                            return json.dumps({"success": False, "error": "Failed to get task"})
                
                elif action == "update":
                    if not task_id:
                        return json.dumps({"success": False, "error": "task_id is required for update action"})
                    if not update_fields:
                        return json.dumps({"success": False, "error": "update_fields is required for update action"})
                    
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.put(
                            urljoin(api_url, f"/api/tasks/{task_id}"),
                            json=update_fields
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            span.set_attribute("success", True)
                            return json.dumps({"success": True, "task": result.get("task"), "message": result.get("message")})
                        else:
                            error_detail = response.text
                            return json.dumps({"success": False, "error": error_detail})
                
                elif action in ["delete", "archive"]:
                    if not task_id:
                        return json.dumps({"success": False, "error": "task_id is required for delete/archive action"})
                    
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.delete(urljoin(api_url, f"/api/tasks/{task_id}"))
                        
                        if response.status_code == 200:
                            result = response.json()
                            span.set_attribute("success", True)
                            return json.dumps({"success": True, "message": result.get("message"), "subtasks_archived": result.get("subtasks_archived", 0)})
                        else:
                            return json.dumps({"success": False, "error": "Failed to archive task"})
                
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Invalid action '{action}'. Must be one of: create, list, get, update, delete, archive"
                    })
                
            except Exception as e:
                logger.error(f"Error in manage_task: {e}")
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                return json.dumps({"success": False, "error": str(e)})
    
    @mcp.tool()
    async def manage_document(
        ctx: Context,
        action: str,
        project_id: str,
        doc_id: str = None,
        document_type: str = None,
        title: str = None,
        content: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Unified tool for document management within projects.
        
        Args:
            action: Operation - "add" | "list" | "get" | "update" | "delete"
            project_id: UUID of the project (always required)
            doc_id: UUID of the document (required for get/update/delete)
            document_type: Type of document (required for add)
            title: Document title (required for add, optional for update)
            content: Document content as structured JSON (for add/update)
            metadata: Dict with optional fields: tags, status, version, author
        
        Returns:
            JSON string with operation results
        
        Examples:
            Add: manage_document(action="add", project_id="uuid", document_type="prd", title="PRD v1.0", content={...})
            List: manage_document(action="list", project_id="uuid")
            Get: manage_document(action="get", project_id="uuid", doc_id="doc-uuid")
            Update: manage_document(action="update", project_id="uuid", doc_id="doc-uuid", content={...})
            Delete: manage_document(action="delete", project_id="uuid", doc_id="doc-uuid")
        """
        with mcp_logger.span("mcp_manage_document") as span:
            span.set_attribute("tool", "manage_document")
            span.set_attribute("action", action)
            span.set_attribute("project_id", project_id)
            
            try:
                # Document management is not yet implemented in the Server API
                return json.dumps({
                    "success": False, 
                    "error": "Document management endpoints are not yet implemented in the Server API"
                })
                
            except Exception as e:
                logger.error(f"Error in manage_document: {e}")
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                return json.dumps({"success": False, "error": str(e)})
    
    @mcp.tool()
    async def manage_versions(
        ctx: Context,
        action: str,
        project_id: str,
        field_name: str,
        version_number: int = None,
        content: Dict[str, Any] = None,
        change_summary: str = None,
        document_id: str = None,
        created_by: str = "system"
    ) -> str:
        """
        Unified tool for document version management.
        
        Args:
            action: Operation - "create" | "list" | "get" | "restore"
            project_id: UUID of the project (always required)
            field_name: Name of the JSONB field ('docs', 'features', 'data', 'prd')
            version_number: Version number (required for get/restore)
            content: Content to snapshot (required for create)
            change_summary: Description of changes (for create)
            document_id: Specific document ID within docs array (for create)
            created_by: Who created this version (for create/restore)
        
        Returns:
            JSON string with operation results
        
        Examples:
            Create: manage_versions(action="create", project_id="uuid", field_name="docs", content={...})
            List: manage_versions(action="list", project_id="uuid", field_name="docs")
            Get: manage_versions(action="get", project_id="uuid", field_name="docs", version_number=3)
            Restore: manage_versions(action="restore", project_id="uuid", field_name="docs", version_number=3)
        """
        with mcp_logger.span("mcp_manage_versions") as span:
            span.set_attribute("tool", "manage_versions")
            span.set_attribute("action", action)
            span.set_attribute("project_id", project_id)
            span.set_attribute("field_name", field_name)
            
            try:
                # Version management is not yet implemented in the Server API
                return json.dumps({
                    "success": False, 
                    "error": "Version management endpoints are not yet implemented in the Server API"
                })
                
            except Exception as e:
                logger.error(f"Error in manage_versions: {e}")
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                return json.dumps({"success": False, "error": str(e)})
    
    @mcp.tool()
    async def get_project_features(ctx: Context, project_id: str) -> str:
        """
        Get features from a project's features JSONB field.
        
        This remains a standalone tool as it's a specific query operation
        that doesn't fit the CRUD pattern of the other tools.
        
        Args:
            project_id: UUID of the project
        
        Returns:
            JSON string with list of features
        """
        try:
            api_url = get_api_url()
            timeout = httpx.Timeout(30.0, connect=5.0)
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(urljoin(api_url, f"/api/projects/{project_id}/features"))
                
                if response.status_code == 200:
                    result = response.json()
                    return json.dumps({"success": True, **result})
                elif response.status_code == 404:
                    return json.dumps({"success": False, "error": "Project not found"})
                else:
                    return json.dumps({"success": False, "error": "Failed to get project features"})
            
        except Exception as e:
            logger.error(f"Error getting project features: {e}")
            return json.dumps({"success": False, "error": str(e)})
    
    logger.info("✓ Project Module registered with 5 consolidated tools")