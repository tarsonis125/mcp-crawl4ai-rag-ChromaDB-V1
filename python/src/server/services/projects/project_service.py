"""
Project Service Module for Archon

This module provides core business logic for project operations that can be
shared between MCP tools and FastAPI endpoints. It follows the pattern of
separating business logic from transport-specific code.
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from src.utils import get_supabase_client

logger = logging.getLogger(__name__)


class ProjectService:
    """Service class for project operations"""
    
    def __init__(self, supabase_client=None):
        """Initialize with optional supabase client"""
        self.supabase_client = supabase_client or get_supabase_client()
    
    def create_project(self, title: str, prd: Dict[str, Any] = None, github_repo: str = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Create a new project with optional PRD and GitHub repo.
        
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Validate inputs
            if not title or not isinstance(title, str) or len(title.strip()) == 0:
                return False, {"error": "Project title is required and must be a non-empty string"}
            
            # Create project data
            project_data = {
                "title": title.strip(),
                "docs": [],  # Will add PRD document after creation
                "features": [],
                "data": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            if github_repo and isinstance(github_repo, str) and len(github_repo.strip()) > 0:
                project_data["github_repo"] = github_repo.strip()
            
            # Insert project
            response = self.supabase_client.table("projects").insert(project_data).execute()
            
            if not response.data:
                logger.error("Supabase returned empty data for project creation")
                return False, {"error": "Failed to create project - database returned no data"}
            
            project = response.data[0]
            project_id = project["id"]
            logger.info(f"Project created successfully with ID: {project_id}")
            
            return True, {
                "project": {
                    "id": project_id,
                    "title": project["title"],
                    "github_repo": project.get("github_repo"),
                    "created_at": project["created_at"]
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating project: {e}")
            return False, {"error": f"Database error: {str(e)}"}
    
    def list_projects(self) -> Tuple[bool, Dict[str, Any]]:
        """
        List all projects.
        
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            response = self.supabase_client.table("projects").select("*").order("created_at", desc=True).execute()
            
            projects = []
            for project in response.data:
                projects.append({
                    "id": project["id"],
                    "title": project["title"],
                    "github_repo": project.get("github_repo"),
                    "created_at": project["created_at"],
                    "updated_at": project["updated_at"]
                })
            
            return True, {
                "projects": projects,
                "total_count": len(projects)
            }
            
        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return False, {"error": f"Error listing projects: {str(e)}"}
    
    def get_project(self, project_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Get a specific project by ID.
        
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            response = self.supabase_client.table("projects").select("*").eq("id", project_id).execute()
            
            if response.data:
                project = response.data[0]
                
                # Get linked sources
                technical_sources = []
                business_sources = []
                
                try:
                    # Get source IDs from project_sources table
                    sources_response = self.supabase_client.table("project_sources").select("source_id, notes").eq("project_id", project["id"]).execute()
                    
                    # Collect source IDs by type
                    technical_source_ids = []
                    business_source_ids = []
                    
                    for source_link in sources_response.data:
                        if source_link.get("notes") == "technical":
                            technical_source_ids.append(source_link["source_id"])
                        elif source_link.get("notes") == "business":
                            business_source_ids.append(source_link["source_id"])
                    
                    # Fetch full source objects
                    if technical_source_ids:
                        tech_sources_response = self.supabase_client.table("sources").select("*").in_("source_id", technical_source_ids).execute()
                        technical_sources = tech_sources_response.data
                    
                    if business_source_ids:
                        biz_sources_response = self.supabase_client.table("sources").select("*").in_("source_id", business_source_ids).execute()
                        business_sources = biz_sources_response.data
                        
                except Exception as e:
                    logger.warning(f"Failed to retrieve linked sources for project {project['id']}: {e}")
                
                # Add sources to project data
                project["technical_sources"] = technical_sources
                project["business_sources"] = business_sources
                
                return True, {"project": project}
            else:
                return False, {"error": f"Project with ID {project_id} not found"}
                
        except Exception as e:
            logger.error(f"Error getting project: {e}")
            return False, {"error": f"Error getting project: {str(e)}"}
    
    def delete_project(self, project_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Delete a project and all its associated tasks.
        
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # First, get task count for reporting
            tasks_response = self.supabase_client.table("tasks").select("id").eq("project_id", project_id).execute()
            tasks_count = len(tasks_response.data) if tasks_response.data else 0
            
            # Delete the project (tasks will be deleted by cascade)
            response = self.supabase_client.table("projects").delete().eq("id", project_id).execute()
            
            if response.data:
                return True, {
                    "project_id": project_id,
                    "deleted_tasks": tasks_count
                }
            else:
                return False, {"error": f"Project with ID {project_id} not found"}
                
        except Exception as e:
            logger.error(f"Error deleting project: {e}")
            return False, {"error": f"Error deleting project: {str(e)}"}
    
    def get_project_features(self, project_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Get features from a project's features JSONB field.
        
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            response = self.supabase_client.table("projects").select("features").eq("id", project_id).single().execute()
            
            if not response.data:
                return False, {"error": "Project not found"}
            
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
            
            return True, {
                "features": feature_options,
                "count": len(feature_options)
            }
            
        except Exception as e:
            logger.error(f"Error getting project features: {e}")
            return False, {"error": f"Error getting project features: {str(e)}"}