"""
Projects Services Package

This package contains all services related to project management,
including project CRUD operations, task management, document management,
and versioning.
"""

from .project_service import ProjectService
from .task_service import TaskService
from .document_service import DocumentService
from .versioning_service import VersioningService

__all__ = [
    "ProjectService",
    "TaskService", 
    "DocumentService",
    "VersioningService"
]