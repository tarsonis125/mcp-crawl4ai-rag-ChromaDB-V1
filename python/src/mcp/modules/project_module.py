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
                        return json.dumps({"success": True, "project": result})
                    else:
                        error_detail = response.json().get("detail", {}).get("error", "Unknown error")
                        return json.dumps({"success": False, "error": error_detail})
            
            elif action == "list":
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(urljoin(api_url, "/api/projects"))
                    
                    if response.status_code == 200:
                        projects = response.json()
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
        sources: List[Dict[str, Any]] = None,
        code_examples: List[Dict[str, Any]] = None,
        update_fields: Dict[str, Any] = None,
        include_closed: bool = False,
        page: int = 1,
        per_page: int = 50
    ) -> str:
        """
        Unified tool for task management operations.
        
        Args:
            action: Operation - "create" | "list" | "get" | "update" | "delete" | "archive"
            task_id: UUID of the task (required for get/update/delete/archive)
            project_id: UUID of the project (required for create, optional for list)
            filter_by: Filter type for list - "status" | "project"
            filter_value: Value for the filter (status value)
            title: Task title (required for create)
            description: Task description (for create)
            assignee: One of 'User', 'Archon', 'AI IDE Agent' (for create)
            task_order: Priority within status - higher number = higher priority (e.g., 10 is higher priority than 1)
            feature: Feature label (for create)
            sources: List of source metadata (for create)
            code_examples: List of code examples (for create)
            update_fields: Dict of fields to update (for update action)
            include_closed: Include done tasks in list (default: False)
            page: Page number for pagination (default: 1)
            per_page: Number of items per page (default: 50, max: 100)
        
        Returns:
            JSON string with operation results including pagination info for list operations
        
        Examples:
            Create: manage_task(action="create", project_id="uuid", title="Implement login")
            List by project: manage_task(action="list", filter_by="project", filter_value="project-uuid", page=1, per_page=25)
            List by status: manage_task(action="list", filter_by="status", filter_value="todo", project_id="uuid")
            Get: manage_task(action="get", task_id="uuid")
            Update: manage_task(action="update", task_id="uuid", update_fields={"status": "doing"})
            Archive: manage_task(action="archive", task_id="uuid")
        """
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
                            "sources": sources,
                            "code_examples": code_examples
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return json.dumps({"success": True, "task": result.get("task"), "message": result.get("message")})
                    else:
                        error_detail = response.text
                        return json.dumps({"success": False, "error": error_detail})
            
            elif action == "list":
                # Build URL with query parameters based on filter type
                params = {
                    "page": page,
                    "per_page": per_page,
                    "exclude_large_fields": True,  # Always exclude large fields in MCP responses
                }
                
                # Use different endpoints based on filter type for proper parameter handling
                if filter_by == "project" and filter_value:
                    # Use project-specific endpoint for project filtering
                    url = urljoin(api_url, f"/api/projects/{filter_value}/tasks")
                    params["include_archived"] = False  # For backward compatibility
                    
                    # Only add include_closed logic for project filtering
                    if not include_closed:
                        # This endpoint handles done task filtering differently
                        pass  # Let the endpoint handle it
                elif filter_by == "status" and filter_value:
                    # Use generic tasks endpoint for status filtering
                    url = urljoin(api_url, "/api/tasks")
                    params["status"] = filter_value
                    params["include_closed"] = include_closed
                    # Add project_id if provided
                    if project_id:
                        params["project_id"] = project_id
                else:
                    # Default to generic tasks endpoint
                    url = urljoin(api_url, "/api/tasks")
                    params["include_closed"] = include_closed
                
                # Make the API call
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    
                    result = response.json()
                    
                    # Handle both direct array and paginated response formats
                    if isinstance(result, list):
                        # Direct array response
                        tasks = result
                        pagination_info = None
                    else:
                        # Paginated response or object with tasks property
                        if "tasks" in result:
                            tasks = result.get("tasks", [])
                            pagination_info = result.get("pagination", {})
                        else:
                            # Direct array in object form
                            tasks = result if isinstance(result, list) else []
                            pagination_info = None
                    
                    return json.dumps({
                        "success": True, 
                        "tasks": tasks,
                        "pagination": pagination_info,
                        "total_count": len(tasks) if pagination_info is None else pagination_info.get("total", len(tasks))
                    })
            
            elif action == "get":
                if not task_id:
                    return json.dumps({"success": False, "error": "task_id is required for get action"})
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(urljoin(api_url, f"/api/tasks/{task_id}"))
                    
                    if response.status_code == 200:
                        task = response.json()
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
        try:
            api_url = get_api_url()
            timeout = httpx.Timeout(30.0, connect=5.0)
            
            if action == "add":
                if not document_type:
                    return json.dumps({"success": False, "error": "document_type is required for add action"})
                if not title:
                    return json.dumps({"success": False, "error": "title is required for add action"})
                
                # Call Server API to create document
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        urljoin(api_url, f"/api/projects/{project_id}/docs"),
                        json={
                            "document_type": document_type,
                            "title": title,
                            "content": content,
                            "tags": metadata.get("tags") if metadata else None,
                            "author": metadata.get("author") if metadata else None
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return json.dumps({"success": True, "document": result.get("document"), "message": result.get("message")})
                    else:
                        error_detail = response.text
                        return json.dumps({"success": False, "error": error_detail})
            
            elif action == "list":
                async with httpx.AsyncClient(timeout=timeout) as client:
                    url = urljoin(api_url, f"/api/projects/{project_id}/docs")
                    logger.info(f"Calling document list API: {url}")
                    response = await client.get(url)
                    
                    logger.info(f"Document list API response: {response.status_code}")
                    if response.status_code == 200:
                        result = response.json()
                        return json.dumps({"success": True, **result})
                    else:
                        error_text = response.text
                        logger.error(f"Document list API error: {response.status_code} - {error_text}")
                        return json.dumps({"success": False, "error": f"HTTP {response.status_code}: {error_text}"})
            
            elif action == "get":
                if not doc_id:
                    return json.dumps({"success": False, "error": "doc_id is required for get action"})
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(urljoin(api_url, f"/api/projects/{project_id}/docs/{doc_id}"))
                    
                    if response.status_code == 200:
                        document = response.json()
                        return json.dumps({"success": True, "document": document})
                    elif response.status_code == 404:
                        return json.dumps({"success": False, "error": f"Document {doc_id} not found"})
                    else:
                        return json.dumps({"success": False, "error": "Failed to get document"})
            
            elif action == "update":
                if not doc_id:
                    return json.dumps({"success": False, "error": "doc_id is required for update action"})
                
                # Build update fields
                update_fields = {}
                if title is not None:
                    update_fields["title"] = title
                if content is not None:
                    update_fields["content"] = content
                if metadata:
                    if "tags" in metadata:
                        update_fields["tags"] = metadata["tags"]
                    if "author" in metadata:
                        update_fields["author"] = metadata["author"]
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.put(
                        urljoin(api_url, f"/api/projects/{project_id}/docs/{doc_id}"),
                        json=update_fields
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return json.dumps({"success": True, "document": result.get("document"), "message": result.get("message")})
                    else:
                        error_detail = response.text
                        return json.dumps({"success": False, "error": error_detail})
            
            elif action == "delete":
                if not doc_id:
                    return json.dumps({"success": False, "error": "doc_id is required for delete action"})
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.delete(urljoin(api_url, f"/api/projects/{project_id}/docs/{doc_id}"))
                    
                    if response.status_code == 200:
                        result = response.json()
                        return json.dumps({"success": True, "message": result.get("message")})
                    else:
                        return json.dumps({"success": False, "error": "Failed to delete document"})
            
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid action '{action}'. Must be one of: add, list, get, update, delete"
                })
            
        except Exception as e:
            logger.error(f"Error in manage_document: {e}")
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
        try:
            api_url = get_api_url()
            timeout = httpx.Timeout(30.0, connect=5.0)
            
            if action == "create":
                if not content:
                    return json.dumps({"success": False, "error": "content is required for create action"})
                
                # Call Server API to create version
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        urljoin(api_url, f"/api/projects/{project_id}/versions"),
                        json={
                            "field_name": field_name,
                            "content": content,
                            "change_summary": change_summary,
                            "change_type": "manual",
                            "document_id": document_id,
                            "created_by": created_by
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return json.dumps({"success": True, "version": result.get("version"), "message": result.get("message")})
                    else:
                        error_detail = response.text
                        return json.dumps({"success": False, "error": error_detail})
            
            elif action == "list":
                # Build URL with optional field_name parameter
                params = {}
                if field_name:
                    params["field_name"] = field_name
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(
                        urljoin(api_url, f"/api/projects/{project_id}/versions"),
                        params=params
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return json.dumps({"success": True, **result})
                    else:
                        return json.dumps({"success": False, "error": "Failed to list versions"})
            
            elif action == "get":
                if not version_number:
                    return json.dumps({"success": False, "error": "version_number is required for get action"})
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(
                        urljoin(api_url, f"/api/projects/{project_id}/versions/{field_name}/{version_number}")
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return json.dumps({"success": True, **result})
                    elif response.status_code == 404:
                        return json.dumps({"success": False, "error": f"Version {version_number} not found"})
                    else:
                        return json.dumps({"success": False, "error": "Failed to get version"})
            
            elif action == "restore":
                if not version_number:
                    return json.dumps({"success": False, "error": "version_number is required for restore action"})
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        urljoin(api_url, f"/api/projects/{project_id}/versions/{field_name}/{version_number}/restore"),
                        json={
                            "restored_by": created_by
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return json.dumps({"success": True, "message": result.get("message")})
                    else:
                        error_detail = response.text
                        return json.dumps({"success": False, "error": error_detail})
            
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid action '{action}'. Must be one of: create, list, get, restore"
                })
            
        except Exception as e:
            logger.error(f"Error in manage_versions: {e}")
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