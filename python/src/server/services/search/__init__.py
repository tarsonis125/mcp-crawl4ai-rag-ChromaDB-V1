"""
Search Services

Handles vector search operations for documents and code.
"""
from .vector_search_service import (
    search_documents,
    search_code_examples
)

__all__ = [
    'search_documents',
    'search_code_examples'
]