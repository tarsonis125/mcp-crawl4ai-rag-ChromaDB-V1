# WebSocket Refactor Plan - Socket.IO Migration

## Executive Summary

**Migration Strategy**: Replace the current custom WebSocket implementation with Socket.IO for improved reliability, automatic reconnection, and simplified development.

**Key Benefits**:
- ✅ Automatic connection lifecycle management
- ✅ Built-in reconnection with exponential backoff
- ✅ Room-based broadcasting and session management
- ✅ Transport fallback (WebSocket → HTTP Long Polling)
- ✅ Simplified codebase with less custom infrastructure
- ✅ Better error handling and debugging

## Current Architecture Issues

### Critical Problems Solved by Socket.IO

1. **Connection Lifecycle Problems**: Manual WebSocket cleanup causing stuck progress cards
2. **Memory Leaks**: Handlers accumulating without proper cleanup
3. **No Automatic Reconnection**: Custom reconnection logic fails after backend restarts
4. **Session Management**: Complex session ID tracking and validation
5. **Event Loop Blocking**: Current parallel processing conflicts with WebSocket health
6. **Multiple Connection Managers**: Inconsistent patterns across different services

## Socket.IO Architecture Design

### Backend (Python/FastAPI) Implementation

#### Core Socket.IO Integration

```python
# main.py or socket_app.py
import socketio
from fastapi import FastAPI

# Create Socket.IO server with FastAPI integration
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins="*",  # Configure for production
    logger=True,
    engineio_logger=True
)

app = FastAPI()

# Wrap FastAPI app with Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# Global Socket.IO instance for use across modules
def get_socketio_instance():
    return sio
```

#### Socket.IO Service Pattern (Best Practice)

```python
# services/socketio_service.py
from typing import Dict, Set, Any, Optional
import socketio
import asyncio
import logging

logger = logging.getLogger(__name__)

class SocketIOService:
    """Base service for Socket.IO event handling with best practices"""
    
    def __init__(self, sio: socketio.AsyncServer, namespace: str = "/"):
        self.sio = sio
        self.namespace = namespace
        self.rooms: Dict[str, Set[str]] = {}  # room_id -> set of session_ids
        
    async def join_room(self, sid: str, room: str):
        """Join a room with automatic tracking"""
        await self.sio.enter_room(sid, room, namespace=self.namespace)
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(sid)
        logger.info(f"Session {sid} joined room {room}")
        
    async def leave_room(self, sid: str, room: str):
        """Leave a room with cleanup"""
        await self.sio.leave_room(sid, room, namespace=self.namespace)
        if room in self.rooms:
            self.rooms[room].discard(sid)
            if not self.rooms[room]:
                del self.rooms[room]
        logger.info(f"Session {sid} left room {room}")
        
    async def broadcast_to_room(self, room: str, event: str, data: Any):
        """Broadcast to all clients in a room"""
        await self.sio.emit(event, data, room=room, namespace=self.namespace)
        
    async def send_to_session(self, sid: str, event: str, data: Any):
        """Send to specific session"""
        await self.sio.emit(event, data, to=sid, namespace=self.namespace)
        
    def register_events(self):
        """Register Socket.IO event handlers - override in subclasses"""
        pass
```

### Frontend (React/TypeScript) Implementation

#### Socket.IO Service Pattern (Best Practice)

```typescript
// services/SocketIOService.ts
import io, { Socket } from 'socket.io-client';

export interface SocketIOConfig {
  namespace?: string;
  autoConnect?: boolean;
  reconnection?: boolean;
  reconnectionAttempts?: number;
  reconnectionDelay?: number;
}

export class SocketIOService {
  private socket: Socket | null = null;
  private config: SocketIOConfig;
  private eventHandlers: Map<string, Function[]> = new Map();

  constructor(config: SocketIOConfig = {}) {
    this.config = {
      namespace: '/',
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      ...config
    };
  }

  connect(serverUrl?: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const url = serverUrl || `${window.location.protocol}//${window.location.hostname}:8080`;
      
      this.socket = io(`${url}${this.config.namespace}`, {
        autoConnect: this.config.autoConnect,
        reconnection: this.config.reconnection,
        reconnectionAttempts: this.config.reconnectionAttempts,
        reconnectionDelay: this.config.reconnectionDelay,
      });

      this.socket.on('connect', () => {
        console.log('✅ Socket.IO connected');
        resolve();
      });

      this.socket.on('connect_error', (error) => {
        console.error('❌ Socket.IO connection error:', error);
        reject(error);
      });

      this.socket.on('disconnect', (reason) => {
        console.log('🔌 Socket.IO disconnected:', reason);
      });

      // Re-register event handlers on reconnection
      this.socket.on('connect', () => {
        this.reregisterEventHandlers();
      });
    });
  }

  on(event: string, handler: Function): void {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, []);
    }
    this.eventHandlers.get(event)!.push(handler);
    
    if (this.socket) {
      this.socket.on(event, handler as any);
    }
  }

  emit(event: string, data?: any): void {
    if (this.socket) {
      this.socket.emit(event, data);
    }
  }

  joinRoom(room: string): void {
    this.emit('join_room', { room });
  }

  leaveRoom(room: string): void {
    this.emit('leave_room', { room });
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.eventHandlers.clear();
  }

  private reregisterEventHandlers(): void {
    if (!this.socket) return;
    
    for (const [event, handlers] of this.eventHandlers) {
      for (const handler of handlers) {
        this.socket.on(event, handler as any);
      }
    }
  }

  get connected(): boolean {
    return this.socket?.connected || false;
  }
}
```

## Services Migration Plan

### 1. **Crawl Progress Service** - HIGH PRIORITY

**Current Issues**: Connection cleanup, progress card stuck states, memory leaks

**Current Files**:
- Backend: `/api/knowledge-api.py` - `websocket_crawl_progress()` 
- Frontend: `crawlProgressServiceV2.ts`

**Socket.IO Implementation**:

```python
# Backend: services/crawl_progress_socketio.py
class CrawlProgressService(SocketIOService):
    def __init__(self, sio: socketio.AsyncServer):
        super().__init__(sio, namespace="/crawl")
        self.active_crawls: Dict[str, Dict] = {}
        self.register_events()
        
    def register_events(self):
        @self.sio.event(namespace=self.namespace)
        async def connect(sid, environ):
            logger.info(f"Crawl progress client connected: {sid}")
            
        @self.sio.event(namespace=self.namespace)
        async def join_crawl(sid, data):
            progress_id = data.get('progress_id')
            if progress_id:
                await self.join_room(sid, f"crawl_{progress_id}")
                
                # Send current progress if available
                if progress_id in self.active_crawls:
                    await self.send_to_session(sid, 'progress_update', 
                                             self.active_crawls[progress_id])
                
        @self.sio.event(namespace=self.namespace)
        async def disconnect(sid):
            logger.info(f"Crawl progress client disconnected: {sid}")
            # Automatic cleanup - no manual session tracking needed!
            
    async def update_progress(self, progress_id: str, progress_data: Dict):
        """Update progress for a specific crawl"""
        self.active_crawls[progress_id] = progress_data
        await self.broadcast_to_room(f"crawl_{progress_id}", 'progress_update', progress_data)
        
        # Auto-cleanup completed crawls
        if progress_data.get('status') in ['completed', 'error']:
            # Wait a bit for final UI updates, then cleanup
            asyncio.create_task(self._cleanup_crawl_after_delay(progress_id, 5.0))
            
    async def _cleanup_crawl_after_delay(self, progress_id: str, delay: float):
        """Clean up crawl data after delay"""
        await asyncio.sleep(delay)
        if progress_id in self.active_crawls:
            del self.active_crawls[progress_id]
        logger.info(f"Cleaned up crawl {progress_id}")
```

```typescript
// Frontend: services/CrawlProgressSocketIOService.ts
export class CrawlProgressSocketIOService extends SocketIOService {
  constructor() {
    super({ namespace: '/crawl' });
  }

  async subscribeToCrawlProgress(progressId: string, onProgress: (data: any) => void): Promise<void> {
    await this.connect();
    
    this.on('progress_update', onProgress);
    this.joinRoom(`crawl_${progressId}`);
    
    // Join specific crawl room
    this.emit('join_crawl', { progress_id: progressId });
  }

  unsubscribeFromCrawl(progressId: string): void {
    this.leaveRoom(`crawl_${progressId}`);
  }
}
```

### 2. **Agent Chat Service** - HIGH PRIORITY

**Current Issues**: Session lifecycle mismatches, reconnection failures, message duplication

**Current Files**:
- Backend: `/api/agent_chat_api.py` - `websocket_chat()`
- Frontend: `agentChatService.ts`

**Socket.IO Implementation**:

```python
# Backend: services/agent_chat_socketio.py
class AgentChatService(SocketIOService):
    def __init__(self, sio: socketio.AsyncServer):
        super().__init__(sio, namespace="/chat")
        self.active_sessions: Dict[str, Dict] = {}
        self.register_events()
        
    def register_events(self):
        @self.sio.event(namespace=self.namespace)
        async def connect(sid, environ):
            logger.info(f"Chat client connected: {sid}")
            
        @self.sio.event(namespace=self.namespace)
        async def join_session(sid, data):
            session_id = data.get('session_id')
            if session_id and self._validate_session(session_id):
                await self.join_room(sid, f"session_{session_id}")
                
                # Send session history only for new connections
                if session_id in self.active_sessions:
                    history = self.active_sessions[session_id].get('messages', [])
                    await self.send_to_session(sid, 'session_history', {'messages': history})
                    
        @self.sio.event(namespace=self.namespace)
        async def send_message(sid, data):
            session_id = data.get('session_id')
            message = data.get('message')
            
            if session_id and message:
                # Process message and broadcast to room
                response = await self._process_chat_message(session_id, message)
                await self.broadcast_to_room(f"session_{session_id}", 'new_message', response)
                
    async def broadcast_message(self, session_id: str, message_data: Dict):
        """Broadcast message to all clients in session"""
        await self.broadcast_to_room(f"session_{session_id}", 'new_message', message_data)
```

### 3. **Project Tasks WebSocket** - MEDIUM PRIORITY

**Current Issues**: Task update broadcasting, real-time synchronization

**Current Files**:
- Backend: `/api/projects_api.py` - `task_updates_websocket()`
- Frontend: Part of `projectService.ts`

### 4. **MCP Server Logs** - MEDIUM PRIORITY  

**Current Issues**: Log streaming, connection management

**Current Files**:
- Backend: `/api/mcp_api.py` - `websocket_log_stream()`
- Frontend: `mcpServerService.ts`

### 5. **Test Execution Streaming** - LOW PRIORITY

**Current Issues**: Real-time test output streaming

**Current Files**:
- Backend: `/api/tests_api.py` - `test_output_websocket()`
- Frontend: `testService.ts`

### 6. **Project Creation Progress** - LOW PRIORITY

**Current Files**:
- Backend: `/api/projects_api.py` - `websocket_project_creation_progress()`
- Frontend: `projectCreationProgressService.ts`

### 7. **Knowledge Items Stream** - LOW PRIORITY

**Current Files**:
- Backend: `/api/knowledge_api.py` - `websocket_knowledge_items()`
- Frontend: Part of `knowledgeBaseService.ts`

## Implementation Strategy

### Phase 1: Setup & Core Infrastructure (Week 1)

1. **Install Dependencies**
   ```bash
   # Backend
   pip install python-socketio
   
   # Frontend  
   npm install socket.io-client
   ```

2. **Create Socket.IO Integration Layer**
   - `src/socketio_app.py` - Main Socket.IO server setup
   - `src/services/base_socketio_service.py` - Base service class
   - `frontend/src/services/SocketIOService.ts` - Base frontend service

3. **Setup Dual Operation**
   - Run Socket.IO alongside existing WebSocket infrastructure
   - No immediate breaking changes

### Phase 2: High-Priority Migrations (Week 2-3)

1. **Crawl Progress Service** (3 days)
   - Migrate backend crawl progress WebSocket to Socket.IO
   - Update frontend crawl progress service
   - Test with knowledge base crawling

2. **Agent Chat Service** (3 days)
   - Migrate chat WebSocket to Socket.IO
   - Update frontend chat service
   - Test chat functionality and session recovery

### Phase 3: Medium-Priority Migrations (Week 4)

1. **Project Tasks WebSocket** (2 days)
2. **MCP Server Logs** (2 days)

### Phase 4: Low-Priority Migrations (Week 5)

1. **Test Execution Streaming** (1 day)
2. **Project Creation Progress** (1 day)
3. **Knowledge Items Stream** (1 day)

### Phase 5: Cleanup & Optimization (Week 6)

1. **Remove Legacy WebSocket Infrastructure**
   - Delete old WebSocket services
   - Remove custom connection managers
   - Clean up frontend services

2. **Performance Optimization**
   - Configure Socket.IO production settings
   - Add monitoring and logging
   - Load testing

## Production Configuration

### Backend Socket.IO Configuration

```python
# Production settings
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=["https://yourdomain.com"],
    logger=False,  # Disable debug logging in production
    engineio_logger=False,
    # Performance settings
    max_http_buffer_size=1000000,  # 1MB
    ping_timeout=60,
    ping_interval=25,
)
```

### Frontend Socket.IO Configuration

```typescript
// Production settings
const socket = io('wss://yourdomain.com', {
  transports: ['websocket', 'polling'], // WebSocket preferred, polling fallback
  upgrade: true,
  reconnection: true,
  reconnectionAttempts: 5,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  maxReconnectionAttempts: 5,
  timeout: 20000,
});
```

## Benefits Summary

### Immediate Benefits
- ✅ **Automatic Reconnection**: No more manual reconnection logic
- ✅ **Session Recovery**: Built-in session persistence and recovery
- ✅ **Room Management**: Simplified group broadcasting
- ✅ **Error Handling**: Better error detection and handling

### Long-term Benefits  
- ✅ **Reduced Complexity**: ~70% reduction in WebSocket-related code
- ✅ **Better Reliability**: Battle-tested library with millions of deployments
- ✅ **Easier Debugging**: Built-in logging and debugging tools
- ✅ **Future Scaling**: Easy horizontal scaling with Redis adapter

### Development Benefits
- ✅ **Faster Development**: Less time debugging connection issues
- ✅ **Consistent Patterns**: Standardized event handling across all services
- ✅ **Better Testing**: Easier to mock and test Socket.IO events

## Risk Mitigation

### Backwards Compatibility
- Maintain existing WebSocket endpoints during migration
- Gradual service-by-service migration
- Feature flags for Socket.IO vs WebSocket selection

### Rollback Plan
- Keep existing WebSocket code until full migration is validated
- Database compatibility maintained
- Quick rollback switches available

### Testing Strategy
- Unit tests for each Socket.IO service
- Integration tests for end-to-end flows
- Load testing for concurrent connections
- Manual testing for reconnection scenarios

## Success Metrics

### Technical Metrics
- 🎯 Zero connection cleanup issues
- 🎯 <2 second reconnection time after server restart  
- 🎯 99.9% message delivery success rate
- 🎯 50%+ reduction in WebSocket-related bug reports

### Code Quality Metrics
- 🎯 70% reduction in WebSocket-related code lines
- 🎯 Elimination of custom connection managers
- 🎯 100% test coverage for Socket.IO services

### User Experience Metrics
- 🎯 Zero stuck progress cards
- 🎯 Seamless chat experience during reconnections
- 🎯 Real-time updates work consistently

## Timeline Summary

- **Week 1**: Infrastructure setup and dual operation
- **Week 2-3**: Critical services migration (Crawl Progress, Agent Chat)
- **Week 4**: Medium priority services
- **Week 5**: Low priority services  
- **Week 6**: Cleanup and optimization

**Total Timeline**: 6 weeks with incremental rollout and minimal disruption