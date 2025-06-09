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

# Import Logfire configuration
from src.logfire_config import setup_logfire, mcp_logger

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
    Manages the shared resources lifecycle - yields immediately for fast startup.
    Following official MCP patterns from the Python SDK documentation.
    """
    logger.info("🚀 Starting Archon MCP server lifespan...")
    
    # FIRST THING: CACHE OPENAI KEY IN MEMORY!
    cached_openai_key = None
    logger.info("🔑 CACHING OPENAI API KEY IN MEMORY...")
    try:
        from src.credential_service import credential_service
        
        # Get OpenAI API key and cache it
        if hasattr(credential_service, '_cache') and credential_service._cache_initialized:
            cached_value = credential_service._cache.get("OPENAI_API_KEY")
            if isinstance(cached_value, dict) and cached_value.get("is_encrypted"):
                encrypted_value = cached_value.get("encrypted_value")
                if encrypted_value:
                    try:
                        cached_openai_key = credential_service._decrypt_value(encrypted_value)
                    except Exception:
                        pass
            elif cached_value:
                cached_openai_key = str(cached_value)
        
        # Fallback to environment variable
        if not cached_openai_key:
            cached_openai_key = os.getenv("OPENAI_API_KEY")
        
        logger.info(f"✓ OpenAI key cached in memory: {'YES' if cached_openai_key else 'NO'}")
        
    except Exception as e:
        logger.warning(f"⚠ Failed to cache OpenAI key from credentials: {e} - using env fallback")
        cached_openai_key = os.getenv("OPENAI_API_KEY")
    
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
        
        # STORE CACHED OPENAI KEY IN CONTEXT FOR DIRECT ACCESS
        context.cached_openai_key = cached_openai_key
        
        # Set ready status
        context.health_status["status"] = "ready"
        context.health_status["database_ready"] = True
        context.health_status["openai_key_cached"] = bool(cached_openai_key)
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
        
        transport = os.getenv("TRANSPORT", "sse")
        host = os.getenv("HOST", "localhost")
        port = int(os.getenv("PORT", "8051"))
        
        # Only print when not using stdio to avoid contaminating JSON-RPC stream
        if transport != "stdio":
            mcp_logger.info("🔥 Logfire initialized for MCP server")
            mcp_logger.info("🌟 Starting Archon MCP server", transport=transport)
        
        if transport == 'sse':
            if transport != "stdio":
                mcp_logger.info("🌐 SSE server starting", url=f"http://{host}:{port}/sse")
            await mcp.run_sse_async()
        elif transport == 'stdio':
            # No prints in stdio mode - client expects pure JSON-RPC
            await mcp.run_stdio_async()
        else:
            raise ValueError(f"Unsupported transport: {transport}. Use 'sse' or 'stdio'")
            
    except Exception as e:
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
