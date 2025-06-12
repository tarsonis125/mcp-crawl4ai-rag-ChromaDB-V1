"""
Document Versioning Module for Archon MCP Server

Simple but effective version control for JSONB fields in projects and tasks.
Compatible with BlockNote editor and existing MCP format.
"""

import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP, Context
from ..utils import get_supabase_client


def register_versioning_tools(mcp: FastMCP):
    """Register document versioning tools with the MCP server"""

    @mcp.tool()
    async def create_document_version(
        ctx: Context, 
        project_id: str, 
        field_name: str, 
        content: Dict[str, Any], 
        change_summary: str = None, 
        change_type: str = "update",
        document_id: str = None,
        created_by: str = "system"
    ) -> str:
        """
        Create a version snapshot for a project JSONB field.
        
        Args:
            ctx: MCP server context
            project_id: UUID of the project
            field_name: Name of the JSONB field ('docs', 'features', 'data', 'prd')
            content: The current content to snapshot
            change_summary: Human-readable description of changes
            change_type: Type of change ('create', 'update', 'delete', 'restore')
            document_id: For docs array, the specific document ID
            created_by: Who created this version
        
        Returns:
            JSON string with version creation results
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            # Get current highest version number for this project/field
            existing_versions = supabase_client.table("document_versions").select("version_number").eq("project_id", project_id).eq("field_name", field_name).order("version_number", desc=True).limit(1).execute()
            
            next_version = 1
            if existing_versions.data:
                next_version = existing_versions.data[0]['version_number'] + 1
            
            # Create new version record
            version_data = {
                'project_id': project_id,
                'field_name': field_name,
                'version_number': next_version,
                'content': content,
                'change_summary': change_summary or f"{change_type.capitalize()} {field_name}",
                'change_type': change_type,
                'document_id': document_id,
                'created_by': created_by,
                'created_at': datetime.now().isoformat()
            }
            
            result = supabase_client.table("document_versions").insert(version_data).execute()
            
            if result.data:
                return json.dumps({
                    "success": True,
                    "version": result.data[0],
                    "project_id": project_id,
                    "field_name": field_name,
                    "version_number": next_version
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": "Failed to create version snapshot"
                })
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error creating version: {str(e)}"
            })

    @mcp.tool()
    async def get_document_version_history(
        ctx: Context, 
        project_id: str, 
        field_name: str = None
    ) -> str:
        """
        Get version history for project JSONB fields.
        
        Args:
            ctx: MCP server context
            project_id: UUID of the project
            field_name: Optional specific field name to filter by
        
        Returns:
            JSON string with version history
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            # Build query
            query = supabase_client.table("document_versions").select("*").eq("project_id", project_id)
            
            if field_name:
                query = query.eq("field_name", field_name)
            
            # Get versions ordered by version number descending
            result = query.order("version_number", desc=True).execute()
            
            if result.data is not None:
                return json.dumps({
                    "success": True,
                    "project_id": project_id,
                    "field_name": field_name,
                    "versions": result.data,
                    "total_count": len(result.data)
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": "Failed to retrieve version history"
                })
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error getting version history: {str(e)}"
            })

    @mcp.tool()
    async def get_version_content(
        ctx: Context, 
        project_id: str = None, 
        field_name: str = None, 
        version_number: int = None
    ) -> str:
        """
        Get the content of a specific version for preview or comparison.
        
        UPDATED: Removed task_id support as task versioning has been removed.
        Only supports project document versioning now.
        
        Args:
            ctx: MCP server context
            project_id: UUID of the project (for document versions)
            field_name: Name of the JSONB field
            version_number: Version number to retrieve
        
        Returns:
            JSON string with version content
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            # Only support project document versions now
            if not project_id:
                return json.dumps({
                    "success": False,
                    "error": "project_id is required - task versioning has been removed"
                })
            
            # Build query for project document versions only
            query = supabase_client.table("document_versions").select("*").eq("project_id", project_id)
            
            # Add field and version filters
            result = query.eq("field_name", field_name).eq("version_number", version_number).execute()
            
            if result.data:
                version = result.data[0]
                return json.dumps({
                    "success": True,
                    "version": version,
                    "content": version['content'],
                    "field_name": field_name,
                    "version_number": version_number
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Version {version_number} not found for {field_name}"
                })
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error getting version content: {str(e)}"
            })

    @mcp.tool()
    async def restore_document_version(
        ctx: Context, 
        project_id: str, 
        field_name: str, 
        version_number: int, 
        restored_by: str = "system"
    ) -> str:
        """
        Restore a project JSONB field to a specific version.
        
        Args:
            ctx: MCP server context
            project_id: UUID of the project
            field_name: Name of the JSONB field to restore
            version_number: Version number to restore to
            restored_by: Who is performing the restore
        
        Returns:
            JSON string with restore results
        """
        try:
            supabase_client = ctx.request_context.lifespan_context.supabase_client
            
            # Get the version to restore
            version_result = supabase_client.table("document_versions").select("*").eq("project_id", project_id).eq("field_name", field_name).eq("version_number", version_number).execute()
            
            if not version_result.data:
                return json.dumps({
                    "success": False,
                    "error": f"Version {version_number} not found for {field_name} in project {project_id}"
                })
            
            version_to_restore = version_result.data[0]
            content_to_restore = version_to_restore['content']
            
            # Get current content to create backup
            current_project = supabase_client.table("projects").select(field_name).eq("id", project_id).execute()
            if current_project.data:
                current_content = current_project.data[0].get(field_name, {})
                
                # Create backup version before restore
                backup_version_data = {
                    'project_id': project_id,
                    'field_name': field_name,
                    'version_number': 0,  # Will be updated below
                    'content': current_content,
                    'change_summary': f"Backup before restoring to version {version_number}",
                    'change_type': 'backup',
                    'created_by': restored_by,
                    'created_at': datetime.now().isoformat()
                }
                
                # Get next version number
                existing_versions = supabase_client.table("document_versions").select("version_number").eq("project_id", project_id).eq("field_name", field_name).order("version_number", desc=True).limit(1).execute()
                next_version = 1
                if existing_versions.data:
                    next_version = existing_versions.data[0]['version_number'] + 1
                backup_version_data['version_number'] = next_version
                
                # Insert backup
                supabase_client.table("document_versions").insert(backup_version_data).execute()
            
            # Restore the content to project
            update_data = {
                field_name: content_to_restore,
                'updated_at': datetime.now().isoformat()
            }
            
            restore_result = supabase_client.table("projects").update(update_data).eq("id", project_id).execute()
            
            if restore_result.data:
                # Create restore version record
                restore_version_data = {
                    'project_id': project_id,
                    'field_name': field_name,
                    'version_number': next_version + 1,
                    'content': content_to_restore,
                    'change_summary': f"Restored to version {version_number}",
                    'change_type': 'restore',
                    'created_by': restored_by,
                    'created_at': datetime.now().isoformat()
                }
                supabase_client.table("document_versions").insert(restore_version_data).execute()
                
                return json.dumps({
                    "success": True,
                    "project_id": project_id,
                    "field_name": field_name,
                    "restored_version": version_number,
                    "restored_by": restored_by
                })
            else:
                return json.dumps({
                    "success": False,
                    "error": "Failed to restore version"
                })
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error restoring version: {str(e)}"
            })

# Direct functions for FastAPI (following RAG module pattern)

async def get_document_version_history_direct(project_id: str, field_name: str = None) -> str:
    """
    Direct function for getting document version history that can be called from FastAPI.
    Follows the same pattern as RAG module's direct functions.
    """
    try:
        supabase_client = get_supabase_client()
        
        # Build query
        query = supabase_client.table("document_versions").select("*").eq("project_id", project_id)
        
        if field_name:
            query = query.eq("field_name", field_name)
        
        # Get versions ordered by version number descending (most recent first)
        result = query.order("version_number", desc=True).execute()
        
        if result.data is not None:
            return json.dumps({
                "success": True,
                "project_id": project_id,
                "field_name": field_name,
                "versions": result.data,
                "total_count": len(result.data)
            })
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to retrieve version history"
            })
                
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Error getting document version history: {str(e)}"
        })

async def get_version_content_direct(project_id: str = None, field_name: str = None, version_number: int = None) -> str:
    """
    Direct function for getting version content that can be called from FastAPI.
    
    UPDATED: Removed task_id support as task versioning has been removed.
    Only supports project document versioning now.
    """
    try:
        supabase_client = get_supabase_client()
        
        # Validate required parameters
        if not field_name or version_number is None:
            return json.dumps({
                "success": False,
                "error": "field_name and version_number are required"
            })
        
        if not project_id:
            return json.dumps({
                "success": False,
                "error": "project_id is required - task versioning has been removed"
            })
        
        # Build query for project document versions only
        query = supabase_client.table("document_versions").select("*").eq("field_name", field_name).eq("version_number", version_number).eq("project_id", project_id)
        
        result = query.single().execute()
        
        if result.data:
            return json.dumps({
                "success": True,
                "version": result.data,
                "content": result.data.get("content"),
                "version_number": version_number,
                "field_name": field_name
            })
        else:
            return json.dumps({
                "success": False,
                "error": f"Version {version_number} not found for {field_name}"
            })
                
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Error getting version content: {str(e)}"
        })

async def restore_document_version_direct(project_id: str, field_name: str, version_number: int, restored_by: str = "system") -> str:
    """
    Direct function for restoring document version that can be called from FastAPI.
    """
    try:
        supabase_client = get_supabase_client()
        
        # Get the version to restore
        version_result = supabase_client.table("document_versions").select("*").eq("project_id", project_id).eq("field_name", field_name).eq("version_number", version_number).single().execute()
        
        if not version_result.data:
            return json.dumps({
                "success": False,
                "error": f"Version {version_number} not found"
            })
        
        version_content = version_result.data.get("content")
        
        # Update the project with the restored content
        update_data = {
            field_name: version_content,
            "updated_at": datetime.now().isoformat()
        }
        
        restore_result = supabase_client.table("projects").update(update_data).eq("id", project_id).execute()
        
        if restore_result.data:
            # Create a new version record for the restore operation
            restore_version_data = {
                'project_id': project_id,
                'field_name': field_name,
                'content': version_content,
                'change_summary': f"Restored to version {version_number}",
                'change_type': 'restore',
                'created_by': restored_by,
                'created_at': datetime.now().isoformat()
            }
            
            # Get next version number
            existing_versions = supabase_client.table("document_versions").select("version_number").eq("project_id", project_id).eq("field_name", field_name).order("version_number", desc=True).limit(1).execute()
            
            next_version = 1
            if existing_versions.data:
                next_version = existing_versions.data[0]['version_number'] + 1
            
            restore_version_data['version_number'] = next_version
            
            # Insert restore version
            supabase_client.table("document_versions").insert(restore_version_data).execute()
            
            return json.dumps({
                "success": True,
                "project_id": project_id,
                "field_name": field_name,
                "restored_to_version": version_number,
                "new_version_number": next_version,
                "message": f"Successfully restored {field_name} to version {version_number}"
            })
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to restore project data"
            })
                
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Error restoring document version: {str(e)}"
        })

async def create_document_version_direct(
    project_id: str, 
    field_name: str, 
    content: Dict[str, Any], 
    change_summary: str = None, 
    change_type: str = "update",
    document_id: str = None,
    created_by: str = "system"
) -> str:
    """
    Direct function for creating document version that can be called from FastAPI.
    """
    try:
        supabase_client = get_supabase_client()
        
        # Get current highest version number for this project/field
        existing_versions = supabase_client.table("document_versions").select("version_number").eq("project_id", project_id).eq("field_name", field_name).order("version_number", desc=True).limit(1).execute()
        
        next_version = 1
        if existing_versions.data:
            next_version = existing_versions.data[0]['version_number'] + 1
        
        # Create new version record
        version_data = {
            'project_id': project_id,
            'field_name': field_name,
            'version_number': next_version,
            'content': content,
            'change_summary': change_summary or f"{change_type.capitalize()} {field_name}",
            'change_type': change_type,
            'document_id': document_id,
            'created_by': created_by,
            'created_at': datetime.now().isoformat()
        }
        
        result = supabase_client.table("document_versions").insert(version_data).execute()
        
        if result.data:
            return json.dumps({
                "success": True,
                "version": result.data[0],
                "project_id": project_id,
                "field_name": field_name,
                "version_number": next_version
            })
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to create version snapshot"
            })
            
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Error creating version: {str(e)}"
        }) 