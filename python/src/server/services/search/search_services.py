"""
Search Services

This module contains all search service classes that handle search and retrieval operations.
These services provide high-level search functionality including RAG queries, code search,
hybrid search, and reranking capabilities.
"""

import json
import os
from typing import List, Dict, Any, Optional, Tuple

# Import CrossEncoder for reranking if available
try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None

from ...utils import get_supabase_client
from .vector_search_service import search_documents, search_code_examples, search_documents_async
from ...config.logfire_config import safe_span, get_logger

logger = get_logger(__name__)


class SearchService:
    """Service class for search operations"""
    
    def __init__(self, supabase_client=None, reranking_model=None):
        """Initialize with optional supabase client and reranking model"""
        self.supabase_client = supabase_client or get_supabase_client()
        self.reranking_model = reranking_model  # CrossEncoder model for reranking

    def get_setting(self, key: str, default: str = "false") -> str:
        """Get a setting from the credential service or fall back to environment variable."""
        try:
            from ..credential_service import credential_service
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
        Rerank search results using the CrossEncoder model.
        
        Args:
            query: The search query
            results: List of search results
            content_key: The key in each result dict that contains the text content
            
        Returns:
            Reranked list of results
        """
        if not self.reranking_model or not results:
            return results
        
        try:
            # Extract texts from results
            texts = [result.get(content_key, "") for result in results]
            
            # Create query-document pairs for the CrossEncoder
            pairs = [[query, text] for text in texts]
            
            # Get reranking scores
            scores = self.reranking_model.predict(pairs)
            
            # Add scores to results and sort
            for i, result in enumerate(results):
                result["rerank_score"] = float(scores[i])
            
            # Sort by rerank score descending
            reranked = sorted(results, key=lambda x: x.get("rerank_score", 0), reverse=True)
            
            return reranked
        except Exception as e:
            logger.error(f"Error during reranking: {e}")
            return results

    async def perform_rag_query(self, query: str, source: str = None, match_count: int = 5) -> Tuple[bool, Dict[str, Any]]:
        """
        Perform a RAG (Retrieval Augmented Generation) query on stored content.
        
        Args:
            query: The search query
            source: Optional source domain to filter results
            match_count: Maximum number of results to return
            
        Returns:
            Tuple of (success, result_dict)
        """
        with safe_span("rag_query",
                            query_length=len(query),
                            source=source,
                            match_count=match_count,
                            client_type="service") as span:
            try:
                logger.info("RAG query started",
                           extra={"query": query[:100] + "..." if len(query) > 100 else query,
                                  "source": source,
                                  "match_count": match_count})
                
                # Build filter metadata if source is provided
                filter_metadata = None
                if source:
                    with safe_span("build_filter"):
                        filter_metadata = {"source": source}
                        logger.debug(f"Built filter metadata for source: {source}")
                        span.set_attribute("filter_applied", True)
                
                # Perform vector search with async
                with safe_span("vector_search"):
                    results = await search_documents_async(
                        client=self.supabase_client,
                        query=query,
                        match_count=match_count,
                        filter_metadata=filter_metadata
                    )
                    span.set_attribute("raw_results_count", len(results))
                
                # Format results for response
                with safe_span("format_response"):
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
                            logger.warning(f"Failed to format result {i}: {format_error}")
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
                
                logger.info(f"RAG query completed successfully - {len(formatted_results)} results found")
                
                return True, response_data
                
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("success", False)
                span.set_attribute("error_type", type(e).__name__)
                
                logger.error(f"RAG query failed: {e} (type: {type(e).__name__}) for query: {query[:50]}")
                
                return False, {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "query": query,
                    "source": source,
                    "execution_path": "service_vector_search"
                }

    async def search_code_examples_service(self, query: str, source_id: Optional[str] = None, match_count: int = 5) -> Tuple[bool, Dict[str, Any]]:
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
                # Standard vector search only - ACTUALLY search code examples, not documents
                results = search_code_examples(
                    client=self.supabase_client,
                    query=query,
                    match_count=match_count,
                    filter_metadata=filter_metadata,
                    source_id=source_id
                )
            
            # Apply reranking if enabled
            use_reranking = self.get_bool_setting("USE_RERANKING", False)
            if use_reranking and self.reranking_model:
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
                "reranking_applied": use_reranking and self.reranking_model is not None,
                "results": formatted_results,
                "count": len(formatted_results)
            }
            
        except Exception as e:
            logger.error(f"Error in code example search: {e}")
            return False, {
                "query": query,
                "error": str(e)
            }