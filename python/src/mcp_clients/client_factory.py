"""
MCP Client Factory for creating transport-specific client instances.

This factory creates the appropriate MCP client based on the transport type
and manages client lifecycle.
"""

import logging
from typing import Dict, Any, Optional

from .base_client import BaseMCPClient
from .sse_client import SSEMCPClient
from ..models.mcp_models import TransportType

logger = logging.getLogger(__name__)

class MCPClientFactory:
    """
    Factory for creating MCP clients based on transport type.
    
    Supports SSE, stdio, Docker, and NPX transports.
    """
    
    @staticmethod
    def create_client(
        client_id: str,
        name: str,
        transport_type: TransportType,
        connection_config: Dict[str, Any],
        **kwargs
    ) -> BaseMCPClient:
        """
        Create an MCP client instance based on transport type.
        
        Args:
            client_id: Unique identifier for the client
            name: Human-readable name for the client
            transport_type: Type of transport (sse, stdio, docker, npx)
            connection_config: Transport-specific configuration
            **kwargs: Additional arguments passed to client constructor
            
        Returns:
            BaseMCPClient: Configured client instance
            
        Raises:
            ValueError: If transport type is not supported
        """
        
        logger.info(f"Creating MCP client {name} with transport {transport_type}")
        
        if transport_type == "sse":
            return SSEMCPClient(
                client_id=client_id,
                name=name,
                connection_config=connection_config,
                **kwargs
            )
        
        elif transport_type == "stdio":
            # Import here to avoid circular dependencies
            from .stdio_client import StdioMCPClient
            return StdioMCPClient(
                client_id=client_id,
                name=name,
                connection_config=connection_config,
                **kwargs
            )
        
        elif transport_type == "docker":
            # Import here to avoid circular dependencies
            from .docker_client import DockerMCPClient
            return DockerMCPClient(
                client_id=client_id,
                name=name,
                connection_config=connection_config,
                **kwargs
            )
        
        elif transport_type == "npx":
            # Import here to avoid circular dependencies
            from .npx_client import NPXMCPClient
            return NPXMCPClient(
                client_id=client_id,
                name=name,
                connection_config=connection_config,
                **kwargs
            )
        
        else:
            raise ValueError(f"Unsupported transport type: {transport_type}")
    
    @staticmethod
    def get_supported_transports() -> list[TransportType]:
        """Get list of supported transport types."""
        return ["sse", "stdio", "docker", "npx"]
    
    @staticmethod
    def validate_config(transport_type: TransportType, config: Dict[str, Any]) -> bool:
        """
        Validate configuration for a specific transport type.
        
        Args:
            transport_type: Type of transport to validate
            config: Configuration to validate
            
        Returns:
            bool: True if configuration is valid
        """
        try:
            if transport_type == "sse":
                from ..models.mcp_models import SSEConfig
                SSEConfig(**config)
                return True
            
            elif transport_type == "stdio":
                from ..models.mcp_models import StdioConfig
                StdioConfig(**config)
                return True
            
            elif transport_type == "docker":
                from ..models.mcp_models import DockerConfig
                DockerConfig(**config)
                return True
            
            elif transport_type == "npx":
                from ..models.mcp_models import NPXConfig
                NPXConfig(**config)
                return True
            
            else:
                return False
                
        except Exception as e:
            logger.warning(f"Configuration validation failed for {transport_type}: {e}")
            return False
    
    @staticmethod
    def get_config_schema(transport_type: TransportType) -> Optional[Dict[str, Any]]:
        """
        Get the JSON schema for a transport type's configuration.
        
        Args:
            transport_type: Type of transport
            
        Returns:
            dict: JSON schema for the configuration
        """
        try:
            if transport_type == "sse":
                from ..models.mcp_models import SSEConfig
                return SSEConfig.schema()
            
            elif transport_type == "stdio":
                from ..models.mcp_models import StdioConfig
                return StdioConfig.schema()
            
            elif transport_type == "docker":
                from ..models.mcp_models import DockerConfig
                return DockerConfig.schema()
            
            elif transport_type == "npx":
                from ..models.mcp_models import NPXConfig
                return NPXConfig.schema()
            
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to get config schema for {transport_type}: {e}")
            return None 