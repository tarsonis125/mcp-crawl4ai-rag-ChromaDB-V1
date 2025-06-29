"""
API Server for Archon - FastAPI microservice
Handles web crawling, document storage, and search operations
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
import uvicorn
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.server.config.settings import get_settings
from src.server.fastapi import api_router
from src.logfire_config import api_logger

settings = get_settings()

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins="*",
    logger=api_logger,
    engineio_logger=False
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    api_logger.info("API Service starting up...")
    yield
    api_logger.info("API Service shutting down...")

# Create FastAPI app
app = FastAPI(
    title="Archon API Service",
    description="Web crawling and document storage microservice",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(internal_router, prefix="/internal")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api"}

# Socket.IO event handlers for crawling progress
@sio.event
async def connect(sid, environ):
    api_logger.info(f"Client connected: {sid}")
    await sio.emit('connected', {'message': 'Connected to API service'}, room=sid)

@sio.event
async def disconnect(sid):
    api_logger.info(f"Client disconnected: {sid}")

# Create combined ASGI app
socket_app = socketio.ASGIApp(sio, app)

if __name__ == "__main__":
    uvicorn.run(
        "src.api.server:socket_app",
        host="0.0.0.0",
        port=int(os.getenv("API_PORT", 8080)),
        reload=os.getenv("ENV", "production") == "development"
    )