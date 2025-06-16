"""
MCP Client Management API endpoints for Archon

Handles:
- Multiple MCP client configurations (CRUD operations)
- Multi-client connection management
- Tool discovery from multiple clients
- Client health monitoring and status
- Transport-specific implementations (SSE, stdio, Docker, NPX)
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, List, Optional, Union
import asyncio
import json
import uuid
from datetime import datetime
import aiohttp
import subprocess
import tempfile
import os
from enum import Enum

from ..utils import get_supabase_client
from ..logfire_config import mcp_logger, api_logger

router = APIRouter(prefix="/api/mcp/clients", tags=["mcp-clients"])

class TransportType(str, Enum):
    SSE = "sse"  # Streamable HTTP (SSE) - the only supported transport for MCP clients

class ClientStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"

class MCPClientConfig(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    transport_type: TransportType
    connection_config: Dict[str, Any]
    auto_connect: bool = True
    health_check_interval: int = Field(default=30, ge=5, le=300)
    is_default: bool = False

    @validator('connection_config')
    def validate_connection_config(cls, v, values):
        transport = values.get('transport_type')
        if transport == TransportType.SSE:
            # For SSE transport, we need the URL endpoint
            required_fields = ['url']
            if not all(field in v for field in required_fields):
                raise ValueError(f"SSE transport requires: {required_fields}")
            # Validate URL format
            url = v.get('url', '')
            if not url.startswith(('http://', 'https://')):
                raise ValueError("SSE URL must start with http:// or https://")
        return v

class MCPClient(BaseModel):
    id: str
    name: str
    transport_type: TransportType
    connection_config: Dict[str, Any]
    status: ClientStatus
    auto_connect: bool
    health_check_interval: int
    last_seen: Optional[datetime]
    last_error: Optional[str]
    is_default: bool
    created_at: datetime
    updated_at: datetime


class ToolCallRequest(BaseModel):
    client_id: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)

class MCPClientManager:
    """Manages multiple MCP client connections and their lifecycle."""
    
    def __init__(self):
        self.active_clients: Dict[str, Any] = {}
        self.client_processes: Dict[str, subprocess.Popen] = {}
        self.health_check_tasks: Dict[str, asyncio.Task] = {}
    
    async def get_all_clients(self) -> List[MCPClient]:
        """Get all configured MCP clients from database."""
        try:
            supabase = get_supabase_client()
            response = supabase.table("mcp_clients").select("*").order("created_at").execute()
            
            clients = []
            for data in response.data:
                client = MCPClient(
                    id=data['id'],
                    name=data['name'],
                    transport_type=data['transport_type'],
                    connection_config=data['connection_config'],
                    status=data['status'],
                    auto_connect=data['auto_connect'],
                    health_check_interval=data['health_check_interval'],
                    last_seen=data['last_seen'],
                    last_error=data['last_error'],
                    is_default=data['is_default'],
                    created_at=data['created_at'],
                    updated_at=data['updated_at']
                )
                clients.append(client)
            
            return clients
        except Exception as e:
            mcp_logger.error("Failed to get MCP clients from database", error=str(e))
            raise

    async def create_client(self, config: MCPClientConfig) -> MCPClient:
        """Create a new MCP client configuration."""
        try:
            supabase = get_supabase_client()
            
            # Check for name uniqueness
            existing = supabase.table("mcp_clients").select("id").eq("name", config.name).execute()
            if existing.data:
                raise ValueError(f"Client with name '{config.name}' already exists")
            
            # If this is set as default, unset other defaults
            if config.is_default:
                supabase.table("mcp_clients").update({"is_default": False}).eq("is_default", True).execute()
            
            client_data = {
                "name": config.name,
                "transport_type": config.transport_type.value,
                "connection_config": config.connection_config,
                "status": ClientStatus.DISCONNECTED.value,
                "auto_connect": config.auto_connect,
                "health_check_interval": config.health_check_interval,
                "is_default": config.is_default
            }
            
            response = supabase.table("mcp_clients").insert(client_data).execute()
            created_client = response.data[0]
            
            mcp_logger.info("Created new MCP client", client_id=created_client['id'], name=config.name)
            
            return MCPClient(**created_client)
        except Exception as e:
            mcp_logger.error("Failed to create MCP client", error=str(e))
            raise

    async def update_client(self, client_id: str, updates: Dict[str, Any]) -> MCPClient:
        """Update an existing MCP client configuration."""
        try:
            supabase = get_supabase_client()
            
            # If setting as default, unset other defaults
            if updates.get('is_default'):
                supabase.table("mcp_clients").update({"is_default": False}).eq("is_default", True).execute()
            
            response = supabase.table("mcp_clients").update(updates).eq("id", client_id).execute()
            
            if not response.data:
                raise HTTPException(status_code=404, detail="Client not found")
            
            updated_client = response.data[0]
            mcp_logger.info("Updated MCP client", client_id=client_id)
            
            return MCPClient(**updated_client)
        except Exception as e:
            mcp_logger.error("Failed to update MCP client", client_id=client_id, error=str(e))
            raise

    async def delete_client(self, client_id: str) -> bool:
        """Delete an MCP client configuration."""
        try:
            # First disconnect if connected
            await self.disconnect_client(client_id)
            
            supabase = get_supabase_client()
            response = supabase.table("mcp_clients").delete().eq("id", client_id).execute()
            
            if not response.data:
                raise HTTPException(status_code=404, detail="Client not found")
            
            mcp_logger.info("Deleted MCP client", client_id=client_id)
            return True
        except Exception as e:
            mcp_logger.error("Failed to delete MCP client", client_id=client_id, error=str(e))
            raise

    async def connect_client(self, client_id: str) -> Dict[str, Any]:
        """Connect to a specific MCP client."""
        try:
            # Get client config from database
            supabase = get_supabase_client()
            response = supabase.table("mcp_clients").select("*").eq("id", client_id).execute()
            
            if not response.data:
                raise HTTPException(status_code=404, detail="Client not found")
            
            client_data = response.data[0]
            transport_type = client_data['transport_type']
            config = client_data['connection_config']
            
            # Update status to connecting
            supabase.table("mcp_clients").update({
                "status": ClientStatus.CONNECTING.value,
                "last_error": None
            }).eq("id", client_id).execute()
            
            try:
                # Use the real MCP client service for connections
                from ..services.mcp_client_service import get_mcp_client_service, MCPClientConfig
                from ..services.mcp_client_service import TransportType as ServiceTransportType
                service = get_mcp_client_service()
                
                # Convert API transport type to service transport type
                service_transport_map = {
                    "sse": ServiceTransportType.SSE
                }
                
                # Convert API config to service config
                service_config = MCPClientConfig(
                    name=client_data['name'],
                    transport_type=service_transport_map[transport_type],
                    connection_config=config,
                    auto_connect=client_data.get('auto_connect', True),
                    health_check_interval=client_data.get('health_check_interval', 30),
                    is_default=client_data.get('is_default', False)
                )
                
                # Add client to service and connect
                client_info = await service.add_client(client_id, service_config)
                success = await service.connect_client(client_id)
                
                if success:
                    self.active_clients[client_id] = {"service_client": True}
                else:
                    raise ValueError("Service failed to connect client")
                
                # Update status to connected
                supabase.table("mcp_clients").update({
                    "status": ClientStatus.CONNECTED.value,
                    "last_seen": datetime.utcnow().isoformat()
                }).eq("id", client_id).execute()
                
                # Start health monitoring
                self.health_check_tasks[client_id] = asyncio.create_task(
                    self._health_monitor(client_id, client_data['health_check_interval'])
                )
                
                # Discover tools
                await self._discover_tools(client_id)
                
                mcp_logger.info("Connected to MCP client", client_id=client_id)
                return {"success": True, "message": "Connected successfully"}
                
            except Exception as e:
                # Update status to error
                supabase.table("mcp_clients").update({
                    "status": ClientStatus.ERROR.value,
                    "last_error": str(e)
                }).eq("id", client_id).execute()
                raise
                
        except Exception as e:
            mcp_logger.error("Failed to connect to MCP client", client_id=client_id, error=str(e))
            raise

    async def disconnect_client(self, client_id: str) -> Dict[str, Any]:
        """Disconnect from a specific MCP client."""
        try:
            # Stop health monitoring
            if client_id in self.health_check_tasks:
                self.health_check_tasks[client_id].cancel()
                del self.health_check_tasks[client_id]
            
            # Close client connection
            if client_id in self.active_clients:
                client = self.active_clients[client_id]
                if hasattr(client, 'close'):
                    await client.close()
                del self.active_clients[client_id]
            
            # Stop process if it exists
            if client_id in self.client_processes:
                process = self.client_processes[client_id]
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                del self.client_processes[client_id]
            
            # Update status in database
            supabase = get_supabase_client()
            supabase.table("mcp_clients").update({
                "status": ClientStatus.DISCONNECTED.value
            }).eq("id", client_id).execute()
            
            mcp_logger.info("Disconnected from MCP client", client_id=client_id)
            return {"success": True, "message": "Disconnected successfully"}
            
        except Exception as e:
            mcp_logger.error("Failed to disconnect from MCP client", client_id=client_id, error=str(e))
            raise

    async def _connect_sse_client(self, client_id: str, config: Dict[str, Any]):
        """Connect to an SSE-based MCP client."""
        url = config.get('url')
        if not url:
            raise ValueError("SSE transport requires 'url' in connection config")
        
        # Test connection
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    raise ValueError(f"SSE endpoint returned status {response.status}")
        
        return {"type": "sse", "url": url, "session": None}

    async def _health_monitor(self, client_id: str, interval: int):
        """Background task to monitor client health."""
        while True:
            try:
                await asyncio.sleep(interval)
                
                # Check if client is still active
                if client_id not in self.active_clients:
                    break
                
                # Perform health check based on transport type
                is_healthy = await self._perform_health_check(client_id)
                
                # Update database
                supabase = get_supabase_client()
                if is_healthy:
                    supabase.table("mcp_clients").update({
                        "last_seen": datetime.utcnow().isoformat(),
                        "status": ClientStatus.CONNECTED.value
                    }).eq("id", client_id).execute()
                else:
                    supabase.table("mcp_clients").update({
                        "status": ClientStatus.ERROR.value,
                        "last_error": "Health check failed"
                    }).eq("id", client_id).execute()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                mcp_logger.error("Health check error", client_id=client_id, error=str(e))
                break

    async def _perform_health_check(self, client_id: str) -> bool:
        """Perform a health check on a specific client."""
        try:
            # Use the real MCP client service for health checks
            from ..services.mcp_client_service import get_mcp_client_service
            service = get_mcp_client_service()
            
            # Check if client exists in service
            if client_id in service.clients:
                return await service.is_client_connected(client_id)
            
            return False
            
        except Exception:
            return False

    async def _discover_tools(self, client_id: str):
        """Discover available tools from a client."""
        try:
            # Get the real MCP client service
            from ..services.mcp_client_service import get_mcp_client_service
            service = get_mcp_client_service()
            
            # Get tools using the real MCP implementation
            tools = await service.get_client_tools(client_id)
            
            if tools:
                mcp_logger.info("Tools discovered", 
                               client_id=client_id, 
                               tools_count=len(tools),
                               tool_names=[tool.name for tool in tools])
            else:
                mcp_logger.warning("No tools discovered", client_id=client_id)
            
        except Exception as e:
            mcp_logger.error("Tool discovery failed", client_id=client_id, error=str(e))

# Global client manager instance
client_manager = MCPClientManager()

# API Endpoints

@router.get("/", response_model=List[MCPClient])
async def list_clients():
    """List all configured MCP clients."""
    with api_logger.span("api_list_mcp_clients") as span:
        try:
            clients = await client_manager.get_all_clients()
            span.set_attribute("client_count", len(clients))
            return clients
        except Exception as e:
            api_logger.error("Failed to list MCP clients", error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=MCPClient)
async def create_client(config: MCPClientConfig):
    """Create a new MCP client configuration."""
    with api_logger.span("api_create_mcp_client") as span:
        span.set_attribute("client_name", config.name)
        span.set_attribute("transport_type", config.transport_type.value)
        
        try:
            client = await client_manager.create_client(config)
            span.set_attribute("client_id", client.id)
            return client
        except ValueError as e:
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            api_logger.error("Failed to create MCP client", error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/{client_id}", response_model=MCPClient)
async def get_client(client_id: str):
    """Get a specific MCP client configuration."""
    with api_logger.span("api_get_mcp_client") as span:
        span.set_attribute("client_id", client_id)
        
        try:
            supabase = get_supabase_client()
            response = supabase.table("mcp_clients").select("*").eq("id", client_id).execute()
            
            if not response.data:
                raise HTTPException(status_code=404, detail="Client not found")
            
            return MCPClient(**response.data[0])
        except HTTPException:
            raise
        except Exception as e:
            api_logger.error("Failed to get MCP client", client_id=client_id, error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.put("/{client_id}", response_model=MCPClient)
async def update_client(client_id: str, updates: Dict[str, Any]):
    """Update an MCP client configuration."""
    with api_logger.span("api_update_mcp_client") as span:
        span.set_attribute("client_id", client_id)
        
        try:
            client = await client_manager.update_client(client_id, updates)
            return client
        except Exception as e:
            api_logger.error("Failed to update MCP client", client_id=client_id, error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{client_id}")
async def delete_client(client_id: str):
    """Delete an MCP client configuration."""
    with api_logger.span("api_delete_mcp_client") as span:
        span.set_attribute("client_id", client_id)
        
        try:
            await client_manager.delete_client(client_id)
            return {"success": True, "message": "Client deleted successfully"}
        except Exception as e:
            api_logger.error("Failed to delete MCP client", client_id=client_id, error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/{client_id}/connect")
async def connect_client(client_id: str, background_tasks: BackgroundTasks):
    """Connect to a specific MCP client."""
    with api_logger.span("api_connect_mcp_client") as span:
        span.set_attribute("client_id", client_id)
        
        try:
            result = await client_manager.connect_client(client_id)
            span.set_attribute("success", result.get("success", False))
            return result
        except Exception as e:
            api_logger.error("Failed to connect to MCP client", client_id=client_id, error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/{client_id}/disconnect")
async def disconnect_client(client_id: str):
    """Disconnect from a specific MCP client."""
    with api_logger.span("api_disconnect_mcp_client") as span:
        span.set_attribute("client_id", client_id)
        
        try:
            result = await client_manager.disconnect_client(client_id)
            span.set_attribute("success", result.get("success", False))
            return result
        except Exception as e:
            api_logger.error("Failed to disconnect from MCP client", client_id=client_id, error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/{client_id}/status")
async def get_client_status(client_id: str):
    """Get the connection status and health of a specific client."""
    with api_logger.span("api_get_mcp_client_status") as span:
        span.set_attribute("client_id", client_id)
        
        try:
            supabase = get_supabase_client()
            response = supabase.table("mcp_clients").select("status, last_seen, last_error").eq("id", client_id).execute()
            
            if not response.data:
                raise HTTPException(status_code=404, detail="Client not found")
            
            data = response.data[0]
            is_active = client_id in client_manager.active_clients
            
            return {
                "client_id": client_id,
                "status": data['status'],
                "last_seen": data['last_seen'],
                "last_error": data['last_error'],
                "is_active": is_active
            }
        except HTTPException:
            raise
        except Exception as e:
            api_logger.error("Failed to get MCP client status", client_id=client_id, error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/{client_id}/tools")
async def get_client_tools(client_id: str):
    """Get tools available from a specific client."""
    with api_logger.span("api_get_mcp_client_tools") as span:
        span.set_attribute("client_id", client_id)
        
        try:
            # Get tools directly from the MCP client service
            from ..services.mcp_client_service import get_mcp_client_service
            service = get_mcp_client_service()
            
            # Get the raw tools from the client
            tools = await service.get_client_tools(client_id)
            
            # Convert to our API format
            tool_list = []
            for tool in tools:
                tool_data = {
                    "id": f"{client_id}-{tool.name}",
                    "client_id": client_id,
                    "tool_name": tool.name,
                    "tool_description": tool.description if hasattr(tool, 'description') else None,
                    "tool_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                }
                tool_list.append(tool_data)
            
            span.set_attribute("tool_count", len(tool_list))
            return {"client_id": client_id, "tools": tool_list, "count": len(tool_list)}
        except Exception as e:
            api_logger.error("Failed to get MCP client tools", client_id=client_id, error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/tools/call")
async def call_tool(request: ToolCallRequest):
    """Call a tool on a specific MCP client."""
    with api_logger.span("api_call_mcp_tool") as span:
        span.set_attribute("client_id", request.client_id)
        span.set_attribute("tool_name", request.tool_name)
        
        try:
            # Use the real MCP client service for tool calls
            from ..services.mcp_client_service import get_mcp_client_service
            service = get_mcp_client_service()
            
            result = await service.call_tool(request.client_id, request.tool_name, request.arguments)
            
            return {
                "success": True,
                "result": result,
                "message": "Tool executed successfully"
            }
        except Exception as e:
            api_logger.error("Failed to call MCP tool", 
                           client_id=request.client_id, 
                           tool_name=request.tool_name, 
                           error=str(e))
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-config")
async def test_client_config(config: MCPClientConfig):
    """Test a client configuration before saving."""
    with api_logger.span("api_test_mcp_config") as span:
        span.set_attribute("transport_type", config.transport_type.value)
        
        try:
            # Test connection without saving
            temp_id = str(uuid.uuid4())
            
            if config.transport_type == TransportType.SSE:
                await client_manager._connect_sse_client(temp_id, config.connection_config)
            else:
                raise ValueError(f"Unsupported transport type: {config.transport_type}")
            
            span.set_attribute("test_success", True)
            return {"success": True, "message": "Configuration test successful"}
            
        except Exception as e:
            span.set_attribute("test_success", False)
            span.set_attribute("error", str(e))
            return {"success": False, "message": f"Configuration test failed: {str(e)}"} 