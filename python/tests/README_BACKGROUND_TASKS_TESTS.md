# Background Tasks Test Suite

This test suite defines how the background tasks system should work in Archon. The tests are written in a Test-Driven Development (TDD) style to guide the implementation.

## Test Files

### 1. `test_background_task_progress.py`
Tests for progress tracking coordination:
- Progress never goes backwards
- Each stage reports within its designated range (crawling: 0-30%, storage: 30-80%, extraction: 80-100%)
- Sub-task progress maps correctly to overall progress
- Progress state persists for reconnecting clients
- Heartbeat messages during long operations

### 2. `test_socketio_persistence.py`
Tests for Socket.IO connection stability:
- Clients can subscribe to progress rooms
- Reconnecting clients receive current state
- Heartbeat messages keep connections alive
- Socket.IO errors don't crash background tasks
- Multiple clients receive updates
- Rate limiting prevents spam

### 3. `test_crawl_orchestration.py`
Tests for proper async/sync separation:
- Text file crawling stays async
- Website crawling uses browser automation async
- Only CPU-intensive operations use threads
- Database operations remain async
- No new event loops in threads

### 4. `test_crawl_integration.py`
Integration tests for complete workflow:
- Full text file crawl workflow
- Full website crawl workflow
- Progress persistence across reconnection
- Error handling and recovery
- Concurrent crawl limits
- Code extraction integration

## Running the Tests

```bash
# Run all background task tests
cd /Users/sean/Software/archon-2
pytest python/tests/test_background_task_progress.py -v
pytest python/tests/test_socketio_persistence.py -v
pytest python/tests/test_crawl_orchestration.py -v
pytest python/tests/test_crawl_integration.py -v

# Run all tests together
pytest python/tests/test_*.py -v

# Run with coverage
pytest python/tests/test_*.py --cov=python.src.server --cov-report=html
```

## Key Testing Principles

### 1. Progress Coordination
- Progress should smoothly increase from 0-100%
- Each stage has a defined range
- Sub-stages map to overall progress
- Never jump backwards

### 2. Socket.IO Resilience
- Connections survive long operations
- Clients can reconnect anytime
- Errors don't crash tasks
- Heartbeats prevent timeouts

### 3. Async/Sync Separation
- Browser operations stay async
- Database operations stay async
- Only text processing goes to threads
- No event loops in threads

### 4. Error Recovery
- Tasks complete despite Socket.IO errors
- Progress updates continue after errors
- Clients get error notifications
- System remains stable

## Implementation Guidelines

Based on these tests, the implementation should:

1. **Use `asyncio.create_task` for background crawling** - not ThreadPoolExecutor
2. **Keep browser automation in the main event loop** - never in threads
3. **Use `run_in_executor` only for CPU tasks** - chunking, embeddings
4. **Implement ProgressMapper** - coordinate progress across stages
5. **Store progress state** - for client reconnections
6. **Send heartbeats** - every 30 seconds during long operations
7. **Handle errors gracefully** - don't let Socket.IO errors crash tasks

## Expected Test Results

When the implementation is correct:
- All tests should pass
- Progress flows smoothly 0→100%
- Clients can navigate away and return
- Both text files and websites crawl successfully
- Socket.IO connections remain stable
- System uses resources efficiently

## Debugging Failed Tests

If tests fail:
1. Check if async operations are running in threads
2. Verify progress mapping calculations
3. Ensure Socket.IO context is maintained
4. Look for event loop conflicts
5. Check error handling paths