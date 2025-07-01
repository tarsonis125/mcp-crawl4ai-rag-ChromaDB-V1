"""
Source Management Service Module for Archon RAG

This module provides core source management functionality including
source retrieval, deletion, and metadata management.
"""

import json
# Removed direct logging import - using unified config
from typing import List, Dict, Any, Optional, Tuple

from src.server.utils import get_supabase_client, update_source_info, extract_source_summary
from ...config.logfire_config import get_logger

logger = get_logger(__name__)


class SourceManagementService:
    """Service class for source management operations"""
    
    def __init__(self, supabase_client=None):
        """Initialize with optional supabase client"""
        self.supabase_client = supabase_client or get_supabase_client()

    def get_available_sources(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Get all available sources from the sources table.
        
        Returns a list of all unique sources that have been crawled and stored.
        
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            response = self.supabase_client.table("sources").select("*").execute()
            
            sources = []
            for row in response.data:
                sources.append({
                    "source_id": row["source_id"],
                    "title": row.get("title", ""),
                    "description": row.get("description", ""),
                    "created_at": row.get("created_at", ""),
                    "last_updated": row.get("last_updated", "")
                })
            
            return True, {
                "sources": sources,
                "total_count": len(sources)
            }
            
        except Exception as e:
            logger.error(f"Error retrieving sources: {e}")
            return False, {"error": f"Error retrieving sources: {str(e)}"}

    def delete_source(self, source_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Delete a source and all associated crawled pages and code examples from the database.
        
        Args:
            source_id: The source ID to delete
        
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            logger.info(f"Starting delete_source for source_id: {source_id}")
            
            # Delete from crawled_pages table
            try:
                logger.info(f"Deleting from crawled_pages table for source_id: {source_id}")
                pages_response = self.supabase_client.table("crawled_pages").delete().eq("source_id", source_id).execute()
                pages_deleted = len(pages_response.data) if pages_response.data else 0
                logger.info(f"Deleted {pages_deleted} pages from crawled_pages")
            except Exception as pages_error:
                logger.error(f"Failed to delete from crawled_pages: {pages_error}")
                return False, {"error": f"Failed to delete crawled pages: {str(pages_error)}"}
            
            # Delete from code_examples table
            try:
                logger.info(f"Deleting from code_examples table for source_id: {source_id}")
                code_response = self.supabase_client.table("code_examples").delete().eq("source_id", source_id).execute()
                code_deleted = len(code_response.data) if code_response.data else 0
                logger.info(f"Deleted {code_deleted} code examples")
            except Exception as code_error:
                logger.error(f"Failed to delete from code_examples: {code_error}")
                return False, {"error": f"Failed to delete code examples: {str(code_error)}"}
            
            # Delete from sources table
            try:
                logger.info(f"Deleting from sources table for source_id: {source_id}")
                source_response = self.supabase_client.table("sources").delete().eq("source_id", source_id).execute()
                source_deleted = len(source_response.data) if source_response.data else 0
                logger.info(f"Deleted {source_deleted} source records")
            except Exception as source_error:
                logger.error(f"Failed to delete from sources: {source_error}")
                return False, {"error": f"Failed to delete source: {str(source_error)}"}
            
            logger.info(f"Delete operation completed successfully")
            return True, {
                "source_id": source_id,
                "pages_deleted": pages_deleted,
                "code_examples_deleted": code_deleted,
                "source_records_deleted": source_deleted
            }
            
        except Exception as e:
            logger.error(f"Unexpected error in delete_source: {e}")
            return False, {"error": f"Error deleting source: {str(e)}"}

    def update_source_metadata(self, source_id: str, title: str = None, description: str = None, 
                             word_count: int = None, knowledge_type: str = None, 
                             tags: List[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Update source metadata.
        
        Args:
            source_id: The source ID to update
            title: Optional new title
            description: Optional new description
            word_count: Optional new word count
            knowledge_type: Optional new knowledge type
            tags: Optional new tags list
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Build update data
            update_data = {}
            if title is not None:
                update_data["title"] = title
            if description is not None:
                update_data["description"] = description
            if word_count is not None:
                update_data["word_count"] = word_count
            if knowledge_type is not None:
                update_data["knowledge_type"] = knowledge_type
            if tags is not None:
                update_data["tags"] = tags
            
            if not update_data:
                return False, {"error": "No update data provided"}
            
            # Update the source
            response = self.supabase_client.table("sources").update(update_data).eq("source_id", source_id).execute()
            
            if response.data:
                return True, {"source_id": source_id, "updated_fields": list(update_data.keys())}
            else:
                return False, {"error": f"Source with ID {source_id} not found"}
                
        except Exception as e:
            logger.error(f"Error updating source metadata: {e}")
            return False, {"error": f"Error updating source metadata: {str(e)}"}

    def create_source_info(self, source_id: str, content_sample: str, word_count: int = 0, 
                          knowledge_type: str = "technical", tags: List[str] = None, 
                          update_frequency: int = 7) -> Tuple[bool, Dict[str, Any]]:
        """
        Create source information entry.
        
        Args:
            source_id: The source ID
            content_sample: Sample content for generating description
            word_count: Total word count for the source
            knowledge_type: Type of knowledge (default: "technical")
            tags: List of tags
            update_frequency: Update frequency in days
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            if tags is None:
                tags = []
                
            # Generate source summary/description
            source_summary = extract_source_summary(source_id, content_sample)
            
            # Create the source info
            update_source_info(
                self.supabase_client, 
                source_id, 
                source_summary, 
                word_count, 
                content_sample[:5000], 
                knowledge_type,
                tags,
                update_frequency
            )
            
            return True, {
                "source_id": source_id,
                "description": source_summary,
                "word_count": word_count,
                "knowledge_type": knowledge_type,
                "tags": tags
            }
            
        except Exception as e:
            logger.error(f"Error creating source info: {e}")
            return False, {"error": f"Error creating source info: {str(e)}"}

    def get_source_details(self, source_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Get detailed information about a specific source.
        
        Args:
            source_id: The source ID to look up
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Get source metadata
            source_response = self.supabase_client.table("sources").select("*").eq("source_id", source_id).execute()
            
            if not source_response.data:
                return False, {"error": f"Source with ID {source_id} not found"}
            
            source_data = source_response.data[0]
            
            # Get page count
            pages_response = self.supabase_client.table("crawled_pages").select("id").eq("source_id", source_id).execute()
            page_count = len(pages_response.data) if pages_response.data else 0
            
            # Get code example count
            code_response = self.supabase_client.table("code_examples").select("id").eq("source_id", source_id).execute()
            code_count = len(code_response.data) if code_response.data else 0
            
            return True, {
                "source": source_data,
                "page_count": page_count,
                "code_example_count": code_count
            }
            
        except Exception as e:
            logger.error(f"Error getting source details: {e}")
            return False, {"error": f"Error getting source details: {str(e)}"}

    def list_sources_by_type(self, knowledge_type: str = None) -> Tuple[bool, Dict[str, Any]]:
        """
        List sources filtered by knowledge type.
        
        Args:
            knowledge_type: Optional knowledge type filter
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            query = self.supabase_client.table("sources").select("*")
            
            if knowledge_type:
                query = query.eq("knowledge_type", knowledge_type)
            
            response = query.execute()
            
            sources = []
            for row in response.data:
                sources.append({
                    "source_id": row["source_id"],
                    "title": row.get("title", ""),
                    "description": row.get("description", ""),
                    "knowledge_type": row.get("knowledge_type", ""),
                    "tags": row.get("tags", []),
                    "word_count": row.get("word_count", 0),
                    "created_at": row.get("created_at", ""),
                    "last_updated": row.get("last_updated", "")
                })
            
            return True, {
                "sources": sources,
                "total_count": len(sources),
                "knowledge_type_filter": knowledge_type
            }
            
        except Exception as e:
            logger.error(f"Error listing sources by type: {e}")
            return False, {"error": f"Error listing sources by type: {str(e)}"}