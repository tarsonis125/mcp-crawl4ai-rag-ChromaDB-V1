"""
Test script for Socket.IO crawl progress.

This script tests the Socket.IO implementation for crawl progress tracking.
"""

import asyncio
import json
from datetime import datetime
import socketio
import httpx

# Configuration
BASE_URL = "http://localhost:8080"

async def test_crawl_with_socketio():
    """Test crawling with Socket.IO progress tracking."""
    
    # Test URL to crawl
    test_url = "https://example.com"
    
    async with httpx.AsyncClient() as client:
        # Start crawl request
        print(f"[{datetime.now()}] Starting crawl request...")
        response = await client.post(
            f"{BASE_URL}/api/knowledge-items/crawl",
            json={
                "url": test_url,
                "knowledge_type": "technical",
                "tags": ["test", "socketio"],
                "update_frequency": 7
            }
        )
        
        if response.status_code != 200:
            print(f"Error starting crawl: {response.status_code} - {response.text}")
            return
        
        result = response.json()
        progress_id = result.get("progressId")
        
        if not progress_id:
            print("No progress ID returned!")
            return
        
        print(f"[{datetime.now()}] Got progress ID: {progress_id}")
        
        # Create Socket.IO client
        sio = socketio.AsyncClient()
        
        # Track completion
        completed = asyncio.Event()
        
        @sio.event(namespace='/crawl')
        async def connect():
            print(f"[{datetime.now()}] Socket.IO connected to /crawl namespace")
            # Subscribe to progress updates
            await sio.emit('subscribe', {'progress_id': progress_id}, namespace='/crawl')
        
        @sio.event(namespace='/crawl')
        async def disconnect():
            print(f"[{datetime.now()}] Socket.IO disconnected")
        
        @sio.event(namespace='/crawl')
        async def connected(data):
            print(f"[{datetime.now()}] Received connection confirmation: {data}")
        
        @sio.event(namespace='/crawl')
        async def progress_update(data):
            status = data.get("status")
            percentage = data.get("percentage", 0)
            logs = data.get("logs", [])
            
            print(f"[{datetime.now()}] Progress: {status} - {percentage}%")
            if logs:
                latest_log = logs[-1] if isinstance(logs, list) else logs
                print(f"  Log: {latest_log}")
        
        @sio.event(namespace='/crawl')
        async def progress_complete(data):
            print(f"[{datetime.now()}] Crawl completed successfully!")
            chunks = data.get("chunksStored", 0)
            words = data.get("wordCount", 0)
            print(f"  Chunks stored: {chunks}")
            print(f"  Words processed: {words}")
            completed.set()
        
        @sio.event(namespace='/crawl')
        async def progress_error(data):
            error = data.get("error", "Unknown error")
            print(f"[{datetime.now()}] Crawl failed: {error}")
            completed.set()
        
        @sio.event(namespace='/crawl')
        async def error(data):
            print(f"[{datetime.now()}] Socket.IO error: {data}")
        
        try:
            # Connect to Socket.IO server
            print(f"[{datetime.now()}] Connecting to Socket.IO server...")
            await sio.connect(BASE_URL, namespaces=['/crawl'])
            
            # Wait for completion or timeout
            try:
                await asyncio.wait_for(completed.wait(), timeout=120.0)
            except asyncio.TimeoutError:
                print(f"[{datetime.now()}] Timeout waiting for crawl completion")
            
        except Exception as e:
            print(f"[{datetime.now()}] Socket.IO connection error: {e}")
        finally:
            if sio.connected:
                await sio.disconnect()

async def test_document_upload_with_socketio():
    """Test document upload with Socket.IO progress tracking."""
    
    # Create a test file content
    test_content = """
    # Test Document
    
    This is a test document for Socket.IO progress tracking.
    It contains some sample content to be processed.
    
    ## Section 1
    Lorem ipsum dolor sit amet, consectetur adipiscing elit.
    
    ## Section 2
    Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
    """
    
    async with httpx.AsyncClient() as client:
        # Prepare file upload
        files = {
            'file': ('test_document.md', test_content.encode(), 'text/markdown')
        }
        data = {
            'knowledge_type': 'technical',
            'tags': json.dumps(['test', 'socketio'])
        }
        
        print(f"[{datetime.now()}] Starting document upload...")
        response = await client.post(
            f"{BASE_URL}/api/documents/upload",
            files=files,
            data=data
        )
        
        if response.status_code != 200:
            print(f"Error uploading document: {response.status_code} - {response.text}")
            return
        
        result = response.json()
        progress_id = result.get("progressId")
        
        if not progress_id:
            print("No progress ID returned!")
            return
        
        print(f"[{datetime.now()}] Got progress ID: {progress_id}")
        
        # Create Socket.IO client
        sio = socketio.AsyncClient()
        
        # Track completion
        completed = asyncio.Event()
        
        @sio.event(namespace='/crawl')
        async def connect():
            print(f"[{datetime.now()}] Socket.IO connected for document upload")
            await sio.emit('subscribe', {'progress_id': progress_id}, namespace='/crawl')
        
        @sio.event(namespace='/crawl')
        async def progress_update(data):
            status = data.get("status")
            percentage = data.get("percentage", 0)
            print(f"[{datetime.now()}] Upload progress: {status} - {percentage}%")
        
        @sio.event(namespace='/crawl')
        async def progress_complete(data):
            print(f"[{datetime.now()}] Document upload completed!")
            chunks = data.get("chunksStored", 0)
            words = data.get("wordCount", 0)
            print(f"  Chunks stored: {chunks}")
            print(f"  Words processed: {words}")
            completed.set()
        
        @sio.event(namespace='/crawl')
        async def progress_error(data):
            error = data.get("error", "Unknown error")
            print(f"[{datetime.now()}] Upload failed: {error}")
            completed.set()
        
        try:
            await sio.connect(BASE_URL, namespaces=['/crawl'])
            await asyncio.wait_for(completed.wait(), timeout=60.0)
        except Exception as e:
            print(f"[{datetime.now()}] Error: {e}")
        finally:
            if sio.connected:
                await sio.disconnect()

async def main():
    """Main test runner."""
    
    print("=" * 60)
    print("Socket.IO Crawl Progress Test")
    print("=" * 60)
    
    # Test 1: Website crawl with Socket.IO progress
    print("\nTest 1: Website crawl with Socket.IO progress")
    print("-" * 40)
    await test_crawl_with_socketio()
    
    # Wait a bit between tests
    await asyncio.sleep(2)
    
    # Test 2: Document upload with Socket.IO progress
    print("\n\nTest 2: Document upload with Socket.IO progress")
    print("-" * 40)
    await test_document_upload_with_socketio()
    
    print("\n" + "=" * 60)
    print("All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())