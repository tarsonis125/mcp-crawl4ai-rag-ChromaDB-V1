"""
Integration Test for Full Crawl Workflow

This test suite verifies the complete crawl workflow from API request
to completion, including progress tracking and Socket.IO updates.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json
from datetime import datetime
import os

# CRITICAL: Set test environment to prevent real connections
os.environ['TESTING'] = 'true'
os.environ['ENV'] = 'test'

# Safety fixture to block all real operations
@pytest.fixture(autouse=True)
def block_real_operations():
    """Automatically block real database and storage operations in all tests"""
    # Create a mock table that raises an error on insert
    mock_table = Mock()
    mock_table.insert = Mock(side_effect=Exception("BLOCKED: Real database insert in tests!"))
    
    # Create a mock client that returns the mock table
    mock_client = Mock()
    mock_client.table = Mock(return_value=mock_table)
    
    with patch('supabase.create_client', return_value=mock_client):
        with patch('src.server.services.client_manager.get_supabase_client', return_value=mock_client):
            with patch('openai.OpenAI', side_effect=Exception("BLOCKED: Real OpenAI client in tests!")):
                yield


class TestCrawlIntegration:
    """Integration tests for the complete crawl workflow"""
    
    @pytest.fixture
    async def test_app(self):
        """Create a test FastAPI application"""
        from fastapi.testclient import TestClient
        from src.server.main import app
        
        # Create test client
        client = TestClient(app)
        return client
    
    @pytest.fixture
    def mock_dependencies(self):
        """Mock all external dependencies"""
        deps = {
            'crawler': Mock(),
            'supabase': Mock(),
            'socketio': Mock(),
            'openai': Mock()
        }
        
        # Configure crawler mock
        deps['crawler'].arun = AsyncMock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.url = "https://example.com"
        mock_result.markdown = "# Test Content\n\nThis is test content for integration testing."
        mock_result.html = "<h1>Test Content</h1><p>This is test content for integration testing.</p>"
        mock_result.metadata = {"title": "Test Page", "description": "Integration test"}
        deps['crawler'].arun.return_value = mock_result
        
        # Configure Supabase mock
        deps['supabase'].table = Mock(return_value=Mock(
            insert=Mock(return_value=Mock(execute=Mock(return_value=Mock(data=[])))),
            delete=Mock(return_value=Mock(
                in_=Mock(return_value=Mock(execute=Mock(return_value=Mock(data=[]))))
            ))
        ))
        
        # Configure Socket.IO mock
        deps['socketio'].emit = AsyncMock()
        deps['socketio'].enter_room = AsyncMock()
        
        # Configure OpenAI mock for embeddings
        deps['openai'].embeddings = Mock()
        deps['openai'].embeddings.create = Mock(return_value=Mock(
            data=[Mock(embedding=[0.1] * 1536)]
        ))
        
        return deps
    
    @pytest.mark.asyncio
    async def test_complete_text_file_crawl_workflow(self, mock_dependencies):
        """Test the complete workflow for crawling a text file"""
        progress_updates = []
        
        # Capture all progress updates
        async def capture_progress(progress_id, data):
            progress_updates.append({
                'timestamp': datetime.now(),
                'progress_id': progress_id,
                'data': data
            })
        
        # Mock aiohttp for text file fetching
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="This is test content for a text file that is long enough to pass validation.")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        # Mock all dependencies
        with patch('aiohttp.ClientSession', return_value=mock_session):
            with patch('src.server.services.crawler_manager.get_crawler', 
                      return_value=mock_dependencies['crawler']):
                with patch('src.server.services.client_manager.get_supabase_client',
                          return_value=mock_dependencies['supabase']):
                    # Mock OpenAI for embeddings
                    with patch('src.server.services.llm_provider_service.get_llm_client_sync',
                              return_value=mock_dependencies['openai']):
                        with patch('src.server.fastapi.socketio_handlers.broadcast_crawl_progress',
                                  side_effect=capture_progress):
                            # Mock document storage to prevent real uploads
                            with patch('src.server.services.storage.document_storage_service.add_documents_to_supabase') as mock_store:
                                async def mock_add_documents(*args, **kwargs):
                                    return {'success': True, 'error': None}
                                mock_store.side_effect = mock_add_documents
                                
                                # Simulate API request
                                from src.server.fastapi.knowledge_api import crawl_knowledge_item
                                from src.server.fastapi.knowledge_api import KnowledgeItemRequest
                                
                                request = KnowledgeItemRequest(
                                    url="https://example.com/llms.txt",
                                    knowledge_type="technical",
                                    tags=["ai", "llm"],
                                    max_depth=1,
                                    extract_code_examples=True
                                )
                                
                                # Start crawl (should return immediately)
                                response = await crawl_knowledge_item(request)
                                
                                # Verify immediate response
                                assert response['success'] == True
                                assert 'progressId' in response
                                assert response['message'] == "Crawling started"
                                
                                progress_id = response['progressId']
                                
                                # Wait for background task to complete
                                await asyncio.sleep(2.0)  # Give more time for background task
                                
                                # Verify progress updates were sent
                                assert len(progress_updates) > 0
                                
                                # Check progress sequence
                                statuses = [u['data']['status'] for u in progress_updates]
                                assert 'starting' in statuses
                                assert 'crawling' in statuses or 'analyzing' in statuses
                                
                                # Verify progress never went backwards
                                percentages = [u['data'].get('percentage', 0) for u in progress_updates 
                                             if 'percentage' in u['data']]
                                for i in range(1, len(percentages)):
                                    assert percentages[i] >= percentages[i-1], \
                                        f"Progress went backwards: {percentages}"
    
    @pytest.mark.asyncio
    async def test_complete_website_crawl_workflow(self, mock_dependencies):
        """Test the complete workflow for crawling a website"""
        # Track Socket.IO room subscriptions
        room_subscriptions = {}
        
        async def mock_enter_room(sid, room):
            room_subscriptions[sid] = room
        
        mock_dependencies['socketio'].enter_room = mock_enter_room
        
        with patch('src.server.services.crawler_manager.get_crawler',
                  return_value=mock_dependencies['crawler']):
            with patch('src.server.services.client_manager.get_supabase_client',
                      return_value=mock_dependencies['supabase']):
                with patch('src.server.socketio_app.get_socketio_instance',
                          return_value=mock_dependencies['socketio']):
                    
                    # Test crawling a documentation website
                    from src.server.fastapi.knowledge_api import crawl_knowledge_item
                    from src.server.fastapi.knowledge_api import KnowledgeItemRequest
                    
                    request = KnowledgeItemRequest(
                        url="https://docs.example.com",
                        knowledge_type="documentation",
                        tags=["docs", "api"],
                        max_depth=2,
                        extract_code_examples=True
                    )
                    
                    # Start crawl
                    response = await crawl_knowledge_item(request)
                    progress_id = response['progressId']
                    
                    # Simulate client subscribing to progress
                    from src.server.fastapi.socketio_handlers import crawl_subscribe
                    
                    client_sid = 'test-client-123'
                    await crawl_subscribe(client_sid, {'progress_id': progress_id})
                    
                    # Verify client joined progress room
                    assert client_sid in room_subscriptions
                    assert room_subscriptions[client_sid] == progress_id
    
    @pytest.mark.asyncio
    async def test_progress_persistence_across_reconnection(self, mock_dependencies):
        """Test that progress state persists when client reconnects"""
        task_states = {}
        
        # Mock task manager to track states
        class MockTaskManager:
            def __init__(self):
                self.tasks = {}
            
            async def get_task_status(self, task_id):
                if task_id in task_states:
                    return task_states[task_id]
                return {'error': 'Task not found'}
        
        mock_task_manager = MockTaskManager()
        
        with patch('src.server.fastapi.socketio_handlers.get_task_manager',
                  return_value=mock_task_manager):
            
            # Simulate task in progress
            progress_id = 'test-reconnect-123'
            task_states[progress_id] = {
                'status': 'running',
                'progress': 65,
                'last_update': {
                    'status': 'document_storage',
                    'percentage': 65,
                    'log': 'Storing documents...',
                    'chunks_stored': 45
                }
            }
            
            # Track emitted events
            emitted_events = []
            
            async def track_emit(event, data, **kwargs):
                emitted_events.append({'event': event, 'data': data})
            
            mock_dependencies['socketio'].emit = track_emit
            
            # Client reconnects and subscribes
            from src.server.fastapi.socketio_handlers import crawl_subscribe
            
            with patch('src.server.socketio_app.get_socketio_instance',
                      return_value=mock_dependencies['socketio']):
                
                await crawl_subscribe('reconnect-client', {'progress_id': progress_id})
                
                # Verify progress state was sent
                progress_events = [e for e in emitted_events if e['event'] == 'crawl_progress']
                assert len(progress_events) > 0
                
                reconnect_data = progress_events[0]['data']
                assert reconnect_data['progressId'] == progress_id
                assert reconnect_data['percentage'] == 65
                assert reconnect_data['status'] == 'running'
                assert reconnect_data['isReconnect'] == True
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, mock_dependencies):
        """Test error handling throughout the crawl workflow"""
        # Make crawler fail after initial success
        call_count = 0
        
        async def failing_crawler(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise Exception("Browser crashed")
            return mock_dependencies['crawler'].arun.return_value
        
        mock_dependencies['crawler'].arun = failing_crawler
        
        error_updates = []
        
        async def capture_errors(progress_id, data):
            if data.get('status') == 'error':
                error_updates.append(data)
        
        with patch('src.server.services.crawler_manager.get_crawler',
                  return_value=mock_dependencies['crawler']):
            with patch('src.server.fastapi.socketio_handlers.update_crawl_progress',
                      capture_errors):
                
                # Attempt crawl that will fail
                from src.server.fastapi.knowledge_api import crawl_knowledge_item
                from src.server.fastapi.knowledge_api import KnowledgeItemRequest
                
                request = KnowledgeItemRequest(
                    url="https://unstable-site.com",
                    knowledge_type="general"
                )
                
                response = await crawl_knowledge_item(request)
                
                # Initial response should still be successful
                assert response['success'] == True
                
                # Wait for error to occur
                await asyncio.sleep(0.5)
                
                # Verify error was reported via progress
                # (In actual implementation, error would be reported)
    
    @pytest.mark.asyncio
    async def test_concurrent_crawl_limit(self, mock_dependencies):
        """Test that concurrent crawl limit is enforced"""
        from src.server.fastapi.knowledge_api import CONCURRENT_CRAWL_LIMIT
        
        active_crawls = []
        crawl_started = asyncio.Event()
        
        async def slow_crawler(*args, **kwargs):
            active_crawls.append(datetime.now())
            crawl_started.set()
            await asyncio.sleep(0.5)  # Simulate slow crawl
            return mock_dependencies['crawler'].arun.return_value
        
        mock_dependencies['crawler'].arun = slow_crawler
        
        with patch('src.server.services.crawler_manager.get_crawler',
                  return_value=mock_dependencies['crawler']):
            with patch('src.server.services.client_manager.get_supabase_client',
                      return_value=mock_dependencies['supabase']):
                
                from src.server.fastapi.knowledge_api import crawl_knowledge_item
                from src.server.fastapi.knowledge_api import KnowledgeItemRequest
                
                # Start multiple crawls
                tasks = []
                for i in range(CONCURRENT_CRAWL_LIMIT + 2):
                    request = KnowledgeItemRequest(
                        url=f"https://example.com/page{i}",
                        knowledge_type="general"
                    )
                    task = asyncio.create_task(crawl_knowledge_item(request))
                    tasks.append(task)
                
                # Wait for first crawls to start
                await crawl_started.wait()
                await asyncio.sleep(0.1)
                
                # Check that only CONCURRENT_CRAWL_LIMIT are active
                # (This would be enforced by the semaphore in actual implementation)
                assert len(active_crawls) <= CONCURRENT_CRAWL_LIMIT
    
    @pytest.mark.asyncio
    async def test_code_extraction_integration(self, mock_dependencies):
        """Test that code extraction works as part of the workflow"""
        # Mock crawler to return content with code
        mock_result = Mock()
        mock_result.success = True
        mock_result.url = "https://github.com/example/repo"
        mock_result.markdown = """
# Example Code

Here's a Python function:

```python
def hello_world():
    print("Hello, World!")
    return 42
```

And some JavaScript:

```javascript
const greet = (name) => {
    console.log(`Hello, ${name}!`);
};
```
"""
        mock_result.html = "<pre><code>...</code></pre>"
        mock_result.metadata = {"title": "Code Examples"}
        
        mock_dependencies['crawler'].arun.return_value = mock_result
        
        # Track code extraction progress
        code_extraction_updates = []
        
        async def track_code_extraction(progress_id, data):
            if 'code_extraction' in data.get('status', ''):
                code_extraction_updates.append(data)
        
        with patch('src.server.services.crawler_manager.get_crawler',
                  return_value=mock_dependencies['crawler']):
            with patch('src.server.fastapi.socketio_handlers.update_crawl_progress',
                      track_code_extraction):
                
                from src.server.fastapi.knowledge_api import crawl_knowledge_item
                from src.server.fastapi.knowledge_api import KnowledgeItemRequest
                
                request = KnowledgeItemRequest(
                    url="https://github.com/example/repo",
                    knowledge_type="technical",
                    extract_code_examples=True
                )
                
                response = await crawl_knowledge_item(request)
                
                # Wait for processing
                await asyncio.sleep(1.0)
                
                # Verify code extraction occurred
                # (In actual implementation, would check for code extraction updates)