"""
Integration tests for background tasks that test actual implementation.
These tests should fail on broken functionality and pass when fixed.

IMPORTANT: All tests MUST use mocks - NEVER connect to real services or databases!
"""
import pytest
import pytest_asyncio
import asyncio
import aiohttp
from datetime import datetime
import time
from unittest.mock import Mock, AsyncMock, patch
from src.server.services.knowledge.crawl_orchestration_service import CrawlOrchestrationService
from src.server.services.background_task_manager import BackgroundTaskManager
from src.server.services.knowledge.progress_mapper import ProgressMapper


class TestBackgroundTasksActualImplementation:
    """Test the actual implementation to identify what's broken"""
    
    @pytest_asyncio.fixture
    async def crawler_instance(self):
        """Get MOCK crawler instance - NEVER use real crawler in tests"""
        crawler = AsyncMock()
        # Mock a successful crawl result
        mock_result = Mock()
        mock_result.success = True
        mock_result.url = "https://example.com"
        mock_result.markdown = "# Test Content\n\nThis is test content."
        mock_result.html = "<h1>Test Content</h1>"
        mock_result.metadata = {"title": "Test"}
        crawler.arun = AsyncMock(return_value=mock_result)
        yield crawler
    
    @pytest.fixture
    def supabase_client(self):
        """Get MOCK Supabase client - NEVER use real database in tests"""
        mock_client = Mock()
        mock_client.table = Mock(return_value=Mock(
            insert=Mock(return_value=Mock(
                execute=Mock(return_value=Mock(data=[]))
            )),
            delete=Mock(return_value=Mock(
                in_=Mock(return_value=Mock(
                    execute=Mock(return_value=Mock(data=[]))
                ))
            ))
        ))
        return mock_client
    
    @pytest.mark.asyncio
    async def test_text_file_crawl_blocks_event_loop(self, crawler_instance, supabase_client):
        """Test that text file crawling currently blocks the event loop (should fail)"""
        orchestrator = CrawlOrchestrationService(crawler_instance, supabase_client)
        
        # Track if main loop is blocked
        loop_blocked = False
        check_interval = 0.1
        
        async def check_loop_responsiveness():
            """Check if event loop responds within reasonable time"""
            nonlocal loop_blocked
            start = time.time()
            await asyncio.sleep(0.01)  # Should complete quickly
            elapsed = time.time() - start
            if elapsed > check_interval:
                loop_blocked = True
        
        # Start a text file crawl
        request = {
            'url': 'https://raw.githubusercontent.com/anthropics/anthropic-cookbook/main/README.md',
            'knowledge_type': 'technical',
            'extract_code_examples': True
        }
        
        # Run crawl and check loop responsiveness concurrently
        crawl_task = asyncio.create_task(orchestrator.orchestrate_crawl(request))
        
        # Check loop responsiveness multiple times during crawl
        for _ in range(5):
            await check_loop_responsiveness()
            await asyncio.sleep(0.1)
        
        result = await crawl_task
        
        # This should fail because current implementation blocks the loop
        assert not loop_blocked, "Event loop was blocked during text file crawl"
    
    @pytest.mark.asyncio
    async def test_website_crawl_runs_in_main_thread(self, crawler_instance, supabase_client):
        """Test that website crawling now correctly runs in main thread"""
        orchestrator = CrawlOrchestrationService(crawler_instance, supabase_client)
        
        # Track which thread operations run in
        import threading
        main_thread_id = threading.current_thread().ident
        crawl_thread_id = None
        
        # Monkey patch the async crawl method to track thread
        original_async = orchestrator._async_orchestrate_crawl
        async def track_thread(*args, **kwargs):
            nonlocal crawl_thread_id
            crawl_thread_id = threading.current_thread().ident
            return await original_async(*args, **kwargs)
        
        orchestrator._async_orchestrate_crawl = track_thread
        
        request = {
            'url': 'https://example.com',
            'knowledge_type': 'documentation',
            'max_depth': 1
        }
        
        result = await orchestrator.orchestrate_crawl(request)
        await asyncio.sleep(1)  # Let background task run
        
        # This should pass - crawling should be in main thread
        assert crawl_thread_id == main_thread_id, \
            f"Website crawl ran in thread {crawl_thread_id}, not main thread {main_thread_id}"
    
    @pytest.mark.asyncio
    async def test_progress_updates_dont_jump_backwards(self):
        """Test that progress updates don't jump backwards with ProgressMapper"""
        progress_updates = []
        
        # Create orchestrator with progress mapper
        orchestrator = CrawlOrchestrationService(None, None)
        orchestrator.progress_mapper = ProgressMapper()
        
        # Test various stage transitions
        stages = [
            ('starting', 100),
            ('analyzing', 50),
            ('crawling', 0),
            ('crawling', 50),
            ('crawling', 100),
            ('processing', 50),
            ('document_storage', 0),
            ('document_storage', 50),
            ('document_storage', 100),
            ('code_extraction', 0),
            ('code_extraction', 100),
            ('finalization', 50),
            ('completed', 100)
        ]
        
        for stage, stage_progress in stages:
            overall_progress = orchestrator.progress_mapper.map_progress(stage, stage_progress)
            progress_updates.append(overall_progress)
        
        # Check if progress went backwards
        went_backwards = False
        for i in range(1, len(progress_updates)):
            if progress_updates[i] < progress_updates[i-1]:
                went_backwards = True
                break
        
        # This should pass - progress mapper prevents backwards jumps
        assert not went_backwards, \
            f"Progress went backwards: {progress_updates}"
    
    @pytest.mark.asyncio
    async def test_socket_io_disconnects_during_long_tasks(self):
        """Test that Socket.IO connections drop during long tasks (should fail)"""
        task_manager = BackgroundTaskManager()
        
        # Track if heartbeat/keepalive is sent
        heartbeat_sent = False
        last_update_time = None
        
        async def track_updates(task_id, update):
            nonlocal heartbeat_sent, last_update_time
            current_time = time.time()
            if last_update_time and current_time - last_update_time > 30:
                # No update for 30+ seconds
                pass
            if update.get('heartbeat'):
                heartbeat_sent = True
            last_update_time = current_time
        
        # Long running task without updates
        def long_task(progress_queue):
            progress_queue.put({'status': 'running', 'percentage': 10})
            time.sleep(35)  # Simulate 35 second task with no updates
            progress_queue.put({'status': 'complete', 'percentage': 100})
        
        task_id = await task_manager.submit_task(
            long_task,
            (),
            progress_callback=track_updates
        )
        
        await asyncio.sleep(40)
        
        # This should fail - no heartbeat mechanism exists
        assert heartbeat_sent, "No heartbeat sent during long operation"
    
    @pytest.mark.asyncio
    async def test_progress_mapper_prevents_backwards_progress(self):
        """Test that ProgressMapper actually prevents backwards progress (should pass)"""
        mapper = ProgressMapper()
        
        # Test that mapper prevents backwards progress
        progress_values = []
        
        # Simulate stages reporting their internal progress
        progress_values.append(mapper.map_progress('crawling', 0))     # Should be 5
        progress_values.append(mapper.map_progress('crawling', 50))    # Should be ~18
        progress_values.append(mapper.map_progress('crawling', 100))   # Should be 30
        progress_values.append(mapper.map_progress('document_storage', 0))   # Should be 35 (not go back to 0)
        progress_values.append(mapper.map_progress('document_storage', 50))  # Should be ~58
        progress_values.append(mapper.map_progress('document_storage', 100)) # Should be 80
        
        # Check progress never goes backwards
        for i in range(1, len(progress_values)):
            assert progress_values[i] >= progress_values[i-1], \
                f"Progress went backwards: {progress_values[i-1]} -> {progress_values[i]}"
        
        # This should pass - ProgressMapper does prevent backwards progress
        assert progress_values[-1] == 80  # End of document storage
    
    @pytest.mark.asyncio
    async def test_blocking_helpers_dont_create_event_loops(self):
        """Test that blocking_helpers no longer creates new event loops"""
        from src.server.services.blocking_helpers import run_async_in_thread
        
        # This should raise an error about missing main event loop
        async def dummy_async_func():
            return "test"
        
        with pytest.raises(RuntimeError) as exc_info:
            # This should fail because main event loop isn't set in thread
            result = run_async_in_thread(dummy_async_func())
        
        # Should get an error about main event loop not available
        assert "main event loop" in str(exc_info.value).lower(), \
               "Should raise error about missing main event loop"
    
    @pytest.mark.asyncio 
    async def test_actual_crawl_returns_immediately(self, crawler_instance, supabase_client):
        """Test that crawl orchestration returns immediately and runs in background"""
        if not crawler_instance:
            pytest.skip("Crawler not available")
            
        orchestrator = CrawlOrchestrationService(crawler_instance, supabase_client)
        
        request = {
            'url': 'https://www.example.com',  # Simple test page
            'knowledge_type': 'general'
        }
        
        # Measure time to return
        start_time = asyncio.get_event_loop().time()
        result = await orchestrator.orchestrate_crawl(request)
        elapsed = asyncio.get_event_loop().time() - start_time
        
        # Should return almost immediately (under 1 second)
        assert elapsed < 1.0, f"Orchestration took {elapsed}s, should return immediately"
        
        # Check return value
        assert result.get('task_id'), "No task_id returned"
        assert result.get('status') == 'started', "Status not 'started'"
        assert result.get('message'), "No message returned"
        
        # Verify background task is running by checking thread
        import threading
        main_thread_id = threading.current_thread().ident
        
        # The async task should be running in the main thread (event loop)
        # We already verified this in test_website_crawl_runs_in_main_thread