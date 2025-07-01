"""
Socket.IO Server Integration for Archon

Simple Socket.IO server setup with FastAPI integration.
All events are handled in projects_api.py using @sio.event decorators.
"""

import socketio
from fastapi import FastAPI
from typing import Optional
import logging

from .config.logfire_config import safe_logfire_info

logger = logging.getLogger(__name__)

# Create Socket.IO server with FastAPI integration
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins="*",  # TODO: Configure for production with specific origins
    logger=False,  # Disable verbose Socket.IO logging
    engineio_logger=False,  # Disable verbose Engine.IO logging
    # Performance settings
    max_http_buffer_size=1000000,  # 1MB
    ping_timeout=60,
    ping_interval=25,
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
    safe_logfire_info("Creating Socket.IO server", 
                 cors_origins="*", 
                 ping_timeout=60,
                 ping_interval=25)
    
    # Register basic connection handlers
    @sio.event
    async def connect(sid, environ):
        """Handle new Socket.IO connections."""
        client_address = environ.get('REMOTE_ADDR', 'unknown')
        safe_logfire_info("Socket.IO client connected", 
                     session_id=sid, 
                     client_address=client_address)
        logger.info(f"Socket.IO client connected: {sid} from {client_address}")
        
        # Send connection acknowledgment
        await sio.emit('connected', {'sid': sid}, to=sid)
    
    @sio.event
    async def disconnect(sid):
        """Handle Socket.IO disconnections."""
        safe_logfire_info("Socket.IO client disconnected", session_id=sid)
        logger.info(f"Socket.IO client disconnected: {sid}")
    
    @sio.event
    async def ping(sid):
        """Handle ping messages for connection health checks."""
        await sio.emit('pong', to=sid)
    
    # Create and return the Socket.IO ASGI app
    socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
    
    # Store the app reference for later use
    sio.app = app
    
    return socket_app