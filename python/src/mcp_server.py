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

try:
    from src.utils import get_supabase_client
except ImportError as e:
    logger.error(f"Failed to import utils: {e}")
    raise

# Load environment variables from the project root .env file
project_root = Path(__file__).resolve().parent.parent
dotenv_path = project_root / '.env'
load_dotenv(dotenv_path, override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/mcp_server.log', mode='a') if os.path.exists('/tmp') else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

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
        response = client.table("app_credentials").select("key").limit(1).execute()
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
    Manages the shared resources lifecycle for all modules.
    
    Initializes and cleans up resources that are shared across
    all MCP tool modules in the Archon system.
    """
    crawler = None
    supabase_client = None
    reranking_model = None
    
    try:
        logger.info("🚀 Starting Archon MCP server lifespan...")
        
        # Create browser configuration
        browser_config = BrowserConfig(
            headless=True,
            verbose=False
        )
        
        # Initialize the crawler with error handling
        try:
            crawler = AsyncWebCrawler(config=browser_config)
            await crawler.__aenter__()
            logger.info("✓ AsyncWebCrawler initialized successfully")
        except Exception as e:
            logger.error(f"✗ Failed to initialize AsyncWebCrawler: {e}")
            raise
        
        # Initialize Supabase client with error handling
        try:
            supabase_client = get_supabase_client()
            # Test the connection
            supabase_client.table("projects").select("count", count="exact").execute()
            logger.info("✓ Supabase client initialized and connected successfully")
        except Exception as e:
            logger.error(f"✗ Failed to initialize Supabase client: {e}")
            raise
        
        # Initialize cross-encoder model for reranking if enabled
        if os.getenv("USE_RERANKING", "false") == "true":
            try:
                reranking_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                logger.info("✓ Reranking model loaded successfully")
            except Exception as e:
                logger.warning(f"⚠ Failed to load reranking model: {e} - continuing without reranking")
                reranking_model = None
        else:
            logger.info("📝 Reranking disabled")
        
        context = ArchonContext(
            crawler=crawler,
            supabase_client=supabase_client,
            reranking_model=reranking_model
        )
        
        logger.info("🎉 Archon context initialized successfully")
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
    mcp = FastMCP(
        "archon-mcp-server",
        description="Modular MCP server for Archon: RAG, Tasks, and UI tools",
        lifespan=archon_lifespan,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8051"))
    )
    logger.info(f"✓ FastMCP server created - host: {os.getenv('HOST', '0.0.0.0')}, port: {int(os.getenv('PORT', '8051'))}")
except Exception as e:
    logger.error(f"✗ Failed to create FastMCP server: {e}")
    raise

# Health check endpoint
@mcp.tool()
async def health_check(ctx: Context) -> str:
    """
    Perform a comprehensive health check of all MCP server components.
    
    Returns:
        JSON string with health status of all services
    """
    import json
    
    try:
        context = ctx.request_context.lifespan_context
        
        # Run the health check (FIXED: removed asyncio.run() call)
        await perform_health_checks(context)
        
        return json.dumps({
            "success": True,
            "health": context.health_status,
            "uptime_seconds": time.time() - context.startup_time,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return json.dumps({
            "success": False,
            "error": f"Health check failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })

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
    
    # Import and register Project module  
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
        transport = os.getenv("TRANSPORT", "sse")
        host = os.getenv("HOST", "localhost")
        port = int(os.getenv("PORT", "8051"))
        
        # Only print when not using stdio to avoid contaminating JSON-RPC stream
        if transport != "stdio":
            logger.info(f"🌟 Starting Archon MCP server with transport: {transport}")
        
        if transport == 'sse':
            if transport != "stdio":
                logger.info(f"🌐 SSE server will be available at: http://{host}:{port}/sse")
            await mcp.run_sse_async()
        elif transport == 'stdio':
            # No prints in stdio mode - client expects pure JSON-RPC
            await mcp.run_stdio_async()
        else:
            raise ValueError(f"Unsupported transport: {transport}. Use 'sse' or 'stdio'")
            
    except Exception as e:
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
