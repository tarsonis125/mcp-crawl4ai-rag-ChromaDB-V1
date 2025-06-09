"""
MCP API endpoints for Archon

Handles:
- MCP server lifecycle (start/stop/status)
- MCP server configuration management
- WebSocket log streaming
- Tool discovery and testing
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import asyncio
import subprocess
import os
import time
from collections import deque
from datetime import datetime
import json

from ..utils import get_supabase_client

# Import Logfire
from ..logfire_config import mcp_logger, api_logger

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

class ServerConfig(BaseModel):
    transport: str = 'sse'
    host: str = 'localhost'
    port: int = 8051

class ServerResponse(BaseModel):
    success: bool
    message: str
    status: Optional[str] = None
    pid: Optional[int] = None

class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str

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
        with mcp_logger.span("mcp_server_start") as span:
            span.set_attribute("action", "start_server")
            
            if self.process and self.process.poll() is None:
                mcp_logger.warning("MCP server start attempted while already running")
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
                    from ..credential_service import credential_service
                    
                    # Get configuration from database
                    openai_key = await credential_service.get_credential('OPENAI_API_KEY', decrypt=True)
                    model_choice = await credential_service.get_credential('MODEL_CHOICE', 'gpt-4o-mini')
                    transport = await credential_service.get_credential('TRANSPORT', 'sse')
                    host = await credential_service.get_credential('HOST', '0.0.0.0')
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
                    mcp_logger.info("MCP server configuration loaded from database", 
                                  transport=transport, host=host, port=port, model=model_choice)
                    
                except Exception as e:
                    # Log the error but don't fallback to environment variables
                    # All configuration should come from the database
                    self._add_log('ERROR', f'Failed to load credentials from database: {e}')
                    self._add_log('ERROR', 'Please ensure all credentials are set via the Settings page')
                    mcp_logger.error("Failed to load MCP server credentials from database", error=str(e))
                    
                    # Set minimal environment for MCP server with empty values
                    env.update({
                        'OPENAI_API_KEY': '',  # Don't override database credentials
                        'SUPABASE_URL': os.getenv('SUPABASE_URL', ''),  # Still need these for connection
                        'SUPABASE_SERVICE_KEY': os.getenv('SUPABASE_SERVICE_KEY', ''),
                        'HOST': '0.0.0.0',
                        'PORT': '8051',
                        'TRANSPORT': 'sse',
                        'MODEL_CHOICE': 'gpt-4o-mini',
                        'USE_CONTEXTUAL_EMBEDDINGS': 'false',
                        'USE_HYBRID_SEARCH': 'false',
                        'USE_AGENTIC_RAG': 'false',
                        'USE_RERANKING': 'false',
                    })
                    
                    self._add_log('WARNING', 'Started MCP server with default configuration due to database error')
                
                # Start the MCP server process (using uv like the old working version)
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
                self._add_log('INFO', 'MCP server starting...')
                mcp_logger.info("MCP server process started", pid=self.process.pid, cmd=cmd)
                span.set_attribute("pid", self.process.pid)
                
                # Start reading logs from the process
                self.log_reader_task = asyncio.create_task(self._read_process_logs())
                
                # Give it a moment to start
                await asyncio.sleep(2)
                
                # Check if process is still running
                if self.process.poll() is None:
                    self.status = 'running'
                    self._add_log('INFO', 'MCP server started successfully')
                    mcp_logger.info("MCP server started successfully", pid=self.process.pid, uptime=0)
                    span.set_attribute("success", True)
                    span.set_attribute("status", "running")
                    return {
                        'success': True,
                        'status': self.status,
                        'message': 'MCP server started successfully',
                        'pid': self.process.pid
                    }
                else:
                    self.status = 'failed'
                    self._add_log('ERROR', 'MCP server failed to start')
                    mcp_logger.error("MCP server failed to start - process exited immediately")
                    span.set_attribute("success", False)
                    span.set_attribute("status", "failed")
                    return {
                        'success': False,
                        'status': self.status,
                        'message': 'MCP server failed to start'
                    }
                    
            except Exception as e:
                self.status = 'failed'
                self._add_log('ERROR', f'Failed to start MCP server: {str(e)}')
                mcp_logger.error("Exception during MCP server startup", error=str(e), error_type=type(e).__name__)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                return {
                    'success': False,
                    'status': self.status,
                    'message': f'Failed to start MCP server: {str(e)}'
                }
    
    async def stop_server(self) -> Dict[str, Any]:
        """Stop the MCP server process."""
        with mcp_logger.span("mcp_server_stop") as span:
            span.set_attribute("action", "stop_server")
            
            if not self.process or self.process.poll() is not None:
                mcp_logger.warning("MCP server stop attempted when not running")
                return {
                    'success': False,
                    'status': 'stopped',
                    'message': 'MCP server is not running'
                }
            
            try:
                self.status = 'stopping'
                self._add_log('INFO', 'Stopping MCP server...')
                mcp_logger.info("Stopping MCP server", pid=self.process.pid)
                span.set_attribute("pid", self.process.pid)
                
                # Cancel log reading task
                if self.log_reader_task:
                    self.log_reader_task.cancel()
                    try:
                        await self.log_reader_task
                    except asyncio.CancelledError:
                        pass
                
                # Terminate the process
                self.process.terminate()
                
                # Wait for process to exit (with timeout)
                try:
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, self.process.wait),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    # Force kill if it doesn't exit gracefully
                    self.process.kill()
                    await asyncio.get_event_loop().run_in_executor(None, self.process.wait)
                    mcp_logger.warning("MCP server force killed after timeout")
                
                self.process = None
                self.status = 'stopped'
                self.start_time = None
                self._add_log('INFO', 'MCP server stopped')
                mcp_logger.info("MCP server stopped successfully")
                span.set_attribute("success", True)
                span.set_attribute("status", "stopped")
                
                return {
                    'success': True,
                    'status': self.status,
                    'message': 'MCP server stopped successfully'
                }
                
            except Exception as e:
                self._add_log('ERROR', f'Error stopping MCP server: {str(e)}')
                mcp_logger.error("Exception during MCP server stop", error=str(e), error_type=type(e).__name__)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                return {
                    'success': False,
                    'status': self.status,
                    'message': f'Error stopping MCP server: {str(e)}'
                }
    
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
                        level, message = self._parse_log_line(line)
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
    
    def _parse_log_line(self, line: str) -> tuple[str, str]:
        """Parse a log line to extract level and message."""
        line = line.strip()
        if not line:
            return 'INFO', ''
        
        # Try to extract log level from common formats
        if line.startswith('[') and ']' in line:
            end_bracket = line.find(']')
            potential_level = line[1:end_bracket].upper()
            if potential_level in ['INFO', 'DEBUG', 'WARNING', 'ERROR', 'CRITICAL']:
                return potential_level, line[end_bracket+1:].strip()
        
        # Check for common log level indicators
        line_lower = line.lower()
        if any(word in line_lower for word in ['error', 'exception', 'failed', 'critical']):
            return 'ERROR', line
        elif any(word in line_lower for word in ['warning', 'warn']):
            return 'WARNING', line
        elif any(word in line_lower for word in ['debug']):
            return 'DEBUG', line
        else:
            return 'INFO', line
    
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

# Global MCP manager instance
mcp_manager = MCPServerManager()

@router.post("/start", response_model=ServerResponse)
async def start_server():
    """Start the MCP server."""
    with api_logger.span("api_mcp_start") as span:
        span.set_attribute("endpoint", "/mcp/start")
        span.set_attribute("method", "POST")
        
        try:
            result = await mcp_manager.start_server()
            api_logger.info("MCP server start API called", success=result.get('success', False))
            span.set_attribute("success", result.get('success', False))
            return result
        except Exception as e:
            api_logger.error("MCP server start API failed", error=str(e))
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop", response_model=ServerResponse)
async def stop_server():
    """Stop the MCP server."""
    with api_logger.span("api_mcp_stop") as span:
        span.set_attribute("endpoint", "/mcp/stop")
        span.set_attribute("method", "POST")
        
        try:
            result = await mcp_manager.stop_server()
            api_logger.info("MCP server stop API called", success=result.get('success', False))
            span.set_attribute("success", result.get('success', False))
            return result
        except Exception as e:
            api_logger.error("MCP server stop API failed", error=str(e))
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_status():
    """Get MCP server status."""
    with api_logger.span("api_mcp_status") as span:
        span.set_attribute("endpoint", "/mcp/status")
        span.set_attribute("method", "GET")
        
        try:
            status = mcp_manager.get_status()
            api_logger.debug("MCP server status checked", status=status.get('status'))
            span.set_attribute("status", status.get('status'))
            span.set_attribute("uptime", status.get('uptime'))
            return status
        except Exception as e:
            api_logger.error("MCP server status API failed", error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs")
async def get_logs(limit: int = 100):
    """Get MCP server logs."""
    with api_logger.span("api_mcp_logs") as span:
        span.set_attribute("endpoint", "/mcp/logs")
        span.set_attribute("method", "GET")
        span.set_attribute("limit", limit)
        
        try:
            logs = mcp_manager.get_logs(limit)
            api_logger.debug("MCP server logs retrieved", count=len(logs))
            span.set_attribute("log_count", len(logs))
            return {'logs': logs}
        except Exception as e:
            api_logger.error("MCP server logs API failed", error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.delete("/logs")
async def clear_logs():
    """Clear MCP server logs."""
    with api_logger.span("api_mcp_clear_logs") as span:
        span.set_attribute("endpoint", "/mcp/logs")
        span.set_attribute("method", "DELETE")
        
        try:
            mcp_manager.clear_logs()
            api_logger.info("MCP server logs cleared")
            span.set_attribute("success", True)
            return {'success': True, 'message': 'Logs cleared successfully'}
        except Exception as e:
            api_logger.error("MCP server clear logs API failed", error=str(e))
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/config")
async def get_mcp_config():
    """Get MCP server configuration."""
    with api_logger.span("api_get_mcp_config") as span:
        span.set_attribute("endpoint", "/api/mcp/config")
        span.set_attribute("method", "GET")
        
        try:
            api_logger.info("Getting MCP server configuration")
            from ..credential_service import credential_service
            
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
                api_logger.info("MCP configuration retrieved from database")
                span.set_attribute("source", "database")
            except Exception:
                # Fallback to environment variables
                import os
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
                api_logger.warning("MCP configuration retrieved from environment variables")
                span.set_attribute("source", "environment")
            
            span.set_attribute("host", config['host'])
            span.set_attribute("port", config['port'])
            span.set_attribute("transport", config['transport'])
            span.set_attribute("model_choice", config['model_choice'])
            
            return config
        except Exception as e:
            api_logger.error("Failed to get MCP configuration", error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/config")
async def save_configuration(config: ServerConfig):
    """Save MCP server configuration."""
    with api_logger.span("api_save_mcp_config") as span:
        span.set_attribute("endpoint", "/api/mcp/config")
        span.set_attribute("method", "POST")
        span.set_attribute("transport", config.transport)
        span.set_attribute("host", config.host)
        span.set_attribute("port", config.port)
        
        try:
            api_logger.info("Saving MCP server configuration", transport=config.transport, host=config.host, port=config.port)
            supabase_client = get_supabase_client()
            
            config_json = config.model_dump_json()
            
            # Check if config exists
            existing = supabase_client.table("credentials").select("id").eq("key_name", "mcp_config").execute()
            
            if existing.data:
                # Update existing
                response = supabase_client.table("credentials").update({
                    "key_value": config_json
                }).eq("key_name", "mcp_config").execute()
                api_logger.info("MCP configuration updated")
                span.set_attribute("operation", "update")
            else:
                # Insert new
                response = supabase_client.table("credentials").insert({
                    "key_name": "mcp_config",
                    "key_value": config_json
                }).execute()
                api_logger.info("MCP configuration created")
                span.set_attribute("operation", "create")
            
            span.set_attribute("success", True)
            return {"success": True, "message": "Configuration saved"}
            
        except Exception as e:
            api_logger.error("Failed to save MCP configuration", error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail={'error': str(e)})

@router.websocket("/logs/stream")
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

@router.get("/tools")
async def get_mcp_tools():
    """Get available MCP tools by querying the running MCP server directly."""
    with api_logger.span("api_get_mcp_tools") as span:
        span.set_attribute("endpoint", "/api/mcp/tools")
        span.set_attribute("method", "GET")
        
        try:
            api_logger.info("Getting MCP tools")
            
            # Check if server is running
            server_status = mcp_manager.get_status()
            is_running = server_status.get('status') == 'running'
            span.set_attribute("server_running", is_running)
            
            if not is_running:
                api_logger.warning("MCP server not running when requesting tools")
                return {
                    'tools': [],
                    'count': 0,
                    'server_running': False,
                    'source': 'server_not_running',
                    'message': 'MCP server is not running. Start the server to see available tools.'
                }

            # Return the expected tools from our modular architecture when server is running
            if is_running:
                tools_from_server = [
                    # System Management Tools
                    {
                        "name": "health_check",
                        "description": "Perform a lightweight health check that can respond immediately.",
                        "module": "system",
                        "parameters": [
                            {"name": "random_string", "type": "string", "required": True, "description": "Dummy parameter for no-parameter tools"}
                        ]
                    },
                    
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
                        "parameters": [
                            {"name": "random_string", "type": "string", "required": True, "description": "Dummy parameter for no-parameter tools"}
                        ]
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
                        "name": "delete_source_tool",
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
                        "parameters": [
                            {"name": "random_string", "type": "string", "required": True, "description": "Dummy parameter for no-parameter tools"}
                        ]
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
                        "name": "delete_project",
                        "description": "Delete a project and all its associated tasks.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the project to delete"}
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
                            {"name": "assignee", "type": "string", "required": False, "description": "Task assignee - one of 'User', 'Archon', 'AI IDE Agent' (default: 'User')"},
                            {"name": "task_order", "type": "integer", "required": False, "description": "Order/priority of the task (default: 0)"},
                            {"name": "feature", "type": "string", "required": False, "description": "Optional feature name/label this task belongs to"},
                            {"name": "parent_task_id", "type": "string", "required": False, "description": "Optional UUID of parent task for subtasks"},
                            {"name": "sources", "type": "array", "required": False, "description": "Optional list of source metadata dicts"},
                            {"name": "code_examples", "type": "array", "required": False, "description": "Optional list of code example dicts"}
                        ]
                    },
                    {
                        "name": "list_tasks_by_project",
                        "description": "List all tasks under a specific project. By default, filters out closed/done tasks.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the project"},
                            {"name": "include_closed", "type": "boolean", "required": False, "description": "Whether to include closed/done tasks (default: False)"}
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
                            {"name": "status", "type": "string", "required": True, "description": "New status - one of 'todo', 'doing', 'review', 'done'"}
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
                            {"name": "status", "type": "string", "required": False, "description": "Optional new status - one of 'todo', 'doing', 'review', 'done'"},
                            {"name": "assignee", "type": "string", "required": False, "description": "Optional new assignee - one of 'User', 'Archon', 'AI IDE Agent'"},
                            {"name": "task_order", "type": "integer", "required": False, "description": "Optional new order/priority"},
                            {"name": "feature", "type": "string", "required": False, "description": "Optional new feature name/label"}
                        ]
                    },
                    {
                        "name": "delete_task",
                        "description": "Archive a task and all its subtasks (soft delete).",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "task_id", "type": "string", "required": True, "description": "UUID of the task to archive"}
                        ]
                    },
                    {
                        "name": "get_task_subtasks",
                        "description": "Get all subtasks of a specific task. By default, filters out closed/done subtasks.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "parent_task_id", "type": "string", "required": True, "description": "UUID of the parent task"},
                            {"name": "include_closed", "type": "boolean", "required": False, "description": "Whether to include closed/done subtasks (default: False)"}
                        ]
                    },
                    {
                        "name": "get_tasks_by_status",
                        "description": "Get all tasks in a project filtered by status.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the project"},
                            {"name": "status", "type": "string", "required": True, "description": "Status to filter by - one of 'todo', 'doing', 'review', 'done'"}
                        ]
                    },
                    
                    # Document Management Tools
                    {
                        "name": "add_project_document",
                        "description": "Add a new document to a project's docs JSONB field using clean MCP format.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the parent project"},
                            {"name": "document_type", "type": "string", "required": True, "description": "Type of document (prd, feature_plan, erd, technical_spec, meeting_notes, api_docs)"},
                            {"name": "title", "type": "string", "required": True, "description": "Document title"},
                            {"name": "content", "type": "object", "required": False, "description": "Document content as structured JSON - MUST follow MCP format"},
                            {"name": "tags", "type": "array", "required": False, "description": "Optional list of tags for categorization"},
                            {"name": "author", "type": "string", "required": False, "description": "Optional author name (defaults to 'System')"}
                        ]
                    },
                    {
                        "name": "list_project_documents",
                        "description": "List all documents in a project's docs JSONB field.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the project"}
                        ]
                    },
                    {
                        "name": "get_project_document",
                        "description": "Get a specific document from a project's docs JSONB field.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the project"},
                            {"name": "doc_id", "type": "string", "required": True, "description": "UUID of the document"}
                        ]
                    },
                    {
                        "name": "update_project_document",
                        "description": "Update a document in a project's docs JSONB field using clean MCP format.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the project"},
                            {"name": "doc_id", "type": "string", "required": True, "description": "UUID of the document to update"},
                            {"name": "title", "type": "string", "required": False, "description": "Optional new title"},
                            {"name": "content", "type": "object", "required": False, "description": "Optional new content - MUST follow MCP format when provided"},
                            {"name": "status", "type": "string", "required": False, "description": "Optional new status (draft, review, approved, archived)"},
                            {"name": "tags", "type": "array", "required": False, "description": "Optional new tags for categorization"},
                            {"name": "author", "type": "string", "required": False, "description": "Optional new author name"},
                            {"name": "version", "type": "string", "required": False, "description": "Optional new version (e.g., '1.1', '2.0')"}
                        ]
                    },
                    {
                        "name": "delete_project_document",
                        "description": "Delete a document from a project's docs JSONB field.",
                        "module": "tasks_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the project"},
                            {"name": "doc_id", "type": "string", "required": True, "description": "UUID of the document to delete"}
                        ]
                    },
                    
                    # Versioning Module Tools
                    {
                        "name": "create_document_version",
                        "description": "Create a version snapshot for a project JSONB field.",
                        "module": "versioning_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the project"},
                            {"name": "field_name", "type": "string", "required": True, "description": "Name of the JSONB field ('docs', 'features', 'data', 'prd')"},
                            {"name": "content", "type": "object", "required": True, "description": "The current content to snapshot"},
                            {"name": "change_summary", "type": "string", "required": False, "description": "Human-readable description of changes"},
                            {"name": "change_type", "type": "string", "required": False, "description": "Type of change ('create', 'update', 'delete', 'restore')"},
                            {"name": "document_id", "type": "string", "required": False, "description": "For docs array, the specific document ID"},
                            {"name": "created_by", "type": "string", "required": False, "description": "Who created this version"}
                        ]
                    },
                    {
                        "name": "create_task_version",
                        "description": "Create a version snapshot for a task JSONB field.",
                        "module": "versioning_module",
                        "parameters": [
                            {"name": "task_id", "type": "string", "required": True, "description": "UUID of the task"},
                            {"name": "field_name", "type": "string", "required": True, "description": "Name of the JSONB field ('sources', 'code_examples')"},
                            {"name": "content", "type": "object", "required": True, "description": "The current content to snapshot"},
                            {"name": "change_summary", "type": "string", "required": False, "description": "Human-readable description of changes"},
                            {"name": "change_type", "type": "string", "required": False, "description": "Type of change ('create', 'update', 'delete', 'restore')"},
                            {"name": "created_by", "type": "string", "required": False, "description": "Who created this version"}
                        ]
                    },
                    {
                        "name": "get_document_version_history",
                        "description": "Get version history for project JSONB fields.",
                        "module": "versioning_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the project"},
                            {"name": "field_name", "type": "string", "required": False, "description": "Optional specific field name to filter by"}
                        ]
                    },
                    {
                        "name": "get_task_version_history",
                        "description": "Get version history for task JSONB fields.",
                        "module": "versioning_module",
                        "parameters": [
                            {"name": "task_id", "type": "string", "required": True, "description": "UUID of the task"},
                            {"name": "field_name", "type": "string", "required": False, "description": "Optional specific field name to filter by"}
                        ]
                    },
                    {
                        "name": "restore_document_version",
                        "description": "Restore a project JSONB field to a specific version.",
                        "module": "versioning_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": True, "description": "UUID of the project"},
                            {"name": "field_name", "type": "string", "required": True, "description": "Name of the JSONB field to restore"},
                            {"name": "version_number", "type": "integer", "required": True, "description": "Version number to restore to"},
                            {"name": "restored_by", "type": "string", "required": False, "description": "Who is performing the restore"}
                        ]
                    },
                    {
                        "name": "restore_task_version",
                        "description": "Restore a task JSONB field to a specific version.",
                        "module": "versioning_module",
                        "parameters": [
                            {"name": "task_id", "type": "string", "required": True, "description": "UUID of the task"},
                            {"name": "field_name", "type": "string", "required": True, "description": "Name of the JSONB field to restore"},
                            {"name": "version_number", "type": "integer", "required": True, "description": "Version number to restore to"},
                            {"name": "restored_by", "type": "string", "required": False, "description": "Who is performing the restore"}
                        ]
                    },
                    {
                        "name": "get_version_content",
                        "description": "Get the content of a specific version for preview or comparison.",
                        "module": "versioning_module",
                        "parameters": [
                            {"name": "project_id", "type": "string", "required": False, "description": "UUID of the project (for document versions)"},
                            {"name": "task_id", "type": "string", "required": False, "description": "UUID of the task (for task versions)"},
                            {"name": "field_name", "type": "string", "required": True, "description": "Name of the JSONB field"},
                            {"name": "version_number", "type": "integer", "required": True, "description": "Version number to retrieve"}
                        ]
                    }
                ]
                
                api_logger.info("MCP tools retrieved", tool_count=len(tools_from_server))
                span.set_attribute("tool_count", len(tools_from_server))
                
                return {
                    'tools': tools_from_server,
                    'count': len(tools_from_server),
                    'server_running': True,
                    'source': 'mcp_server_introspection',
                    'message': f'Retrieved {len(tools_from_server)} tools from running MCP server'
                }
        
        except Exception as e:
            api_logger.error("Failed to get MCP tools", error=str(e))
            span.set_attribute("error", str(e))
            return {
                'tools': [],
                'count': 0,
                'server_running': False,
                'source': 'error',
                'message': f'Error retrieving tools: {str(e)}'
            }

@router.get("/health")
async def mcp_health():
    """Health check for MCP API."""
    with api_logger.span("api_mcp_health") as span:
        span.set_attribute("endpoint", "/api/mcp/health")
        span.set_attribute("method", "GET")
        
        api_logger.info("MCP health check requested")
        result = {"status": "healthy", "service": "mcp"}
        span.set_attribute("status", "healthy")
        
        return result 
