"""
Lightweight MCP Server for Archon (Microservices Version)

This is the lightweight MCP server that uses HTTP calls to other services
instead of importing heavy dependencies directly. This significantly reduces
the container size from 1.66GB to ~150MB.

Modules:
- RAG Module: Delegates to API service via HTTP
- Project Module: Delegates to API service via HTTP
- Health & Session: Local lightweight operations
"""
from mcp.server.fastmcp import FastMCP, Context
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Optional, Any
from dotenv import load_dotenv
from pathlib import Path
import os
import sys
import asyncio
import logging
import traceback
import time
from datetime import datetime
import threading
import json

# Add the project root to Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load environment variables from the project root .env file
project_root = Path(__file__).resolve().parent.parent
dotenv_path = project_root / '.env'
load_dotenv(dotenv_path, override=True)

# Configure logging FIRST before any imports that might use it
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/mcp_server.log', mode='a') if os.path.exists('/tmp') else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import Logfire configuration
from src.server.config.logfire_config import setup_logfire, mcp_logger

# Import session management (lightweight)
from src.server.services.mcp_session_manager import get_session_manager

# Import service client for HTTP calls
from src.server.services.mcp_service_client import get_mcp_service_client

# Global initialization lock and flag
_initialization_lock = threading.Lock()
_initialization_complete = False
_shared_context = None

@dataclass
class LightweightArchonContext:
    """
    Lightweight context for MCP server.
    No heavy dependencies - just service client for HTTP calls.
    """
    service_client: Any
    health_status: dict = None
    startup_time: float = None

    def __post_init__(self):
        if self.health_status is None:
            self.health_status = {
                "status": "healthy",
                "api_service": False,
                "agents_service": False,
                "last_health_check": None
            }
        if self.startup_time is None:
            self.startup_time = time.time()

async def perform_health_checks(context: LightweightArchonContext):
    """Perform health checks on dependent services via HTTP."""
    try:
        # Check dependent services
        service_health = await context.service_client.health_check()
        
        context.health_status["api_service"] = service_health.get("api_service", False)
        context.health_status["agents_service"] = service_health.get("agents_service", False)
        
        # Overall status
        all_critical_ready = context.health_status["api_service"]
        
        context.health_status["status"] = "healthy" if all_critical_ready else "degraded"
        context.health_status["last_health_check"] = datetime.now().isoformat()
        
        if not all_critical_ready:
            logger.warning(f"Health check failed: {context.health_status}")
        else:
            logger.info("Health check passed - dependent services healthy")
            
    except Exception as e:
        logger.error(f"Health check error: {e}")
        context.health_status["status"] = "unhealthy"
        context.health_status["last_health_check"] = datetime.now().isoformat()

@asynccontextmanager
async def lightweight_lifespan(server: FastMCP) -> AsyncIterator[LightweightArchonContext]:
    """
    Lightweight lifecycle manager - no heavy dependencies.
    """
    global _initialization_complete, _shared_context
    
    # Quick check without lock
    if _initialization_complete and _shared_context:
        logger.info("♻️ Reusing existing lightweight context for new SSE connection")
        yield _shared_context
        return
    
    # Acquire lock for initialization
    with _initialization_lock:
        # Double-check pattern
        if _initialization_complete and _shared_context:
            logger.info("♻️ Reusing existing lightweight context for new SSE connection")
            yield _shared_context
            return
        
        logger.info("🚀 Starting Lightweight MCP server...")
        
        try:
            # Initialize session manager (lightweight)
            logger.info("🔐 Initializing session manager...")
            session_manager = get_session_manager()
            logger.info("✓ Session manager initialized")
            
            # Initialize service client for HTTP calls
            logger.info("🌐 Initializing service client...")
            service_client = get_mcp_service_client()
            logger.info("✓ Service client initialized")
            
            # Create lightweight context  
            context = LightweightArchonContext(
                service_client=service_client
            )
            
            # Perform initial health check
            await perform_health_checks(context)
            
            logger.info("✓ Lightweight MCP server ready")
            
            # Store context globally
            _shared_context = context
            _initialization_complete = True
            
            yield context
            
        except Exception as e:
            logger.error(f"💥 Critical error in lifespan setup: {e}")
            logger.error(traceback.format_exc())
            raise
        finally:
            # Clean up resources  
            logger.info("🧹 Cleaning up lightweight MCP server...")
            logger.info("✅ Lightweight MCP server shutdown complete")

# Initialize the main FastMCP server with fixed configuration
try:
    # Fixed configuration for SSE-only mode
    server_host = "0.0.0.0"  # Listen on all interfaces
    server_port = 8051       # Fixed port
    
    logger.info("🏗️ LIGHTWEIGHT MCP SERVER INITIALIZATION:")
    logger.info(f"   Server Name: archon-mcp-server-lightweight")
    logger.info(f"   Description: Lightweight MCP server using HTTP calls")
    logger.info(f"   Host: {server_host}")
    logger.info(f"   Port: {server_port}")
    logger.info(f"   Mode: SSE-only")
    
    mcp = FastMCP(
        "archon-mcp-server-lightweight",
        description="Lightweight MCP server for Archon - uses HTTP calls to other services",
        lifespan=lightweight_lifespan,
        host=server_host,
        port=server_port
    )
    logger.info(f"✓ Lightweight FastMCP server instance created successfully")
    logger.info(f"   SSE endpoint: http://{server_host}:{server_port}/sse")
    
except Exception as e:
    logger.error(f"✗ Failed to create FastMCP server: {e}")
    logger.error(traceback.format_exc())
    raise

# Health check endpoint
@mcp.tool()
async def health_check(ctx: Context) -> str:
    """
    Perform a health check on the MCP server and its dependencies.
    
    Returns:
        JSON string with current health status
    """
    try:
        # Try to get the lifespan context
        context = getattr(ctx.request_context, 'lifespan_context', None)
        
        if context is None:
            # Server starting up
            return json.dumps({
                "success": True,
                "status": "starting",
                "message": "MCP server is initializing...",
                "timestamp": datetime.now().isoformat()
            })
        
        # Server is ready - perform health checks
        if hasattr(context, 'health_status') and context.health_status:
            await perform_health_checks(context)
            
            return json.dumps({
                "success": True,
                "health": context.health_status,
                "uptime_seconds": time.time() - context.startup_time,
                "timestamp": datetime.now().isoformat()
            })
        else:
            return json.dumps({
                "success": True,
                "status": "ready",
                "message": "MCP server is running",
                "timestamp": datetime.now().isoformat()
            })
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return json.dumps({
            "success": False,
            "error": f"Health check failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })

# Session management endpoint
@mcp.tool()
async def session_info(ctx: Context) -> str:
    """
    Get information about the current session and all active sessions.
    
    Returns:
        JSON string with session information
    """
    try:
        session_manager = get_session_manager()
        
        # Build session info
        session_info_data = {
            'active_sessions': session_manager.get_active_session_count(),
            'session_timeout': session_manager.timeout
        }
        
        # Add server uptime
        context = getattr(ctx.request_context, 'lifespan_context', None)
        if context and hasattr(context, 'startup_time'):
            session_info_data['server_uptime_seconds'] = time.time() - context.startup_time
        
        return json.dumps({
            "success": True,
            "session_management": session_info_data,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Session info failed: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to get session info: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })

# Import and register lightweight modules
def register_modules():
    """Register all MCP tool modules (lightweight versions)."""
    logger.info("🔧 Registering lightweight MCP tool modules...")
    
    modules_registered = 0
    
    # Import and register RAG module (HTTP-based version)
    try:
        from src.mcp.modules.rag_module import register_rag_tools
        register_rag_tools(mcp)
        modules_registered += 1
        logger.info("✓ RAG module registered (HTTP-based)")
    except ImportError as e:
        logger.warning(f"⚠ RAG module not available: {e}")
    except Exception as e:
        logger.error(f"✗ Error registering RAG module: {e}")
        logger.error(traceback.format_exc())
    
    # Import and register Project module - only if Projects are enabled
    projects_enabled = os.getenv("PROJECTS_ENABLED", "true").lower() == "true"
    if projects_enabled:
        try:
            from src.mcp.modules.project_module import register_project_tools
            register_project_tools(mcp)
            modules_registered += 1
            logger.info("✓ Project module registered (HTTP-based)")
        except ImportError as e:
            logger.warning(f"⚠ Project module not available: {e}")
        except Exception as e:
            logger.error(f"✗ Error registering Project module: {e}")
            logger.error(traceback.format_exc())
    else:
        logger.info("⚠ Project module skipped - Projects are disabled")
    
    logger.info(f"📦 Total modules registered: {modules_registered}")
    
    if modules_registered == 0:
        logger.error("💥 No modules were successfully registered!")
        raise RuntimeError("No MCP modules available")

# Register all modules when this file is imported
try:
    register_modules()
except Exception as e:
    logger.error(f"💥 Critical error during module registration: {e}")
    logger.error(traceback.format_exc())
    raise

async def main():
    """Main entry point for the lightweight MCP server."""
    try:
        # Initialize Logfire first
        setup_logfire(service_name="archon-mcp-server-lightweight")
        
        # Fixed configuration for SSE-only mode
        host = "0.0.0.0"
        port = 8051
        
        logger.info("🚀 Starting Lightweight Archon MCP Server")
        logger.info(f"   Mode: SSE-only")
        logger.info(f"   Host: {host}")
        logger.info(f"   Port: {port}")
        logger.info(f"   URL: http://{host}:{port}/sse")
        
        mcp_logger.info("🔥 Logfire initialized for lightweight MCP server")
        mcp_logger.info("🌟 Starting lightweight MCP server", host=host, port=port)
        
        # Run SSE server
        logger.info("🌐 Starting Server-Sent Events (SSE) transport")
        await mcp.run_sse_async()
            
    except Exception as e:
        mcp_logger.error("💥 Fatal error in main", error=str(e), error_type=type(e).__name__)
        logger.error(f"💥 Fatal error in main: {e}")
        logger.error(traceback.format_exc())
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Lightweight MCP server stopped by user")
    except Exception as e:
        logger.error(f"💥 Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

# Missing import fix
from typing import Any