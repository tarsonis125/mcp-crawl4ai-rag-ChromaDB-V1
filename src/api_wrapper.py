"""
Backend API wrapper that provides REST endpoints for the React app.
This server manages the MCP server process and forwards requests.
"""
import asyncio
import subprocess
import time
import json
import os
import signal
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import httpx

from src.config import load_environment_config, get_rag_strategy_config


# Request/Response Models
class CrawlSingleRequest(BaseModel):
    url: HttpUrl


class SmartCrawlRequest(BaseModel):
    url: HttpUrl
    max_depth: Optional[int] = 3
    max_concurrent: Optional[int] = 10
    chunk_size: Optional[int] = 5000


class RAGQueryRequest(BaseModel):
    query: str
    source: Optional[str] = None
    match_count: Optional[int] = 5


class MCPServerManager:
    """Manages the MCP server process lifecycle."""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.status: str = 'stopped'
        self.start_time: Optional[float] = None
        self.logs: List[str] = []
    
    def start_server(self) -> Dict[str, Any]:
        """Start the MCP server process."""
        if self.process and self.process.poll() is None:
            return {
                'success': False,
                'status': self.status,
                'message': 'MCP server is already running'
            }
        
        try:
            # Load configuration
            config = load_environment_config()
            
            # Set up environment variables for the MCP server
            env = os.environ.copy()
            env.update({
                'OPENAI_API_KEY': config.openai_api_key,
                'SUPABASE_URL': config.supabase_url,
                'SUPABASE_SERVICE_KEY': config.supabase_service_key,
                'HOST': config.host,
                'PORT': str(config.port),
                'TRANSPORT': config.transport,
                'MODEL_CHOICE': config.model_choice,
            })
            
            # Add RAG strategy config
            rag_config = get_rag_strategy_config()
            env.update({
                'USE_CONTEXTUAL_EMBEDDINGS': str(rag_config.use_contextual_embeddings).lower(),
                'USE_HYBRID_SEARCH': str(rag_config.use_hybrid_search).lower(),
                'USE_AGENTIC_RAG': str(rag_config.use_agentic_rag).lower(),
                'USE_RERANKING': str(rag_config.use_reranking).lower(),
            })
            
            # Start the MCP server process
            cmd = ['python', '-m', 'uv', 'run', 'src/crawl4ai_mcp.py']
            self.process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.status = 'starting'
            self.start_time = time.time()
            self.logs.append(f'[{time.strftime("%H:%M:%S")}] MCP server process started')
            
            return {
                'success': True,
                'status': 'starting',
                'message': 'MCP server is starting'
            }
            
        except Exception as e:
            self.logs.append(f'[{time.strftime("%H:%M:%S")}] Error starting server: {str(e)}')
            raise Exception(f"Server start failed: {str(e)}")
    
    def stop_server(self) -> Dict[str, Any]:
        """Stop the MCP server process."""
        if not self.process or self.process.poll() is not None:
            self.status = 'stopped'
            return {
                'success': True,
                'status': 'stopped',
                'message': 'MCP server is already stopped'
            }
        
        try:
            self.process.terminate()
            
            # Wait for graceful shutdown
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            
            self.process = None
            self.status = 'stopped'
            self.logs.append(f'[{time.strftime("%H:%M:%S")}] MCP server stopped')
            
            return {
                'success': True,
                'status': 'stopped',
                'message': 'MCP server stopped'
            }
            
        except Exception as e:
            self.logs.append(f'[{time.strftime("%H:%M:%S")}] Error stopping server: {str(e)}')
            raise Exception(f"Server stop failed: {str(e)}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current server status."""
        if self.process:
            if self.process.poll() is None:
                self.status = 'running'
            else:
                self.status = 'stopped'
                self.process = None
        
        uptime = None
        if self.status == 'running' and self.start_time:
            uptime = int(time.time() - self.start_time)
        
        return {
            'status': self.status,
            'uptime': uptime,
            'logs': self.logs[-10:]  # Return last 10 log entries
        }


class MCPClient:
    """Client to communicate with the MCP server."""
    
    def __init__(self, base_url: str = "http://localhost:8051"):
        self.base_url = base_url
    
    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server."""
        # This is a simplified version - in reality, we'd use the MCP protocol
        # For now, we'll simulate the tool calls based on the tool name
        
        if tool_name == 'crawl_single_page':
            return {
                'success': True,
                'url': params['url'],
                'chunks_stored': 5,
                'content_length': 1500
            }
        elif tool_name == 'smart_crawl_url':
            return {
                'success': True,
                'crawl_type': 'webpage',
                'urls_processed': 10,
                'total_chunks': 50
            }
        elif tool_name == 'perform_rag_query':
            return {
                'results': [
                    {'content': 'Relevant content 1', 'score': 0.95},
                    {'content': 'Relevant content 2', 'score': 0.87}
                ],
                'query': params['query']
            }
        elif tool_name == 'get_available_sources':
            return {
                'sources': ['example.com', 'docs.example.com', 'blog.example.com']
            }
        else:
            raise ValueError(f"Unknown tool: {tool_name}")


# Global instances
mcp_manager = MCPServerManager()
mcp_client = MCPClient()


# Lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    yield
    # Shutdown - stop MCP server if running
    if mcp_manager.process and mcp_manager.process.poll() is None:
        mcp_manager.stop_server()


# Create FastAPI app
app = FastAPI(
    title="MCP Server API Wrapper",
    description="REST API wrapper for the MCP server",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# MCP Server Management Endpoints
@app.post("/api/mcp/start")
async def start_mcp_server():
    """Start the MCP server."""
    try:
        result = mcp_manager.start_server()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.post("/api/mcp/stop")
async def stop_mcp_server():
    """Stop the MCP server."""
    try:
        result = mcp_manager.stop_server()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.get("/api/mcp/status")
async def get_mcp_server_status():
    """Get MCP server status."""
    try:
        return mcp_manager.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


# Crawling Endpoints
@app.post("/api/crawl/single")
async def crawl_single_page(request: CrawlSingleRequest):
    """Crawl a single page."""
    try:
        result = await mcp_client.call_tool('crawl_single_page', {'url': str(request.url)})
        return result
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail={'error': f'MCP server not available: {str(e)}'})
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.post("/api/crawl/smart")
async def smart_crawl_url(request: SmartCrawlRequest):
    """Smart crawl a URL."""
    try:
        params = {
            'url': str(request.url),
            'max_depth': request.max_depth,
            'max_concurrent': request.max_concurrent,
            'chunk_size': request.chunk_size
        }
        result = await mcp_client.call_tool('smart_crawl_url', params)
        return result
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail={'error': f'MCP server not available: {str(e)}'})
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


# RAG Endpoints
@app.post("/api/rag/query")
async def perform_rag_query(request: RAGQueryRequest):
    """Perform a RAG query."""
    try:
        params = {
            'query': request.query,
            'source': request.source,
            'match_count': request.match_count
        }
        result = await mcp_client.call_tool('perform_rag_query', params)
        return result
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail={'error': f'MCP server not available: {str(e)}'})
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.get("/api/rag/sources")
async def get_available_sources():
    """Get available sources."""
    try:
        result = await mcp_client.call_tool('get_available_sources', {})
        return result
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail={'error': f'MCP server not available: {str(e)}'})
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


# Database Endpoints
def get_database_metrics() -> Dict[str, Any]:
    """Get database metrics from Supabase."""
    # This would normally query Supabase directly
    return {
        'documents': 256,
        'storage_used': '1.2 GB',
        'last_sync': '2024-01-20T10:30:00Z'
    }


@app.get("/api/database/metrics")
async def database_metrics():
    """Get database metrics."""
    try:
        return get_database_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


# Error handlers
@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    """Handle validation errors."""
    return HTTPException(status_code=400, detail={'error': 'Validation error'})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080) 