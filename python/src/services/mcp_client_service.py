"""
Universal MCP Client Service

This service implements a proper MCP client that works exactly like Cursor/Windsurf.
It connects to MCP servers using real MCP protocol transports:
- stdio: Direct subprocess communication  
- docker: Docker exec with stdio transport
- sse: Server-sent events for remote servers
- npx: NPX subprocess for Node.js servers

The service is completely independent of FastAPI and uses the official MCP Python SDK.
"""

import asyncio
import json
import logging
import subprocess
import signal
import os
import httpx
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union, AsyncGenerator
from dataclasses import dataclass, asdict
from enum import Enum

from mcp import ClientSession
from mcp.types import (
    Tool, 
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    InitializeRequest,
    InitializedNotification,
    JSONRPCMessage,
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError
)
import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import logfire configuration using established pattern
from src.logfire_config import mcp_logger

class TransportType(str, Enum):
    SSE = "sse"  # Streamable HTTP (SSE) - the only supported transport for MCP clients

class ClientStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

@dataclass
class MCPClientConfig:
    name: str
    transport_type: TransportType
    connection_config: Dict[str, Any]
    auto_connect: bool = False
    health_check_interval: int = 30
    is_default: bool = False

@dataclass
class MCPClientInfo:
    id: str
    config: MCPClientConfig
    status: ClientStatus = ClientStatus.DISCONNECTED
    last_seen: Optional[datetime] = None
    last_error: Optional[str] = None
    tools: List[Tool] = None
    
    def __post_init__(self):
        if self.tools is None:
            self.tools = []

class MCPClientService:
    """
    Universal MCP Client Service that connects to any MCP server using proper MCP protocol.
    
    This service works exactly like Cursor/Windsurf MCP clients:
    - Uses official MCP Python SDK
    - Supports stdio, SSE, docker exec, NPX transports
    - Maintains persistent connections
    - Provides tool discovery and execution
    - Handles automatic reconnection on failures
    """
    
    def __init__(self):
        self.clients: Dict[str, MCPClientInfo] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self._sse_contexts: Dict[str, Any] = {}  # Store SSE context managers
        self._sse_tasks: Dict[str, asyncio.Task] = {}  # Store SSE connection tasks
        self._shutdown_event = asyncio.Event()
        self._running = False
        self._reconnect_tasks: Dict[str, asyncio.Task] = {}  # Track reconnection tasks
        self._reconnect_delays: Dict[str, float] = {}  # Track backoff delays
        
    async def start(self):
        """Start the MCP client service"""
        if self._running:
            return
            
        self._running = True
        mcp_logger.info("Starting Universal MCP Client Service")
        
        # Start background tasks
        asyncio.create_task(self._health_check_loop())
        
    async def stop(self):
        """Stop the MCP client service"""
        if not self._running:
            return
            
        mcp_logger.info("Stopping Universal MCP Client Service")
        self._running = False
        self._shutdown_event.set()
        
        # Cancel all reconnection tasks
        for task in self._reconnect_tasks.values():
            task.cancel()
        self._reconnect_tasks.clear()
        
        # Disconnect all clients
        for client_id in list(self.clients.keys()):
            await self.disconnect_client(client_id)
            
    # ========================================
    # CLIENT MANAGEMENT
    # ========================================
    
    async def add_client(self, client_id: str, config: MCPClientConfig) -> MCPClientInfo:
        """Add a new MCP client configuration"""
        client_info = MCPClientInfo(
            id=client_id,
            config=config
        )
        
        self.clients[client_id] = client_info
        logger.info(f"Added MCP client: {config.name} ({config.transport_type})")
        
        # Auto-connect if requested
        if config.auto_connect:
            try:
                await self.connect_client(client_id)
            except Exception as e:
                logger.error(f"Auto-connect failed for {config.name}: {e}")
                client_info.last_error = str(e)
                
        return client_info
        
    async def remove_client(self, client_id: str) -> bool:
        """Remove an MCP client"""
        if client_id not in self.clients:
            return False
            
        # Disconnect first
        await self.disconnect_client(client_id)
        
        # Remove from tracking
        del self.clients[client_id]
        logger.info(f"Removed MCP client: {client_id}")
        return True
        
    def get_client(self, client_id: str) -> Optional[MCPClientInfo]:
        """Get client info by ID"""
        return self.clients.get(client_id)
        
    def list_clients(self) -> List[MCPClientInfo]:
        """List all clients"""
        return list(self.clients.values())
        
    # ========================================
    # CONNECTION MANAGEMENT  
    # ========================================
    
    async def connect_client(self, client_id: str) -> bool:
        """Connect to an MCP client"""
        with mcp_logger.span("mcp_client.connect", client_id=client_id):
            client_info = self.clients.get(client_id)
            if not client_info:
                mcp_logger.error("Client not found", client_id=client_id)
                raise ValueError(f"Client not found: {client_id}")
                
            if client_info.status == ClientStatus.CONNECTED:
                mcp_logger.info("Client already connected", client_id=client_id, client_name=client_info.config.name)
                return True
                
            config = client_info.config
            client_info.status = ClientStatus.CONNECTING
            client_info.last_error = None
            
            mcp_logger.info("Starting client connection", 
                           client_id=client_id,
                           client_name=config.name, 
                           transport_type=config.transport_type,
                           connection_config=config.connection_config)
            
            try:
                logger.info(f"Connecting to {config.name} via {config.transport_type}")
                
                # For SSE, we implement the connection directly here
                if config.transport_type == TransportType.SSE:
                    url = config.connection_config.get('url')
                    if not url:
                        raise ValueError("SSE transport requires 'url' in connection_config")
                    
                    # Create the SSE session using our simplified implementation
                    session = await self._create_sse_session_direct(config)
                    mcp_logger.info("SSE session created successfully", client_id=client_id)
                    
                    # Initialize the MCP session
                    mcp_logger.debug("Sending initialize request to MCP server")
                    init_result = await session.initialize()
                    mcp_logger.info("Session initialized successfully", 
                                   client_id=client_id,
                                   server_name=getattr(init_result.serverInfo, 'name', 'unknown'),
                                   server_version=getattr(init_result.serverInfo, 'version', 'unknown'),
                                   protocol_version=init_result.protocolVersion,
                                   capabilities=init_result.capabilities)
                    
                    # Store session
                    self.sessions[client_id] = session
                    client_info.status = ClientStatus.CONNECTED
                    client_info.last_seen = datetime.now(timezone.utc)
                    
                    # Discover tools
                    await self._discover_tools(client_id)
                    
                    logger.info(f"Successfully connected to {config.name}")
                    mcp_logger.info("Client connection completed successfully", 
                                   client_id=client_id,
                                   client_name=config.name,
                                   tools_count=len(client_info.tools))
                    return True
                else:
                    raise ValueError(f"Unsupported transport type: {config.transport_type}. Only SSE is supported.")
                
            except Exception as e:
                mcp_logger.error("Client connection failed", 
                                client_id=client_id,
                                client_name=config.name,
                                error=str(e),
                                transport_type=config.transport_type)
                client_info.status = ClientStatus.ERROR
                client_info.last_error = str(e)
                logger.error(f"Failed to connect to {config.name}: {e}")
                
                # Cleanup any partial connection
                await self._cleanup_client_connection(client_id)
                raise
            
    async def disconnect_client(self, client_id: str) -> bool:
        """Disconnect from an MCP client"""
        client_info = self.clients.get(client_id)
        if not client_info:
            return False
            
        logger.info(f"Disconnecting from {client_info.config.name}")
        
        # Cancel any pending reconnection
        if client_id in self._reconnect_tasks:
            self._reconnect_tasks[client_id].cancel()
            del self._reconnect_tasks[client_id]
        
        await self._cleanup_client_connection(client_id)
        
        client_info.status = ClientStatus.DISCONNECTED
        client_info.tools = []
        
        return True
        
    async def _reconnect_client(self, client_id: str):
        """Handle automatic reconnection with exponential backoff"""
        client_info = self.clients.get(client_id)
        if not client_info or not client_info.config.auto_connect:
            return
            
        # Check if already reconnecting
        if client_id in self._reconnect_tasks and not self._reconnect_tasks[client_id].done():
            return
            
        async def reconnect_with_backoff():
            max_delay = 60  # Maximum delay of 1 minute
            base_delay = 1  # Start with 1 second
            
            # Get current delay or start with base
            current_delay = self._reconnect_delays.get(client_id, base_delay)
            
            while self._running and client_info.config.auto_connect:
                try:
                    logger.info(f"Attempting to reconnect {client_info.config.name} after {current_delay}s delay")
                    
                    # Wait with exponential backoff
                    await asyncio.sleep(current_delay)
                    
                    # Disconnect first to clean up
                    await self._cleanup_client_connection(client_id)
                    
                    # Try to reconnect
                    await self.connect_client(client_id)
                    
                    # Success - reset delay
                    self._reconnect_delays[client_id] = base_delay
                    logger.info(f"Successfully reconnected to {client_info.config.name}")
                    break
                    
                except Exception as e:
                    logger.error(f"Reconnection failed for {client_info.config.name}: {e}")
                    
                    # Increase delay with exponential backoff
                    current_delay = min(current_delay * 2, max_delay)
                    self._reconnect_delays[client_id] = current_delay
                    
                    # Check if we should continue
                    if not self._running or not client_info.config.auto_connect:
                        break
                        
            # Clean up
            if client_id in self._reconnect_tasks:
                del self._reconnect_tasks[client_id]
                
        # Start reconnection task
        self._reconnect_tasks[client_id] = asyncio.create_task(reconnect_with_backoff())
        
    async def _cleanup_client_connection(self, client_id: str):
        """Clean up all resources for a client connection"""
        # Cancel SSE task if exists
        if client_id in self._sse_tasks:
            try:
                task = self._sse_tasks[client_id]
                if not task.done():
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, timeout=5)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
            except Exception as e:
                logger.warning(f"Error cancelling SSE task for {client_id}: {e}")
            finally:
                del self._sse_tasks[client_id]
                
        # Close session
        if client_id in self.sessions:
            try:
                session = self.sessions[client_id]
                # Clean up SSE context if it exists
                if hasattr(session, '_transport_client_id'):
                    transport_id = session._transport_client_id
                    if transport_id in self._sse_contexts:
                        context = self._sse_contexts[transport_id]
                        if 'http_client' in context:
                            await context['http_client'].aclose()
                        del self._sse_contexts[transport_id]
            except Exception as e:
                logger.warning(f"Error closing session for {client_id}: {e}")
            finally:
                del self.sessions[client_id]
                
        # Terminate process if exists
        if client_id in self.processes:
            try:
                process = self.processes[client_id]
                if process.poll() is None:  # Still running
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
            except Exception as e:
                logger.warning(f"Error terminating process for {client_id}: {e}")
            finally:
                del self.processes[client_id]
                
    # ========================================
    # SSE TRANSPORT IMPLEMENTATION
    # ========================================
    
    async def _create_sse_session_direct(self, config: MCPClientConfig) -> ClientSession:
        """Create SSE transport session with proper MCP protocol implementation"""
        url = config.connection_config.get('url')
        if not url:
            raise ValueError("SSE transport requires 'url' in connection_config")
            
        mcp_logger.info(f"Creating SSE session for endpoint: {url}")
        
        # Store the HTTP client and session info
        client_id = str(uuid.uuid4())
        session_info = {
            'url': url,
            'session_id': None,
            'http_client': httpx.AsyncClient(timeout=httpx.Timeout(30.0)),
            'connected': False
        }
        
        # Create memory streams for the session
        read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
        write_stream, write_stream_reader = anyio.create_memory_object_stream(0)
        
        # Store session info
        self._sse_contexts[client_id] = {
            'session_info': session_info,
            'read_stream_writer': read_stream_writer,
            'write_stream_reader': write_stream_reader,
            'http_client': session_info['http_client']
        }
        
        # Start the SSE message handler task
        task = asyncio.create_task(self._handle_sse_messages(client_id, url))
        self._sse_tasks[client_id] = task
        
        # Create and return the session
        session = ClientSession(read_stream, write_stream)
        
        # Store client_id in session for cleanup
        session._transport_client_id = client_id
        
        return session
    
    async def _handle_sse_messages(self, client_id: str, url: str):
        """Handle SSE message flow for MCP protocol"""
        context = self._sse_contexts.get(client_id)
        if not context:
            return
            
        session_info = context['session_info']
        read_stream_writer = context['read_stream_writer']
        write_stream_reader = context['write_stream_reader']
        http_client = context['http_client']
        
        try:
            # Process outgoing messages
            async with write_stream_reader:
                async for message in write_stream_reader:
                    try:
                        # Convert message to dict for JSON serialization
                        if hasattr(message, 'model_dump'):
                            message_dict = message.model_dump(by_alias=True, exclude_none=True)
                        else:
                            message_dict = message
                        
                        # Handle initialize request specially
                        if message_dict.get('method') == 'initialize':
                            # POST initialize request
                            response = await http_client.post(
                                url,
                                json=message_dict,
                                headers={'Content-Type': 'application/json'}
                            )
                            response.raise_for_status()
                            
                            # Parse response
                            response_data = response.json()
                            
                            # Extract session ID from headers if present
                            session_id = response.headers.get('Mcp-Session-Id')
                            if session_id:
                                session_info['session_id'] = session_id
                                mcp_logger.info(f"Got session ID: {session_id}")
                            
                            # Send response back through the stream
                            response_msg = JSONRPCResponse.model_validate(response_data)
                            await read_stream_writer.send(response_msg)
                            
                        elif message_dict.get('method') == 'initialized':
                            # Send initialized notification
                            headers = {'Content-Type': 'application/json'}
                            if session_info['session_id']:
                                headers['Mcp-Session-Id'] = session_info['session_id']
                            
                            response = await http_client.post(
                                url,
                                json=message_dict,
                                headers=headers
                            )
                            # Notification responses are typically 202 Accepted
                            if response.status_code not in (200, 202):
                                mcp_logger.warning(f"Initialized notification got status {response.status_code}")
                            
                            session_info['connected'] = True
                            
                        else:
                            # Regular request
                            headers = {'Content-Type': 'application/json'}
                            if session_info['session_id']:
                                headers['Mcp-Session-Id'] = session_info['session_id']
                            
                            response = await http_client.post(
                                url,
                                json=message_dict,
                                headers=headers
                            )
                            
                            # Handle 404 - session expired, need to reconnect
                            if response.status_code == 404:
                                mcp_logger.warning(f"Session expired (404), triggering reconnection for {client_id}")
                                # Mark session as invalid
                                session_info['session_id'] = None
                                session_info['connected'] = False
                                # Send error response to trigger reconnection
                                if 'id' in message_dict:
                                    error_response = JSONRPCResponse(
                                        jsonrpc="2.0",
                                        id=message_dict['id'],
                                        error=JSONRPCError(
                                            code=-32000,
                                            message="Session expired - reconnection required"
                                        )
                                    )
                                    await read_stream_writer.send(error_response)
                                # Trigger reconnection
                                asyncio.create_task(self._reconnect_client(client_id))
                                return
                            
                            response.raise_for_status()
                            
                            # Parse and send response
                            response_data = response.json()
                            response_msg = JSONRPCResponse.model_validate(response_data)
                            await read_stream_writer.send(response_msg)
                            
                    except Exception as e:
                        mcp_logger.error(f"Error processing message: {e}", exc_info=True)
                        # Send error response
                        if 'id' in message_dict:
                            error_response = JSONRPCResponse(
                                jsonrpc="2.0",
                                id=message_dict['id'],
                                error=JSONRPCError(
                                    code=-32603,
                                    message=str(e)
                                )
                            )
                            await read_stream_writer.send(error_response)
                            
        except Exception as e:
            mcp_logger.error(f"SSE message handler error: {e}", exc_info=True)
        finally:
            # Cleanup
            await read_stream_writer.aclose()
            await http_client.aclose()
        
    # ========================================
    # TOOL DISCOVERY & EXECUTION
    # ========================================
    
    async def _discover_tools(self, client_id: str):
        """Discover tools from a connected client"""
        with mcp_logger.span("mcp_client.discover_tools", client_id=client_id):
            session = self.sessions.get(client_id)
            client_info = self.clients.get(client_id)
            
            if not session or not client_info:
                mcp_logger.warning("No session or client info found for tool discovery", 
                              client_id=client_id,
                              has_session=session is not None,
                              has_client_info=client_info is not None)
                return
                
            try:
                mcp_logger.info("Requesting tools from MCP server", 
                           client_id=client_id,
                           client_name=client_info.config.name)
                
                # List available tools
                mcp_logger.debug("Calling session.list_tools()")
                result = await session.list_tools()
                
                # Log the raw result for debugging
                mcp_logger.debug("list_tools result", 
                            result_type=type(result).__name__,
                            has_tools=hasattr(result, 'tools'),
                            tools_count=len(result.tools) if hasattr(result, 'tools') else 0)
                
                client_info.tools = result.tools if result.tools else []
                client_info.last_seen = datetime.now(timezone.utc)
                
                mcp_logger.info("Tools discovered successfully", 
                           client_id=client_id,
                           client_name=client_info.config.name,
                           tools_count=len(client_info.tools),
                           tool_names=[tool.name for tool in client_info.tools])
                
                logger.info(f"Discovered {len(client_info.tools)} tools from {client_info.config.name}")
                
                # Log individual tools for debugging
                for tool in client_info.tools:
                    mcp_logger.debug("Tool details",
                                   name=tool.name,
                                   description=getattr(tool, 'description', 'No description'),
                                   schema=getattr(tool, 'inputSchema', {}))
                
            except Exception as e:
                mcp_logger.error("Failed to discover tools", 
                            client_id=client_id,
                            client_name=client_info.config.name,
                            error=str(e),
                            error_type=type(e).__name__,
                            exc_info=True)
                logger.error(f"Failed to discover tools from {client_info.config.name}: {e}")
                client_info.last_error = str(e)
            
    async def get_client_tools(self, client_id: str) -> List[Tool]:
        """Get tools from a specific client"""
        client_info = self.clients.get(client_id)
        if not client_info:
            raise ValueError(f"Client not found: {client_id}")
            
        if client_info.status != ClientStatus.CONNECTED:
            return []
            
        # Refresh tools if needed
        if not client_info.tools:
            await self._discover_tools(client_id)
            
        return client_info.tools or []
        
    async def call_tool(self, client_id: str, tool_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Call a tool on a specific client"""
        session = self.sessions.get(client_id)
        client_info = self.clients.get(client_id)
        
        if not session or not client_info:
            raise ValueError(f"Client not found or not connected: {client_id}")
            
        if client_info.status != ClientStatus.CONNECTED:
            raise RuntimeError(f"Client not connected: {client_id}")
            
        try:
            mcp_logger.info(f"Calling tool {tool_name}", 
                          client_id=client_id,
                          tool_name=tool_name,
                          arguments=arguments)
            
            # Execute the tool call
            result = await session.call_tool(tool_name, arguments)
            client_info.last_seen = datetime.now(timezone.utc)
            
            logger.info(f"Successfully called tool {tool_name} on {client_info.config.name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name} on {client_info.config.name}: {e}")
            client_info.last_error = str(e)
            raise
            
    async def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get tools from all connected clients"""
        all_tools = {}
        
        for client_id, client_info in self.clients.items():
            if client_info.status == ClientStatus.CONNECTED:
                try:
                    tools = await self.get_client_tools(client_id)
                    all_tools[client_id] = {
                        'client_name': client_info.config.name,
                        'tools': [asdict(tool) for tool in tools],
                        'count': len(tools)
                    }
                except Exception as e:
                    logger.warning(f"Failed to get tools from {client_info.config.name}: {e}")
                    
        return all_tools
        
    async def is_client_connected(self, client_id: str) -> bool:
        """Check if a client is connected"""
        client_info = self.clients.get(client_id)
        if not client_info:
            return False
        return client_info.status == ClientStatus.CONNECTED
        
    # ========================================
    # HEALTH CHECKING
    # ========================================
    
    async def _health_check_loop(self):
        """Background task to monitor client health"""
        while self._running:
            try:
                await self._perform_health_checks()
            except Exception as e:
                logger.error(f"Health check error: {e}")
                
            # Wait for next check or shutdown
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=30)
                break  # Shutdown requested
            except asyncio.TimeoutError:
                continue  # Continue health checking
                
    async def _perform_health_checks(self):
        """Perform health checks on all connected clients"""
        for client_id, client_info in self.clients.items():
            if client_info.status == ClientStatus.CONNECTED:
                try:
                    # Simple ping by listing tools
                    await self._discover_tools(client_id)
                except Exception as e:
                    logger.warning(f"Health check failed for {client_info.config.name}: {e}")
                    client_info.status = ClientStatus.ERROR
                    client_info.last_error = str(e)
                    
                    # Attempt reconnection if auto_connect is enabled
                    if client_info.config.auto_connect:
                        await self._reconnect_client(client_id)

# Global service instance
_mcp_client_service: Optional[MCPClientService] = None

def get_mcp_client_service() -> MCPClientService:
    """Get the global MCP client service instance"""
    global _mcp_client_service
    if _mcp_client_service is None:
        _mcp_client_service = MCPClientService()
    return _mcp_client_service

async def start_mcp_client_service() -> MCPClientService:
    """Start the MCP client service"""
    service = get_mcp_client_service()
    await service.start()
    return service

async def stop_mcp_client_service():
    """Stop the MCP client service"""
    global _mcp_client_service
    if _mcp_client_service:
        await _mcp_client_service.stop()
        _mcp_client_service = None

# ========================================
# EXAMPLE CONFIGURATIONS
# ========================================

def get_archon_config() -> MCPClientConfig:
    """Get Archon MCP client configuration (SSE-only)"""
    # Use service discovery to get the correct MCP URL
    from ..config.service_discovery import ServiceDiscovery
    discovery = ServiceDiscovery()
    mcp_url = discovery.get_service_url("mcp")
    
    return MCPClientConfig(
        name="Archon (Default)",
        transport_type=TransportType.SSE,
        connection_config={
            "url": f"{mcp_url}/sse"
        },
        auto_connect=True,
        health_check_interval=30,
        is_default=True
    )

def get_example_sse_config() -> MCPClientConfig:
    """Get example SSE MCP client configuration"""
    return MCPClientConfig(
        name="Remote MCP Server",
        transport_type=TransportType.SSE,
        connection_config={
            "url": "http://example.com:8080/sse"
        },
        auto_connect=False,
        health_check_interval=60
    ) 