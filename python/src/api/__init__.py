"""
API package for Archon - modular FastAPI endpoints

This package organizes the API into logical modules:
- settings_api: Settings and credentials management
- mcp_api: MCP server management and WebSocket streaming  
- knowledge_api: Knowledge base, crawling, and RAG operations
- projects_api: Project and task management with streaming
"""

from .settings_api import router as settings_router
from .mcp_api import router as mcp_router  
from .knowledge_api import router as knowledge_router
from .projects_api import router as projects_router

__all__ = ['settings_router', 'mcp_router', 'knowledge_router', 'projects_router'] 