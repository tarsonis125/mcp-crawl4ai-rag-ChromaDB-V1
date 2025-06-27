"""
HTTP client for API service to communicate with Agents service
Handles reranking and analysis operations via HTTP
"""

import os
from typing import Dict, Any, List, Optional
import httpx
from urllib.parse import urljoin

from src.logfire_config import api_logger


class AgentsServiceClient:
    """HTTP client for communicating with the Agents service"""
    
    def __init__(self, agents_url: Optional[str] = None):
        """Initialize the Agents service client
        
        Args:
            agents_url: Base URL for the Agents service. 
                       Defaults to AGENTS_SERVICE_URL env var or http://agents:8052
        """
        self.agents_url = agents_url or os.getenv("AGENTS_SERVICE_URL", "http://agents:8052")
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self.headers = {
            "X-Service-Auth": os.getenv("INTERNAL_SERVICE_AUTH", "internal-service-key"),
            "Content-Type": "application/json"
        }
    
    async def rerank_results(
        self, 
        query: str, 
        results: List[Dict[str, Any]], 
        content_key: str = "content"
    ) -> List[Dict[str, Any]]:
        """
        Rerank search results using the Agents service's cross-encoder model
        
        Args:
            query: The search query
            results: List of search results to rerank
            content_key: The key in each result dict that contains the text content
            
        Returns:
            Reranked list of results with rerank_score added
        """
        if not results:
            return results
            
        try:
            endpoint = urljoin(self.agents_url, "/internal/rerank")
            
            # Prepare the request data
            request_data = {
                "query": query,
                "results": results
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=request_data,
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        # Convert the response format back to our expected format
                        reranked = []
                        for item in result.get("reranked_results", []):
                            # Find the original result and update it with rerank score
                            for original in results:
                                if original.get("id") == item.get("id"):
                                    original["rerank_score"] = item.get("rerank_score", 0.0)
                                    reranked.append(original)
                                    break
                        
                        # Sort by rerank score descending
                        reranked.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
                        return reranked
                    else:
                        api_logger.error(f"Reranking failed: {result.get('error')}")
                        return results
                else:
                    api_logger.error(f"Reranking request failed with status {response.status_code}")
                    return results
                    
        except Exception as e:
            api_logger.error(f"Error calling Agents service for reranking: {str(e)}")
            # Return original results if reranking fails
            return results
    
    async def analyze_document(
        self,
        document_id: str,
        analysis_type: str = "summarize",
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a document using the Agents service
        
        Args:
            document_id: ID of the document to analyze
            analysis_type: Type of analysis to perform
            options: Additional options for the analysis
            
        Returns:
            Analysis results
        """
        try:
            endpoint = urljoin(self.agents_url, "/internal/analyze")
            
            request_data = {
                "document_id": document_id,
                "analysis_type": analysis_type,
                "options": options or {}
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=request_data,
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        return result.get("analysis", {})
                    else:
                        api_logger.error(f"Analysis failed: {result.get('error')}")
                        return {"error": result.get("error", "Analysis failed")}
                else:
                    api_logger.error(f"Analysis request failed with status {response.status_code}")
                    return {"error": f"Request failed with status {response.status_code}"}
                    
        except Exception as e:
            api_logger.error(f"Error calling Agents service for analysis: {str(e)}")
            return {"error": str(e)}