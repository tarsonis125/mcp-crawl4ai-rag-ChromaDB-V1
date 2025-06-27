"""
Search Service Module for Archon RAG

This module provides core search functionality including RAG queries,
code example search, hybrid search, and reranking capabilities.
"""

import json
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
# Reranking is now handled by Agents service via HTTP

from src.utils import get_supabase_client, search_documents, search_code_examples
from src.logfire_config import rag_logger, search_logger

logger = logging.getLogger(__name__)


class SearchService:
    """Service class for search operations"""
    
    def __init__(self, supabase_client=None, agents_client=None):
        """Initialize with optional supabase client and agents client for reranking"""
        self.supabase_client = supabase_client or get_supabase_client()
        self.agents_client = agents_client  # Will be injected for microservices mode

    def get_setting(self, key: str, default: str = "false") -> str:
        """Get a setting from the credential service or fall back to environment variable."""
        try:
            from src.credential_service import credential_service
            if hasattr(credential_service, '_cache') and credential_service._cache_initialized:
                cached_value = credential_service._cache.get(key)
                if isinstance(cached_value, dict) and cached_value.get("is_encrypted"):
                    encrypted_value = cached_value.get("encrypted_value")
                    if encrypted_value:
                        try:
                            return credential_service._decrypt_value(encrypted_value)
                        except Exception:
                            pass
                elif cached_value:
                    return str(cached_value)
            # Fallback to environment variable
            return os.getenv(key, default)
        except Exception:
            return os.getenv(key, default)

    def get_bool_setting(self, key: str, default: bool = False) -> bool:
        """Get a boolean setting from credential service."""
        value = self.get_setting(key, "false" if not default else "true")
        return value.lower() in ("true", "1", "yes", "on")

    async def rerank_results(self, query: str, results: List[Dict[str, Any]], content_key: str = "content") -> List[Dict[str, Any]]:
        """
        Rerank search results using the Agents service.
        
        Args:
            query: The search query
            results: List of search results
            content_key: The key in each result dict that contains the text content
            
        Returns:
            Reranked list of results
        """
        if not self.agents_client or not results:
            return results
        
        try:
            # Use the Agents service client to rerank results
            return await self.agents_client.rerank_results(query, results, content_key)
        except Exception as e:
            logger.error(f"Error reranking results: {str(e)}")
            # Return original results if reranking fails
            return results
            reranked = sorted(results, key=lambda x: x.get("rerank_score", 0), reverse=True)
            
            return reranked
        except Exception as e:
            logger.error(f"Error during reranking: {e}")
            return results

    def perform_rag_query(self, query: str, source: str = None, match_count: int = 5) -> Tuple[bool, Dict[str, Any]]:
        """
        Perform a RAG (Retrieval Augmented Generation) query on stored content.
        
        Args:
            query: The search query
            source: Optional source domain to filter results
            match_count: Maximum number of results to return
            
        Returns:
            Tuple of (success, result_dict)
        """
        with rag_logger.span("rag_query",
                            query_length=len(query),
                            source=source,
                            match_count=match_count,
                            client_type="service") as span:
            try:
                rag_logger.info("RAG query started",
                               query=query[:100] + "..." if len(query) > 100 else query,
                               source=source,
                               match_count=match_count)
                
                # Build filter metadata if source is provided
                filter_metadata = None
                if source:
                    with rag_logger.span("build_filter"):
                        filter_metadata = {"source": source}
                        rag_logger.debug("Built filter metadata", source=source)
                        span.set_attribute("filter_applied", True)
                
                # Perform vector search
                with rag_logger.span("vector_search"):
                    results = search_documents(
                        client=self.supabase_client,
                        query=query,
                        match_count=match_count,
                        filter_metadata=filter_metadata
                    )
                    span.set_attribute("raw_results_count", len(results))
                
                # Format results for response
                with rag_logger.span("format_response"):
                    formatted_results = []
                    for i, result in enumerate(results):
                        try:
                            formatted_result = {
                                "id": result.get("id", f"result_{i}"),
                                "content": result.get("content", "")[:1000],  # Limit content
                                "metadata": result.get("metadata", {}),
                                "similarity_score": result.get("similarity", 0.0)
                            }
                            formatted_results.append(formatted_result)
                        except Exception as format_error:
                            rag_logger.warning("Failed to format result", 
                                             result_index=i, 
                                             error=str(format_error))
                            continue
                
                response_data = {
                    "results": formatted_results,
                    "query": query,
                    "source": source,
                    "match_count": match_count,
                    "total_found": len(formatted_results),
                    "execution_path": "service_vector_search"
                }
                
                span.set_attribute("final_results_count", len(formatted_results))
                span.set_attribute("success", True)
                
                rag_logger.info("RAG query completed successfully",
                               results_count=len(formatted_results),
                               execution_path="service_vector_search")
                
                return True, response_data
                
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error_type", type(e).__name__)
                
                rag_logger.exception("RAG query failed",
                                    error=str(e),
                                    error_type=type(e).__name__,
                                    query=query[:50],
                                    source=source)
                
                return False, {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "query": query,
                    "source": source,
                    "execution_path": "service_vector_search"
                }

    async def search_code_examples_service(self, query: str, source_id: str = None, match_count: int = 5) -> Tuple[bool, Dict[str, Any]]:
        """
        Search for code examples relevant to the query.
        
        Args:
            query: The search query
            source_id: Optional source ID to filter results
            match_count: Maximum number of results to return
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Check if code example extraction is enabled
            extract_code_examples_enabled = self.get_bool_setting("USE_AGENTIC_RAG", False)
            if not extract_code_examples_enabled:
                return False, {
                    "error": "Code example extraction is disabled. Perform a normal RAG search."
                }
            
            # Check if hybrid search is enabled
            use_hybrid_search = self.get_bool_setting("USE_HYBRID_SEARCH", False)
            
            # Prepare filter if source is provided and not empty
            filter_metadata = None
            if source_id and source_id.strip():
                filter_metadata = {"source": source_id}  # Use "source" to match original
            
            if use_hybrid_search:
                # Hybrid search: combine vector and keyword search
                
                # 1. Get vector search results (get more to account for filtering)
                vector_results = search_code_examples(
                    client=self.supabase_client,
                    query=query,
                    match_count=match_count * 2,  # Get double to have room for filtering
                    filter_metadata=filter_metadata
                )
                
                # 2. Get keyword search results using ILIKE on both content and summary
                keyword_query = self.supabase_client.from_('code_examples')\
                    .select('id, url, chunk_number, content, summary, metadata, source_id')\
                    .or_(f'content.ilike.%{query}%,summary.ilike.%{query}%')
                
                # Apply source filter if provided
                if source_id and source_id.strip():
                    keyword_query = keyword_query.eq('source_id', source_id)
                
                # Execute keyword search
                keyword_response = keyword_query.limit(match_count * 2).execute()
                keyword_results = keyword_response.data if keyword_response.data else []
                
                # 3. Combine results with preference for items appearing in both
                seen_ids = set()
                combined_results = []
                
                # First, add items that appear in both searches (these are the best matches)
                vector_ids = {r.get('id') for r in vector_results if r.get('id')}
                for kr in keyword_results:
                    if kr['id'] in vector_ids and kr['id'] not in seen_ids:
                        # Find the vector result to get similarity score
                        for vr in vector_results:
                            if vr.get('id') == kr['id']:
                                # Boost similarity score for items in both results
                                vr['similarity'] = min(1.0, vr.get('similarity', 0) * 1.2)
                                combined_results.append(vr)
                                seen_ids.add(kr['id'])
                                break
                
                # Then add remaining vector results (semantic matches without exact keyword)
                for vr in vector_results:
                    if vr.get('id') and vr['id'] not in seen_ids and len(combined_results) < match_count:
                        combined_results.append(vr)
                        seen_ids.add(vr['id'])
                
                # Finally, add pure keyword matches if we still need more results
                for kr in keyword_results:
                    if kr['id'] not in seen_ids and len(combined_results) < match_count:
                        # Convert keyword result to match vector result format
                        combined_results.append({
                            'id': kr['id'],
                            'url': kr['url'],
                            'chunk_number': kr['chunk_number'],
                            'content': kr['content'],
                            'summary': kr['summary'],
                            'metadata': kr['metadata'],
                            'source_id': kr['source_id'],
                            'similarity': 0.5  # Default similarity for keyword-only matches
                        })
                        seen_ids.add(kr['id'])
                
                # Use combined results
                results = combined_results[:match_count]
                
            else:
                # Standard vector search only
                results = search_code_examples(
                    client=self.supabase_client,
                    query=query,
                    match_count=match_count,
                    filter_metadata=filter_metadata
                )
            
            # Apply reranking if enabled
            use_reranking = self.get_bool_setting("USE_RERANKING", False)
            if use_reranking and self.agents_client:
                results = await self.rerank_results(query, results, content_key="content")
            
            # Format the results
            formatted_results = []
            for result in results:
                formatted_result = {
                    "url": result.get("url"),
                    "code": result.get("content"),
                    "summary": result.get("summary"),
                    "metadata": result.get("metadata"),
                    "source_id": result.get("source_id"),
                    "similarity": result.get("similarity")
                }
                # Include rerank score if available
                if "rerank_score" in result:
                    formatted_result["rerank_score"] = result["rerank_score"]
                formatted_results.append(formatted_result)
            
            return True, {
                "query": query,
                "source_filter": source_id,
                "search_mode": "hybrid" if use_hybrid_search else "vector",
                "reranking_applied": use_reranking and self.agents_client is not None,
                "results": formatted_results,
                "count": len(formatted_results)
            }
            
        except Exception as e:
            logger.error(f"Error in code example search: {e}")
            return False, {
                "query": query,
                "error": str(e)
            }