"""
Pydantic models for MCP Client Management System.

These models define the data structures for managing multiple MCP clients,
their configurations, tools, and health monitoring.
"""

from typing import Optional, Dict, Any, List, Union, Literal
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum

# Transport Types
TransportType = Literal["sse", "stdio", "docker", "npx"]
ClientStatus = Literal["connected", "disconnected", "connecting", "error"]
HealthStatus = Literal["success", "failure", "timeout"]

# Configuration Models for each transport type
class SSEConfig(BaseModel):
    """Configuration for SSE transport."""
    host: str = "localhost"
    port: int = 8051
    endpoint: str = "/sse"
    timeout: int = 30
    auth_headers: Optional[Dict[str, str]] = None

class StdioConfig(BaseModel):
    """Configuration for stdio transport."""
    command: str
    args: List[str] = []
    env_vars: Optional[Dict[str, str]] = None
    working_dir: Optional[str] = None
    timeout: int = 30

class DockerConfig(BaseModel):
    """Configuration for Docker transport."""
    image: str
    command: List[str]
    ports: Optional[Dict[str, str]] = None
    env_vars: Optional[Dict[str, str]] = None
    volumes: Optional[Dict[str, str]] = None
    auto_remove: bool = True
    network: Optional[str] = None

class NPXConfig(BaseModel):
    """Configuration for NPX transport."""
    package: str
    version: str = "latest"
    args: List[str] = []
    env_vars: Optional[Dict[str, str]] = None
    registry: Optional[str] = None
    timeout: int = 60

# Union type for connection configurations
ConnectionConfig = Union[SSEConfig, StdioConfig, DockerConfig, NPXConfig]

class MCPTool(BaseModel):
    """Represents an MCP tool discovered from a client."""
    name: str
    description: str
    inputSchema: Dict[str, Any]
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    client_status: Optional[ClientStatus] = None
    discovered_at: Optional[datetime] = None

class MCPClientBase(BaseModel):
    """Base model for MCP client creation."""
    name: str = Field(..., min_length=1, max_length=255)
    transport_type: TransportType
    connection_config: Dict[str, Any]
    auto_connect: bool = True
    health_check_interval: int = Field(default=30, ge=10, le=3600)

    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()

    @validator('connection_config')
    def validate_connection_config(cls, v, values):
        """Validate connection config based on transport type."""
        transport_type = values.get('transport_type')
        if not transport_type:
            return v
        
        # Validate config structure based on transport type
        try:
            if transport_type == 'sse':
                SSEConfig(**v)
            elif transport_type == 'stdio':
                StdioConfig(**v)
            elif transport_type == 'docker':
                DockerConfig(**v)
            elif transport_type == 'npx':
                NPXConfig(**v)
        except Exception as e:
            raise ValueError(f'Invalid {transport_type} configuration: {str(e)}')
        
        return v

class MCPClient(MCPClientBase):
    """Complete MCP client model with database fields."""
    id: str
    status: ClientStatus = "disconnected"
    last_seen: Optional[datetime] = None
    last_error: Optional[str] = None
    is_default: bool = False
    tools_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class MCPClientCreate(MCPClientBase):
    """Model for creating new MCP clients."""
    pass

class MCPClientUpdate(BaseModel):
    """Model for updating MCP clients."""
    name: Optional[str] = None
    connection_config: Optional[Dict[str, Any]] = None
    auto_connect: Optional[bool] = None
    health_check_interval: Optional[int] = Field(None, ge=10, le=3600)

class MCPClientStatus(BaseModel):
    """Detailed status information for an MCP client."""
    id: str
    name: str
    status: ClientStatus
    transport_type: TransportType
    last_seen: Optional[datetime] = None
    connection_established: Optional[datetime] = None
    uptime_seconds: Optional[int] = None
    tools_count: int = 0
    health_checks: Optional[Dict[str, Any]] = None
    performance: Optional[Dict[str, Any]] = None
    process_info: Optional[Dict[str, Any]] = None

class MCPClientSession(BaseModel):
    """Model for tracking client sessions."""
    id: str
    client_id: str
    session_start: datetime
    session_end: Optional[datetime] = None
    connection_time_ms: Optional[int] = None
    total_tool_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    avg_response_time_ms: Optional[float] = None
    process_id: Optional[int] = None
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    is_active: bool = True

class MCPHealthCheck(BaseModel):
    """Model for health check results."""
    id: str
    client_id: str
    check_time: datetime
    status: HealthStatus
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class MCPToolCall(BaseModel):
    """Model for tool call requests."""
    tool_name: str
    arguments: Dict[str, Any] = {}
    client_id: Optional[str] = None  # If not specified, auto-route based on tool name

class MCPToolCallResponse(BaseModel):
    """Response from tool call."""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    client_id: str
    client_name: str
    execution_time_ms: int
    timestamp: datetime

class MCPClientListResponse(BaseModel):
    """Response for listing MCP clients."""
    success: bool
    clients: List[MCPClient]
    total_count: int
    connected_count: int
    total_tools: int

class MCPClientToolsResponse(BaseModel):
    """Response for client tools."""
    success: bool
    client: Dict[str, Any]
    tools: List[MCPTool]
    tools_count: int
    last_discovery: Optional[datetime] = None

class MCPAggregateToolsResponse(BaseModel):
    """Response for aggregated tools from all clients."""
    success: bool
    tools: List[MCPTool]
    clients_summary: List[Dict[str, Any]]
    total_tools: int
    connected_clients: int

class MCPClientConnectResponse(BaseModel):
    """Response for client connection attempts."""
    success: bool
    client_id: str
    status: ClientStatus
    connection_time: Optional[datetime] = None
    tools_discovered: int = 0
    message: str
    error: Optional[str] = None

class MCPClientTestResponse(BaseModel):
    """Response for testing client configurations."""
    success: bool
    message: str
    connection_time_ms: Optional[int] = None
    tools_discovered: int = 0
    error: Optional[str] = None
    warnings: List[str] = []

# Template configurations for common MCP servers
MCP_CLIENT_TEMPLATES = {
    "brave-search": {
        "name": "Brave Search",
        "transport_type": "npx",
        "connection_config": {
            "package": "@modelcontextprotocol/server-brave-search",
            "version": "latest",
            "args": ["--api-key", "env:BRAVE_API_KEY"],
            "env_vars": {
                "BRAVE_API_KEY": ""
            }
        },
        "description": "Web search using Brave Search API"
    },
    "weather": {
        "name": "Weather Service",
        "transport_type": "npx",
        "connection_config": {
            "package": "@modelcontextprotocol/server-weather",
            "version": "latest",
            "args": [],
            "env_vars": {}
        },
        "description": "Weather information service"
    },
    "filesystem": {
        "name": "File System",
        "transport_type": "npx",
        "connection_config": {
            "package": "@modelcontextprotocol/server-filesystem",
            "version": "latest",
            "args": ["--allowed-directory", "/tmp"],
            "env_vars": {}
        },
        "description": "File system operations"
    },
    "postgres": {
        "name": "PostgreSQL",
        "transport_type": "npx",
        "connection_config": {
            "package": "@modelcontextprotocol/server-postgres",
            "version": "latest",
            "args": [],
            "env_vars": {
                "POSTGRES_URL": ""
            }
        },
        "description": "PostgreSQL database operations"
    }
} 