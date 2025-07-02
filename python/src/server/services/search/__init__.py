"""
Search Services

Handles vector search operations for documents and code.
"""
from .vector_search_service import (
    search_documents,
    search_code_examples
)
from .search_services import SearchService

__all__ = [
    # Service classes
    'SearchService',
    
    # Search utilities
    'search_documents',
    'search_code_examples'
]