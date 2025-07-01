"""
Crawl Progress Namespace for Socket.IO

This namespace handles all crawl progress tracking using Socket.IO rooms.
Each progress_id becomes a room that clients can join to receive updates.
"""

import socketio
from typing import Dict, Any
import logging

from ..config.logfire_config import logfire

logger = logging.getLogger(__name__)


class CrawlNamespace(socketio.AsyncNamespace):
    """Socket.IO namespace for crawl progress tracking."""
    
    def __init__(self, namespace=None):
        super().__init__(namespace)
    
    async def on_connect(self, sid, environ):
        """Handle client connection to crawl namespace."""
        logfire.info("Client connected to crawl namespace", sid=sid)
        await self.emit('connected', {'message': 'Connected to crawl progress'}, to=sid)
    
    async def on_disconnect(self, sid):
        """Handle client disconnection from crawl namespace."""
        logfire.info("Client disconnected from crawl namespace", sid=sid)
    
    async def on_subscribe(self, sid, data):
        """Subscribe to crawl progress updates for a specific progress_id."""
        progress_id = data.get('progress_id')
        if not progress_id:
            await self.emit('error', {'message': 'progress_id required'}, to=sid)
            return
        
        # Join the room for this progress ID
        self.enter_room(sid, progress_id)
        logfire.info(f"Client {sid} subscribed to progress {progress_id}")
        
        # Import here to avoid circular dependency
        from .progress_utils import get_active_crawl
        
        # Send current progress if available
        active_crawl = get_active_crawl(progress_id)
        if active_crawl:
            await self.emit('progress_update', active_crawl, to=sid)
    
    async def on_unsubscribe(self, sid, data):
        """Unsubscribe from crawl progress updates."""
        progress_id = data.get('progress_id')
        if progress_id:
            self.leave_room(sid, progress_id)
            logfire.info(f"Client {sid} unsubscribed from progress {progress_id}")