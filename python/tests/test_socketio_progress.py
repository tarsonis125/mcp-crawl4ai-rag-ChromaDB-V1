"""
Test Socket.IO Progress Tracking

Verifies that Socket.IO progress tracking still works correctly after refactoring.
"""
import asyncio
import socketio
import uuid
from datetime import datetime


async def test_crawl_progress():
    """Test crawl progress tracking via Socket.IO."""
    # Create Socket.IO client
    sio = socketio.AsyncClient()
    progress_id = str(uuid.uuid4())
    progress_updates = []
    
    @sio.on('crawl_progress')
    async def on_crawl_progress(data):
        """Handle crawl progress updates."""
        print(f"[{datetime.now().isoformat()}] Progress Update:")
        print(f"  Status: {data.get('status')}")
        print(f"  Percentage: {data.get('percentage')}%")
        print(f"  Log: {data.get('log')}")
        print(f"  Progress ID: {data.get('progressId')}")
        print("---")
        progress_updates.append(data)
    
    @sio.on('connect')
    async def on_connect():
        print("Connected to Socket.IO server")
        # Join the progress room
        await sio.emit('join_progress_room', {'progressId': progress_id})
    
    @sio.on('disconnect')
    async def on_disconnect():
        print("Disconnected from Socket.IO server")
    
    try:
        # Connect to the server
        print(f"Connecting to Socket.IO server...")
        await sio.connect('http://localhost:8000', socketio_path='/socket.io/')
        
        # Wait for connection
        await asyncio.sleep(1)
        
        # Make a crawl request
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # Test with a simple URL
            test_url = "https://example.com"
            
            print(f"\nStarting crawl test for {test_url}")
            print(f"Progress ID: {progress_id}")
            
            # Make the crawl request
            async with session.post(
                'http://localhost:8000/api/knowledge-items/crawl',
                json={
                    'url': test_url,
                    'knowledge_type': 'technical',
                    'tags': ['test'],
                    'max_depth': 1,
                    'extract_code_examples': False
                }
            ) as resp:
                result = await resp.json()
                print(f"\nCrawl request response: {result}")
                
                # The response should have our progress ID
                response_progress_id = result.get('progressId')
                
                # Join the actual progress room
                await sio.emit('join_progress_room', {'progressId': response_progress_id})
        
        # Wait for progress updates
        print("\nWaiting for progress updates...")
        await asyncio.sleep(10)  # Wait 10 seconds for updates
        
        # Check results
        print(f"\nReceived {len(progress_updates)} progress updates")
        
        # Verify we got expected progress updates
        statuses_seen = [update.get('status') for update in progress_updates]
        print(f"Statuses seen: {statuses_seen}")
        
        # We should see various statuses like: starting, analyzing, crawling, etc.
        expected_statuses = ['starting', 'analyzing', 'crawling']
        for status in expected_statuses:
            if any(status in s for s in statuses_seen if s):
                print(f"✅ Saw expected status: {status}")
            else:
                print(f"❌ Missing expected status: {status}")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await sio.disconnect()


async def test_progress_tracker_utility():
    """Test the new ProgressTracker utility."""
    from src.server.utils.progress import ProgressTracker
    from src.server.socketio_app import get_socketio_instance
    
    print("\n=== Testing ProgressTracker Utility ===")
    
    # Get Socket.IO instance
    sio = get_socketio_instance()
    progress_id = str(uuid.uuid4())
    
    # Create progress tracker
    tracker = ProgressTracker(sio, progress_id, 'test')
    
    # Test various methods
    await tracker.start({'test': 'data'})
    print("✅ Started progress tracking")
    
    await tracker.update('processing', 25, 'Processing data...')
    print("✅ Updated progress to 25%")
    
    await tracker.update_batch_progress(1, 4, 10, 'Processing batch 1 of 4')
    print("✅ Updated batch progress")
    
    await tracker.update_crawl_stats(5, 10, 'https://example.com/page5')
    print("✅ Updated crawl stats")
    
    await tracker.complete({'final': 'data'})
    print("✅ Completed progress tracking")
    
    # Check state
    final_state = tracker.get_state()
    print(f"\nFinal state: {final_state}")


if __name__ == '__main__':
    print("=== Socket.IO Progress Tracking Test ===")
    print("Make sure the Archon server is running on localhost:8000")
    print("")
    
    # Run tests
    asyncio.run(test_crawl_progress())
    # asyncio.run(test_progress_tracker_utility())  # Uncomment if you want to test the utility directly