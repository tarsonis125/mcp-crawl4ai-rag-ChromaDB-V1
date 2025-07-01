"""
Projects Services Package

This package contains all services related to project management,
including project CRUD operations, task management, document management,
versioning, progress tracking, source linking, and AI-assisted project creation.
"""

from .project_service import ProjectService
from .task_service import TaskService
from .document_service import DocumentService
from .versioning_service import VersioningService
from .progress_service import ProgressService, progress_service
from .project_creation_service import ProjectCreationService
from .source_linking_service import SourceLinkingService

__all__ = [
    "ProjectService",
    "TaskService", 
    "DocumentService",
    "VersioningService",
    "ProgressService",
    "progress_service",
    "ProjectCreationService",
    "SourceLinkingService"
]