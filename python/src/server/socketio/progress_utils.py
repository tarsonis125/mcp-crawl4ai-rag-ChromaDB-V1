"""
Progress Tracking Utilities using Socket.IO

This module provides helper functions for progress tracking using Socket.IO rooms
instead of the old CrawlProgressManager.
"""

from typing import Dict, Any
from datetime import datetime

from ..socketio_app import get_socketio_instance, NAMESPACE_CRAWL
from ..config.logfire_config import logfire

# Get the Socket.IO instance
sio = get_socketio_instance()

# Track active crawls for initial state sending
active_crawls: Dict[str, Dict[str, Any]] = {}


async def start_crawl_progress(progress_id: str, initial_data: Dict[str, Any]) -> None:
    """Start tracking a new crawl operation."""
    # Ensure logs is always a list
    if 'logs' not in initial_data:
        initial_data['logs'] = []
    elif isinstance(initial_data.get('logs'), str):
        initial_data['logs'] = [initial_data['logs']]
    
    crawl_data = {
        'status': 'starting',
        'percentage': 0,
        'start_time': datetime.now().isoformat(),
        'logs': initial_data.get('logs', ['Starting crawl...']),
        'progressId': progress_id,
        **initial_data
    }
    
    # Store in active crawls
    active_crawls[progress_id] = crawl_data
    
    # Emit initial progress
    await sio.emit('progress_update', crawl_data, room=progress_id, namespace=NAMESPACE_CRAWL)
    logfire.info(f"Started crawl progress tracking for {progress_id}")


async def update_crawl_progress(progress_id: str, update_data: Dict[str, Any]) -> None:
    """Update crawling progress and notify connected clients."""
    if progress_id not in active_crawls:
        return
    
    # Update progress data
    active_crawls[progress_id].update(update_data)
    active_crawls[progress_id]['updated_at'] = datetime.now().isoformat()
    
    # Add to logs if message provided
    if 'log' in update_data:
        active_crawls[progress_id]['logs'].append(update_data['log'])
    
    # Emit progress update
    await sio.emit('progress_update', active_crawls[progress_id], room=progress_id, namespace=NAMESPACE_CRAWL)


async def complete_crawl_progress(progress_id: str, completion_data: Dict[str, Any]) -> None:
    """Mark crawl as completed and notify clients."""
    if progress_id not in active_crawls:
        return
    
    active_crawls[progress_id].update({
        'status': 'completed',
        'percentage': 100,
        'completed_at': datetime.now().isoformat(),
        **completion_data
    })
    
    if 'log' in completion_data:
        active_crawls[progress_id]['logs'].append(completion_data['log'])
    
    # Emit completion
    await sio.emit('progress_complete', active_crawls[progress_id], room=progress_id, namespace=NAMESPACE_CRAWL)
    
    # Clean up after 5 minutes
    # Note: In production, this should use a proper task scheduler
    import asyncio
    await asyncio.sleep(300)
    active_crawls.pop(progress_id, None)


async def error_crawl_progress(progress_id: str, error_message: str) -> None:
    """Mark crawl as failed and notify clients."""
    if progress_id not in active_crawls:
        return
    
    active_crawls[progress_id].update({
        'status': 'error',
        'error': error_message,
        'completed_at': datetime.now().isoformat()
    })
    
    active_crawls[progress_id]['logs'].append(f"Error: {error_message}")
    
    # Emit error
    await sio.emit('progress_error', active_crawls[progress_id], room=progress_id, namespace=NAMESPACE_CRAWL)


def get_active_crawl(progress_id: str) -> Dict[str, Any]:
    """Get active crawl data if available."""
    return active_crawls.get(progress_id)


# Note: WebSocket connection waiting is no longer needed with Socket.IO
# Clients will automatically receive updates when they join the room