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

# Import service classes
from ..services.projects.project_service import ProjectService
from ..services.projects.task_service import TaskService
from ..services.projects.document_service import DocumentService
from ..services.projects.versioning_service import VersioningService

# Import Logfire
from ..logfire_config import mcp_logger

# Import the direct function for FastAPI
from ..utils import get_supabase_client

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
                # Get Supabase client
                supabase_client = ctx.request_context.lifespan_context.supabase_client
                service = ProjectService(supabase_client)
                
                if action == "create":
                    if not title:
                        return json.dumps({"success": False, "error": "Title is required for create action"})
                    
                    success, result = service.create_project(title, prd, github_repo)
                    
                    # If project created successfully, try to add PRD document
                    if success and prd:
                        try:
                            doc_service = DocumentService(supabase_client)
                            doc_success, doc_result = doc_service.add_document(
                                project_id=result["project"]["id"],
                                document_type="prd",
                                title=f"{title} - Product Requirements Document",
                                content=prd,
                                tags=["prd", "requirements"],
                                author="System"
                            )
                            if not doc_success:
                                result["warning"] = "Project created but PRD document creation failed"
                        except Exception as e:
                            logger.warning(f"Failed to create PRD document: {e}")
                            result["warning"] = "Project created but PRD document creation failed"
                    
                    span.set_attribute("success", success)
                    if success:
                        span.set_attribute("project_id", result.get("project", {}).get("id"))
                    return json.dumps({"success": success, **result})
                
                elif action == "list":
                    success, result = service.list_projects()
                    span.set_attribute("success", success)
                    if success:
                        span.set_attribute("project_count", len(result.get("projects", [])))
                    return json.dumps({"success": success, **result})
                
                elif action == "get":
                    if not project_id:
                        return json.dumps({"success": False, "error": "project_id is required for get action"})
                    success, result = service.get_project(project_id)
                    span.set_attribute("success", success)
                    return json.dumps({"success": success, **result})
                
                elif action == "delete":
                    if not project_id:
                        return json.dumps({"success": False, "error": "project_id is required for delete action"})
                    success, result = service.delete_project(project_id)
                    span.set_attribute("success", success)
                    return json.dumps({"success": success, **result})
                
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
                # Get Supabase client
                supabase_client = ctx.request_context.lifespan_context.supabase_client
                service = TaskService(supabase_client)
                
                if action == "create":
                    if not project_id:
                        return json.dumps({"success": False, "error": "project_id is required for create action"})
                    if not title:
                        return json.dumps({"success": False, "error": "title is required for create action"})
                    
                    success, result = service.create_task(
                        project_id, title, description, assignee, task_order,
                        feature, parent_task_id, sources, code_examples
                    )
                    span.set_attribute("success", success)
                    if success:
                        span.set_attribute("task_id", result.get("task", {}).get("id"))
                    return json.dumps({"success": success, **result})
                
                elif action == "list":
                    # Determine filters based on filter_by
                    list_project_id = None
                    list_parent_id = None
                    list_status = None
                    
                    if filter_by == "project" and filter_value:
                        list_project_id = filter_value
                    elif filter_by == "parent" and filter_value:
                        list_parent_id = filter_value
                    elif filter_by == "status" and filter_value:
                        list_status = filter_value
                        list_project_id = project_id  # Status filter usually needs project context
                    elif project_id:  # Default to project filter if project_id provided
                        list_project_id = project_id
                    
                    success, result = service.list_tasks(
                        project_id=list_project_id,
                        parent_task_id=list_parent_id,
                        status=list_status,
                        include_closed=include_closed
                    )
                    span.set_attribute("success", success)
                    if success:
                        span.set_attribute("task_count", len(result.get("tasks", [])))
                    return json.dumps({"success": success, **result})
                
                elif action == "get":
                    if not task_id:
                        return json.dumps({"success": False, "error": "task_id is required for get action"})
                    success, result = service.get_task(task_id)
                    span.set_attribute("success", success)
                    return json.dumps({"success": success, **result})
                
                elif action == "update":
                    if not task_id:
                        return json.dumps({"success": False, "error": "task_id is required for update action"})
                    if not update_fields:
                        return json.dumps({"success": False, "error": "update_fields is required for update action"})
                    
                    success, result = service.update_task(task_id, update_fields)
                    
                    # Broadcast WebSocket update if available
                    if success:
                        progress_callback = getattr(ctx, 'progress_callback', None)
                        if progress_callback:
                            try:
                                await progress_callback(
                                    event_type="task_updated",
                                    task_data=result.get("task")
                                )
                            except Exception as ws_error:
                                logger.warning(f"Failed to broadcast WebSocket update: {ws_error}")
                    
                    span.set_attribute("success", success)
                    return json.dumps({"success": success, **result})
                
                elif action in ["delete", "archive"]:
                    if not task_id:
                        return json.dumps({"success": False, "error": "task_id is required for delete/archive action"})
                    success, result = service.archive_task(task_id)
                    span.set_attribute("success", success)
                    return json.dumps({"success": success, **result})
                
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
                # Get Supabase client
                supabase_client = ctx.request_context.lifespan_context.supabase_client
                service = DocumentService(supabase_client)
                
                if action == "add":
                    if not document_type:
                        return json.dumps({"success": False, "error": "document_type is required for add action"})
                    if not title:
                        return json.dumps({"success": False, "error": "title is required for add action"})
                    
                    # Extract metadata fields
                    tags = metadata.get("tags") if metadata else None
                    author = metadata.get("author") if metadata else None
                    
                    success, result = service.add_document(
                        project_id, document_type, title, content, tags, author
                    )
                    span.set_attribute("success", success)
                    if success:
                        span.set_attribute("doc_id", result.get("document", {}).get("id"))
                    return json.dumps({"success": success, **result})
                
                elif action == "list":
                    success, result = service.list_documents(project_id)
                    span.set_attribute("success", success)
                    if success:
                        span.set_attribute("document_count", len(result.get("documents", [])))
                    return json.dumps({"success": success, **result})
                
                elif action == "get":
                    if not doc_id:
                        return json.dumps({"success": False, "error": "doc_id is required for get action"})
                    success, result = service.get_document(project_id, doc_id)
                    span.set_attribute("success", success)
                    return json.dumps({"success": success, **result})
                
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
                        for key in ["status", "tags", "author", "version"]:
                            if key in metadata:
                                update_fields[key] = metadata[key]
                    
                    if not update_fields:
                        return json.dumps({"success": False, "error": "No fields to update"})
                    
                    success, result = service.update_document(project_id, doc_id, update_fields)
                    span.set_attribute("success", success)
                    return json.dumps({"success": success, **result})
                
                elif action == "delete":
                    if not doc_id:
                        return json.dumps({"success": False, "error": "doc_id is required for delete action"})
                    success, result = service.delete_document(project_id, doc_id)
                    span.set_attribute("success", success)
                    return json.dumps({"success": success, **result})
                
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Invalid action '{action}'. Must be one of: add, list, get, update, delete"
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
                # Get Supabase client
                supabase_client = ctx.request_context.lifespan_context.supabase_client
                service = VersioningService(supabase_client)
                
                if action == "create":
                    if not content:
                        return json.dumps({"success": False, "error": "content is required for create action"})
                    
                    success, result = service.create_version(
                        project_id, field_name, content, change_summary,
                        "update", document_id, created_by
                    )
                    span.set_attribute("success", success)
                    if success:
                        span.set_attribute("version_number", result.get("version_number"))
                    return json.dumps({"success": success, **result})
                
                elif action == "list":
                    success, result = service.list_versions(project_id, field_name)
                    span.set_attribute("success", success)
                    if success:
                        span.set_attribute("version_count", len(result.get("versions", [])))
                    return json.dumps({"success": success, **result})
                
                elif action == "get":
                    if version_number is None:
                        return json.dumps({"success": False, "error": "version_number is required for get action"})
                    success, result = service.get_version_content(project_id, field_name, version_number)
                    span.set_attribute("success", success)
                    return json.dumps({"success": success, **result})
                
                elif action == "restore":
                    if version_number is None:
                        return json.dumps({"success": False, "error": "version_number is required for restore action"})
                    success, result = service.restore_version(project_id, field_name, version_number, created_by)
                    span.set_attribute("success", success)
                    return json.dumps({"success": success, **result})
                
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Invalid action '{action}'. Must be one of: create, list, get, restore"
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
            # Get Supabase client
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            service = ProjectService(supabase_client)
            
            success, result = service.get_project_features(project_id)
            return json.dumps({"success": success, **result})
            
        except Exception as e:
            logger.error(f"Error getting project features: {e}")
            return json.dumps({"success": False, "error": str(e)})
    
    logger.info("✓ Project Module registered with 5 consolidated tools")


# Direct function for FastAPI endpoints (following RAG pattern)
async def update_task_status_direct(ctx, task_id: str, status: str) -> str:
    """
    Direct function for updating task status that can be called from FastAPI with context.
    Follows the same pattern as RAG module's smart_crawl_url_direct.
    """
    try:
        # Get Supabase client directly
        supabase_client = get_supabase_client()
        service = TaskService(supabase_client)
        
        # Update task status
        success, result = service.update_task(task_id, {"status": status})
        
        if success:
            # Check for progress callback and broadcast WebSocket update
            progress_callback = getattr(ctx, 'progress_callback', None)
            if progress_callback:
                try:
                    await progress_callback(
                        event_type="task_updated",
                        task_data=result.get("task")
                    )
                    logger.info(f"WebSocket update broadcast for task {task_id}")
                except Exception as ws_error:
                    logger.warning(f"Failed to broadcast WebSocket update: {ws_error}")
        
        return json.dumps({"success": success, **result})
        
    except Exception as e:
        logger.error(f"Error updating task status: {str(e)}")
        return json.dumps({
            "success": False,
            "error": f"Error updating task status: {str(e)}"
        })