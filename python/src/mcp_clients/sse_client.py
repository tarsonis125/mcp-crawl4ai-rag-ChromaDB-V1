"""
SSE (Server-Sent Events) MCP Client implementation.

This client connects to MCP servers that use SSE transport,
including our own Archon MCP server.
"""

import asyncio
import json
import aiohttp
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .base_client import BaseMCPClient, MCPConnectionError, MCPToolCallError
from ..models.mcp_models import MCPTool, SSEConfig

logger = logging.getLogger(__name__)

class SSEMCPClient(BaseMCPClient):
    """
    MCP Client for SSE transport.
    
    Connects to MCP servers via HTTP/SSE endpoints and communicates
    using JSON-RPC over HTTP.
    """
    
    def __init__(self, client_id: str, name: str, connection_config: Dict[str, Any], **kwargs):
        super().__init__(client_id, name, "sse", connection_config, **kwargs)
        
        # Parse SSE-specific configuration
        self.config = SSEConfig(**connection_config)
        
        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None
        self._base_url = f"http://{self.config.host}:{self.config.port}"
        
        # Request tracking
        self._request_id = 0
        self._pending_requests: Dict[str, asyncio.Future] = {}
    
    async def connect(self) -> bool:
        """Connect to the SSE MCP server."""
        try:
            await self._set_status("connecting")
            
            # Create HTTP session
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            headers = {}
            
            if self.config.auth_headers:
                headers.update(self.config.auth_headers)
            
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers
            )
            
            # Test connection with a simple health check
            health_url = f"{self._base_url}/health"
            try:
                async with self._session.get(health_url) as response:
                    if response.status == 200:
                        logger.info(f"SSE MCP client {self.name} connected successfully")
                        await self._set_status("connected")
                        return True
                    else:
                        raise MCPConnectionError(f"Health check failed: HTTP {response.status}")
            except aiohttp.ClientError as e:
                # If health endpoint doesn't exist, try a basic MCP call
                try:
                    await self._make_mcp_request("ping", {})
                    logger.info(f"SSE MCP client {self.name} connected via MCP ping")
                    await self._set_status("connected")
                    return True
                except Exception:
                    raise MCPConnectionError(f"Connection test failed: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to connect SSE MCP client {self.name}: {e}")
            await self._set_status("error", str(e))
            await self._cleanup_session()
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from the SSE MCP server."""
        try:
            await self._cleanup_session()
            await self._set_status("disconnected")
            logger.info(f"SSE MCP client {self.name} disconnected")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting SSE MCP client {self.name}: {e}")
            return False
    
    async def is_healthy(self) -> bool:
        """Check if the SSE connection is healthy."""
        if not self._session or self._session.closed:
            return False
        
        try:
            # Try a simple ping request
            await self._make_mcp_request("ping", {}, timeout=5)
            return True
        except Exception:
            return False
    
    async def discover_tools(self) -> List[MCPTool]:
        """Discover tools from the SSE MCP server."""
        try:
            # Make MCP tools/list request
            result = await self._make_mcp_request("tools/list", {})
            
            tools = []
            if isinstance(result, dict) and "tools" in result:
                for tool_data in result["tools"]:
                    try:
                        tool = MCPTool(
                            name=tool_data.get("name", ""),
                            description=tool_data.get("description", ""),
                            inputSchema=tool_data.get("inputSchema", {})
                        )
                        tools.append(tool)
                    except Exception as e:
                        logger.warning(f"Failed to parse tool {tool_data}: {e}")
            
            logger.info(f"Discovered {len(tools)} tools from SSE client {self.name}")
            return tools
            
        except Exception as e:
            logger.error(f"Failed to discover tools from SSE client {self.name}: {e}")
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the SSE MCP server."""
        try:
            # Make MCP tools/call request
            result = await self._make_mcp_request("tools/call", {
                "name": tool_name,
                "arguments": arguments
            })
            
            # Handle different response formats
            if isinstance(result, dict):
                if "content" in result:
                    # Standard MCP tool response format
                    content = result["content"]
                    if isinstance(content, list) and content:
                        # Return first content item (text result)
                        return content[0].get("text", result)
                    return content
                elif "result" in result:
                    # Some tools return result directly
                    return result["result"]
                else:
                    # Return the whole result
                    return result
            
            return result
            
        except Exception as e:
            logger.error(f"Tool call failed for SSE client {self.name}.{tool_name}: {e}")
            raise MCPToolCallError(f"Tool call failed: {e}") from e
    
    async def _make_mcp_request(self, method: str, params: Dict[str, Any], timeout: Optional[float] = None) -> Any:
        """Make an MCP JSON-RPC request to the server."""
        if not self._session:
            raise MCPConnectionError("No active session")
        
        # Generate request ID
        self._request_id += 1
        request_id = str(self._request_id)
        
        # Prepare JSON-RPC request
        request_data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        # Determine endpoint URL
        if method.startswith("tools/"):
            # Direct tool calls go to the main endpoint
            url = f"{self._base_url}{self.config.endpoint}"
        else:
            # Other methods might go to different endpoints
            url = f"{self._base_url}{self.config.endpoint}"
        
        try:
            request_timeout = timeout or self.config.timeout
            
            async with self._session.post(
                url,
                json=request_data,
                timeout=aiohttp.ClientTimeout(total=request_timeout)
            ) as response:
                
                if response.status != 200:
                    raise MCPConnectionError(f"HTTP error {response.status}: {await response.text()}")
                
                response_data = await response.json()
                
                # Validate JSON-RPC response
                if "error" in response_data:
                    error = response_data["error"]
                    raise MCPToolCallError(f"MCP error: {error.get('message', 'Unknown error')}")
                
                if "result" not in response_data:
                    raise MCPConnectionError("Invalid MCP response: missing result")
                
                return response_data["result"]
                
        except aiohttp.ClientError as e:
            logger.error(f"Network error in MCP request to {url}: {e}")
            raise MCPConnectionError(f"Network error: {e}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from MCP server: {e}")
            raise MCPConnectionError(f"Invalid JSON response: {e}") from e
        except asyncio.TimeoutError as e:
            logger.error(f"Timeout in MCP request to {url}")
            raise MCPConnectionError("Request timeout") from e
    
    async def _cleanup_session(self):
        """Clean up the HTTP session."""
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception as e:
                logger.warning(f"Error closing HTTP session: {e}")
        self._session = None
        
        # Cancel any pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()
    
    def __del__(self):
        """Cleanup on deletion."""
        if self._session and not self._session.closed:
            # Schedule cleanup in event loop if possible
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._cleanup_session())
            except Exception:
                pass 