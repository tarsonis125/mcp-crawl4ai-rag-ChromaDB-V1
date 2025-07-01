"""
Vector Search Service

Handles vector similarity search for documents and code examples.
"""
from typing import List, Dict, Any, Optional
from supabase import Client

from ...config.logfire_config import search_logger, safe_span
from ..embeddings.embedding_service import create_embedding


def search_documents(
    client: Client,
    query: str,
    match_count: int = 5,
    threshold: float = 0.7,
    filter_metadata: Optional[dict] = None,
    use_hybrid_search: bool = False,
    cached_api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search for documents in the database using semantic search.
    
    Args:
        client: Supabase client
        query: Search query string
        match_count: Number of results to return
        threshold: Similarity threshold for results
        filter_metadata: Optional metadata filter dict
        use_hybrid_search: Whether to use hybrid keyword + semantic search
        cached_api_key: Cached OpenAI API key for embeddings (deprecated)
    
    Returns:
        List of matching documents
    """
    with safe_span("vector_search", 
                           query_length=len(query),
                           match_count=match_count,
                           threshold=threshold,
                           has_filter=filter_metadata is not None) as span:
        try:
            search_logger.info("Document search started", 
                              query=query[:100] + "..." if len(query) > 100 else query,
                              match_count=match_count,
                              threshold=threshold,
                              filter_metadata=filter_metadata)
            
            # Create embedding for the query
            with safe_span("create_embedding"):
                query_embedding = create_embedding(query)
                
                if not query_embedding:
                    search_logger.error("Failed to create embedding for query")
                    return []
                
                span.set_attribute("embedding_dimensions", len(query_embedding))
            
            # Build the filter for the RPC call
            with safe_span("prepare_rpc_params"):
                rpc_params = {
                    "query_embedding": query_embedding,
                    "match_count": match_count
                }
                
                # Add filter to RPC params if provided
                if filter_metadata:
                    search_logger.debug("Adding filter to RPC params", filter_metadata=filter_metadata)
                    
                    # Check if we have a source filter specifically
                    if "source" in filter_metadata:
                        # Use the version with source_filter parameter
                        rpc_params["source_filter"] = filter_metadata["source"]
                        # Also add the general filter as empty jsonb to satisfy the function signature
                        rpc_params["filter"] = {}
                    else:
                        # Use the general filter parameter
                        rpc_params["filter"] = filter_metadata
                    
                    span.set_attribute("filter_applied", True)
                    span.set_attribute("filter_keys", list(filter_metadata.keys()) if filter_metadata else [])
                else:
                    # No filter provided - use empty jsonb for filter parameter
                    rpc_params["filter"] = {}
            
            # Call the RPC function
            with safe_span("supabase_rpc_call"):
                search_logger.debug("Calling Supabase RPC function", 
                                  function_name="match_crawled_pages",
                                  rpc_params_keys=list(rpc_params.keys()))
                
                response = client.rpc("match_crawled_pages", rpc_params).execute()
                span.set_attribute("rpc_success", True)
                span.set_attribute("raw_results_count", len(response.data) if response.data else 0)
            
            results_count = len(response.data) if response.data else 0
            
            span.set_attribute("success", True)
            span.set_attribute("final_results_count", results_count)
            
            search_logger.info("Document search completed", 
                              query=query[:100] + "..." if len(query) > 100 else query,
                              results_count=results_count)
            
            return response.data or []
        
        except Exception as e:
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            
            search_logger.error("Document search failed", 
                               query=query[:100] + "..." if len(query) > 100 else query,
                               error=str(e),
                               error_type=type(e).__name__)
            
            # Return empty list on error
            return []


def search_code_examples(
    client: Client, 
    query: str, 
    match_count: int = 10, 
    filter_metadata: Optional[Dict[str, Any]] = None,
    source_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search for code examples in Supabase using vector similarity.
    
    Args:
        client: Supabase client
        query: Query text
        match_count: Maximum number of results to return
        filter_metadata: Optional metadata filter
        source_id: Optional source ID to filter results
        
    Returns:
        List of matching code examples
    """
    # Create a more descriptive query for better embedding match
    # Since code examples are embedded with their summaries, we should make the query more descriptive
    enhanced_query = f"Code example for {query}\n\nSummary: Example code showing {query}"
    
    # Create embedding for the enhanced query
    query_embedding = create_embedding(enhanced_query)
    
    # Execute the search using the match_code_examples function
    try:
        # Only include filter parameter if filter_metadata is provided and not empty
        params = {
            'query_embedding': query_embedding,
            'match_count': match_count
        }
        
        # Only add the filter if it's actually provided and not empty
        if filter_metadata:
            params['filter'] = filter_metadata
            
        # Add source filter if provided
        if source_id:
            params['source_filter'] = source_id
        
        result = client.rpc('match_code_examples', params).execute()
        
        return result.data
    except Exception as e:
        search_logger.error(f"Error searching code examples: {e}")
        return []