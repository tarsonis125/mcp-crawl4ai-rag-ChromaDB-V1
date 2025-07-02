"""
Utility functions for the Crawl4AI MCP server - Compatibility Layer

This file now serves as a compatibility layer, importing functions from
the new service modules to maintain backward compatibility.

The actual implementations have been moved to:
- services/embeddings/ - Embedding operations
- services/storage/ - Document and code storage
- services/search/ - Vector search operations
- services/source_management_service.py - Source metadata
- services/client_manager.py - Client connections
"""

# Import all functions from new services for backward compatibility
from ..services.embeddings import (
    create_embedding,
    create_embeddings_batch,
    create_embedding_async,
    create_embeddings_batch_async,
    get_openai_client,
    get_openai_api_key,
    get_openai_api_key_sync,
    generate_contextual_embedding,
    generate_contextual_embedding_async,
    generate_contextual_embeddings_batch,
    process_chunk_with_context,
    process_chunk_with_context_async
)

# Note: storage and search imports removed to avoid circular dependency
# Import these directly from their modules when needed:
# from ..services.storage import add_documents_to_supabase, extract_code_blocks, etc.
# from ..services.search import search_documents, search_code_examples

from ..services.source_management_service import (
    extract_source_summary,
    generate_source_title_and_metadata,
    update_source_info
)

from ..services.client_manager import (
    get_supabase_client
)

# Re-export threading service imports for compatibility
from ..services.threading_service import (
    get_threading_service, 
    ProcessingMode, 
    ThreadingConfig, 
    RateLimitConfig
)

# Keep some imports that are still needed
import os
import asyncio
from typing import Optional

# Global threading service instance for optimization
_threading_service = None

async def initialize_threading_service(
    threading_config: Optional[ThreadingConfig] = None,
    rate_limit_config: Optional[RateLimitConfig] = None
):
    """Initialize the global threading service for utilities"""
    global _threading_service
    if _threading_service is None:
        from ..services.threading_service import ThreadingService
        _threading_service = ThreadingService(threading_config, rate_limit_config)
        await _threading_service.start()
    return _threading_service

def get_utils_threading_service():
    """Get the threading service instance (lazy initialization)"""
    global _threading_service
    if _threading_service is None:
        _threading_service = get_threading_service()
    return _threading_service

# Export all imported functions for backward compatibility
__all__ = [
    # Threading functions
    'initialize_threading_service',
    'get_utils_threading_service',
    'get_threading_service',
    'ProcessingMode',
    'ThreadingConfig',
    'RateLimitConfig',
    
    # Client functions
    'get_supabase_client',
    
    # Embedding functions
    'create_embedding',
    'create_embeddings_batch',
    'create_embedding_async',
    'create_embeddings_batch_async',
    'get_openai_client',
    'get_openai_api_key',
    'get_openai_api_key_sync',
    
    # Contextual embedding functions
    'generate_contextual_embedding',
    'generate_contextual_embedding_async',
    'generate_contextual_embeddings_batch',
    'process_chunk_with_context',
    'process_chunk_with_context_async',
    
    # Note: Document storage and search functions not exported from utils
    # to avoid circular dependencies. Import directly from services modules.
    
    # Source management functions
    'extract_source_summary',
    'generate_source_title_and_metadata',
    'update_source_info',
]