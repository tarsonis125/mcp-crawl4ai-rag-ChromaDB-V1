"""
Socket.IO Event Handlers for Archon

This module contains all Socket.IO event handlers for real-time communication.
Keeps the main projects_api.py file focused on REST endpoints.
"""

# Removed direct logging import - using unified config
from ..socketio_app import get_socketio_instance
from ..utils import get_supabase_client
from ..services.projects import ProjectService, TaskService, SourceLinkingService

from ..config.logfire_config import get_logger

logger = get_logger(__name__)

# Get Socket.IO instance
sio = get_socketio_instance()
logger.info(f"🔗 [SOCKETIO] Socket.IO instance ID: {id(sio)}")

# Broadcast helper functions
async def broadcast_task_update(project_id: str, event_type: str, task_data: dict):
    """Broadcast task updates to project room."""
    await sio.emit(event_type, task_data, room=project_id)
    logger.info(f"Broadcasted {event_type} to project {project_id}")

async def broadcast_project_update():
    """Broadcast project list to subscribers."""
    try:
        project_service = ProjectService()
        success, result = project_service.list_projects()
        
        if not success:
            logger.error(f"Failed to get projects for broadcast: {result}")
            return
        
        # Use SourceLinkingService to format projects with sources
        source_service = SourceLinkingService()
        formatted_projects = source_service.format_projects_with_sources(result["projects"])
        
        await sio.emit('projects_update', {'projects': formatted_projects}, room='project_list')
        logger.info(f"Broadcasted project list update with {len(formatted_projects)} projects")
    except Exception as e:
        logger.error(f"Failed to broadcast project update: {e}")

async def broadcast_progress_update(progress_id: str, progress_data: dict):
    """Broadcast progress updates to progress room."""
    await sio.emit('project_progress', progress_data, room=progress_id)
    logger.debug(f"Broadcasted progress update for {progress_id}")

async def broadcast_crawl_progress(progress_id: str, data: dict):
    """Broadcast crawl progress to subscribers."""
    # Ensure progressId is included in the data
    data['progressId'] = progress_id
    
    # Get room info for debugging
    try:
        room_sids = []
        if hasattr(sio.manager, 'rooms'):
            room_sids = list(sio.manager.rooms.get('/', {}).get(progress_id, []))
        print(f"📢 [SOCKETIO DEBUG] Room {progress_id} has {len(room_sids)} subscribers: {room_sids}")
    except Exception as e:
        print(f"📢 [SOCKETIO DEBUG] Could not get room info: {e}")
    
    # Log the room we're broadcasting to
    logger.info(f"📢 [SOCKETIO] Broadcasting crawl_progress to room: {progress_id}, data keys: {list(data.keys())}")
    print(f"📢 [SOCKETIO DEBUG] Broadcasting data: {data}")
    await sio.emit('crawl_progress', data, room=progress_id)
    logger.info(f"✅ [SOCKETIO] Broadcasted crawl progress for {progress_id}")

# Crawl progress helper functions for knowledge API
async def start_crawl_progress(progress_id: str, data: dict):
    """Start crawl progress tracking."""
    data['status'] = 'starting'
    await broadcast_crawl_progress(progress_id, data)

async def update_crawl_progress(progress_id: str, data: dict):
    """Update crawl progress."""
    await broadcast_crawl_progress(progress_id, data)

async def complete_crawl_progress(progress_id: str, data: dict):
    """Complete crawl progress tracking."""
    data['status'] = 'completed'
    await broadcast_crawl_progress(progress_id, data)

async def error_crawl_progress(progress_id: str, error_msg: str):
    """Signal crawl progress error."""
    data = {
        'status': 'error',
        'error': error_msg,
        'progressId': progress_id
    }
    await broadcast_crawl_progress(progress_id, data)

@sio.event
async def connect(sid, environ):
    """Handle client connection."""
    client_address = environ.get('REMOTE_ADDR', 'unknown')
    query_params = environ.get('QUERY_STRING', '')
    logger.info(f'🔌 [SOCKETIO] Client connected: {sid} from {client_address}, query: {query_params}')
    print(f'🔌 Client connected: {sid} from {client_address}')

@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    # Log which rooms the client was in before disconnecting
    rooms = sio.rooms(sid) if hasattr(sio, 'rooms') else []
    logger.info(f'🔌 [SOCKETIO] Client disconnected: {sid}, was in rooms: {rooms}')
    print(f'🔌 Client disconnected: {sid}, was in rooms: {rooms}')

@sio.event
async def join_project(sid, data):
    """Join a project room to receive task updates."""
    project_id = data.get('project_id')
    if not project_id:
        await sio.emit('error', {'message': 'project_id required'}, to=sid)
        return
    
    # Join the room for this project
    await sio.enter_room(sid, project_id)
    logger.info(f"📥 [SOCKETIO] Client {sid} joined project room: {project_id}")
    print(f"✅ Client {sid} joined project {project_id}")
    
    # Send initial tasks for this project using TaskService
    try:
        task_service = TaskService()
        success, result = task_service.list_tasks(
            project_id=project_id,
            include_closed=True  # Send all tasks initially
        )
        
        if success:
            tasks = result.get("tasks", [])
            await sio.emit('initial_tasks', tasks, to=sid)
            print(f"📤 Sent {len(tasks)} initial tasks to client {sid}")
        else:
            await sio.emit('error', {'message': result.get("error", "Failed to load tasks")}, to=sid)
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, to=sid)

@sio.event
async def leave_project(sid, data):
    """Leave a project room."""
    project_id = data.get('project_id')
    if project_id:
        await sio.leave_room(sid, project_id)
        print(f"🛑 Client {sid} left project {project_id}")

@sio.event
async def subscribe_projects(sid, data=None):
    """Subscribe to project list updates."""
    await sio.enter_room(sid, 'project_list')
    logger.info(f"📥 [SOCKETIO] Client {sid} joined project_list room")
    print(f"✅ Client {sid} subscribed to project list")
    
    # Send current project list using ProjectService
    try:
        project_service = ProjectService()
        success, result = project_service.list_projects()
        
        if not success:
            await sio.emit('error', {'message': result.get("error", "Failed to load projects")}, to=sid)
            return
        
        # Use SourceLinkingService to format projects with sources
        source_service = SourceLinkingService()
        formatted_projects = source_service.format_projects_with_sources(result["projects"])
        
        await sio.emit('projects_update', {'projects': formatted_projects}, to=sid)
        print(f"📤 Sent {len(formatted_projects)} projects to client {sid}")
        
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, to=sid)

@sio.event
async def unsubscribe_projects(sid, data=None):
    """Unsubscribe from project list updates."""
    await sio.leave_room(sid, 'project_list')
    print(f"🛑 Client {sid} unsubscribed from project list")

@sio.event
async def subscribe_progress(sid, data):
    """Subscribe to project creation progress."""
    logger.info(f"🔔 [SOCKETIO] Received subscribe_progress from {sid} with data: {data}")
    progress_id = data.get('progress_id')
    if not progress_id:
        logger.error(f"🔔 [SOCKETIO] No progress_id provided by {sid}")
        await sio.emit('error', {'message': 'progress_id required'}, to=sid)
        return
    
    await sio.enter_room(sid, progress_id)
    logger.info(f"📥 [SOCKETIO] Client {sid} joined progress room: {progress_id}")
    
    # Send current progress state if operation exists
    try:
        from ..services.projects.progress_service import progress_service
        current_status = progress_service.get_operation_status(progress_id)
        if current_status:
            logger.info(f"📤 [SOCKETIO] Sending current progress state to new subscriber {sid}: {current_status}")
            # Send the current state immediately to the new subscriber
            current_status_copy = current_status.copy()
            current_status_copy['progressId'] = progress_id
            
            # Convert datetime to ISO string for JSON serialization
            if 'start_time' in current_status_copy and hasattr(current_status_copy['start_time'], 'isoformat'):
                current_status_copy['start_time'] = current_status_copy['start_time'].isoformat()
            
            await sio.emit('project_progress', current_status_copy, to=sid)
        else:
            logger.warning(f"📤 [SOCKETIO] No progress operation found for {progress_id}")
    except Exception as e:
        logger.error(f"📤 [SOCKETIO] Error sending current progress state: {e}")
    
    print(f"✅ Client {sid} subscribed to progress {progress_id}")

@sio.event
async def unsubscribe_progress(sid, data):
    """Unsubscribe from project creation progress."""
    progress_id = data.get('progress_id')
    if progress_id:
        await sio.leave_room(sid, progress_id)
        print(f"🛑 Client {sid} unsubscribed from progress {progress_id}")

@sio.event
async def crawl_subscribe(sid, data):
    """Subscribe to crawl progress updates."""
    logger.info(f"📥 [SOCKETIO] Received crawl_subscribe from {sid} with data: {data}")
    print(f"📥 [SOCKETIO DEBUG] crawl_subscribe event - sid: {sid}, data: {data}")
    progress_id = data.get('progress_id')
    if not progress_id:
        logger.error(f"❌ [SOCKETIO] No progress_id in crawl_subscribe from {sid}")
        await sio.emit('error', {'message': 'progress_id required'}, to=sid)
        return
    
    await sio.enter_room(sid, progress_id)
    logger.info(f"✅ [SOCKETIO] Client {sid} subscribed to crawl progress room: {progress_id}")
    print(f"✅ Client {sid} subscribed to crawl progress {progress_id}")
    
    # Get current rooms for this client
    try:
        rooms = sio.rooms(sid) if hasattr(sio, 'rooms') else []
        print(f"📥 [SOCKETIO DEBUG] Client {sid} is now in rooms: {rooms}")
    except:
        pass
    
    # Send acknowledgment
    await sio.emit('crawl_subscribe_ack', {'progress_id': progress_id, 'status': 'subscribed'}, to=sid)

@sio.event
async def crawl_unsubscribe(sid, data):
    """Unsubscribe from crawl progress updates."""
    progress_id = data.get('progress_id')
    if progress_id:
        await sio.leave_room(sid, progress_id)
        logger.info(f"📤 [SOCKETIO] Client {sid} left crawl progress room: {progress_id}")
        print(f"🛑 Client {sid} unsubscribed from crawl progress {progress_id}")