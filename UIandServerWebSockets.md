# WebSocket Communication Patterns & Best Practices

## Overview

Archon implements real-time communication using WebSocket connections for streaming progress updates, server logs, and live data synchronization between the Python backend and React frontend. This document provides comprehensive patterns, examples, and best practices for implementing WebSocket communication in full-stack applications.

## Table of Contents

1. [WebSocket Endpoints](#-websocket-endpoints)
2. [Python Backend Patterns](#-python-backend-websocket-patterns)
3. [React Frontend Patterns](#-react-frontend-websocket-patterns)
4. [Best Practices & Common Pitfalls](#-best-practices--common-pitfalls)
5. [Testing WebSocket Connections](#-testing-websocket-connections)
6. [Troubleshooting Guide](#-troubleshooting-guide)

---

## 🔌 WebSocket Endpoints

| Endpoint | Purpose | Status | Pattern |
|----------|---------|--------|---------|
| `/api/mcp/logs/stream` | MCP Server logs streaming | ✅ Working | Server-to-Client Broadcast |
| `/api/crawl-progress/{progress_id}` | Crawl progress updates | ✅ Working | Progress Tracking Pattern |
| `/api/knowledge-items/stream` | Knowledge base updates | ✅ Working | Data Synchronization |

---

## 🐍 Python Backend WebSocket Patterns

### Pattern 1: Progress Tracking with Callbacks

**Use Case**: Real-time progress updates during long-running operations (crawling, processing)

```python
class CrawlProgressManager:
    def __init__(self):
        self.active_crawls: Dict[str, Dict[str, Any]] = {}
        self.progress_websockets: Dict[str, List[WebSocket]] = {}
    
    async def add_websocket(self, progress_id: str, websocket: WebSocket) -> None:
        """Add WebSocket connection for progress updates"""
        # CRITICAL: Accept WebSocket connection FIRST
        await websocket.accept()
        
        if progress_id not in self.progress_websockets:
            self.progress_websockets[progress_id] = []
        
        self.progress_websockets[progress_id].append(websocket)
        
        # Send current progress if available
        if progress_id in self.active_crawls:
            data = self.active_crawls[progress_id].copy()
            data['progressId'] = progress_id
            
            # Convert datetime objects for JSON serialization
            if 'start_time' in data and hasattr(data['start_time'], 'isoformat'):
                data['start_time'] = data['start_time'].isoformat()
            
            await websocket.send_json({
                "type": "crawl_progress",
                "data": data
            })
    
    async def update_progress(self, progress_id: str, update_data: Dict[str, Any]) -> None:
        """Update progress and broadcast to connected clients"""
        if progress_id not in self.active_crawls:
            return
        
        self.active_crawls[progress_id].update(update_data)
        await self._broadcast_progress(progress_id)
    
    async def _broadcast_progress(self, progress_id: str) -> None:
        """Broadcast progress to all connected WebSocket clients"""
        if progress_id not in self.progress_websockets:
            print(f"DEBUG: Broadcasting progress ({self.active_crawls[progress_id].get('percentage', 0)}%) - No WebSocket connections found")
            return
        
        progress_data = self.active_crawls.get(progress_id, {}).copy()
        progress_data['progressId'] = progress_id
        
        # Serialize datetime objects
        if 'start_time' in progress_data and hasattr(progress_data['start_time'], 'isoformat'):
            progress_data['start_time'] = progress_data['start_time'].isoformat()
        
        message = {
            "type": "crawl_progress" if progress_data.get('status') != 'completed' else "crawl_completed",
            "data": progress_data
        }
        
        print(f"DEBUG: Broadcasting message: {progress_data.get('status', 'unknown')} ({progress_data.get('percentage', 0)}%) - Sending to {len(self.progress_websockets[progress_id])} connections")
        
        # Send to all connected clients with error handling
        disconnected = []
        for websocket in self.progress_websockets[progress_id]:
            try:
                await websocket.send_json(message)
                print(f"DEBUG: Successfully sent progress update via WebSocket")
            except Exception as e:
                print(f"DEBUG: Failed to send WebSocket message: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected WebSockets
        for ws in disconnected:
            self.remove_websocket(progress_id, ws)
    
    def remove_websocket(self, progress_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection"""
        if progress_id in self.progress_websockets:
            try:
                self.progress_websockets[progress_id].remove(websocket)
                if not self.progress_websockets[progress_id]:
                    del self.progress_websockets[progress_id]
            except ValueError:
                pass
```

### Pattern 2: Server-to-Client Broadcasting

**Use Case**: Server logs, system status updates, general notifications

```python
class MCPServerManager:
    def __init__(self):
        self.log_websockets: List[WebSocket] = []
        self.logs: deque = deque(maxlen=1000)
    
    def _add_log(self, level: str, message: str):
        """Add log entry and broadcast to connected WebSockets"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level,
            'message': message
        }
        self.logs.append(log_entry)
        
        # Broadcast asynchronously
        asyncio.create_task(self._broadcast_log(log_entry))
    
    async def _broadcast_log(self, log_entry: Dict[str, Any]):
        """Broadcast log entry to all connected WebSockets"""
        disconnected = []
        for ws in self.log_websockets:
            try:
                await ws.send_json(log_entry)
            except Exception:
                disconnected.append(ws)
        
        # Remove disconnected WebSockets
        for ws in disconnected:
            self.log_websockets.remove(ws)
    
    async def add_websocket(self, websocket: WebSocket):
        """Add WebSocket for log streaming"""
        await websocket.accept()
        self.log_websockets.append(websocket)
        
        # Send recent logs to new connection
        for log in list(self.logs)[-50:]:
            try:
                await websocket.send_json(log)
            except Exception:
                break
    
    def remove_websocket(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        try:
            self.log_websockets.remove(websocket)
        except ValueError:
            pass
```

### Pattern 3: Progress Callback Integration

**Use Case**: Integrating progress callbacks with long-running MCP functions

```python
# In API wrapper
async def _perform_crawl_with_progress(progress_id: str, request: KnowledgeItemRequest):
    """Perform crawl with real-time progress tracking"""
    
    # Create progress callback
    async def progress_callback(status: str, percentage: int, message: str, **kwargs):
        """Callback for real-time progress updates from crawling functions"""
        await progress_manager.update_progress(progress_id, {
            'status': status,
            'percentage': percentage,
            'currentUrl': kwargs.get('currentUrl', str(request.url)),
            'totalPages': kwargs.get('totalPages', 0),
            'processedPages': kwargs.get('processedPages', 0),
            'log': message,
            **kwargs
        })
    
    # Pass callback to MCP function
    ctx.progress_callback = progress_callback
    
    # Call crawling function with progress support
    result = await mcp_smart_crawl_url(ctx=ctx, url=str(request.url))

# In MCP function
async def smart_crawl_url(ctx: Context, url: str) -> str:
    """Crawl URL with progress reporting"""
    
    # Get progress callback if available
    progress_callback = getattr(ctx, 'progress_callback', None)
    
    async def report_progress(status: str, percentage: int, message: str, **kwargs):
        """Helper to report progress if callback available"""
        if progress_callback:
            await progress_callback(status, percentage, message, **kwargs)
    
    # Report actual crawling progress
    await report_progress('analyzing', 5, f'Analyzing URL type: {url}')
    
    # URL type detection and handling...
    if 'sitemap' in url.lower():
        await report_progress('sitemap', 10, 'Detected sitemap, extracting URLs...')
        # Process sitemap
    else:
        await report_progress('webpage', 10, 'Detected webpage, starting recursive crawl...')
        # Process webpage
    
    await report_progress('crawling', 15, f'Found {total_urls} URLs, starting crawl...')
    
    # Batch crawling with progress
    if is_sitemap:
        results = await crawl_batch_with_progress(
            crawler, urls, max_concurrent, progress_callback, 15, 60
        )
    else:
        results = await crawl_recursive_with_progress(
            crawler, [url], max_depth, max_concurrent, progress_callback, 15, 60
        )
    
    await report_progress('processing', 65, f'Processing {len(results)} pages into chunks...')
    # Process and chunk content...
    
    await report_progress('storing', 80, 'Storing content in database...')
    # Store in database...
    
    await report_progress('completed', 100, f'Successfully crawled {len(results)} pages')
    
    return result
```

---

## ⚛️ React Frontend WebSocket Patterns

### Pattern 1: Service-Based WebSocket Management

**File**: `services/crawlProgressService.ts`

```typescript
interface CrawlProgressData {
  progressId: string;
  status: string;
  percentage: number;
  currentUrl?: string;
  totalPages?: number;
  processedPages?: number;
  log?: string;
}

class CrawlProgressService {
  private connections: Map<string, WebSocket> = new Map();
  
  streamProgress(
    progressId: string, 
    onProgress: (data: CrawlProgressData) => void,
    options: { autoReconnect?: boolean; reconnectDelay?: number } = {}
  ): void {
    const wsUrl = `ws://localhost:8080/api/crawl-progress/${progressId}`;
    
    const connect = () => {
      const ws = new WebSocket(wsUrl);
      this.connections.set(progressId, ws);
      
      ws.onopen = () => {
        console.log(`🚀 WebSocket connected for progress: ${progressId}`);
      };
      
      ws.onmessage = (event) => {
        try {
          console.log(`📨 RAW WebSocket message received:`, event.data);
          const message = JSON.parse(event.data);
          console.log(`📨 Parsed WebSocket message:`, message);
          
          // Handle different message types
          if (message.type === 'crawl_progress' || message.type === 'crawl_completed') {
            console.log(`🎯 Calling progress callback with data:`, message.data);
            onProgress(message.data);
          } else if (message.type === 'ping') {
            // Heartbeat - connection alive
            console.log(`💓 Heartbeat received`);
            return;
          } else {
            console.log(`🤷 Unknown message type: ${message.type}`);
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };
      
      ws.onclose = (event) => {
        console.log(`🔌 WebSocket closed for ${progressId}:`, event.code);
        this.connections.delete(progressId);
        
        // Auto-reconnect for non-normal closures
        if (options.autoReconnect && event.code !== 1000) {
          console.log(`🔄 Reconnecting in ${options.reconnectDelay || 5000}ms...`);
          setTimeout(connect, options.reconnectDelay || 5000);
        }
      };
      
      ws.onerror = (error) => {
        console.error(`❌ WebSocket error for ${progressId}:`, error);
      };
    };
    
    connect();
  }
  
  disconnect(progressId: string): void {
    const ws = this.connections.get(progressId);
    if (ws) {
      ws.close(1000); // Normal closure
      this.connections.delete(progressId);
    }
  }
  
  disconnectAll(): void {
    this.connections.forEach((ws, progressId) => {
      ws.close(1000);
    });
    this.connections.clear();
  }
}

export const crawlProgressService = new CrawlProgressService();
```

### Pattern 2: Component Integration with Progress Tracking

**File**: `pages/KnowledgeBasePage.tsx`

```typescript
const KnowledgeBasePage = () => {
  const [progressItems, setProgressItems] = useState<CrawlProgressData[]>([]);
  
  const handleStartCrawl = (progressId: string, initialData: Partial<CrawlProgressData>) => {
    console.log(`Starting crawl tracking for: ${progressId}`);
    
    // Add initial progress item
    const newProgressItem: CrawlProgressData = {
      progressId,
      status: 'starting',
      percentage: 0,
      logs: ['Starting crawl...'],
      ...initialData
    };
    
    setProgressItems(prev => [...prev, newProgressItem]);
    
    // Set up progress streaming BEFORE any potential race conditions
    const progressCallback = (data: CrawlProgressData) => {
      console.log(`📈 Progress callback called with:`, data);
      
      if (data.progressId === progressId) {
        // Update progress state
        setProgressItems(prev => 
          prev.map(item => 
            item.progressId === progressId ? data : item
          )
        );
        
        // Handle completion
        if (data.status === 'completed') {
          console.log(`✅ Crawl completed for ${progressId}`);
          setTimeout(() => {
            setProgressItems(prev => 
              prev.filter(item => item.progressId !== progressId)
            );
          }, 2000); // Remove after 2 seconds
        }
      }
    };
    
    // Start streaming with auto-reconnect
    crawlProgressService.streamProgress(progressId, progressCallback, {
      autoReconnect: true,
      reconnectDelay: 5000
    });
  };
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      crawlProgressService.disconnectAll();
    };
  }, []);
  
  return (
    <div>
      {/* Knowledge Base content */}
      
      {/* Progress Cards */}
      <div className="space-y-4">
        {progressItems.map((progressData) => (
          <CrawlingProgressCard 
            key={progressData.progressId}
            progressData={progressData}
            onComplete={(data) => {
              console.log(`Crawl completed:`, data);
              // Handle completion if needed
            }}
            onError={(error) => {
              console.error(`Crawl error:`, error);
              showToast('Crawl failed: ' + error, 'error');
            }}
          />
        ))}
      </div>
    </div>
  );
};
```

### Pattern 3: Progress Card Component

**File**: `components/CrawlingProgressCard.tsx`

```typescript
interface CrawlingProgressCardProps {
  progressData: CrawlProgressData;
  onComplete?: (data: CrawlProgressData) => void;
  onError?: (error: string) => void;
  onRetry?: () => void;
}

export const CrawlingProgressCard = ({ 
  progressData, 
  onComplete, 
  onError, 
  onRetry 
}: CrawlingProgressCardProps) => {
  // Use props directly - no local state to avoid conflicts
  const { status, percentage, currentUrl, log, error } = progressData;
  
  // Handle completion events
  useEffect(() => {
    if (status === 'completed' && onComplete) {
      onComplete(progressData);
    } else if (status === 'error' && onError) {
      onError(error || 'Unknown error');
    }
  }, [status, progressData, onComplete, onError, error]);
  
  return (
    <Card className="relative overflow-hidden">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
          {status === 'completed' ? (
            <CheckCircle className="w-5 h-5 text-green-500" />
          ) : status === 'error' ? (
            <XCircle className="w-5 h-5 text-red-500" />
          ) : (
            <Globe className="w-5 h-5 text-blue-500" />
          )}
        </div>
        
        <div className="flex-1">
          <h3 className="text-sm font-medium text-gray-800 dark:text-white">
            {status === 'completed' ? 'Crawling Complete' : 'Crawling in progress...'}
          </h3>
          <p className="text-xs text-gray-500 dark:text-zinc-400 truncate">
            {currentUrl || 'Processing...'}
          </p>
        </div>
        
        <div className="text-right">
          <span className="text-lg font-bold text-blue-600 dark:text-blue-400">
            {percentage}%
          </span>
        </div>
      </div>
      
      {/* Progress Bar */}
      <div className="w-full bg-gray-200 dark:bg-zinc-800 rounded-full h-2 mb-3">
        <div 
          className="bg-gradient-to-r from-blue-500 to-blue-600 h-2 rounded-full transition-all duration-500"
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
      
      {/* Current Status */}
      {log && (
        <div className="text-xs text-gray-600 dark:text-zinc-400 mb-2">
          {log}
        </div>
      )}
      
      {/* Error State */}
      {status === 'error' && onRetry && (
        <div className="flex justify-end">
          <Button onClick={onRetry} variant="ghost" size="sm">
            <RotateCcw className="w-4 h-4 mr-1" />
            Retry
          </Button>
        </div>
      )}
    </Card>
  );
};
```

---

## 🔧 Best Practices & Common Pitfalls

### ✅ Do's

1. **Always Accept WebSocket First**: Call `await websocket.accept()` before any send operations
2. **Handle Datetime Serialization**: Convert datetime objects to ISO strings for JSON
3. **Implement Reconnection Logic**: Auto-reconnect on non-normal closures (code !== 1000)
4. **Use Progress IDs**: Unique identifiers for tracking multiple concurrent operations  
5. **Clean Up Connections**: Remove disconnected WebSockets from collections
6. **Send Initial State**: When client connects, send current progress if available
7. **Use Callbacks for Integration**: Pass progress callbacks from API layer to business logic
8. **Handle Race Conditions**: Set up WebSocket connections before starting async operations

### ❌ Don'ts

1. **Don't Ignore Connection Errors**: Always handle `onclose` and `onerror` events
2. **Don't Hardcode Progress**: Base percentages on actual work completed
3. **Don't Mix Local and Prop State**: Use either props OR local state, not both
4. **Don't Block WebSocket Sends**: Use try-catch around WebSocket operations
5. **Don't Forget Cleanup**: Always disconnect WebSockets on component unmount
6. **Don't Send Unserializable Data**: Ensure all data is JSON-serializable

### 🎯 Architecture Principles

1. **Separation of Concerns**: WebSocket services separate from UI components
2. **Progress Callback Pattern**: Business logic reports progress via callbacks
3. **Event-Driven Updates**: UI reacts to WebSocket events, not polling
4. **Graceful Degradation**: System works without WebSockets (polling fallback)
5. **Real-Time First**: Design for real-time, add caching as optimization

---

## 🔬 Testing WebSocket Connections

### Manual Testing with wscat

```bash
# Test WebSocket endpoint directly
wscat -c ws://localhost:8080/api/crawl-progress/test-id

# Expected response:
# {"type": "connection_established", "data": {"progressId": "test-id", "status": "waiting"}}
```

### Backend Testing

```python
# Test progress manager
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_progress_manager_websocket():
    manager = CrawlProgressManager()
    mock_websocket = AsyncMock()
    
    # Test adding websocket
    await manager.add_websocket("test-123", mock_websocket)
    
    # Verify accept was called
    mock_websocket.accept.assert_called_once()
    
    # Test broadcasting progress
    await manager.update_progress("test-123", {
        "status": "crawling",
        "percentage": 50,
        "log": "Processing pages..."
    })
    
    # Verify message was sent
    mock_websocket.send_json.assert_called()
```

### Frontend Testing

```typescript
// Test WebSocket service
describe('CrawlProgressService', () => {
  it('should connect and receive messages', (done) => {
    const mockProgressData = {
      progressId: 'test-123',
      status: 'crawling',
      percentage: 50
    };
    
    const onProgress = jest.fn((data) => {
      expect(data).toEqual(mockProgressData);
      done();
    });
    
    // Mock WebSocket
    global.WebSocket = jest.fn(() => ({
      onopen: null,
      onmessage: null,
      onclose: null,
      onerror: null,
      close: jest.fn()
    }));
    
    crawlProgressService.streamProgress('test-123', onProgress);
    
    // Simulate message
    const ws = global.WebSocket.mock.instances[0];
    ws.onmessage({
      data: JSON.stringify({
        type: 'crawl_progress',
        data: mockProgressData
      })
    });
  });
});
```

---

## 🐛 Troubleshooting Guide

### Common Issues & Solutions

#### 1. "Expected ASGI message 'websocket.accept'" Error

**Problem**: Trying to send WebSocket messages before accepting the connection.

**Solution**:
```python
# ❌ Wrong
async def websocket_endpoint(websocket: WebSocket):
    await websocket.send_json({"message": "hello"})  # Error!
    await websocket.accept()

# ✅ Correct
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()  # Accept first!
    await websocket.send_json({"message": "hello"})
```

#### 2. "Object of type datetime is not JSON serializable"

**Problem**: Sending datetime objects in WebSocket messages.

**Solution**:
```python
# ❌ Wrong
message = {"timestamp": datetime.utcnow(), "data": "test"}
await websocket.send_json(message)  # Error!

# ✅ Correct
message = {
    "timestamp": datetime.utcnow().isoformat() + 'Z',
    "data": "test"
}
await websocket.send_json(message)
```

#### 3. WebSocket Connects But No Messages Received

**Problem**: Race condition where WebSocket connects after operation starts.

**Solution**:
```typescript
// ❌ Wrong - WebSocket connects after API call
const result = await apiCall();  // Starts background process
setupWebSocket();  // Misses early messages

// ✅ Correct - WebSocket connects before API call
setupWebSocket();  // Ready to receive messages
const result = await apiCall();  // Background process sends messages
```

#### 4. Component State Not Updating

**Problem**: Mixing local state with WebSocket prop updates.

**Solution**:
```typescript
// ❌ Wrong - Local state overwrites props
const [localProgress, setLocalProgress] = useState(0);
useEffect(() => {
  // Props change but local state doesn't update
}, [progressData.percentage]);

// ✅ Correct - Use props directly
const { percentage } = progressData;  // No local state conflict
```

#### 5. Memory Leaks from Unclosed WebSockets

**Problem**: Not cleaning up WebSocket connections on component unmount.

**Solution**:
```typescript
// ✅ Always cleanup WebSockets
useEffect(() => {
  return () => {
    crawlProgressService.disconnectAll();
  };
}, []);
```

### Debug Logging

Add comprehensive logging to track WebSocket flow:

```python
# Backend debug logging
async def _broadcast_progress(self, progress_id: str):
    if progress_id not in self.progress_websockets:
        print(f"DEBUG: No WebSocket connections for {progress_id}")
        return
    
    print(f"DEBUG: Broadcasting to {len(self.progress_websockets[progress_id])} connections")
    
    for ws in self.progress_websockets[progress_id]:
        try:
            await ws.send_json(message)
            print(f"DEBUG: Message sent successfully")
        except Exception as e:
            print(f"DEBUG: Failed to send message: {e}")
```

```typescript
// Frontend debug logging
ws.onmessage = (event) => {
  console.log(`🔍 RAW WebSocket data:`, event.data);
  
  try {
    const message = JSON.parse(event.data);
    console.log(`🔍 Parsed message:`, message);
    
    if (message.type === 'crawl_progress') {
      console.log(`🔍 Calling progress callback...`);
      onProgress(message.data);
    }
  } catch (error) {
    console.error(`🔍 Parse error:`, error);
  }
};
```

---

This comprehensive guide covers all aspects of WebSocket implementation in Archon, from basic patterns to advanced troubleshooting. Use it as a reference for implementing real-time features in your own full-stack applications. 