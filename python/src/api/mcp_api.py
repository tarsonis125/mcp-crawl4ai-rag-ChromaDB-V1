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
        if self.process and self.process.poll() is None:
            return {
                'success': False,
                'status': self.status,
                'message': 'MCP server is already running'
            }
        
        try:
            # Set up environment variables for the MCP server
            env = os.environ.copy()
            env.update({
                'TRANSPORT': 'sse',
                'HOST': 'localhost',
                'PORT': '8051'
            })
            
            # Start the MCP server process
            self.process = subprocess.Popen(
                ['python', 'src/mcp_server.py'],
                cwd='python',
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env
            )
            
            self.status = 'starting'
            self.start_time = time.time()
            self._add_log('INFO', 'MCP server starting...')
            
            # Start reading logs from the process
            self.log_reader_task = asyncio.create_task(self._read_process_logs())
            
            # Give it a moment to start
            await asyncio.sleep(2)
            
            # Check if process is still running
            if self.process.poll() is None:
                self.status = 'running'
                self._add_log('INFO', 'MCP server started successfully')
                return {
                    'success': True,
                    'status': self.status,
                    'message': 'MCP server started successfully',
                    'pid': self.process.pid
                }
            else:
                self.status = 'failed'
                self._add_log('ERROR', 'MCP server failed to start')
                return {
                    'success': False,
                    'status': self.status,
                    'message': 'MCP server failed to start'
                }
                
        except Exception as e:
            self.status = 'failed'
            self._add_log('ERROR', f'Failed to start MCP server: {str(e)}')
            return {
                'success': False,
                'status': self.status,
                'message': f'Failed to start MCP server: {str(e)}'
            }
    
    async def stop_server(self) -> Dict[str, Any]:
        """Stop the MCP server process."""
        if not self.process or self.process.poll() is not None:
            return {
                'success': False,
                'status': 'stopped',
                'message': 'MCP server is not running'
            }
        
        try:
            self.status = 'stopping'
            self._add_log('INFO', 'Stopping MCP server...')
            
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
            
            self.process = None
            self.status = 'stopped'
            self.start_time = None
            self._add_log('INFO', 'MCP server stopped')
            
            return {
                'success': True,
                'status': self.status,
                'message': 'MCP server stopped successfully'
            }
            
        except Exception as e:
            self._add_log('ERROR', f'Error stopping MCP server: {str(e)}')
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
    result = await mcp_manager.start_server()
    return ServerResponse(**result)

@router.post("/stop", response_model=ServerResponse)
async def stop_server():
    """Stop the MCP server."""
    result = await mcp_manager.stop_server()
    return ServerResponse(**result)

@router.get("/status")
async def get_status():
    """Get MCP server status."""
    return mcp_manager.get_status()

@router.get("/logs")
async def get_logs(limit: int = 100):
    """Get MCP server logs."""
    return mcp_manager.get_logs(limit)

@router.delete("/logs")
async def clear_logs():
    """Clear MCP server logs."""
    mcp_manager.clear_logs()
    return {"success": True, "message": "Logs cleared"}

@router.get("/config")
async def get_configuration():
    """Get MCP server configuration."""
    try:
        supabase_client = get_supabase_client()
        
        # Try to get config from database first
        response = supabase_client.table("credentials").select("key_value").eq("key_name", "mcp_config").execute()
        
        if response.data:
            config_data = json.loads(response.data[0]['key_value'])
            return ServerConfig(**config_data)
        else:
            # Return default config
            return ServerConfig()
            
    except Exception as e:
        # Return default config on error
        return ServerConfig()

@router.post("/config")
async def save_configuration(config: ServerConfig):
    """Save MCP server configuration."""
    try:
        supabase_client = get_supabase_client()
        
        config_json = config.model_dump_json()
        
        # Check if config exists
        existing = supabase_client.table("credentials").select("id").eq("key_name", "mcp_config").execute()
        
        if existing.data:
            # Update existing
            response = supabase_client.table("credentials").update({
                "key_value": config_json
            }).eq("key_name", "mcp_config").execute()
        else:
            # Insert new
            response = supabase_client.table("credentials").insert({
                "key_name": "mcp_config",
                "key_value": config_json
            }).execute()
        
        return {"success": True, "message": "Configuration saved"}
        
    except Exception as e:
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
    """Get list of available MCP tools."""
    try:
        # This would normally call the MCP server to get available tools
        # For now, return a placeholder response
        return {
            "tools": [
                {
                    "name": "search_knowledge",
                    "description": "Search the knowledge base",
                    "parameters": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Max results"}
                    }
                },
                {
                    "name": "create_task", 
                    "description": "Create a new task",
                    "parameters": {
                        "title": {"type": "string", "description": "Task title"},
                        "description": {"type": "string", "description": "Task description"}
                    }
                }
            ],
            "count": 2,
            "server_status": mcp_manager.get_status()["status"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/health")
async def mcp_health():
    """Health check for MCP API."""
    return {"status": "healthy", "service": "mcp"} 