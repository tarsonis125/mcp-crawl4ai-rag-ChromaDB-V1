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
import re
from typing import Dict, Any, Optional, List, Tuple
from contextlib import asynccontextmanager
from datetime import datetime
from collections import deque
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import httpx

# Import crawling functions and dependencies from crawl4ai_mcp
from crawl4ai import AsyncWebCrawler, BrowserConfig
from sentence_transformers import CrossEncoder
from supabase import Client

# Import the actual crawling functions
from src.crawl4ai_mcp import (
    smart_crawl_url as mcp_smart_crawl_url,
    crawl_single_page as mcp_crawl_single_page,
    get_available_sources as mcp_get_available_sources,
    perform_rag_query as mcp_perform_rag_query,
    delete_source as mcp_delete_source,
    search_code_examples as mcp_search_code_examples
)

# Import utils for Supabase client
from src.utils import get_supabase_client

from src.config import load_environment_config, get_rag_strategy_config
from src.credential_service import credential_service, CredentialItem, initialize_credentials


# Create a simple context class that matches what the MCP functions expect
@dataclass
class MockRequestContext:
    lifespan_context: Any

@dataclass
class MockContext:
    request_context: MockRequestContext
    state: Any = None


class CrawlingContext:
    """Context for direct crawling function calls."""
    
    def __init__(self):
        self.crawler: Optional[AsyncWebCrawler] = None
        self.supabase_client: Optional[Client] = None
        self.reranking_model: Optional[CrossEncoder] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the crawling context."""
        if self._initialized:
            return
        
        try:
            # Create browser configuration
            browser_config = BrowserConfig(
                headless=True,
                verbose=False
            )
            
            # Initialize the crawler
            self.crawler = AsyncWebCrawler(config=browser_config)
            await self.crawler.__aenter__()
            
            # Initialize Supabase client
            self.supabase_client = get_supabase_client()
            
            # Initialize cross-encoder model for reranking if enabled
            if os.getenv("USE_RERANKING", "false") == "true":
                try:
                    self.reranking_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                except Exception as e:
                    print(f"Failed to load reranking model: {e}")
                    self.reranking_model = None
            
            self._initialized = True
            
        except Exception as e:
            print(f"Error initializing crawling context: {e}")
            raise
    
    async def cleanup(self):
        """Clean up the crawling context."""
        if self.crawler:
            try:
                await self.crawler.__aexit__(None, None, None)
            except Exception as e:
                print(f"Error cleaning up crawler: {e}")
            finally:
                self.crawler = None
        
        self._initialized = False
    
    def create_context(self) -> MockContext:
        """Create a context object that matches what MCP functions expect."""
        lifespan_context = type('LifespanContext', (), {
            'crawler': self.crawler,
            'supabase_client': self.supabase_client,
            'reranking_model': self.reranking_model
        })()
        
        request_context = MockRequestContext(lifespan_context=lifespan_context)
        context = MockContext(request_context=request_context)
        context.state = type('State', (), {'supabase_client': self.supabase_client})()
        
        return context


# Global crawling context
crawling_context = CrawlingContext()


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


# Log parsing utility
def parse_log_line(line: str) -> Tuple[str, str]:
    """Parse a log line to extract level and message."""
    # Match common log formats like [INFO], [ERROR], etc.
    match = re.match(r'^\[(\w+)\]\s*(.*)$', line)
    if match:
        return match.group(1), match.group(2)
    
    # Check for common log patterns
    if line.startswith(('INFO:', 'INFO ')):
        return 'INFO', line
    elif line.startswith(('ERROR:', 'ERROR ', 'CRITICAL:', 'CRITICAL ')):
        return 'ERROR', line
    elif line.startswith(('WARNING:', 'WARNING ', 'WARN:', 'WARN ')):
        return 'WARNING', line
    elif line.startswith(('DEBUG:', 'DEBUG ')):
        return 'DEBUG', line
    
    # UV package manager outputs
    if any(keyword in line.lower() for keyword in ['downloading', 'building', 'built', 'installed', 'creating virtual environment', 'using cpython']):
        return 'INFO', line
    
    # Default to INFO level for unparsed lines
    return 'INFO', line


class MCPServerManager:
    """Manages the MCP server process lifecycle."""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.status: str = 'stopped'
        self.start_time: Optional[float] = None
        self.logs: deque = deque(maxlen=1000)  # Keep last 1000 log entries
        self.log_websockets: List[WebSocket] = []
        self.log_reader_task: Optional[asyncio.Task] = None
    
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
                
                self._add_log('INFO', 'Using database configuration')
                
            except Exception as e:
                # Fallback to environment variables
                self._add_log('WARNING', f'Database config failed, using env vars: {e}')
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
                text=True,
                bufsize=1  # Line buffered
            )
            
            self.status = 'starting'
            self.start_time = time.time()
            self._add_log('INFO', 'MCP server process started')
            
            # Start log reader task
            if self.log_reader_task:
                self.log_reader_task.cancel()
            self.log_reader_task = asyncio.create_task(self._read_process_logs())
            
            return {
                'success': True,
                'status': 'starting',
                'message': 'MCP server is starting'
            }
            
        except Exception as e:
            self._add_log('ERROR', f'Error starting server: {str(e)}')
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
            # Cancel log reader task
            if self.log_reader_task:
                self.log_reader_task.cancel()
                self.log_reader_task = None
            
            self.process.terminate()
            
            # Wait for graceful shutdown
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            
            self.process = None
            self.status = 'stopped'
            self._add_log('INFO', 'MCP server stopped')
            
            return {
                'success': True,
                'status': 'stopped',
                'message': 'MCP server stopped'
            }
            
        except Exception as e:
            self._add_log('ERROR', f'Error stopping server: {str(e)}')
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
        
        # Convert log entries to strings for backward compatibility
        recent_logs = []
        for log in list(self.logs)[-10:]:
            if isinstance(log, dict):
                recent_logs.append(f"[{log['level']}] {log['message']}")
            else:
                recent_logs.append(str(log))
        
        return {
            'status': self.status,
            'uptime': uptime,
            'logs': recent_logs
        }
    
    def _add_log(self, level: str, message: str):
        """Add a log entry and broadcast to connected WebSockets."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level,
            'message': message
        }
        self.logs.append(log_entry)
        
        # Broadcast to all connected WebSockets
        asyncio.create_task(self._broadcast_log(log_entry))
    
    async def _broadcast_log(self, log_entry: Dict[str, Any]):
        """Broadcast log entry to all connected WebSockets."""
        disconnected = []
        for ws in self.log_websockets:
            try:
                await ws.send_json(log_entry)
            except Exception:
                disconnected.append(ws)
        
        # Remove disconnected WebSockets
        for ws in disconnected:
            self.log_websockets.remove(ws)
    
    async def _read_process_logs(self):
        """Read logs from process stdout/stderr."""
        if not self.process:
            return
        
        async def read_stream(stream, is_stderr=False):
            while True:
                try:
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, stream.readline
                    )
                    if not line:
                        break
                    
                    line = line.strip()
                    if line:
                        level, message = parse_log_line(line)
                        # Only mark stderr as ERROR if it's not already parsed as something else
                        if is_stderr and level == 'INFO' and not any(
                            keyword in line.lower() for keyword in 
                            ['info:', 'downloading', 'building', 'installed', 'creating', 'using cpython', 'uvicorn running']
                        ):
                            # Check if it looks like an actual error
                            if any(err in line.lower() for err in ['error', 'exception', 'failed', 'critical']):
                                level = 'ERROR'
                        self._add_log(level, message)
                except Exception as e:
                    self._add_log('ERROR', f'Log reading error: {str(e)}')
                    break
        
        # Read both stdout and stderr concurrently
        try:
            await asyncio.gather(
                read_stream(self.process.stdout),
                read_stream(self.process.stderr, is_stderr=True)
            )
        except asyncio.CancelledError:
            pass
        finally:
            # Process has ended
            if self.process and self.process.poll() is not None:
                self._add_log('INFO', f'MCP server process terminated with code {self.process.returncode}')
    
    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get historical logs."""
        logs = list(self.logs)
        if limit > 0:
            logs = logs[-limit:]
        return logs
    
    def clear_logs(self):
        """Clear the log buffer."""
        self.logs.clear()
        self._add_log('INFO', 'Logs cleared')
    
    async def add_websocket(self, websocket: WebSocket):
        """Add a WebSocket connection for log streaming."""
        await websocket.accept()
        self.log_websockets.append(websocket)
        
        # Send recent logs to new connection
        for log in list(self.logs)[-50:]:  # Send last 50 logs
            try:
                await websocket.send_json(log)
            except Exception:
                break
    
    def remove_websocket(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.log_websockets:
            self.log_websockets.remove(websocket)


# Global instances
mcp_manager = MCPServerManager()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

# Global connection manager
manager = ConnectionManager()


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
    
    # Initialize crawling context
    try:
        await crawling_context.initialize()
    except Exception as e:
        print(f"Warning: Could not initialize crawling context: {e}")
    
    yield
    
    # Shutdown - stop MCP server if running
    if mcp_manager.process and mcp_manager.process.poll() is None:
        mcp_manager.stop_server()
    
    # Cleanup crawling context
    try:
        await crawling_context.cleanup()
    except Exception as e:
        print(f"Warning: Could not cleanup crawling context: {e}")


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


# Log Management Endpoints
@app.get("/api/mcp/logs")
async def get_mcp_logs(limit: int = 100):
    """Get historical MCP server logs."""
    try:
        logs = mcp_manager.get_logs(limit=limit)
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.delete("/api/mcp/logs")
async def clear_mcp_logs():
    """Clear MCP server logs."""
    try:
        mcp_manager.clear_logs()
        return {'success': True, 'message': 'Logs cleared'}
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.websocket("/api/mcp/logs/stream")
async def websocket_log_stream(websocket: WebSocket):
    """WebSocket endpoint for streaming MCP server logs."""
    await mcp_manager.add_websocket(websocket)
    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(1)
            # Check if WebSocket is still connected
            await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        mcp_manager.remove_websocket(websocket)
    except Exception:
        mcp_manager.remove_websocket(websocket)
        try:
            await websocket.close()
        except:
            pass


# Crawling Endpoints
@app.post("/api/crawl/single")
async def crawl_single_page(request: CrawlSingleRequest):
    """Crawl a single page."""
    try:
        # Create context for the MCP function
        ctx = crawling_context.create_context()
        
        # Call the actual function
        result = await mcp_crawl_single_page(ctx, str(request.url))
        
        # Parse JSON string response if needed
        if isinstance(result, str):
            result = json.loads(result)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.post("/api/crawl/smart")
async def smart_crawl_url(request: SmartCrawlRequest):
    """Smart crawl a URL."""
    try:
        # Create context for the MCP function
        ctx = crawling_context.create_context()
        
        # Call the actual function
        result = await mcp_smart_crawl_url(
            ctx=ctx,
            url=str(request.url),
            max_depth=request.max_depth,
            max_concurrent=request.max_concurrent,
            chunk_size=request.chunk_size
        )
        
        # Parse JSON string response if needed
        if isinstance(result, str):
            result = json.loads(result)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


# RAG Endpoints
@app.post("/api/rag/query")
async def perform_rag_query(request: RAGQueryRequest):
    """Perform a RAG query."""
    try:
        # Ensure crawling context is initialized once
        if not crawling_context._initialized:
            await crawling_context.initialize()
        
        # Create context for the MCP function
        ctx = crawling_context.create_context()
        
        # Call the actual function
        result = await mcp_perform_rag_query(
            ctx=ctx,
            query=request.query,
            source=request.source,
            match_count=request.match_count
        )
        
        # Parse JSON string response if needed
        if isinstance(result, str):
            result = json.loads(result)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.get("/api/rag/sources")
async def get_available_sources():
    """Get available sources."""
    try:
        # Ensure crawling context is initialized once
        if not crawling_context._initialized:
            await crawling_context.initialize()
        
        # Create context for the MCP function
        ctx = crawling_context.create_context()
        
        # Call the actual function
        result = await mcp_get_available_sources(ctx)
        
        # Parse JSON string response if needed
        if isinstance(result, str):
            result = json.loads(result)
        
        return result
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
async def list_credentials(category: Optional[str] = None):
    """List all credentials and their categories."""
    try:
        credentials = await credential_service.list_all_credentials()
        
        # Filter by category if specified
        if category:
            credentials = [cred for cred in credentials if cred.category == category]
        
        return [
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
async def update_credential(key: str, request: Dict[str, Any]):
    """Update an existing credential."""
    try:
        # Handle both CredentialUpdateRequest and full Credential object formats
        if isinstance(request, dict):
            # If the request contains a 'value' field directly, use it
            value = request.get('value', '')
            is_encrypted = request.get('is_encrypted')
            category = request.get('category')
            description = request.get('description')
        else:
            value = request.value
            is_encrypted = request.is_encrypted
            category = request.category
            description = request.description
            
        # Get existing credential to preserve metadata if not provided
        existing_creds = await credential_service.list_all_credentials()
        existing = next((c for c in existing_creds if c.key == key), None)
        
        if existing is None:
            # If credential doesn't exist, create it
            is_encrypted = is_encrypted if is_encrypted is not None else False
        else:
            # Preserve existing values if not provided
            if is_encrypted is None:
                is_encrypted = existing.is_encrypted
            if category is None:
                category = existing.category
            if description is None:
                description = existing.description
        
        success = await credential_service.set_credential(
            key=key,
            value=value,
            is_encrypted=is_encrypted,
            category=category,
            description=description
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


# Knowledge Base Endpoints

# Request/Response Models for Knowledge Base
class KnowledgeItemRequest(BaseModel):
    url: str
    knowledge_type: str = 'technical'
    tags: List[str] = []
    update_frequency: int = 7


class KnowledgeUploadRequest(BaseModel):
    knowledge_type: str = 'technical'
    tags: List[str] = []


@app.get("/api/mcp/config")
async def get_mcp_config():
    """Get MCP server configuration."""
    try:
        # Get configuration from database or defaults
        try:
            config = {
                'host': await credential_service.get_credential('HOST', 'localhost'),
                'port': int(await credential_service.get_credential('PORT', '8051')),
                'transport': await credential_service.get_credential('TRANSPORT', 'sse'),
                'model_choice': await credential_service.get_credential('MODEL_CHOICE', 'gpt-4o-mini'),
                'use_contextual_embeddings': (await credential_service.get_credential('USE_CONTEXTUAL_EMBEDDINGS', 'false')).lower() == 'true',
                'use_hybrid_search': (await credential_service.get_credential('USE_HYBRID_SEARCH', 'false')).lower() == 'true',
                'use_agentic_rag': (await credential_service.get_credential('USE_AGENTIC_RAG', 'false')).lower() == 'true',
                'use_reranking': (await credential_service.get_credential('USE_RERANKING', 'false')).lower() == 'true',
            }
        except Exception:
            # Fallback to environment variables
            config = {
                'host': os.getenv('HOST', 'localhost'),
                'port': int(os.getenv('PORT', '8051')),
                'transport': os.getenv('TRANSPORT', 'sse'),
                'model_choice': os.getenv('MODEL_CHOICE', 'gpt-4o-mini'),
                'use_contextual_embeddings': os.getenv('USE_CONTEXTUAL_EMBEDDINGS', 'false').lower() == 'true',
                'use_hybrid_search': os.getenv('USE_HYBRID_SEARCH', 'false').lower() == 'true',
                'use_agentic_rag': os.getenv('USE_AGENTIC_RAG', 'false').lower() == 'true',
                'use_reranking': os.getenv('USE_RERANKING', 'false').lower() == 'true',
            }
        
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.get("/api/knowledge-items")
async def get_knowledge_items(
    page: int = 1,
    per_page: int = 20,
    knowledge_type: Optional[str] = None,
    search: Optional[str] = None
):
    """Get knowledge items with pagination and filtering."""
    try:
        # Ensure crawling context is initialized once  
        if not crawling_context._initialized:
            await crawling_context.initialize()
        
        # Create context for the MCP function
        ctx = crawling_context.create_context()
        
        # Get all sources using the MCP function
        sources_result = await mcp_get_available_sources(ctx)
        
        # Parse the JSON response
        if isinstance(sources_result, str):
            sources_data = json.loads(sources_result)
        else:
            sources_data = sources_result
        
        # Transform the data to match frontend expectations
        items = []
        for source in sources_data.get('sources', []):
            # Get first crawled page for this source to extract metadata
            pages_result = await mcp_perform_rag_query(
                ctx=ctx,
                query='overview',
                source=source['source_id'],
                match_count=1
            )
            
            # Parse the JSON response
            if isinstance(pages_result, str):
                pages_data = json.loads(pages_result)
            else:
                pages_data = pages_result
            
            first_page = pages_data.get('results', [{}])[0] if pages_data.get('results') else {}
            metadata = first_page.get('metadata', {})
            
            item = {
                'id': source['source_id'],
                'title': metadata.get('title', source.get('summary', 'Untitled')),
                'url': first_page.get('url', f"source://{source['source_id']}"),
                'source_id': source['source_id'],
                'metadata': {
                    'knowledge_type': metadata.get('knowledge_type', 'technical'),
                    'tags': metadata.get('tags', []),
                    'source_type': metadata.get('source_type', 'url'),
                    'status': 'active',
                    'description': metadata.get('description', source.get('summary', '')),
                    'chunks_count': source.get('total_word_count', 0),
                    'word_count': source.get('total_word_count', 0),
                    'last_scraped': source.get('updated_at'),
                    **metadata
                },
                'created_at': source.get('created_at'),
                'updated_at': source.get('updated_at')
            }
            items.append(item)
        
        # Filter by search term if provided
        if search:
            search_lower = search.lower()
            items = [
                item for item in items 
                if search_lower in item['title'].lower() 
                or search_lower in item['metadata'].get('description', '').lower()
                or any(search_lower in tag.lower() for tag in item['metadata'].get('tags', []))
            ]
        
        # Filter by knowledge type if provided
        if knowledge_type:
            items = [
                item for item in items 
                if item['metadata'].get('knowledge_type') == knowledge_type
            ]
        
        # Apply pagination
        total = len(items)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_items = items[start_idx:end_idx]
        
        return {
            'items': paginated_items,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.post("/api/knowledge-items/crawl")
async def crawl_knowledge_item(request: KnowledgeItemRequest):
    """Crawl a URL and add it to the knowledge base."""
    try:
        # Use the same logic as the existing smart crawl endpoint
        params = {
            'url': str(request.url),
            'max_depth': 2,
            'max_concurrent': 5,
            'chunk_size': 5000
        }
        
        # Ensure crawling context is initialized once
        if not crawling_context._initialized:
            await crawling_context.initialize()
        
        # Create context for the MCP function
        ctx = crawling_context.create_context()
        
        # Call the actual function
        result = await mcp_smart_crawl_url(
            ctx=ctx,
            url=str(request.url),
            max_depth=2,
            max_concurrent=5,
            chunk_size=5000
        )
        
        # Parse JSON string response if needed
        if isinstance(result, str):
            result = json.loads(result)
        
        # Broadcast update to WebSocket clients
        await manager.broadcast({
            "type": "crawl_completed",
            "data": {
                "url": str(request.url),
                "success": result.get('success', False),
                "message": f'Crawling completed for {request.url}'
            }
        })
        
        return {
            'success': True,
            'message': f'Successfully started crawling {request.url}',
            'crawl_result': result
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.delete("/api/knowledge-items/{source_id}")
async def delete_knowledge_item(source_id: str):
    """Delete a knowledge item from the database."""
    try:
        # Ensure crawling context is initialized once
        if not crawling_context._initialized:
            await crawling_context.initialize()
        
        # Create context for the MCP function
        ctx = crawling_context.create_context()
        
        # Call the actual function
        result = await mcp_delete_source(ctx, source_id)
        
        # Parse JSON string response if needed
        if isinstance(result, str):
            result = json.loads(result)
        
        if result.get('success'):
            return {
                'success': True,
                'message': f'Successfully deleted knowledge item {source_id}'
            }
        else:
            raise HTTPException(status_code=500, detail={'error': result.get('error', 'Deletion failed')})
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.post("/api/knowledge-items/upload")
async def upload_knowledge_document(request: Request):
    """Upload a document and add it to the knowledge base."""
    try:
        # This would handle file upload functionality
        # For now, return a placeholder response
        return {
            'success': True,
            'source_id': f'uploaded_{int(time.time())}',
            'message': 'Document upload functionality coming soon',
            'filename': 'uploaded_document.pdf'
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


# Error handlers
@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    """Handle validation errors."""
    return HTTPException(status_code=400, detail={'error': 'Validation error'})


@app.websocket("/api/knowledge-items/stream")
async def websocket_knowledge_items(websocket: WebSocket):
    """WebSocket endpoint for real-time knowledge items updates."""
    await manager.connect(websocket)
    try:
        # Send initial data
        ctx = crawling_context.create_context()
        sources_result = await mcp_get_available_sources(ctx)
        
        if isinstance(sources_result, str):
            sources_data = json.loads(sources_result)
        else:
            sources_data = sources_result
        
        # Transform data for frontend
        items = []
        for source in sources_data.get('sources', []):
            item = {
                'id': source['source_id'],
                'title': source.get('summary', 'Untitled'),
                'url': f"source://{source['source_id']}",
                'source_id': source['source_id'],
                'metadata': {
                    'knowledge_type': 'technical',
                    'tags': [],
                    'source_type': 'url',
                    'status': 'active',
                    'description': source.get('summary', ''),
                    'chunks_count': source.get('total_word_count', 0),
                    'word_count': source.get('total_word_count', 0),
                    'last_scraped': source.get('updated_at'),
                },
                'created_at': source.get('created_at'),
                'updated_at': source.get('updated_at')
            }
            items.append(item)
        
        await websocket.send_json({
            "type": "knowledge_items_update",
            "data": {
                "items": items,
                "total": len(items),
                "page": 1,
                "per_page": 20,
                "pages": 1
            }
        })
        
        # Keep connection alive and listen for updates
        while True:
            await asyncio.sleep(5)  # Check for updates every 5 seconds
            # Send heartbeat
            await websocket.send_json({"type": "heartbeat"})
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.websocket("/api/crawl/stream")
async def websocket_crawl_status(websocket: WebSocket):
    """WebSocket endpoint for real-time crawling status updates."""
    await manager.connect(websocket)
    try:
        while True:
            await asyncio.sleep(1)
            # Send heartbeat
            await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080) 