"""
Base MCP Client class that all transport implementations inherit from.

This provides the common interface and functionality for all MCP clients,
regardless of their transport type.
"""

import asyncio
import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone

from ..models.mcp_models import MCPTool, ClientStatus, TransportType

logger = logging.getLogger(__name__)

class MCPClientError(Exception):
    """Base exception for MCP client errors."""
    pass

class MCPConnectionError(MCPClientError):
    """Raised when connection to MCP server fails."""
    pass

class MCPToolCallError(MCPClientError):
    """Raised when tool call fails."""
    pass

class BaseMCPClient(ABC):
    """
    Base class for all MCP client implementations.
    
    This class defines the common interface that all transport-specific
    MCP clients must implement.
    """
    
    def __init__(
        self,
        client_id: str,
        name: str,
        transport_type: TransportType,
        connection_config: Dict[str, Any],
        health_check_interval: int = 30
    ):
        self.client_id = client_id
        self.name = name
        self.transport_type = transport_type
        self.connection_config = connection_config
        self.health_check_interval = health_check_interval
        
        # Connection state
        self.status: ClientStatus = "disconnected"
        self.connected_at: Optional[datetime] = None
        self.last_seen: Optional[datetime] = None
        self.last_error: Optional[str] = None
        
        # Tools cache
        self.tools: Dict[str, MCPTool] = {}
        self.tools_last_discovered: Optional[datetime] = None
        
        # Performance metrics
        self.total_tool_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.response_times: List[float] = []
        
        # Event callbacks
        self.on_status_change: Optional[Callable[[ClientStatus], None]] = None
        self.on_tools_discovered: Optional[Callable[[List[MCPTool]], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        
        # Internal state
        self._connection_lock = asyncio.Lock()
        self._tools_lock = asyncio.Lock()
        
    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the MCP server.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from the MCP server.
        
        Returns:
            True if disconnection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def is_healthy(self) -> bool:
        """
        Check if the connection is healthy.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        pass
    
    @abstractmethod
    async def discover_tools(self) -> List[MCPTool]:
        """
        Discover available tools from the MCP server.
        
        Returns:
            List of discovered tools
        """
        pass
    
    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a specific tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool execution result
            
        Raises:
            MCPToolCallError: If tool call fails
        """
        pass
    
    # Common methods implemented here
    
    async def ensure_connected(self) -> bool:
        """Ensure the client is connected, connecting if necessary."""
        async with self._connection_lock:
            if self.status == "connected" and await self.is_healthy():
                return True
            
            logger.info(f"Connecting to MCP client {self.name}")
            try:
                success = await self.connect()
                if success:
                    await self.refresh_tools()
                return success
            except Exception as e:
                logger.error(f"Failed to connect to MCP client {self.name}: {e}")
                await self._set_status("error", str(e))
                return False
    
    async def refresh_tools(self) -> List[MCPTool]:
        """Refresh the tools cache by discovering tools from the server."""
        async with self._tools_lock:
            try:
                logger.info(f"Discovering tools for MCP client {self.name}")
                tools = await self.discover_tools()
                
                # Update tools cache
                self.tools = {tool.name: tool for tool in tools}
                self.tools_last_discovered = datetime.now(timezone.utc)
                
                # Trigger callback
                if self.on_tools_discovered:
                    self.on_tools_discovered(tools)
                
                logger.info(f"Discovered {len(tools)} tools for {self.name}")
                return tools
                
            except Exception as e:
                logger.error(f"Failed to discover tools for {self.name}: {e}")
                return []
    
    async def call_tool_with_metrics(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool with performance tracking."""
        start_time = time.time()
        
        try:
            # Ensure we're connected
            if not await self.ensure_connected():
                raise MCPConnectionError(f"Cannot connect to MCP client {self.name}")
            
            # Check if tool exists
            if tool_name not in self.tools:
                await self.refresh_tools()  # Try refreshing tools cache
                if tool_name not in self.tools:
                    raise MCPToolCallError(f"Tool '{tool_name}' not found in client {self.name}")
            
            # Call the tool
            result = await self.call_tool(tool_name, arguments)
            
            # Update metrics
            execution_time = (time.time() - start_time) * 1000  # Convert to ms
            self.response_times.append(execution_time)
            self.total_tool_calls += 1
            self.successful_calls += 1
            
            # Keep only last 100 response times for moving average
            if len(self.response_times) > 100:
                self.response_times = self.response_times[-100:]
            
            self.last_seen = datetime.now(timezone.utc)
            
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.total_tool_calls += 1
            self.failed_calls += 1
            
            error_msg = f"Tool call failed for {self.name}.{tool_name}: {str(e)}"
            logger.error(error_msg)
            
            if self.on_error:
                self.on_error(error_msg)
            
            raise MCPToolCallError(error_msg) from e
    
    async def get_tools_list(self) -> List[MCPTool]:
        """Get the current list of tools, refreshing if necessary."""
        if not self.tools or not self.tools_last_discovered:
            await self.refresh_tools()
        
        # Add client info to tools
        tools_with_client_info = []
        for tool in self.tools.values():
            tool_copy = tool.model_copy()
            tool_copy.client_id = self.client_id
            tool_copy.client_name = self.name
            tool_copy.client_status = self.status
            tool_copy.discovered_at = self.tools_last_discovered
            tools_with_client_info.append(tool_copy)
        
        return tools_with_client_info
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for this client."""
        avg_response_time = (
            sum(self.response_times) / len(self.response_times)
            if self.response_times else 0
        )
        
        uptime_seconds = (
            int((datetime.now(timezone.utc) - self.connected_at).total_seconds())
            if self.connected_at else 0
        )
        
        return {
            "total_tool_calls": self.total_tool_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "avg_response_time_ms": round(avg_response_time, 2),
            "uptime_seconds": uptime_seconds,
            "tools_count": len(self.tools),
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "connection_established": self.connected_at.isoformat() if self.connected_at else None
        }
    
    async def _set_status(self, status: ClientStatus, error: Optional[str] = None):
        """Update the client status and trigger callbacks."""
        old_status = self.status
        self.status = status
        self.last_error = error
        
        if status == "connected":
            self.connected_at = datetime.now(timezone.utc)
            self.last_seen = self.connected_at
        elif status in ["disconnected", "error"]:
            self.connected_at = None
        
        # Trigger status change callback
        if self.on_status_change and old_status != status:
            try:
                self.on_status_change(status)
            except Exception as e:
                logger.error(f"Error in status change callback: {e}")
        
        logger.info(f"MCP client {self.name} status changed: {old_status} -> {status}")
        if error:
            logger.error(f"MCP client {self.name} error: {error}")
    
    def __str__(self) -> str:
        return f"MCPClient({self.name}, {self.transport_type}, {self.status})"
    
    def __repr__(self) -> str:
        return (
            f"MCPClient(id={self.client_id}, name={self.name}, "
            f"transport={self.transport_type}, status={self.status})"
        ) 