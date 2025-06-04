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
from contextlib import asynccontextmanager
from typing import Any
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import modular API routers
from .api.settings_api import router as settings_router
from .api.mcp_api import router as mcp_router
from .api.knowledge_api import router as knowledge_router  
from .api.projects_api import router as projects_router

# Import utilities  
from .credential_service import initialize_credentials

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown tasks."""
    # Startup
    logger.info("🚀 Starting Archon backend...")
    
    try:
        # Initialize credentials from database
        await initialize_credentials()
        logger.info("✅ Credentials initialized")
        
        # Additional startup tasks can go here
        
        logger.info("🎉 Archon backend started successfully!")
        
    except Exception as e:
        logger.error(f"❌ Failed to start backend: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Archon backend...")
    
    try:
        # Cleanup tasks can go here
        logger.info("✅ Cleanup completed")
        
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")

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
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(settings_router)
app.include_router(mcp_router)
app.include_router(knowledge_router)
app.include_router(projects_router)

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
            "knowledge",
            "projects"
        ]
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "archon-backend",
        "timestamp": "2024-01-01T00:00:00Z"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    ) 