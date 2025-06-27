"""
API package for Archon - modular FastAPI endpoints

This package organizes the API into logical modules:
- settings_api: Settings and credentials management
- mcp_api: MCP server management and WebSocket streaming  
- mcp_client_api: Multi-client MCP management system
- knowledge_api: Knowledge base, crawling, and RAG operations
- projects_api: Project and task management with streaming
- tests_api: Test execution and streaming with real-time output
"""

from .settings_api import router as settings_router
from .mcp_api import router as mcp_router  
from .mcp_client_api import router as mcp_client_router
from .knowledge_api import router as knowledge_router
from .projects_api import router as projects_router
from .tests_api import router as tests_router

__all__ = ['settings_router', 'mcp_router', 'mcp_client_router', 'knowledge_router', 'projects_router', 'tests_router'] 
