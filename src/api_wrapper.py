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
from src.credential_service import credential_service, CredentialItem, initialize_credentials


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


# Credential Management Models
class CredentialRequest(BaseModel):
    key: str
    value: str
    is_encrypted: bool = False
    category: Optional[str] = None
    description: Optional[str] = None


class CredentialUpdateRequest(BaseModel):
    value: str
    is_encrypted: Optional[bool] = None
    category: Optional[str] = None
    description: Optional[str] = None


class MCPServerManager:
    """Manages the MCP server process lifecycle."""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.status: str = 'stopped'
        self.start_time: Optional[float] = None
        self.logs: List[str] = []
    
    async def start_server(self) -> Dict[str, Any]:
        """Start the MCP server process."""
        if self.process and self.process.poll() is None:
            return {
                'success': False,
                'status': self.status,
                'message': 'MCP server is already running'
            }
        
        try:
            # Set up environment variables for the MCP server
            env = os.environ.copy()
            
            # Try to get credentials from database first, fallback to env vars
            try:
                # Get configuration from database
                openai_key = await credential_service.get_credential('OPENAI_API_KEY', decrypt=True)
                model_choice = await credential_service.get_credential('MODEL_CHOICE', 'gpt-4o-mini')
                transport = await credential_service.get_credential('TRANSPORT', 'sse')
                host = await credential_service.get_credential('HOST', 'localhost')
                port = await credential_service.get_credential('PORT', '8051')
                
                # RAG strategy flags
                use_contextual = await credential_service.get_credential('USE_CONTEXTUAL_EMBEDDINGS', 'false')
                use_hybrid = await credential_service.get_credential('USE_HYBRID_SEARCH', 'false')
                use_agentic = await credential_service.get_credential('USE_AGENTIC_RAG', 'false')
                use_reranking = await credential_service.get_credential('USE_RERANKING', 'false')
                
                env.update({
                    'OPENAI_API_KEY': str(openai_key) if openai_key else '',
                    'SUPABASE_URL': os.getenv('SUPABASE_URL', ''),
                    'SUPABASE_SERVICE_KEY': os.getenv('SUPABASE_SERVICE_KEY', ''),
                    'HOST': str(host),
                    'PORT': str(port),
                    'TRANSPORT': str(transport),
                    'MODEL_CHOICE': str(model_choice),
                    'USE_CONTEXTUAL_EMBEDDINGS': str(use_contextual).lower(),
                    'USE_HYBRID_SEARCH': str(use_hybrid).lower(),
                    'USE_AGENTIC_RAG': str(use_agentic).lower(),
                    'USE_RERANKING': str(use_reranking).lower(),
                })
                
                self.logs.append(f'[{time.strftime("%H:%M:%S")}] Using database configuration')
                
            except Exception as e:
                # Fallback to environment variables
                self.logs.append(f'[{time.strftime("%H:%M:%S")}] Database config failed, using env vars: {e}')
                config = load_environment_config()
                rag_config = get_rag_strategy_config()
                
                env.update({
                    'OPENAI_API_KEY': config.openai_api_key,
                    'SUPABASE_URL': config.supabase_url,
                    'SUPABASE_SERVICE_KEY': config.supabase_service_key,
                    'HOST': config.host,
                    'PORT': str(config.port),
                    'TRANSPORT': config.transport,
                    'MODEL_CHOICE': config.model_choice,
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
    # Startup - initialize credentials from database
    try:
        await initialize_credentials()
    except Exception as e:
        print(f"Warning: Could not initialize credentials from database: {e}")
        print("Falling back to environment variables")
    
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
    allow_origins=["http://localhost:3737", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# MCP Server Management Endpoints
@app.post("/api/mcp/start")
async def start_mcp_server():
    """Start the MCP server."""
    try:
        result = await mcp_manager.start_server()
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


# Credential Management Endpoints
@app.get("/api/credentials")
async def list_credentials():
    """List all credentials and their categories."""
    try:
        credentials = await credential_service.list_all_credentials()
        return {
            'credentials': [
                {
                    'key': cred.key,
                    'value': cred.value,
                    'encrypted_value': cred.encrypted_value,
                    'is_encrypted': cred.is_encrypted,
                    'category': cred.category,
                    'description': cred.description
                }
                for cred in credentials
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.get("/api/credentials/categories/{category}")
async def get_credentials_by_category(category: str):
    """Get all credentials for a specific category."""
    try:
        credentials = await credential_service.get_credentials_by_category(category)
        return {'credentials': credentials}
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.post("/api/credentials")
async def create_credential(request: CredentialRequest):
    """Create or update a credential."""
    try:
        success = await credential_service.set_credential(
            key=request.key,
            value=request.value,
            is_encrypted=request.is_encrypted,
            category=request.category,
            description=request.description
        )
        
        if success:
            return {
                'success': True,
                'message': f'Credential {request.key} {"encrypted and " if request.is_encrypted else ""}saved successfully'
            }
        else:
            raise HTTPException(status_code=500, detail={'error': 'Failed to save credential'})
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.get("/api/credentials/{key}")
async def get_credential(key: str, decrypt: bool = True):
    """Get a specific credential by key."""
    try:
        value = await credential_service.get_credential(key, decrypt=decrypt)
        
        if value is None:
            raise HTTPException(status_code=404, detail={'error': f'Credential {key} not found'})
        
        # For encrypted credentials, return metadata instead of the actual value for security
        if isinstance(value, dict) and value.get('is_encrypted') and not decrypt:
            return {
                'key': key,
                'is_encrypted': True,
                'category': value.get('category'),
                'description': value.get('description'),
                'has_value': bool(value.get('encrypted_value'))
            }
        
        return {
            'key': key,
            'value': value,
            'is_encrypted': False
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.put("/api/credentials/{key}")
async def update_credential(key: str, request: CredentialUpdateRequest):
    """Update an existing credential."""
    try:
        # Get existing credential to preserve metadata if not provided
        existing = await credential_service.get_credential(key, decrypt=False)
        if existing is None:
            raise HTTPException(status_code=404, detail={'error': f'Credential {key} not found'})
        
        # Determine if encrypted from request or existing data
        is_encrypted = request.is_encrypted
        if is_encrypted is None:
            if isinstance(existing, dict):
                is_encrypted = existing.get('is_encrypted', False)
            else:
                is_encrypted = False
        
        success = await credential_service.set_credential(
            key=key,
            value=request.value,
            is_encrypted=is_encrypted,
            category=request.category,
            description=request.description
        )
        
        if success:
            return {
                'success': True,
                'message': f'Credential {key} updated successfully'
            }
        else:
            raise HTTPException(status_code=500, detail={'error': 'Failed to update credential'})
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.delete("/api/credentials/{key}")
async def delete_credential(key: str):
    """Delete a credential."""
    try:
        success = await credential_service.delete_credential(key)
        
        if success:
            return {
                'success': True,
                'message': f'Credential {key} deleted successfully'
            }
        else:
            raise HTTPException(status_code=500, detail={'error': 'Failed to delete credential'})
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.post("/api/credentials/initialize")
async def initialize_credentials_endpoint():
    """Reload credentials from database."""
    try:
        await initialize_credentials()
        return {
            'success': True,
            'message': 'Credentials reloaded from database'
        }
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