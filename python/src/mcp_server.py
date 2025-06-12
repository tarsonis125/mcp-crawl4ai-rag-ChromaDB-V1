"""
# TODO: Add robust error handling, connection pooling for external services, health check endpoints, circuit breaker pattern, and resource optimization.
# Example: Use tenacity for retries, implement /health endpoint, and wrap external calls with circuit breaker logic.
Modular MCP Server for Archon

This is the main MCP server that coordinates multiple tool modules:
- RAG Module: Web crawling, document storage, and retrieval
- Tasks Module: Project and task management
- Future UI Module: Agent-UI integration

Each module registers its tools with this shared FastMCP instance.

Enhanced with comprehensive error handling, logging, and robustness features.
"""
from mcp.server.fastmcp import FastMCP, Context
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Optional
from sentence_transformers import CrossEncoder
from dotenv import load_dotenv
from supabase import Client
from pathlib import Path
import os
import sys
import asyncio
import logging
import traceback
import time
from datetime import datetime

from crawl4ai import AsyncWebCrawler, BrowserConfig

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
from src.logfire_config import setup_logfire, mcp_logger

try:
    from src.utils import get_supabase_client
except ImportError as e:
    logger.error(f"Failed to import utils: {e}")
    raise

@dataclass
class ArchonContext:
    """
    Shared context for all Archon MCP modules.
    
    This context holds resources that can be used by any module:
    - AsyncWebCrawler for web operations
    - Supabase client for database operations  
    - Optional reranking model for search enhancement
    """
    crawler: AsyncWebCrawler
    supabase_client: Client
    reranking_model: Optional[CrossEncoder] = None
    health_status: dict = None
    startup_time: float = None

    def __post_init__(self):
        if self.health_status is None:
            self.health_status = {
                "status": "healthy",
                "crawler_ready": False,
                "database_ready": False,
                "reranking_ready": False,
                "last_health_check": None
            }
        if self.startup_time is None:
            self.startup_time = time.time()

def check_supabase_health(client: Client) -> bool:
    """Check if Supabase is accessible."""
    try:
        # Try a simple query to test connection
        response = client.table("settings").select("key").limit(1).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase health check failed: {e}")
        return False

def check_crawler_health(crawler: AsyncWebCrawler) -> bool:
    """Check if crawler is ready."""
    try:
        # Simple check to see if crawler is initialized
        return hasattr(crawler, 'config') and crawler.config is not None
    except Exception as e:
        logger.error(f"Crawler health check failed: {e}")
        return False

async def perform_health_checks(context: ArchonContext):
    """Perform comprehensive health checks on all services."""
    try:
        # Check database
        context.health_status["database_ready"] = check_supabase_health(context.supabase_client)
        
        # Check crawler
        context.health_status["crawler_ready"] = check_crawler_health(context.crawler)
        
        # Check reranking model
        context.health_status["reranking_ready"] = context.reranking_model is not None
        
        # Overall status
        all_critical_ready = (
            context.health_status["database_ready"] and 
            context.health_status["crawler_ready"]
        )
        
        context.health_status["status"] = "healthy" if all_critical_ready else "degraded"
        context.health_status["last_health_check"] = datetime.now().isoformat()
        
        if not all_critical_ready:
            logger.warning(f"Health check failed: {context.health_status}")
        else:
            logger.info("Health check passed - all services healthy")
            
    except Exception as e:
        logger.error(f"Health check error: {e}")
        context.health_status["status"] = "unhealthy"
        context.health_status["last_health_check"] = datetime.now().isoformat()

@asynccontextmanager
async def archon_lifespan(server: FastMCP) -> AsyncIterator[ArchonContext]:
    """
    Manages the shared resources lifecycle - yields immediately for fast startup.
    Following official MCP patterns from the Python SDK documentation.
    """
    logger.info("🚀 Starting Archon MCP server lifespan...")
    
    # Check OpenAI API key availability (should be set by FastAPI startup)
    openai_key_available = bool(os.getenv("OPENAI_API_KEY"))
    logger.info(f"🔑 OpenAI API key status: {'AVAILABLE' if openai_key_available else 'NOT FOUND'}")
    
    # Initialize minimal resources needed for basic operation
    crawler = None
    supabase_client = None
    reranking_model = None
    
    try:
        # Initialize essential services (fast operations only)
        logger.info("🗄️ Initializing Supabase client...")
        supabase_client = get_supabase_client()
        logger.info("✓ Supabase client initialized")
        
        # Create context and yield immediately  
        context = ArchonContext(
            crawler=crawler,
            supabase_client=supabase_client,
            reranking_model=reranking_model
        )
        
        # Set ready status
        context.health_status["status"] = "ready"
        context.health_status["database_ready"] = True
        context.health_status["openai_key_available"] = openai_key_available
        context.health_status["last_health_check"] = datetime.now().isoformat()
        
        logger.info("✓ Archon context ready - server can accept requests")
        yield context
        
    except Exception as e:
        logger.error(f"💥 Critical error in lifespan setup: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        # Clean up resources  
        logger.info("🧹 Cleaning up Archon resources...")
        try:
            if crawler:
                await crawler.__aexit__(None, None, None)
                logger.info("✓ Crawler cleaned up")
        except Exception as e:
            logger.error(f"✗ Error cleaning up crawler: {e}")
        
        logger.info("✅ Archon MCP server lifespan ended")

# Initialize the main FastMCP server
try:
    server_host = os.getenv("HOST", "0.0.0.0")
    server_port = int(os.getenv("PORT", "8051"))
    
    logger.info("🏗️ FASTMCP SERVER INITIALIZATION:")
    logger.info(f"   Server Name: archon-mcp-server")
    logger.info(f"   Description: Modular MCP server for Archon: RAG, Tasks, and UI tools")
    logger.info(f"   Host: {server_host}")
    logger.info(f"   Port: {server_port}")
    
    mcp = FastMCP(
        "archon-mcp-server",
        description="Modular MCP server for Archon: RAG, Tasks, and UI tools",
        lifespan=archon_lifespan,
        host=server_host,
        port=server_port
    )
    logger.info(f"✓ FastMCP server instance created successfully")
    logger.info(f"   Available at: http://{server_host}:{server_port} (SSE mode)")
    logger.info(f"   Docker exec command: docker exec -it <container> uv run python src/mcp_server.py (stdio mode)")
    
except Exception as e:
    logger.error(f"✗ Failed to create FastMCP server: {e}")
    logger.error(traceback.format_exc())
    raise

# Health check endpoint
@mcp.tool()
async def health_check(ctx: Context) -> str:
    """
    Perform a lightweight health check that can respond immediately.
    
    Returns:
        JSON string with current health status
    """
    import json
    
    try:
        # Try to get the lifespan context (may not be ready during startup)
        context = getattr(ctx.request_context, 'lifespan_context', None)
        
        if context is None:
            # Server starting up - return basic status
            return json.dumps({
                "success": True,
                "status": "starting",
                "message": "MCP server is initializing...",
                "timestamp": datetime.now().isoformat()
            })
        
        # Server is ready - return full health status
        if hasattr(context, 'health_status') and context.health_status:
            # Perform quick health checks without blocking
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
        # Always return something - never crash
        return json.dumps({
            "success": False,
            "error": f"Health check failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })

# FastMCP automatically handles MCP protocol initialization (initialize/initialized)
# No need for explicit handlers - the library does this for us

# Import and register all modules
def register_modules():
    """Register all MCP tool modules with the main server."""
    transport = os.getenv("TRANSPORT", "sse")
    
    # Only print when not using stdio to avoid contaminating JSON-RPC stream
    if transport != "stdio":
        logger.info("🔧 Registering MCP tool modules...")
    
    modules_registered = 0
    
    # Import and register RAG module
    try:
        from src.modules.rag_module import register_rag_tools
        register_rag_tools(mcp)
        modules_registered += 1
        if transport != "stdio":
            logger.info("✓ RAG module registered")
    except ImportError as e:
        if transport != "stdio":
            logger.warning(f"⚠ RAG module not available: {e}")
    except Exception as e:
        if transport != "stdio":
            logger.error(f"✗ Error registering RAG module: {e}")
            logger.error(traceback.format_exc())
    
    # Import and register Project module - only if Projects are enabled
    projects_enabled = os.getenv("PROJECTS_ENABLED", "true").lower() == "true"
    if projects_enabled:
        try:
            from src.modules.project_module import register_project_tools
            register_project_tools(mcp)
            modules_registered += 1
            if transport != "stdio":
                logger.info("✓ Project module registered")
        except ImportError as e:
            if transport != "stdio":
                logger.warning(f"⚠ Project module not available: {e}")
        except Exception as e:
            if transport != "stdio":
                logger.error(f"✗ Error registering Project module: {e}")
                logger.error(traceback.format_exc())
    else:
        if transport != "stdio":
            logger.info("⚠ Project module skipped - Projects are disabled")
    
    # Import and register Versioning module (for document versioning only - task versioning removed)
    try:
        from src.modules.versioning_module import register_versioning_tools
        register_versioning_tools(mcp)
        modules_registered += 1
        if transport != "stdio":
            logger.info("✓ Versioning module registered (document versioning only)")
    except ImportError as e:
        if transport != "stdio":
            logger.warning(f"⚠ Versioning module not available: {e}")
    except Exception as e:
        if transport != "stdio":
            logger.error(f"✗ Error registering Versioning module: {e}")
            logger.error(traceback.format_exc())
    
    # Future UI module will be added here
    # try:
    #     from src.modules.ui_module import register_ui_tools
    #     register_ui_tools(mcp)
    #     modules_registered += 1
    #     logger.info("✓ UI module registered") 
    # except ImportError as e:
    #     logger.warning(f"⚠ UI module not available: {e}")
    # except Exception as e:
    #     logger.error(f"✗ Error registering UI module: {e}")
    
    if transport != "stdio":
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
    """Main entry point for the MCP server."""
    try:
        # Initialize Logfire first
        setup_logfire(service_name="archon-mcp-server")
        
        # Log all environment variables related to transport configuration
        logger.info("🔧 TRANSPORT CONFIGURATION DEBUG:")
        logger.info(f"   TRANSPORT env var: {os.getenv('TRANSPORT', 'NOT_SET')}")
        logger.info(f"   DOCKER_EXEC_STDIO env var: {os.getenv('DOCKER_EXEC_STDIO', 'NOT_SET')}")
        logger.info(f"   stdin.isatty(): {sys.stdin.isatty()}")
        logger.info(f"   HOST env var: {os.getenv('HOST', 'NOT_SET (will default to localhost)')}")
        logger.info(f"   PORT env var: {os.getenv('PORT', 'NOT_SET (will default to 8051)')}")
        
        # Determine transport mode
        transport = os.getenv("TRANSPORT")
        host = os.getenv("HOST", "localhost")
        port = int(os.getenv("PORT", "8051"))
        
        # Auto-detect transport based on how the script was invoked
        if not transport:
            # Check explicitly for docker exec stdio flag first
            if os.getenv("DOCKER_EXEC_STDIO") == "1":
                transport = "stdio"
                logger.info("🎯 Transport set to STDIO via DOCKER_EXEC_STDIO=1")
            # Then check if stdin is not a tty (piped input)
            elif not sys.stdin.isatty():
                transport = "stdio"
                logger.info("🎯 Transport set to STDIO via stdin.isatty() = False")
            else:
                transport = "sse"
                logger.info("🎯 Transport set to SSE (default - stdin is a tty)")
        else:
            logger.info(f"🎯 Transport explicitly set via TRANSPORT env var: {transport}")
        
        logger.info(f"🚀 FINAL CONFIGURATION:")
        logger.info(f"   Transport: {transport}")
        logger.info(f"   Host: {host}")
        logger.info(f"   Port: {port}")
        
        mcp_logger.info("🔥 Logfire initialized for MCP server")
        mcp_logger.info("🌟 Starting Archon MCP server", transport=transport)
        
        if transport == 'dual':
            # Dual mode: Run SSE server, stdio available via docker exec
            logger.info("🔀 DUAL MODE - SSE server + STDIO via docker exec")
            logger.info(f"🌐 SSE server: http://{host}:{port}/sse")
            logger.info(f"🌐 WebSocket: ws://{host}:{port}/ws") 
            logger.info("📡 STDIO available via: docker exec -i -e TRANSPORT=stdio archon-pyserver uv run python src/mcp_server.py")
            logger.info("   Web clients use SSE, IDE clients use docker exec with stdio")
            
            mcp_logger.info("🔀 Dual mode: SSE server starting", 
                          sse_url=f"http://{host}:{port}/sse",
                          stdio_via_exec=True)
            
            # Run SSE server (stdio connections come via separate docker exec processes)
            await mcp.run_sse_async()
                
        elif transport == 'sse':
            logger.info("🌐 SSE MODE - Starting Server-Sent Events transport only")
            logger.info(f"   SSE URL: http://{host}:{port}/sse")
            logger.info(f"   WebSocket URL: ws://{host}:{port}/ws")
            logger.info("   This mode is for web browser clients and HTTP-based connections")
            
            mcp_logger.info("🌐 SSE server starting", url=f"http://{host}:{port}/sse")
            await mcp.run_sse_async()
            
        elif transport == 'stdio':
            # Log to stderr in stdio mode to avoid contaminating stdout JSON-RPC stream
            print("📡 STDIO MODE - Starting Standard Input/Output transport only", file=sys.stderr)
            print("   This mode is for command-line clients like Cursor/Claude", file=sys.stderr)
            print("   All JSON-RPC communication happens via stdin/stdout", file=sys.stderr)
            print("   No HTTP server will be started", file=sys.stderr)
            
            # For stdio mode, ensure we're running the stdio transport
            # No prints to stdout in stdio mode - client expects pure JSON-RPC
            await mcp.run_stdio_async()
            
        else:
            error_msg = f"Unsupported transport: {transport}. Use 'dual', 'sse', or 'stdio'"
            logger.error(f"💥 {error_msg}")
            raise ValueError(error_msg)
            
    except Exception as e:
        # Handle errors appropriately based on transport mode
        transport = os.getenv("TRANSPORT", "dual")
        if transport == "stdio":
            print(f"💥 Fatal error in MCP server: {e}", file=sys.stderr)
        else:
            mcp_logger.error("💥 Fatal error in main", error=str(e), error_type=type(e).__name__)
            logger.error(f"💥 Fatal error in main: {e}")
            logger.error(traceback.format_exc())
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Archon MCP server stopped by user")
    except Exception as e:
        logger.error(f"💥 Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1) 
