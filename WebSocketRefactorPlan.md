# WebSocket Refactor Plan

## Background

The current WebSocket implementation in Archon has several critical issues:

1. **Connection Lifecycle Problems**: WebSocket connections are not properly disconnected after crawl completion, leading to stuck progress cards when trying to re-crawl after deletion
2. **Memory Leaks**: Handlers accumulate in the singleton services without proper cleanup
3. **Lack of Centralization**: Multiple WebSocket instances created without global connection tracking
4. **No Connection Health Monitoring**: Missing heartbeat/ping mechanisms to detect stale connections
5. **Event Loop Blocking**: Current parallel processing doesn't properly yield control, causing WebSocket disconnections

## Current Architecture Analysis

### Frontend (TypeScript/React)
- **websocketService.ts**: Contains multiple singleton WebSocket services (knowledgeWebSocket, crawlWebSocket, etc.)
- **EnhancedWebSocketService**: Provides connection management but lacks proper lifecycle hooks
- **crawlProgressServiceV2**: Manages progress tracking but doesn't clean up connections properly

### Backend (Python/FastAPI)
- **CrawlProgressManager**: In-memory storage of active crawls and WebSocket connections
- **No asyncio.Queue pattern**: Missing the recommended pattern from best practices
- **No broadcast mechanism**: Each WebSocket connection handled individually

### Key Issues Identified

1. **Frontend Issues**:
   ```typescript
   // Current: No cleanup when progress completes
   handleProgressComplete(data: CrawlProgressData) {
     // Updates UI but doesn't disconnect WebSocket
   }
   ```

2. **Backend Issues**:
   ```python
   # Current: WebSockets remain in memory after crawl completion
   self.progress_websockets[progress_id].append(websocket)
   # Never cleaned up unless client disconnects
   ```

## Redis vs asyncio.Queue Analysis

### Why People Use Redis

1. **Multi-Process Support**: When running multiple Uvicorn workers, in-memory state isn't shared
2. **Persistence**: Progress survives server restarts
3. **Pub/Sub**: Built-in broadcasting to all connected clients
4. **Horizontal Scaling**: Enables load balancing across multiple servers
5. **Background Jobs**: Perfect for cron jobs and task queues

### asyncio.Queue Benefits

1. **Simplicity**: No external dependencies
2. **Performance**: In-memory operations are faster
3. **Native Integration**: Works seamlessly with asyncio event loop

### Our Requirements Analysis

**Do we need Redis?**
- ✅ **Yes for**: Background cron jobs for document updates
- ✅ **Yes for**: Future horizontal scaling
- ✅ **Yes for**: Preventing progress loss on server restart
- ❌ **No if**: We stay with single-process deployment
- ❌ **No if**: We don't mind losing progress on restart

## Python Package Analysis

### Current Dependencies Review

**Core packages** (30 total):
- **Web Framework**: FastAPI, Uvicorn
- **AI/ML**: OpenAI, sentence-transformers, pydantic-ai
- **Database**: Supabase, asyncpg
- **Document Processing**: pypdf2, pdfplumber, python-docx
- **Monitoring**: Logfire
- **MCP**: mcp
- **Web Crawling**: crawl4ai

### Overlapping Functionality

1. **PDF Processing**: Both pypdf2 and pdfplumber (could standardize on pdfplumber)
2. **HTTP Clients**: httpx and requests (could standardize on httpx for async)
3. **Environment**: dotenv and python-dotenv (duplicate)

### Redis Addition Impact

Adding Redis would introduce:
- `redis==5.0.1` or `redis[hiredis]==5.0.1` (with C extension for performance)
- Minimal complexity increase
- Would enable removal of in-memory state management code

## Proposed Architecture

### 1. Centralized WebSocket Manager (Backend)

```python
class CentralWebSocketManager:
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.connections: Dict[str, Set[WebSocket]] = {}
        self.queues: Dict[str, asyncio.Queue] = {}
        
    async def register_connection(self, channel: str, ws: WebSocket):
        """Register WebSocket with automatic cleanup"""
        # Add to connections
        # Set TTL in Redis
        # Start heartbeat task
        
    async def broadcast(self, channel: str, message: dict):
        """Broadcast to all connections in channel"""
        if self.redis:
            await self.redis.publish(channel, json.dumps(message))
        else:
            # In-memory broadcast
```

### 2. Progress Worker Pattern (Backend)

```python
async def progress_worker(queue: asyncio.Queue, manager: CentralWebSocketManager):
    """Background worker processing progress updates"""
    while True:
        update = await queue.get()
        await manager.broadcast(update['channel'], update['data'])
        
        # Auto-cleanup completed tasks
        if update['data']['status'] in ['completed', 'error']:
            await manager.cleanup_channel(update['channel'])
```

### 3. Frontend Connection Lifecycle

```typescript
class ManagedWebSocketService {
  private cleanup: (() => void)[] = [];
  
  async connect(progressId: string): Promise<void> {
    // Connect
    await this.ws.connect(`/ws/progress/${progressId}`);
    
    // Register cleanup
    this.cleanup.push(() => this.disconnect(progressId));
    
    // Auto-disconnect on completion
    this.onMessage('completed', () => {
      setTimeout(() => this.disconnect(progressId), 2000);
    });
  }
  
  disconnect(progressId: string): void {
    // Clean up handlers
    // Close connection
    // Clear state
  }
}
```

## Background Cron Jobs Architecture

If we add Redis, we can implement:

```python
# Document update checker
async def check_document_updates():
    """Run every hour to check for stale documents"""
    async with redis.client() as r:
        sources = await r.smembers("sources:active")
        for source in sources:
            last_updated = await r.get(f"source:{source}:updated")
            if needs_update(last_updated):
                await r.lpush("crawl:queue", source)

# Worker to process update queue
async def update_worker():
    while True:
        source = await redis.blpop("crawl:queue")
        await crawl_and_update(source)
```

## Implementation Steps

### Phase 1: Fix Immediate Issues (No Redis)

1. **Frontend Cleanup** (2 hours)
   - Add `disconnectProgress()` call in `handleProgressComplete`
   - Implement proper cleanup in `useEffect` return
   - Add connection state checks before re-crawl

2. **Backend Auto-Cleanup** (2 hours)
   - Add auto-removal of WebSockets after crawl completion
   - Implement 5-minute timeout for stale connections
   - Add connection tracking by progressId

3. **Add Heartbeat Mechanism** (1 hour)
   - Frontend: Send ping every 30s
   - Backend: Close connections that don't respond

### Phase 2: Centralized WebSocket Manager (No Redis)

1. **Create CentralWebSocketManager** (3 hours)
   - Singleton pattern with proper lifecycle
   - Channel-based organization
   - Automatic cleanup on completion

2. **Implement asyncio.Queue Pattern** (2 hours)
   - Create worker tasks for progress updates
   - Non-blocking broadcast mechanism
   - Proper event loop yielding

3. **Refactor Existing Services** (4 hours)
   - Migrate all WebSocket endpoints to use manager
   - Update frontend services to use new patterns
   - Add comprehensive logging

### Phase 3: Redis Integration (Optional)

1. **Add Redis Support** (2 hours)
   - Add redis to dependencies
   - Create Redis connection pool
   - Add Redis pub/sub handlers

2. **Implement Background Jobs** (3 hours)
   - Document update checker
   - Crawl queue processor
   - Scheduled task runner

3. **Multi-Process Support** (2 hours)
   - Replace in-memory state with Redis
   - Add Redis-based broadcasting
   - Enable multiple Uvicorn workers

## Package Cleanup Recommendations

1. **Remove duplicates**:
   - Remove `dotenv==0.9.9` (keep `python-dotenv`)
   - Standardize on `httpx` (remove `requests` from main deps)

2. **Consider removing** (if not actively used):
   - `pypdf2` (use `pdfplumber` only)
   - `python-jose` (if not doing JWT auth)

3. **Add for better architecture**:
   - `redis[hiredis]>=5.0.1` (for Phase 3)
   - `apscheduler>=3.10.4` (for cron jobs)

## Decision Matrix

| Feature | asyncio.Queue Only | With Redis |
|---------|-------------------|------------|
| Single Process | ✅ Works perfectly | ✅ Works |
| Multi-Process | ❌ Not supported | ✅ Works |
| Horizontal Scale | ❌ Not possible | ✅ Supported |
| Background Jobs | 🟡 Limited | ✅ Full support |
| Complexity | ✅ Low | 🟡 Medium |
| Dependencies | ✅ None | 🟡 Redis server |
| Performance | ✅ Fastest | ✅ Fast enough |
| Progress Persistence | ❌ Lost on restart | ✅ Survives restart |

## Recommendation

1. **Immediate**: Implement Phase 1 fixes to solve the current WebSocket cleanup issues
2. **Next Sprint**: Implement Phase 2 for better architecture without Redis
3. **Future**: Add Redis when we need:
   - Background document update jobs
   - Multi-process deployment
   - Horizontal scaling
   - Progress persistence

The Redis addition would simplify our architecture and enable new features, but it's not required to fix the current issues. The investment is worth it for the background job capabilities alone.