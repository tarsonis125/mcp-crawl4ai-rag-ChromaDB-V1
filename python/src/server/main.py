"""
FastAPI Backend for Archon Knowledge Engine

This is the main entry point for the Archon backend API.
It uses a modular approach with separate API modules for different functionality.

Modules:
- settings_api: Settings and credentials management
- mcp_api: MCP server management and WebSocket streaming  
- knowledge_api: Knowledge base, crawling, and RAG operations
- projects_api: Project and task management with streaming
"""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any, Optional
import logging
from dataclasses import dataclass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Import Logfire configuration
from .config.logfire_config import setup_logfire, api_logger

# Import Socket.IO integration
from .socketio_app import create_socketio_app

# Import modular API routers
from .fastapi.settings_api import router as settings_router
from .fastapi.mcp_api import router as mcp_router
from .fastapi.knowledge_api import router as knowledge_router  
from .fastapi.projects_api import router as projects_router
from .fastapi.tests_api import router as tests_router
# from .fastapi.agent_chat_api import router as agent_chat_router  # TODO: Fix to use HTTP calls to agents service

# Import utilities and core classes
from .services.credential_service import initialize_credentials
from .utils import get_supabase_client

# Import missing dependencies that the modular APIs need
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig
    from sentence_transformers import CrossEncoder
except ImportError:
    # These are optional dependencies for full functionality
    AsyncWebCrawler = None
    BrowserConfig = None
    CrossEncoder = None

# Logger will be initialized after credentials are loaded
logger = logging.getLogger(__name__)

# Set up logging configuration to reduce noise
import uvicorn.logging

# Override uvicorn's access log format to be less verbose
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.setLevel(logging.WARNING)  # Only log warnings and errors, not every request

class CrawlingContext:
    """Context for direct crawling function calls."""
    
    def __init__(self):
        self.crawler: Optional[Any] = None
        self.supabase_client: Optional[Any] = None
        self.reranking_model: Optional[Any] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the crawling context."""
        if self._initialized:
            return
        
        try:
            # Create browser configuration if crawl4ai is available
            if AsyncWebCrawler and BrowserConfig:
                browser_config = BrowserConfig(
                    headless=True,
                    verbose=False
                )
                
                # Initialize the crawler
                self.crawler = AsyncWebCrawler(config=browser_config)
                await self.crawler.__aenter__()
            
            # Initialize Supabase client
            self.supabase_client = get_supabase_client()
            
            # Initialize cross-encoder model for reranking if enabled
            if os.getenv("USE_RERANKING", "false") == "true" and CrossEncoder:
                try:
                    self.reranking_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                except Exception as e:
                    logger.warning(f"Failed to load reranking model: {e}")
                    self.reranking_model = None
            
            self._initialized = True
            logger.info("✅ Crawling context initialized")
            
        except Exception as e:
            logger.error(f"Error initializing crawling context: {e}")
            # Don't raise - allow startup to continue without full crawling functionality
    
    async def cleanup(self):
        """Clean up the crawling context."""
        if self.crawler:
            try:
                await self.crawler.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error cleaning up crawler: {e}")
            finally:
                self.crawler = None
        
        self._initialized = False
    

# Global crawling context instance
crawling_context = CrawlingContext()

# Global flag to track if initialization is complete
_initialization_complete = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown tasks."""
    global _initialization_complete
    _initialization_complete = False
    
    # Startup
    logger.info("🚀 Starting Archon backend...")
    
    try:
        # Initialize credentials from database FIRST - this is the foundation for everything else
        await initialize_credentials()
        
        # Now that credentials are loaded, we can properly initialize logging
        # This must happen AFTER credentials so LOGFIRE_ENABLED is set from database
        setup_logfire(service_name="archon-backend")
        
        # Now we can safely use the logger
        logger.info("✅ Credentials initialized")
        api_logger.info("🔥 Logfire initialized for backend")
        
        # Initialize crawling context
        try:
            await crawling_context.initialize()
        except Exception as e:
            api_logger.warning("Could not fully initialize crawling context", error=str(e))
        
        # Make crawling context available to modules
        app.state.crawling_context = crawling_context
        
        # Initialize Socket.IO services
        try:
            # Import API modules to register their Socket.IO handlers
            from .fastapi import knowledge_api, projects_api  # agent_chat_api removed - TODO: Fix to use HTTP calls
            api_logger.info("✅ Socket.IO handlers imported from API modules")
        except Exception as e:
            api_logger.warning(f"Could not initialize Socket.IO services: {e}")
        
        # Initialize prompt service
        try:
            from .services.prompt_service import prompt_service
            await prompt_service.load_prompts()
            api_logger.info("✅ Prompt service initialized")
        except Exception as e:
            api_logger.warning(f"Could not initialize prompt service: {e}")
        
        # MCP Client functionality removed from architecture
        # Agents now use MCP tools directly
        
        # Mark initialization as complete
        _initialization_complete = True
        api_logger.info("🎉 Archon backend started successfully!")
        
    except Exception as e:
        api_logger.error("❌ Failed to start backend", error=str(e))
        raise
    
    yield
    
    # Shutdown
    _initialization_complete = False
    api_logger.info("🛑 Shutting down Archon backend...")
    
    try:
        # MCP Client cleanup not needed
        
        # Cleanup crawling context
        try:
            await crawling_context.cleanup()
        except Exception as e:
            api_logger.warning("Could not cleanup crawling context", error=str(e))
        
        api_logger.info("✅ Cleanup completed")
        
    except Exception as e:
        api_logger.error("❌ Error during shutdown", error=str(e))

# Create FastAPI application
app = FastAPI(
    title="Archon Knowledge Engine API",
    description="Backend API for the Archon knowledge management and project automation platform",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing WebSocket issue
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware to skip logging for health checks
@app.middleware("http")
async def skip_health_check_logs(request, call_next):
    # Skip logging for health check endpoints
    if request.url.path in ["/health", "/api/health"]:
        # Temporarily suppress the log
        import logging
        logger = logging.getLogger("uvicorn.access")
        old_level = logger.level
        logger.setLevel(logging.ERROR)
        response = await call_next(request)
        logger.setLevel(old_level)
        return response
    return await call_next(request)

# Include API routers
app.include_router(settings_router)
app.include_router(mcp_router)
# app.include_router(mcp_client_router)  # Removed - not part of new architecture
app.include_router(knowledge_router)
app.include_router(projects_router)
app.include_router(tests_router)
# app.include_router(agent_chat_router)  # TODO: Fix to use HTTP calls to agents service
# app.include_router(internal_router)  # Removed - internal API deleted

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "name": "Archon Knowledge Engine API",
        "version": "1.0.0",
        "description": "Backend API for knowledge management and project automation",
        "status": "healthy",
        "modules": [
            "settings",
            "mcp",
            "mcp-clients", 
            "knowledge",
            "projects"
        ]
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint that indicates true readiness including credential loading."""
    from datetime import datetime
    import os
    
    # Check if initialization is complete
    if not _initialization_complete:
        return {
            "status": "initializing",
            "service": "archon-backend",
            "timestamp": datetime.now().isoformat(),
            "message": "Backend is starting up, credentials loading...",
            "ready": False
        }
    
    # Check if credentials are actually loaded
    openai_key_available = bool(os.getenv("OPENAI_API_KEY"))
    
    return {
        "status": "healthy",
        "service": "archon-backend", 
        "timestamp": datetime.now().isoformat(),
        "ready": True,
        "credentials_loaded": True,
        "openai_key_available": openai_key_available
    }

# API health check endpoint (alias for /health at /api/health)
@app.get("/api/health")
async def api_health_check():
    """API health check endpoint - alias for /health."""
    return await health_check()

# Create Socket.IO app wrapper
# This wraps the FastAPI app with Socket.IO functionality
socket_app = create_socketio_app(app)

# Export the socket_app for uvicorn to use
# The socket_app still handles all FastAPI routes, but also adds Socket.IO support

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:socket_app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    ) 
