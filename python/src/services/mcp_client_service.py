"""
Database service layer for MCP Client Management.

This service handles all database operations for MCP clients, tools, sessions,
and health monitoring.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from uuid import UUID

from supabase import AsyncClient
from ..models.mcp_models import (
    MCPClient, MCPClientCreate, MCPClientUpdate, MCPTool,
    MCPClientSession, MCPHealthCheck, ClientStatus, TransportType
)

logger = logging.getLogger(__name__)

class MCPClientService:
    """Service for managing MCP clients in the database."""
    
    def __init__(self, supabase: AsyncClient):
        self.supabase = supabase
    
    # Client CRUD Operations
    
    async def create_client(self, client_data: MCPClientCreate) -> MCPClient:
        """Create a new MCP client in the database."""
        try:
            # Prepare data for insertion
            insert_data = {
                "name": client_data.name,
                "transport_type": client_data.transport_type,
                "connection_config": client_data.connection_config,
                "auto_connect": client_data.auto_connect,
                "health_check_interval": client_data.health_check_interval,
                "status": "disconnected"
            }
            
            # Insert into database
            result = await self.supabase.table("mcp_clients").insert(insert_data).execute()
            
            if not result.data:
                raise Exception("Failed to create client - no data returned")
            
            client_record = result.data[0]
            
            # Convert to MCPClient model
            client = MCPClient(
                id=client_record["id"],
                name=client_record["name"],
                transport_type=client_record["transport_type"],
                connection_config=client_record["connection_config"],
                status=client_record["status"],
                auto_connect=client_record["auto_connect"],
                health_check_interval=client_record["health_check_interval"],
                last_seen=client_record.get("last_seen"),
                last_error=client_record.get("last_error"),
                is_default=client_record.get("is_default", False),
                tools_count=0,  # Will be updated when tools are discovered
                created_at=datetime.fromisoformat(client_record["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(client_record["updated_at"].replace("Z", "+00:00")) if client_record.get("updated_at") else None
            )
            
            logger.info(f"Created MCP client {client.name} with ID {client.id}")
            return client
            
        except Exception as e:
            logger.error(f"Failed to create MCP client {client_data.name}: {e}")
            raise
    
    async def get_client(self, client_id: str) -> Optional[MCPClient]:
        """Get an MCP client by ID."""
        try:
            result = await self.supabase.table("mcp_clients").select("*").eq("id", client_id).execute()
            
            if not result.data:
                return None
            
            client_record = result.data[0]
            
            # Get tools count
            tools_result = await self.supabase.table("mcp_client_tools").select("id").eq("client_id", client_id).execute()
            tools_count = len(tools_result.data) if tools_result.data else 0
            
            return MCPClient(
                id=client_record["id"],
                name=client_record["name"],
                transport_type=client_record["transport_type"],
                connection_config=client_record["connection_config"],
                status=client_record["status"],
                auto_connect=client_record["auto_connect"],
                health_check_interval=client_record["health_check_interval"],
                last_seen=datetime.fromisoformat(client_record["last_seen"].replace("Z", "+00:00")) if client_record.get("last_seen") else None,
                last_error=client_record.get("last_error"),
                is_default=client_record.get("is_default", False),
                tools_count=tools_count,
                created_at=datetime.fromisoformat(client_record["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(client_record["updated_at"].replace("Z", "+00:00")) if client_record.get("updated_at") else None
            )
            
        except Exception as e:
            logger.error(f"Failed to get MCP client {client_id}: {e}")
            return None
    
    async def list_clients(self, include_disconnected: bool = True) -> List[MCPClient]:
        """List all MCP clients."""
        try:
            query = self.supabase.table("mcp_clients").select("*")
            
            if not include_disconnected:
                query = query.neq("status", "disconnected")
            
            result = await query.execute()
            
            clients = []
            for client_record in result.data:
                # Get tools count for each client
                tools_result = await self.supabase.table("mcp_client_tools").select("id").eq("client_id", client_record["id"]).execute()
                tools_count = len(tools_result.data) if tools_result.data else 0
                
                client = MCPClient(
                    id=client_record["id"],
                    name=client_record["name"],
                    transport_type=client_record["transport_type"],
                    connection_config=client_record["connection_config"],
                    status=client_record["status"],
                    auto_connect=client_record["auto_connect"],
                    health_check_interval=client_record["health_check_interval"],
                    last_seen=datetime.fromisoformat(client_record["last_seen"].replace("Z", "+00:00")) if client_record.get("last_seen") else None,
                    last_error=client_record.get("last_error"),
                    is_default=client_record.get("is_default", False),
                    tools_count=tools_count,
                    created_at=datetime.fromisoformat(client_record["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(client_record["updated_at"].replace("Z", "+00:00")) if client_record.get("updated_at") else None
                )
                clients.append(client)
            
            return clients
            
        except Exception as e:
            logger.error(f"Failed to list MCP clients: {e}")
            return []
    
    async def update_client(self, client_id: str, update_data: MCPClientUpdate) -> Optional[MCPClient]:
        """Update an MCP client."""
        try:
            # Prepare update data
            update_fields = {}
            if update_data.name is not None:
                update_fields["name"] = update_data.name
            if update_data.connection_config is not None:
                update_fields["connection_config"] = update_data.connection_config
            if update_data.auto_connect is not None:
                update_fields["auto_connect"] = update_data.auto_connect
            if update_data.health_check_interval is not None:
                update_fields["health_check_interval"] = update_data.health_check_interval
            
            if not update_fields:
                # No updates to make
                return await self.get_client(client_id)
            
            # Update in database
            result = await self.supabase.table("mcp_clients").update(update_fields).eq("id", client_id).execute()
            
            if not result.data:
                return None
            
            logger.info(f"Updated MCP client {client_id}")
            return await self.get_client(client_id)
            
        except Exception as e:
            logger.error(f"Failed to update MCP client {client_id}: {e}")
            return None
    
    async def delete_client(self, client_id: str) -> bool:
        """Delete an MCP client and all related data."""
        try:
            # Delete related data first (cascading should handle this, but being explicit)
            await self.supabase.table("mcp_client_tools").delete().eq("client_id", client_id).execute()
            await self.supabase.table("mcp_client_sessions").delete().eq("client_id", client_id).execute()
            await self.supabase.table("mcp_client_health_checks").delete().eq("client_id", client_id).execute()
            
            # Delete the client
            result = await self.supabase.table("mcp_clients").delete().eq("id", client_id).execute()
            
            logger.info(f"Deleted MCP client {client_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete MCP client {client_id}: {e}")
            return False
    
    async def update_client_status(
        self, 
        client_id: str, 
        status: ClientStatus, 
        error: Optional[str] = None,
        last_seen: Optional[datetime] = None
    ) -> bool:
        """Update client status and last seen timestamp."""
        try:
            update_data = {
                "status": status,
                "last_error": error
            }
            
            if last_seen:
                update_data["last_seen"] = last_seen.isoformat()
            elif status == "connected":
                update_data["last_seen"] = datetime.now(timezone.utc).isoformat()
            
            await self.supabase.table("mcp_clients").update(update_data).eq("id", client_id).execute()
            
            logger.debug(f"Updated status for client {client_id}: {status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update status for client {client_id}: {e}")
            return False
    
    # Tools Management
    
    async def save_client_tools(self, client_id: str, tools: List[MCPTool]) -> bool:
        """Save discovered tools for a client."""
        try:
            # Delete existing tools for this client
            await self.supabase.table("mcp_client_tools").delete().eq("client_id", client_id).execute()
            
            # Insert new tools
            if tools:
                tools_data = []
                for tool in tools:
                    tools_data.append({
                        "client_id": client_id,
                        "tool_name": tool.name,
                        "tool_description": tool.description,
                        "tool_schema": {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        }
                    })
                
                await self.supabase.table("mcp_client_tools").insert(tools_data).execute()
            
            logger.info(f"Saved {len(tools)} tools for client {client_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save tools for client {client_id}: {e}")
            return False
    
    async def get_client_tools(self, client_id: str) -> List[MCPTool]:
        """Get tools for a specific client."""
        try:
            result = await self.supabase.table("mcp_client_tools").select("*").eq("client_id", client_id).execute()
            
            tools = []
            for tool_record in result.data:
                tool = MCPTool(
                    name=tool_record["tool_name"],
                    description=tool_record["tool_description"],
                    inputSchema=tool_record["tool_schema"].get("inputSchema", {}),
                    client_id=client_id,
                    discovered_at=datetime.fromisoformat(tool_record["discovered_at"].replace("Z", "+00:00"))
                )
                tools.append(tool)
            
            return tools
            
        except Exception as e:
            logger.error(f"Failed to get tools for client {client_id}: {e}")
            return []
    
    async def get_all_tools(self) -> List[MCPTool]:
        """Get all tools from all clients."""
        try:
            # Join with clients to get client names and status
            result = await self.supabase.table("mcp_client_tools").select(
                "*, mcp_clients(name, status)"
            ).execute()
            
            tools = []
            for tool_record in result.data:
                client_info = tool_record.get("mcp_clients", {})
                
                tool = MCPTool(
                    name=tool_record["tool_name"],
                    description=tool_record["tool_description"],
                    inputSchema=tool_record["tool_schema"].get("inputSchema", {}),
                    client_id=tool_record["client_id"],
                    client_name=client_info.get("name", "Unknown"),
                    client_status=client_info.get("status", "unknown"),
                    discovered_at=datetime.fromisoformat(tool_record["discovered_at"].replace("Z", "+00:00"))
                )
                tools.append(tool)
            
            return tools
            
        except Exception as e:
            logger.error(f"Failed to get all tools: {e}")
            return []
    
    # Session Management
    
    async def create_session(self, client_id: str, process_id: Optional[int] = None) -> str:
        """Create a new session for a client."""
        try:
            session_data = {
                "client_id": client_id,
                "process_id": process_id,
                "is_active": True
            }
            
            result = await self.supabase.table("mcp_client_sessions").insert(session_data).execute()
            
            if result.data:
                session_id = result.data[0]["id"]
                logger.info(f"Created session {session_id} for client {client_id}")
                return session_id
            else:
                raise Exception("No session data returned")
                
        except Exception as e:
            logger.error(f"Failed to create session for client {client_id}: {e}")
            raise
    
    async def end_session(self, session_id: str) -> bool:
        """End an active session."""
        try:
            update_data = {
                "session_end": datetime.now(timezone.utc).isoformat(),
                "is_active": False
            }
            
            await self.supabase.table("mcp_client_sessions").update(update_data).eq("id", session_id).execute()
            
            logger.info(f"Ended session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to end session {session_id}: {e}")
            return False
    
    # Health Check Management
    
    async def record_health_check(
        self,
        client_id: str,
        status: str,
        response_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Record a health check result."""
        try:
            health_data = {
                "client_id": client_id,
                "status": status,
                "response_time_ms": response_time_ms,
                "error_message": error_message,
                "metadata": metadata or {}
            }
            
            await self.supabase.table("mcp_client_health_checks").insert(health_data).execute()
            
            logger.debug(f"Recorded health check for client {client_id}: {status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record health check for client {client_id}: {e}")
            return False
    
    async def get_client_health_history(self, client_id: str, limit: int = 10) -> List[MCPHealthCheck]:
        """Get recent health check history for a client."""
        try:
            result = await self.supabase.table("mcp_client_health_checks").select("*").eq("client_id", client_id).order("check_time", desc=True).limit(limit).execute()
            
            health_checks = []
            for record in result.data:
                health_check = MCPHealthCheck(
                    id=record["id"],
                    client_id=record["client_id"],
                    check_time=datetime.fromisoformat(record["check_time"].replace("Z", "+00:00")),
                    status=record["status"],
                    response_time_ms=record.get("response_time_ms"),
                    error_message=record.get("error_message"),
                    metadata=record.get("metadata", {})
                )
                health_checks.append(health_check)
            
            return health_checks
            
        except Exception as e:
            logger.error(f"Failed to get health history for client {client_id}: {e}")
            return [] 