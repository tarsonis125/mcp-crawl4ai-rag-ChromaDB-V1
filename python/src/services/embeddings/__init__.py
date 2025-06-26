"""
Embedding Services

Handles all embedding-related operations.
"""
from .embedding_service import (
    create_embedding,
    create_embeddings_batch,
    create_embedding_async,
    create_embeddings_batch_async,
    get_openai_client,
    get_openai_api_key,
    get_openai_api_key_sync
)

from .contextual_embedding_service import (
    generate_contextual_embedding,
    generate_contextual_embedding_async,
    generate_contextual_embeddings_batch,
    process_chunk_with_context,
    process_chunk_with_context_async
)

__all__ = [
    # Embedding functions
    'create_embedding',
    'create_embeddings_batch',
    'create_embedding_async',
    'create_embeddings_batch_async',
    'get_openai_client',
    
    # Deprecated functions
    'get_openai_api_key',
    'get_openai_api_key_sync',
    
    # Contextual embedding functions
    'generate_contextual_embedding',
    'generate_contextual_embedding_async',
    'generate_contextual_embeddings_batch',
    'process_chunk_with_context',
    'process_chunk_with_context_async'
]