"""
Socket.IO Event Handlers for Archon

This module contains all Socket.IO event handlers for real-time communication.
Keeps the main projects_api.py file focused on REST endpoints.
"""

# Removed direct logging import - using unified config
import asyncio
from ..socketio_app import get_socketio_instance
from ..services.projects.project_service import ProjectService
from ..services.projects.source_linking_service import SourceLinkingService

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
    
    # Get detailed room info for debugging
    try:
        room_sids = []
        all_rooms = {}
        if hasattr(sio.manager, 'rooms'):
            # Get all rooms for all namespaces
            for namespace in sio.manager.rooms:
                all_rooms[namespace] = {}
                for room, sids in sio.manager.rooms[namespace].items():
                    all_rooms[namespace][room] = list(sids)
                    if namespace == '/' and room == progress_id:
                        room_sids = list(sids)
        
        print(f"📢 [SOCKETIO DEBUG] Broadcasting to room '{progress_id}'")
        print(f"📢 [SOCKETIO DEBUG] Room {progress_id} has {len(room_sids)} subscribers: {room_sids}")
        print(f"📢 [SOCKETIO DEBUG] All rooms in namespace '/': {list(all_rooms.get('/', {}).keys())}")
        
        # Log if the room doesn't exist
        if not room_sids:
            print(f"⚠️  [SOCKETIO DEBUG] WARNING: Room '{progress_id}' has no subscribers!")
            logger.warning(f"Room '{progress_id}' has no subscribers when broadcasting crawl progress")
            
    except Exception as e:
        print(f"📢 [SOCKETIO DEBUG] Could not get room info: {e}")
        import traceback
        traceback.print_exc()
    
    # Log the data we're broadcasting
    logger.info(f"📢 [SOCKETIO] Broadcasting crawl_progress to room: {progress_id}")
    logger.info(f"📢 [SOCKETIO] Data keys: {list(data.keys())}")
    logger.info(f"📢 [SOCKETIO] Progress percentage: {data.get('percentage', 'N/A')}")
    logger.info(f"📢 [SOCKETIO] Status: {data.get('status', 'N/A')}")
    
    # Detailed debug logging
    print(f"📢 [SOCKETIO DEBUG] Full broadcast data:")
    for key, value in data.items():
        if key in ['logs', 'workers']:  # Truncate long lists
            print(f"  - {key}: {type(value).__name__} with {len(value) if isinstance(value, (list, dict)) else 'N/A'} items")
        else:
            print(f"  - {key}: {value}")
    
    # Emit the event
    await sio.emit('crawl_progress', data, room=progress_id)
    # Yield control to event loop to help with Socket.IO delivery
    await asyncio.sleep(0)
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
    data['percentage'] = 100  # Ensure we show 100% when complete
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
    headers = {k: v for k, v in environ.items() if k.startswith('HTTP_')}
    
    logger.info(f'🔌 [SOCKETIO] Client connected: {sid} from {client_address}')
    logger.info(f'🔌 [SOCKETIO] Query params: {query_params}')
    logger.info(f'🔌 [SOCKETIO] User-Agent: {headers.get("HTTP_USER_AGENT", "unknown")}')
    
    print(f'🔌 [SOCKETIO DEBUG] New connection:')
    print(f'  - SID: {sid}')
    print(f'  - Address: {client_address}')
    print(f'  - Query: {query_params}')
    print(f'  - Transport: {headers.get("HTTP_UPGRADE", "unknown")}')
    
    # Parse query params to check for session_id
    if query_params:
        import urllib.parse
        params = urllib.parse.parse_qs(query_params)
        session_id = params.get('session_id', [None])[0]
        if session_id:
            print(f'  - Session ID: {session_id}')
    
    # Log total connected clients
    try:
        if hasattr(sio.manager, 'rooms'):
            all_sids = set()
            for namespace_rooms in sio.manager.rooms.values():
                for room_sids in namespace_rooms.values():
                    all_sids.update(room_sids)
            print(f'📊 [SOCKETIO DEBUG] Total connected clients: {len(all_sids)}')
    except:
        pass

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
    
    # Send confirmation - let frontend request initial tasks via API
    await sio.emit('joined_project', {'project_id': project_id}, to=sid)

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
async def crawl_subscribe(sid, data=None):
    """Subscribe to crawl progress updates."""
    logger.info(f"📥 [SOCKETIO] Received crawl_subscribe from {sid} with data: {data}")
    print(f"📥 [SOCKETIO DEBUG] crawl_subscribe event - sid: {sid}, data: {data}")
    progress_id = data.get('progress_id') if data else None
    if not progress_id:
        logger.error(f"❌ [SOCKETIO] No progress_id in crawl_subscribe from {sid}")
        await sio.emit('error', {'message': 'progress_id required'}, to=sid)
        return
    
    # Enter the room
    await sio.enter_room(sid, progress_id)
    logger.info(f"✅ [SOCKETIO] Client {sid} subscribed to crawl progress room: {progress_id}")
    print(f"✅ Client {sid} subscribed to crawl progress {progress_id}")
    
    # Verify room membership
    try:
        # Get all rooms for this client
        client_rooms = []
        if hasattr(sio, 'rooms') and callable(sio.rooms):
            try:
                rooms_result = sio.rooms(sid)
                # Handle different return types from rooms()
                if rooms_result is None:
                    client_rooms = []
                elif isinstance(rooms_result, (list, set, tuple)):
                    client_rooms = list(rooms_result)
                elif isinstance(rooms_result, dict):
                    client_rooms = list(rooms_result.keys())
                else:
                    # Assume it's a single room ID
                    client_rooms = [str(rooms_result)]
            except Exception as e:
                logger.debug(f"Could not get rooms for sid {sid}: {e}")
        elif hasattr(sio.manager, 'rooms'):
            # Alternative method to check rooms
            for room, sids in sio.manager.rooms.get('/', {}).items():
                if sid in sids:
                    client_rooms.append(room)
        
        print(f"📥 [SOCKETIO DEBUG] Client {sid} is now in rooms: {client_rooms}")
        print(f"📥 [SOCKETIO DEBUG] Room '{progress_id}' membership confirmed: {progress_id in client_rooms}")
        
        # Double-check room membership by listing all members
        if hasattr(sio.manager, 'rooms'):
            room_members = list(sio.manager.rooms.get('/', {}).get(progress_id, []))
            print(f"📥 [SOCKETIO DEBUG] Room '{progress_id}' now has {len(room_members)} members: {room_members}")
            print(f"📥 [SOCKETIO DEBUG] Client {sid} is in room: {sid in room_members}")
            
    except Exception as e:
        print(f"📥 [SOCKETIO DEBUG] Error checking room membership: {e}")
        import traceback
        traceback.print_exc()
    
    # Send acknowledgment
    ack_data = {'progress_id': progress_id, 'status': 'subscribed'}
    print(f"📤 [SOCKETIO DEBUG] Sending acknowledgment: {ack_data}")
    await sio.emit('crawl_subscribe_ack', ack_data, to=sid)
    logger.info(f"📤 [SOCKETIO] Sent subscription acknowledgment to {sid} for {progress_id}")
    
    # Test broadcast to the room immediately
    print(f"🧪 [SOCKETIO DEBUG] Testing broadcast to room '{progress_id}'...")
    test_data = {
        'progressId': progress_id,
        'status': 'subscribed',
        'message': f'Test broadcast after subscription',
        'percentage': 0
    }
    await sio.emit('crawl_progress', test_data, room=progress_id)
    print(f"🧪 [SOCKETIO DEBUG] Test broadcast sent to room '{progress_id}'")

@sio.event
async def crawl_unsubscribe(sid, data):
    """Unsubscribe from crawl progress updates."""
    progress_id = data.get('progress_id')
    if progress_id:
        await sio.leave_room(sid, progress_id)
        logger.info(f"📤 [SOCKETIO] Client {sid} left crawl progress room: {progress_id}")
        print(f"🛑 Client {sid} unsubscribed from crawl progress {progress_id}")