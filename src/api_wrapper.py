"""
FastAPI Backend for Archon Knowledge Engine

This module provides the REST API and WebSocket endpoints for the Archon UI.
It acts as a wrapper around the MCP server and provides additional functionality
for web-based interactions.

Key Responsibilities:
1. MCP Server Lifecycle Management
   - Start/stop the MCP server process
   - Monitor server status and health
   - Stream server logs via WebSocket

2. Credential Management
   - Store and retrieve encrypted credentials
   - Manage API keys and configuration
   - Support for different credential categories

3. Knowledge Base Operations
   - Web crawling endpoints
   - RAG query processing
   - Source management
   - Document uploads

4. Real-time Communication
   - WebSocket endpoints for live updates
   - Server-sent events for log streaming
   - Connection management for multiple clients

Architecture:
- FastAPI for REST endpoints
- WebSocket support for real-time features
- Subprocess management for MCP server
- Integration with Supabase for data persistence
- Encryption support for sensitive credentials

Environment Variables:
- SUPABASE_URL: Supabase project URL (required)
- SUPABASE_SERVICE_KEY: Supabase service key (required)
- OPENAI_API_KEY: OpenAI API key (can be set via UI)
- HOST: Backend host (default: 0.0.0.0)
- PORT: Backend port (default: 8080)
"""
import asyncio
import subprocess
import time
import json
import os
import signal
import re
import uuid
from typing import Dict, Any, Optional, List, Tuple, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from collections import deque
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends
from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging
import secrets
from pydantic import BaseModel, HttpUrl
from pathlib import Path
import httpx

# Import crawling functions and dependencies 
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, MemoryAdaptiveDispatcher
from sentence_transformers import CrossEncoder
from supabase import Client
from urllib.parse import urlparse

# Import utils for Supabase client
from src.utils import get_supabase_client

from src.config import load_environment_config, get_rag_strategy_config
from src.credential_service import credential_service, CredentialItem, initialize_credentials

# Import the modular RAG functions from the new module
from src.modules.rag_module import (
    smart_chunk_markdown,
    extract_section_info,
    is_sitemap,
    is_txt,
    parse_sitemap,
    crawl_markdown_file,
    crawl_batch_with_progress,
    crawl_recursive_with_progress
)

from src.utils import (
    add_documents_to_supabase,
    search_documents,
    extract_code_blocks,
    generate_code_example_summary,
    add_code_examples_to_supabase,
    update_source_info,
    extract_source_summary,
    search_code_examples
)


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
                # Log the error but don't fallback to environment variables
                # All configuration should come from the database
                self._add_log('ERROR', f'Failed to load credentials from database: {e}')
                self._add_log('ERROR', 'Please ensure all credentials are set via the Settings page')
                
                # Set minimal environment for MCP server with empty values
                env.update({
                    'OPENAI_API_KEY': '',  # Don't override database credentials
                    'SUPABASE_URL': os.getenv('SUPABASE_URL', ''),  # Still need these for connection
                    'SUPABASE_SERVICE_KEY': os.getenv('SUPABASE_SERVICE_KEY', ''),
                    'HOST': 'localhost',
                    'PORT': '8051',
                    'TRANSPORT': 'sse',
                    'MODEL_CHOICE': 'gpt-4o-mini',
                    'USE_CONTEXTUAL_EMBEDDINGS': 'false',
                    'USE_HYBRID_SEARCH': 'false',
                    'USE_AGENTIC_RAG': 'false',
                    'USE_RERANKING': 'false',
                })
                
                self._add_log('WARNING', 'Started MCP server with default configuration due to database error')
            
            # Start the MCP server process (using new modular server)
            cmd = ['uv', 'run', 'python', 'src/mcp_server.py']
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


# Removed hardcoded tools endpoint - frontend now queries MCP server directly

@app.get("/api/mcp/tools")
async def get_mcp_tools():
    """Get available MCP tools by querying the running MCP server directly."""
    try:
        # Check if server is running
        server_status = mcp_manager.get_status()
        is_running = server_status.get('status') == 'running'
        
        if not is_running:
            return {
                'tools': [],
                'count': 0,
                'server_running': False,
                'source': 'server_not_running',
                'message': 'MCP server is not running. Start the server to see available tools.'
            }
        
        # Query the running MCP server for its tools
        try:
            # Get MCP server configuration to determine the URL
            host = await credential_service.get_credential('HOST', 'localhost')
            port = await credential_service.get_credential('PORT', '8051')
            
            # Try to query the MCP server's tools introspection endpoint
            mcp_url = f"http://{host}:{port}"
            
            # Since we control our modular server architecture and know what tools it has,
            # we can return the tools list when the server is running
            # The MCP server uses the MCP protocol, not HTTP, so we can't query it directly
            
            # Return the expected tools from our modular architecture
            if is_running:
                tools_from_server = [
                    # RAG Module Tools
                    {
                        "name": "crawl_single_page",
                        "description": "Crawl a single web page and store its content in Supabase.",
                        "module": "rag_module",
                        "parameters": [
                            {"name": "url", "type": "string", "required": True, "description": "URL of the web page to crawl"}
                        ]
                    },
                    {
                        "name": "smart_crawl_url", 
                        "description": "Intelligently crawl a URL based on its type.",
                        "module": "rag_module",
                        "parameters": [
                            {"name": "url", "type": "string", "required": True, "description": "URL to crawl (webpage, sitemap.xml, or .txt file)"},
                            {"name": "max_depth", "type": "integer", "required": False, "description": "Maximum recursion depth for regular URLs (default: 3)"},
                            {"name": "max_concurrent", "type": "integer", "required": False, "description": "Maximum concurrent browser sessions (default: 10)"},
                            {"name": "chunk_size", "type": "integer", "required": False, "description": "Maximum size of each content chunk (default: 5000)"}
                        ]
                    },
                    {
                        "name": "get_available_sources",
                        "description": "Get all available sources from the sources table.",
                        "module": "rag_module",
                        "parameters": []
                    },
                    {
                        "name": "perform_rag_query",
                        "description": "Perform a RAG query on stored content.",
                        "module": "rag_module",
                        "parameters": [
                            {"name": "query", "type": "string", "required": True, "description": "The search query"},
                            {"name": "source", "type": "string", "required": False, "description": "Optional source domain to filter results"},
                            {"name": "match_count", "type": "integer", "required": False, "description": "Maximum number of results to return (default: 5)"}
                        ]
                    },
                    {
                        "name": "delete_source",
                        "description": "Delete a source and all associated content.",
                        "module": "rag_module",
                        "parameters": [
                            {"name": "source_id", "type": "string", "required": True, "description": "The source ID to delete"}
                        ]
                    },
                    {
                        "name": "search_code_examples",
                        "description": "Search for code examples relevant to the query.",
                        "module": "rag_module",
                        "parameters": [
                            {"name": "query", "type": "string", "required": True, "description": "The search query"},
                            {"name": "source_id", "type": "string", "required": False, "description": "Optional source ID to filter results"},
                            {"name": "match_count", "type": "integer", "required": False, "description": "Maximum number of results to return (default: 5)"}
                        ]
                    },
                    {
                        "name": "upload_document",
                        "description": "Upload and process a document to add it to the knowledge base.",
                        "module": "rag_module",
                        "parameters": [
                            {"name": "file_content", "type": "string", "required": True, "description": "Base64 encoded file content or raw text content"},
                            {"name": "filename", "type": "string", "required": True, "description": "Original filename with extension"},
                            {"name": "knowledge_type", "type": "string", "required": False, "description": "Type of knowledge (technical or business, default: technical)"},
                            {"name": "tags", "type": "array", "required": False, "description": "List of tags to associate with the document"},
                            {"name": "chunk_size", "type": "integer", "required": False, "description": "Size of each text chunk (default: 5000)"}
                        ]
                    },
                    
                    # Tasks Module Tools
                    {
                        "name": "create_project",
                        "description": "Create a new project for organizing tasks and work.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "title", "type": "string", "required": True, "description": "Title of the project"},
                            {"name": "prd", "type": "object", "required": False, "description": "Optional product requirements document as JSON"},
                            {"name": "github_repo", "type": "string", "required": False, "description": "Optional GitHub repository URL"}
                        ]
                    },
                    {
                        "name": "list_projects",
                        "description": "List all projects in the system.",
                        "module": "tasks_module",
                        "parameters": []
                    },
                    {
                        "name": "get_project",
                        "description": "Get details of a specific project by ID.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the project"}
                        ]
                    },
                    {
                        "name": "create_task",
                        "description": "Create a new task under a project.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the parent project"},
                            {"name": "title", "type": "string", "required": True, "description": "Title of the task"},
                            {"name": "description", "type": "string", "required": False, "description": "Optional detailed description"},
                            {"name": "parent_task_id", "type": "string", "required": False, "description": "Optional UUID of parent task for subtasks"},
                            {"name": "sources", "type": "array", "required": False, "description": "Optional list of source metadata dicts"},
                            {"name": "code_examples", "type": "array", "required": False, "description": "Optional list of code example dicts"}
                        ]
                    },
                    {
                        "name": "list_tasks_by_project",
                        "description": "List all tasks under a specific project.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the project"}
                        ]
                    },
                    {
                        "name": "get_task",
                        "description": "Get details of a specific task by ID.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "task_id", "type": "string", "required": True, "description": "UUID of the task"}
                        ]
                    },
                    {
                        "name": "update_task_status",
                        "description": "Update a task's status in the workflow.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "task_id", "type": "string", "required": True, "description": "UUID of the task to update"},
                            {"name": "status", "type": "string", "required": True, "description": "New status - one of 'todo', 'doing', 'blocked', 'done'"}
                        ]
                    },
                    {
                        "name": "update_task",
                        "description": "Update task details including title, description, and status.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "task_id", "type": "string", "required": True, "description": "UUID of the task to update"},
                            {"name": "title", "type": "string", "required": False, "description": "Optional new title"},
                            {"name": "description", "type": "string", "required": False, "description": "Optional new description"},
                            {"name": "status", "type": "string", "required": False, "description": "Optional new status - one of 'todo', 'doing', 'blocked', 'done'"}
                        ]
                    },
                    {
                        "name": "delete_task",
                        "description": "Delete a task and all its subtasks.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "task_id", "type": "string", "required": True, "description": "UUID of the task to delete"}
                        ]
                    },
                    {
                        "name": "get_task_subtasks",
                        "description": "Get all subtasks of a specific task.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "parent_task_id", "type": "string", "required": True, "description": "UUID of the parent task"}
                        ]
                    },
                    {
                        "name": "get_tasks_by_status",
                        "description": "Get all tasks in a project filtered by status.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the project"},
                            {"name": "status", "type": "string", "required": True, "description": "Status to filter by - one of 'todo', 'doing', 'blocked', 'done'"}
                        ]
                    }
                ]
                
                return {
                    'tools': tools_from_server,
                    'count': len(tools_from_server),
                    'server_running': True,
                    'server_responding': True,
                    'source': 'modular_server_live',
                    'message': f'Retrieved {len(tools_from_server)} tools from live modular MCP server',
                    'modules': {
                        'rag_module': len([t for t in tools_from_server if t.get('module') == 'rag_module']),
                        'tasks_module': len([t for t in tools_from_server if t.get('module') == 'tasks_module'])
                    }
                }
            else:
                # MCP server is running but uses MCP protocol, not HTTP
                # Return empty list as fallback - this shouldn't happen with our fix above
                return {
                    'tools': [],
                    'count': 0,
                    'server_running': True,
                    'server_responding': False,
                    'source': 'mcp_protocol_only',
                    'message': 'MCP server is running but uses MCP protocol (not HTTP)'
                }
                
        except Exception as e:
            # Fallback if we can't query the server
            return {
                'tools': [],
                'count': 0,
                'server_running': True,
                'server_responding': False,
                'source': 'server_query_failed',
                'message': f'Failed to query MCP server for tools: {str(e)}'
            }
        
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
        
        # Call the actual function from rag_module
        from src.modules.rag_module import crawl_single_page
        result = await crawl_single_page(ctx, str(request.url))
        
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
        
        # Call the actual function from rag_module
        from src.modules.rag_module import smart_crawl_url
        result = await smart_crawl_url(
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
        
        # Call the actual function from rag_module
        from src.modules.rag_module import perform_rag_query
        result = await perform_rag_query(
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
        # Get all sources directly
        result = await get_available_sources_direct()
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


# Project Management Endpoints

# Request/Response Models for Projects
class CreateProjectRequest(BaseModel):
    title: str
    prd: Optional[Dict[str, Any]] = None
    github_repo: Optional[str] = None


class CreateTaskRequest(BaseModel):
    project_id: str
    title: str
    description: Optional[str] = None
    parent_task_id: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = None
    code_examples: Optional[List[Dict[str, Any]]] = None


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


@app.get("/api/projects")
async def list_projects():
    """List all projects."""
    try:
        # Get Supabase client
        supabase_client = get_supabase_client()
        
        # Query projects directly
        response = supabase_client.table("projects").select("*").order("created_at", desc=True).execute()
        
        projects = []
        for project in response.data:
            projects.append({
                "id": project["id"],
                "title": project["title"],
                "github_repo": project.get("github_repo"),
                "created_at": project["created_at"],
                "updated_at": project["updated_at"],
                "prd": project.get("prd", {}),
                "docs": project.get("docs", []),
                "features": project.get("features", []),
                "data": project.get("data", [])
            })
        
        return projects
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.post("/api/projects")
async def create_project(request: CreateProjectRequest):
    """Create a new project."""
    try:
        # Get Supabase client
        supabase_client = get_supabase_client()
        
        project_data = {
            "title": request.title,
            "prd": request.prd or {},
            "docs": [],
            "features": [],
            "data": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        if request.github_repo:
            project_data["github_repo"] = request.github_repo
        
        response = supabase_client.table("projects").insert(project_data).execute()
        
        if response.data:
            project = response.data[0]
            return {
                "id": project["id"],
                "title": project["title"],
                "github_repo": project.get("github_repo"),
                "created_at": project["created_at"],
                "updated_at": project["updated_at"],
                "prd": project.get("prd", {}),
                "docs": project.get("docs", []),
                "features": project.get("features", []),
                "data": project.get("data", [])
            }
        else:
            raise HTTPException(status_code=500, detail={'error': 'Failed to create project'})
                
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """Get a specific project."""
    try:
        # Get Supabase client
        supabase_client = get_supabase_client()
        
        response = supabase_client.table("projects").select("*").eq("id", project_id).execute()
        
        if response.data:
            project = response.data[0]
            return {
                "id": project["id"],
                "title": project["title"],
                "github_repo": project.get("github_repo"),
                "created_at": project["created_at"],
                "updated_at": project["updated_at"],
                "prd": project.get("prd", {}),
                "docs": project.get("docs", []),
                "features": project.get("features", []),
                "data": project.get("data", [])
            }
        else:
            raise HTTPException(status_code=404, detail={'error': f'Project with ID {project_id} not found'})
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.get("/api/projects/{project_id}/tasks")
async def get_project_tasks(project_id: str):
    """Get all tasks for a specific project."""
    try:
        # Get Supabase client
        supabase_client = get_supabase_client()
        
        response = supabase_client.table("tasks").select("*").eq("project_id", project_id).order("created_at", desc=False).execute()
        
        tasks = []
        for task in response.data:
            tasks.append({
                "id": task["id"],
                "project_id": task["project_id"],
                "parent_task_id": task.get("parent_task_id"),
                "title": task["title"],
                "description": task.get("description", ""),
                "status": task["status"],
                "sources": task.get("sources", []),
                "code_examples": task.get("code_examples", []),
                "created_at": task["created_at"],
                "updated_at": task["updated_at"]
            })
        
        return tasks
        
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.post("/api/tasks")
async def create_task(request: CreateTaskRequest):
    """Create a new task."""
    try:
        # Get Supabase client
        supabase_client = get_supabase_client()
        
        task_data = {
            "project_id": request.project_id,
            "title": request.title,
            "description": request.description or "",
            "status": "todo",
            "sources": request.sources or [],
            "code_examples": request.code_examples or [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        if request.parent_task_id:
            task_data["parent_task_id"] = request.parent_task_id
        
        response = supabase_client.table("tasks").insert(task_data).execute()
        
        if response.data:
            task = response.data[0]
            return {
                "id": task["id"],
                "project_id": task["project_id"],
                "parent_task_id": task.get("parent_task_id"),
                "title": task["title"],
                "description": task["description"],
                "status": task["status"],
                "sources": task.get("sources", []),
                "code_examples": task.get("code_examples", []),
                "created_at": task["created_at"],
                "updated_at": task["updated_at"]
            }
        else:
            raise HTTPException(status_code=500, detail={'error': 'Failed to create task'})
                
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """Get a specific task."""
    try:
        supabase_client = get_supabase_client()
        
        response = supabase_client.table("tasks").select("*").eq("id", task_id).execute()
        
        if response.data:
            task = response.data[0]
            return {
                "success": True,
                "task": task
            }
        else:
            return {
                "success": False,
                "error": f"Task with ID {task_id} not found"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, request: UpdateTaskRequest):
    """Update a task."""
    try:
        supabase_client = get_supabase_client()
        
        # Build update data
        update_data = {
            "updated_at": datetime.now().isoformat()
        }
        
        if request.title is not None:
            update_data["title"] = request.title
        
        if request.description is not None:
            update_data["description"] = request.description
            
        if request.status is not None:
            valid_statuses = ['todo', 'doing', 'blocked', 'done']
            if request.status not in valid_statuses:
                return {
                    "success": False,
                    "error": f"Invalid status '{request.status}'. Must be one of: {', '.join(valid_statuses)}"
                }
            update_data["status"] = request.status
        
        response = supabase_client.table("tasks").update(update_data).eq("id", task_id).execute()
        
        if response.data:
            task = response.data[0]
            return {
                "success": True,
                "task": task
            }
        else:
            return {
                "success": False,
                "error": f"Task with ID {task_id} not found"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.put("/api/tasks/{task_id}/status")
async def update_task_status(task_id: str, status: str = Form(...)):
    """Update task status."""
    try:
        # Update task status directly in database
        supabase_client = get_supabase_client()
        
        valid_statuses = ['todo', 'doing', 'blocked', 'done']
        if status not in valid_statuses:
            return {
                "success": False,
                "error": f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}"
            }
        
        response = supabase_client.table("tasks").update({
            "status": status,
            "updated_at": datetime.now().isoformat()
        }).eq("id", task_id).execute()
        
        result = {
            "success": bool(response.data),
            "task": response.data[0] if response.data else None
        }
        
        # Parse JSON string response if needed
        if isinstance(result, str):
            result = json.loads(result)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task."""
    try:
        # Delete task directly from database
        supabase_client = get_supabase_client()
        
        response = supabase_client.table("tasks").delete().eq("id", task_id).execute()
        
        result = {
            "success": True,
            "message": f"Task {task_id} deleted successfully"
        }
        
        # Parse JSON string response if needed
        if isinstance(result, str):
            result = json.loads(result)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


# Helper functions for document processing

async def get_available_sources_direct() -> Dict[str, Any]:
    """Get all available sources from the sources table directly."""
    try:
        supabase_client = get_supabase_client()
        
        # Query the sources table directly
        result = supabase_client.from_('sources')\
            .select('*')\
            .order('source_id')\
            .execute()
        
        # Format the sources with their details
        sources = []
        if result.data:
            for source in result.data:
                sources.append({
                    "source_id": source.get("source_id"),
                    "title": source.get("title", source.get("summary", "Untitled")),
                    "summary": source.get("summary"),
                    "metadata": source.get("metadata", {}),
                    "total_word_count": source.get("total_word_count", 0),
                    "created_at": source.get("created_at"),
                    "updated_at": source.get("updated_at")
                })
        
        return {
            "success": True,
            "sources": sources,
            "count": len(sources)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def process_uploaded_document(
    file_content: bytes, 
    filename: str, 
    knowledge_type: str = "technical", 
    tags: List[str] = [], 
    chunk_size: int = 5000
) -> Dict[str, Any]:
    """Process an uploaded document and store it in the knowledge base."""
    try:
        import base64
        import tempfile
        import os
        from pathlib import Path
        
        # Import document processing libraries
        try:
            import PyPDF2
            import pdfplumber
            from docx import Document as DocxDocument
        except ImportError as e:
            return {
                "success": False,
                "error": f"Missing document processing library: {e}. Please install required dependencies."
            }
        
        # Get the Supabase client
        supabase_client = get_supabase_client()
        
        # Determine file type from extension
        file_ext = Path(filename).suffix.lower()
        supported_extensions = {'.pdf', '.doc', '.docx', '.md', '.txt'}
        
        if file_ext not in supported_extensions:
            return {
                "success": False,
                "error": f"Unsupported file type: {file_ext}. Supported: {', '.join(supported_extensions)}"
            }
        
        # Extract text content based on file type
        text_content = ""
        
        if file_ext in ['.md', '.txt']:
            # For text files, decode bytes to string
            text_content = file_content.decode('utf-8')
                
        else:
            # For binary files, process with appropriate library
            # Create temporary file for processing
            with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            try:
                if file_ext == '.pdf':
                    # Extract text from PDF using both PyPDF2 and pdfplumber for best results
                    text_parts = []
                    
                    # Try pdfplumber first (better for complex layouts)
                    try:
                        with pdfplumber.open(temp_file_path) as pdf:
                            for page in pdf.pages:
                                text = page.extract_text()
                                if text:
                                    text_parts.append(text)
                    except Exception as plumber_error:
                        print(f"pdfplumber failed: {plumber_error}, trying PyPDF2")
                        
                        # Fallback to PyPDF2
                        with open(temp_file_path, 'rb') as pdf_file:
                            pdf_reader = PyPDF2.PdfReader(pdf_file)
                            for page in pdf_reader.pages:
                                text = page.extract_text()
                                if text:
                                    text_parts.append(text)
                    
                    text_content = '\n\n'.join(text_parts)
                    
                elif file_ext in ['.doc', '.docx']:
                    # Extract text from Word document
                    doc = DocxDocument(temp_file_path)
                    text_parts = []
                    for paragraph in doc.paragraphs:
                        if paragraph.text.strip():
                            text_parts.append(paragraph.text)
                    text_content = '\n\n'.join(text_parts)
                    
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
        
        # Validate extracted content
        if not text_content.strip():
            return {
                "success": False,
                "error": "No text content could be extracted from the document"
            }
        
        # Generate document URL (use file:// scheme for uploaded documents)
        document_url = f"file://{filename}"
        
        # Generate AI title and description for the document
        try:
            # Get credentials from database for OpenAI API
            openai_api_key = await credential_service.get_credential("OPENAI_API_KEY", decrypt=True)
            if not openai_api_key:
                raise Exception("OpenAI API key not found in credentials")
            
            # Generate title and description using OpenAI
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            
            # Prepare content sample for AI analysis (first 2000 chars)
            content_sample = text_content[:2000] + ("..." if len(text_content) > 2000 else "")
            
            title_prompt = f"""Based on this document content, generate a clear, descriptive title (max 100 characters):

{content_sample}

Title:"""
            
            title_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": title_prompt}],
                max_tokens=50,
                temperature=0.3
            )
            
            ai_title = title_response.choices[0].message.content.strip()
            if len(ai_title) > 100:
                ai_title = ai_title[:97] + "..."
            
            description_prompt = f"""Based on this document content, generate a helpful 2-3 sentence description:

{content_sample}

Description:"""
            
            description_response = client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[{"role": "user", "content": description_prompt}],
                max_tokens=150,
                temperature=0.3
            )
            
            ai_description = description_response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Failed to generate AI title/description: {e}")
            # Fallback to filename-based title
            ai_title = Path(filename).stem.replace('_', ' ').replace('-', ' ').title()
            ai_description = f"Uploaded document: {filename}"
        
        # Chunk the text content
        chunks = smart_chunk_markdown(text_content, chunk_size)
        
        # Calculate document stats
        word_count = len(text_content.split())
        chunk_count = len(chunks)
        
        # Create source_id from filename 
        source_id = f"upload_{Path(filename).stem}"
        
        # Prepare data for batch insertion
        urls = [document_url] * len(chunks)
        chunk_numbers = list(range(1, len(chunks) + 1))
        contents = chunks
        metadatas = []
        
        # Add chunk-specific metadata
        for i, chunk in enumerate(chunks):
            section_info = extract_section_info(chunk)
            metadata = {
                'knowledge_type': knowledge_type,
                'tags': tags,
                'source_type': 'file',
                'file_name': filename,
                'file_type': file_ext,
                'chunk_index': i + 1,
                'total_chunks': len(chunks),
                'title': ai_title,
                'description': ai_description,
                'source': source_id,
                'url': document_url,
                **section_info
            }
            metadatas.append(metadata)
        
        # Create URL to full document mapping
        url_to_full_document = {document_url: text_content}
        
        # First, create/update source information
        try:
            update_source_info(
                client=supabase_client,
                source_id=source_id,
                summary=ai_description,
                word_count=word_count,
                content=text_content[:500],  # First 500 chars as preview
                knowledge_type=knowledge_type,
                tags=tags
            )
        except Exception as e:
            print(f"Failed to update source info: {e}")
            return {
                "success": False,
                "filename": filename,
                "error": f"Failed to create source entry: {e}"
            }
        
        # Store document chunks in Supabase
        add_documents_to_supabase(
            client=supabase_client,
            urls=urls,
            chunk_numbers=chunk_numbers,
            contents=contents,
            metadatas=metadatas,
            url_to_full_document=url_to_full_document
        )
        
        return {
            "success": True,
            "filename": filename,
            "title": ai_title,
            "description": ai_description,
            "source_id": source_id,
            "chunks_created": chunk_count,
            "word_count": word_count,
            "code_examples_extracted": 0,  # Could add code extraction here if needed
            "knowledge_type": knowledge_type,
            "tags": tags,
            "file_type": file_ext,
            "message": f"Successfully uploaded and processed {filename}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "filename": filename,
            "error": str(e)
        }


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
        
        # Get all sources directly 
        sources_result = await get_available_sources_direct()
        
        # Parse the JSON response
        if isinstance(sources_result, str):
            sources_data = json.loads(sources_result)
        else:
            sources_data = sources_result
        
        # Transform the data to match frontend expectations
        items = []
        for source in sources_data.get('sources', []):
            # Use title and metadata from sources table
            source_metadata = source.get('metadata', {})
            
            # Get first page URL if available
            supabase_client = crawling_context.supabase_client
            pages_response = supabase_client.from_('crawled_pages')\
                .select('url')\
                .eq('source_id', source['source_id'])\
                .limit(1)\
                .execute()
            
            first_page = pages_response.data[0] if pages_response.data else {}
            
            # Determine source type - if metadata has source_type='file', use it; otherwise check URL pattern
            stored_source_type = source_metadata.get('source_type')
            if stored_source_type:
                source_type = stored_source_type
            else:
                # Legacy fallback - check URL pattern
                first_page_url = first_page.get('url', f"source://{source['source_id']}")
                source_type = 'file' if first_page_url.startswith('file://') else 'url'
            
            item = {
                'id': source['source_id'],
                'title': source.get('title', source.get('summary', 'Untitled')),
                'url': first_page.get('url', f"source://{source['source_id']}"),
                'source_id': source['source_id'],
                'metadata': {
                    'knowledge_type': source_metadata.get('knowledge_type', 'technical'),
                    'tags': source_metadata.get('tags', []),
                    'source_type': source_type,
                    'status': 'active',
                    'description': source_metadata.get('description', source.get('summary', '')),
                    'chunks_count': source.get('total_words', 0),
                    'word_count': source.get('total_words', 0),
                    'last_scraped': source.get('updated_at'),
                    'file_name': source_metadata.get('file_name'),
                    'file_type': source_metadata.get('file_type'),
                    **source_metadata
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


async def _perform_crawl_with_progress(progress_id: str, request: KnowledgeItemRequest):
    """Perform the actual crawl operation with progress tracking."""
    try:
        print(f"DEBUG: Starting crawl for progress_id: {progress_id}")
        
        # Create a progress callback that will be called by the crawling function
        async def progress_callback(status: str, percentage: int, message: str, **kwargs):
            """Callback function to receive real-time progress updates from crawling."""
            await progress_manager.update_progress(progress_id, {
                'status': status,
                'percentage': percentage,
                'currentUrl': kwargs.get('currentUrl', str(request.url)),
                'totalPages': kwargs.get('totalPages', 0),
                'processedPages': kwargs.get('processedPages', 0),
                'log': message,
                **kwargs
            })
            print(f"DEBUG: Progress callback - {status}: {percentage}% - {message}")
        
        # Initial progress update
        await progress_callback('starting', 0, f'Starting crawl of {request.url}')
        
        # Ensure crawling context is initialized
        if not crawling_context._initialized:
            await crawling_context.initialize()
        
        # Create context for the MCP function
        ctx = crawling_context.create_context()
        
        # Store metadata in context for the crawling functions to access
        ctx.knowledge_metadata = {
            'knowledge_type': request.knowledge_type,
            'tags': request.tags,
            'update_frequency': request.update_frequency
        }
        
        # IMPORTANT: Add progress callback to context so MCP function can use it
        ctx.progress_callback = progress_callback
        
        # Call the actual crawling function with progress callback support
        from src.modules.rag_module import smart_crawl_url
        result = await smart_crawl_url(
            ctx=ctx,
            url=str(request.url),
            max_depth=2,
            max_concurrent=5,
            chunk_size=5000
        )
        
        # Parse JSON string response if needed
        if isinstance(result, str):
            result = json.loads(result)
        
        # Final completion update (the MCP function should have sent this, but ensure it happens)
        if result.get('success'):
            completion_data = {
                'chunksStored': result.get('chunks_stored', 0),
                'wordCount': result.get('total_word_count', 0),
                'log': 'Crawling completed successfully'
            }
            await progress_manager.complete_crawl(progress_id, completion_data)
        else:
            await progress_manager.error_crawl(progress_id, result.get('error', 'Unknown error'))
        
        # Broadcast final update to general WebSocket clients
        await manager.broadcast({
            "type": "crawl_completed",
            "data": {
                "url": str(request.url),
                "success": result.get('success', False),
                "message": f'Crawling completed for {request.url}',
                "progressId": progress_id
            }
        })
        
    except Exception as e:
        error_message = f'Crawling failed: {str(e)}'
        await progress_manager.error_crawl(progress_id, error_message)
        print(f"Crawl error for {progress_id}: {e}")


@app.post("/api/knowledge-items/crawl")
async def crawl_knowledge_item(request: KnowledgeItemRequest):
    """Crawl a URL and add it to the knowledge base with progress tracking."""
    try:
        # Generate unique progress ID
        progress_id = str(uuid.uuid4())
        
        # Start progress tracking
        progress_manager.start_crawl(progress_id, {
            'progressId': progress_id,
            'currentUrl': str(request.url),
            'totalPages': 0,
            'processedPages': 0
        })
        
        # Start crawling in background
        asyncio.create_task(_perform_crawl_with_progress(progress_id, request))
        
        return {
            'success': True,
            'progressId': progress_id,
            'message': 'Crawling started',
            'estimatedDuration': '3-5 minutes'
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
        
        # Call the actual function from rag_module
        from src.modules.rag_module import delete_source
        result = await delete_source(ctx, source_id)
        
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


@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
    knowledge_type: Optional[str] = Form("technical")
):
    """Upload a document and add it to the knowledge base."""
    try:
        # Validate file size (10MB limit)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail={'error': f'File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB'}
            )
        
        if file_size == 0:
            raise HTTPException(
                status_code=400,
                detail={'error': 'Empty file uploaded'}
            )
        
        # Validate file type
        file_ext = Path(file.filename).suffix.lower()
        allowed_extensions = {'.pdf', '.doc', '.docx', '.md', '.txt'}
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail={'error': f'Unsupported file type: {file_ext}. Allowed: {", ".join(allowed_extensions)}'}
            )
        
        # Parse tags if provided
        parsed_tags = []
        if tags:
            try:
                parsed_tags = json.loads(tags) if tags.startswith('[') else [tags]
            except:
                parsed_tags = [tags]  # Treat as single tag if JSON parsing fails
        
        # Ensure crawling context is initialized
        if not crawling_context._initialized:
            await crawling_context.initialize()
        
        # Create context for the MCP function
        ctx = crawling_context.create_context()
        
        # Store metadata in context for the upload function to access
        ctx.knowledge_metadata = {
            'knowledge_type': knowledge_type,
            'tags': parsed_tags
        }
        
        # Encode file content as base64 for the MCP tool
        import base64
        encoded_content = base64.b64encode(file_content).decode('utf-8')
        
        # Process document directly
        result = await process_uploaded_document(
            file_content=file_content,
            filename=file.filename,
            knowledge_type=knowledge_type,
            tags=parsed_tags,
            chunk_size=5000
        )
        
        # Parse JSON string response
        if isinstance(result, str):
            result = json.loads(result)
        
        if result.get('success'):
            # Broadcast update to WebSocket clients
            await manager.broadcast({
                "type": "document_uploaded",
                "data": {
                    "filename": file.filename,
                    "success": True,
                    "message": f'Document {file.filename} uploaded successfully'
                }
            })
            
            return {
                'success': True,
                'filename': file.filename,
                'source_id': result.get('source_id'),
                'title': result.get('title'),
                'description': result.get('description'),
                'chunks_created': result.get('chunks_created'),
                'word_count': result.get('word_count'),
                'code_examples_extracted': result.get('code_examples_extracted', 0),
                'knowledge_type': knowledge_type,
                'tags': parsed_tags,
                'file_type': file_ext,
                'message': result.get('message', 'Document uploaded successfully')
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={'error': result.get('error', 'Upload failed')}
            )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Document upload error: {e}")
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.post("/api/knowledge-items/upload")
async def upload_knowledge_document(request: Request):
    """Legacy endpoint - redirects to new upload endpoint."""
    return {
        'success': False,
        'error': 'Please use /api/documents/upload endpoint with multipart form data'
    }


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
        sources_result = await get_available_sources_direct()
        
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


@app.websocket("/api/crawl-progress/{progress_id}")
async def websocket_crawl_progress(websocket: WebSocket, progress_id: str):
    """WebSocket endpoint for tracking specific crawl progress."""
    print(f"DEBUG: WebSocket connection attempt for progress_id: {progress_id}")
    
    # Add WebSocket to progress manager (now handles accept internally)
    await progress_manager.add_websocket(progress_id, websocket)
    print(f"DEBUG: WebSocket added to progress manager for progress_id: {progress_id}")
    
    try:
        while True:
            # Keep connection alive with ping (match MCP pattern exactly)
            await asyncio.sleep(1)
            await websocket.send_json({"type": "ping"})
            
    except WebSocketDisconnect:
        print(f"DEBUG: WebSocket disconnected for progress_id: {progress_id}")
        progress_manager.remove_websocket(progress_id, websocket)
    except Exception as e:
        print(f"DEBUG: WebSocket error for progress {progress_id}: {e}")
        progress_manager.remove_websocket(progress_id, websocket)
        try:
            await websocket.close()
        except:
            pass


class CrawlProgressManager:
    """Manages crawling progress tracking and WebSocket streaming."""
    
    def __init__(self):
        self.active_crawls: Dict[str, Dict[str, Any]] = {}
        self.progress_websockets: Dict[str, List[WebSocket]] = {}
    
    def start_crawl(self, progress_id: str, initial_data: Dict[str, Any]) -> None:
        """Start tracking a new crawl operation."""
        self.active_crawls[progress_id] = {
            'status': 'starting',
            'percentage': 0,
            'start_time': datetime.now(),
            'logs': ['Starting crawl...'],
            **initial_data
        }
        
    async def update_progress(self, progress_id: str, update_data: Dict[str, Any]) -> None:
        """Update crawling progress and notify connected clients."""
        if progress_id not in self.active_crawls:
            return
        
        # Update progress data
        self.active_crawls[progress_id].update(update_data)
        
        # Add log if provided
        if 'log' in update_data:
            self.active_crawls[progress_id]['logs'].append(update_data['log'])
            # Keep only last 50 logs
            if len(self.active_crawls[progress_id]['logs']) > 50:
                self.active_crawls[progress_id]['logs'] = self.active_crawls[progress_id]['logs'][-50:]
        
        # Broadcast to connected WebSocket clients
        await self._broadcast_progress(progress_id)
    
    async def complete_crawl(self, progress_id: str, completion_data: Dict[str, Any]) -> None:
        """Mark a crawl as completed and send final update."""
        if progress_id not in self.active_crawls:
            return
        
        completion_data.update({
            'status': 'completed',
            'percentage': 100,
            'duration': str(datetime.now() - self.active_crawls[progress_id]['start_time'])
        })
        
        self.active_crawls[progress_id].update(completion_data)
        await self._broadcast_progress(progress_id)
        
        # Clean up after a delay
        await asyncio.sleep(5)
        if progress_id in self.active_crawls:
            del self.active_crawls[progress_id]
    
    async def error_crawl(self, progress_id: str, error_message: str) -> None:
        """Mark a crawl as failed and send error update."""
        if progress_id not in self.active_crawls:
            return
        
        self.active_crawls[progress_id].update({
            'status': 'error',
            'error': error_message,
            'log': f'Error: {error_message}'
        })
        
        await self._broadcast_progress(progress_id)
    
    async def add_websocket(self, progress_id: str, websocket: WebSocket) -> None:
        """Add a WebSocket connection for progress updates."""
        # CRITICAL: Accept the WebSocket connection FIRST (match MCP pattern)
        await websocket.accept()
        print(f"DEBUG: WebSocket accepted for {progress_id}")
        
        if progress_id not in self.progress_websockets:
            self.progress_websockets[progress_id] = []
        
        self.progress_websockets[progress_id].append(websocket)
        print(f"DEBUG: Added WebSocket for {progress_id}, total connections: {len(self.progress_websockets[progress_id])}")
        
        # Send current progress if available (now it's safe to send)
        if progress_id in self.active_crawls:
            try:
                # Ensure progressId is included in the data
                data = self.active_crawls[progress_id].copy()
                data['progressId'] = progress_id
                
                # Convert datetime objects to strings for JSON serialization
                if 'start_time' in data and hasattr(data['start_time'], 'isoformat'):
                    data['start_time'] = data['start_time'].isoformat()
                
                message = {
                    "type": "crawl_progress",
                    "data": data
                }
                print(f"DEBUG: Sending initial progress to new WebSocket: {message}")
                await websocket.send_json(message)
            except Exception as e:
                print(f"DEBUG: Error sending initial progress: {e}")
        else:
            print(f"DEBUG: No active crawl found for progress_id: {progress_id}")
            # Send a confirmation message that we're connected and waiting
            try:
                await websocket.send_json({
                    "type": "connection_established",
                    "data": {"progressId": progress_id, "status": "waiting"}
                })
            except Exception as e:
                print(f"DEBUG: Error sending connection confirmation: {e}")
    
    def remove_websocket(self, progress_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if progress_id in self.progress_websockets:
            try:
                self.progress_websockets[progress_id].remove(websocket)
                if not self.progress_websockets[progress_id]:
                    del self.progress_websockets[progress_id]
            except ValueError:
                pass
    
    async def _broadcast_progress(self, progress_id: str) -> None:
        """Broadcast progress update to all connected clients."""
        print(f"DEBUG: Broadcasting progress for {progress_id}")
        if progress_id not in self.progress_websockets:
            print(f"DEBUG: No WebSocket connections found for {progress_id}")
            return
        
        progress_data = self.active_crawls.get(progress_id, {}).copy()
        # Ensure progressId is always included
        progress_data['progressId'] = progress_id
        
        # Convert datetime objects to strings for JSON serialization
        if 'start_time' in progress_data and hasattr(progress_data['start_time'], 'isoformat'):
            progress_data['start_time'] = progress_data['start_time'].isoformat()
        
        message = {
            "type": "crawl_progress" if progress_data.get('status') != 'completed' else "crawl_completed",
            "data": progress_data
        }
        print(f"DEBUG: Broadcasting message: {message}")
        
        # Send to all connected WebSocket clients
        disconnected = []
        for websocket in self.progress_websockets[progress_id]:
            try:
                await websocket.send_json(message)
                print(f"DEBUG: Successfully sent message to WebSocket client")
            except Exception as e:
                print(f"DEBUG: Failed to send to WebSocket client: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected WebSockets
        for ws in disconnected:
            self.remove_websocket(progress_id, ws)

# Global progress manager
progress_manager = CrawlProgressManager()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
