"""
Socket.IO Server Integration for Archon

This module provides the core Socket.IO server setup and integration
with FastAPI for real-time WebSocket communication.
"""

import socketio
from fastapi import FastAPI
from typing import Optional
import logging

from .logfire_config import logfire

logger = logging.getLogger(__name__)

# Create Socket.IO server with FastAPI integration
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins="*",  # TODO: Configure for production with specific origins
    logger=True,
    engineio_logger=True,
    # Performance settings
    max_http_buffer_size=1000000,  # 1MB
    ping_timeout=60,
    ping_interval=25,
    # Use default path /socket.io/ for proper proxy support
)

# Global Socket.IO instance for use across modules
_socketio_instance: Optional[socketio.AsyncServer] = None

def get_socketio_instance() -> socketio.AsyncServer:
    """Get the global Socket.IO server instance."""
    global _socketio_instance
    if _socketio_instance is None:
        _socketio_instance = sio
    return _socketio_instance

def create_socketio_app(app: FastAPI) -> socketio.ASGIApp:
    """
    Wrap FastAPI app with Socket.IO ASGI app.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        Socket.IO ASGI app that wraps the FastAPI app
    """
    # Log Socket.IO server creation
    logfire.info("Creating Socket.IO server", 
                 cors_origins="*", 
                 ping_timeout=60,
                 ping_interval=25)
    
    # Register global error handlers
    @sio.event
    async def connect(sid, environ):
        """Handle new Socket.IO connections."""
        client_address = environ.get('REMOTE_ADDR', 'unknown')
        headers = environ.get('asgi', {}).get('headers', [])
        
        logfire.info("Socket.IO client connected", 
                     session_id=sid, 
                     client_address=client_address)
        logger.info(f"Socket.IO client connected: {sid} from {client_address}")
        
        # Send connection acknowledgment
        await sio.emit('connected', {'sid': sid}, to=sid)
    
    @sio.event
    async def disconnect(sid):
        """Handle Socket.IO disconnections."""
        logfire.info("Socket.IO client disconnected", session_id=sid)
        logger.info(f"Socket.IO client disconnected: {sid}")
    
    @sio.event
    async def ping(sid):
        """Handle ping messages for connection health checks."""
        await sio.emit('pong', to=sid)
        logger.debug(f"Ping/Pong with client: {sid}")
    
    # Create and return the Socket.IO ASGI app
    # IMPORTANT: other_asgi_app parameter ensures non-Socket.IO requests are forwarded to FastAPI
    socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
    
    # Store the app reference for later use
    sio.app = app
    
    return socket_app

# Namespace constants
NAMESPACE_CRAWL = "/crawl"
NAMESPACE_CHAT = "/chat"
NAMESPACE_TASKS = "/tasks"
NAMESPACE_LOGS = "/logs"
NAMESPACE_TESTS = "/tests"
NAMESPACE_PROJECT = "/project"
NAMESPACE_KNOWLEDGE = "/knowledge"

def register_namespaces():
    """
    Register all Socket.IO namespaces.
    This should be called after all services have been initialized.
    """
    namespaces = [
        NAMESPACE_CRAWL,
        NAMESPACE_CHAT,
        NAMESPACE_TASKS,
        NAMESPACE_LOGS,
        NAMESPACE_TESTS,
        NAMESPACE_PROJECT,
        NAMESPACE_KNOWLEDGE
    ]
    
    for namespace in namespaces:
        logfire.info(f"Registered Socket.IO namespace: {namespace}")
        logger.info(f"Registered Socket.IO namespace: {namespace}")