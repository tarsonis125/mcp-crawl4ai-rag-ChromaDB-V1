"""
Test the crawling improvements including Socket.IO connection verification,
retry logic, and error handling.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# Import the modules to test
from src.server.services.rag.crawling_service import CrawlingService
from src.server.fastapi.socketio_handlers import start_crawl_progress, update_crawl_progress, complete_crawl_progress


class TestCrawlProgressWithSocketIO:
    """Test crawl progress tracking with Socket.IO instead of WebSocket."""
    
    @pytest.mark.asyncio
    async def test_socketio_progress_tracking(self):
        """Test that progress is tracked via Socket.IO."""
        progress_id = "test-progress-123"
        
        # Mock Socket.IO emit
        with patch('src.server.fastapi.socketio_handlers.broadcast_crawl_progress') as mock_emit:
            # Start crawl progress
            await start_crawl_progress(progress_id, {
                "url": "https://example.com",
                "status": "starting"
            })
            
            # Verify emit was called
            mock_emit.assert_called_once_with(progress_id, {
                "url": "https://example.com",
                "status": "starting"
            })
            
            # Update progress
            await update_crawl_progress(progress_id, {
                "status": "crawling",
                "percentage": 50,
                "log": "Crawling in progress..."
            })
            
            # Verify update was emitted
            assert mock_emit.call_count == 2
    
    @pytest.mark.asyncio
    async def test_progress_without_socketio_connection(self):
        """Test that progress updates work even without active Socket.IO connections."""
        progress_id = "test-progress-456"
        
        # Progress updates should not fail even if no clients are connected
        try:
            await start_crawl_progress(progress_id, {"url": "https://example.com"})
            await update_crawl_progress(progress_id, {
                "status": "crawling",
                "percentage": 50,
                "log": "Crawling in progress..."
            })
            await complete_crawl_progress(progress_id, {
                "chunksStored": 10,
                "wordCount": 1000
            })
            # Should complete without errors
            assert True
        except Exception as e:
            pytest.fail(f"Progress updates failed without Socket.IO: {e}")
    
    @pytest.mark.asyncio
    async def test_cleanup_after_completion(self):
        """Test that progress tracking handles completion properly."""
        progress_id = "test-progress-789"
        
        with patch('src.server.fastapi.socketio_handlers.broadcast_crawl_progress') as mock_emit:
            # Start and complete crawl
            await start_crawl_progress(progress_id, {"url": "https://example.com"})
            await complete_crawl_progress(progress_id, {
                "chunksStored": 10,
                "wordCount": 1000
            })
            
            # Verify completion was emitted
            calls = mock_emit.call_args_list
            assert any('complete' in str(call) for call in calls)


class TestCrawlingServiceRetry:
    """Test the enhanced crawling service with retry logic."""
    
    @pytest.mark.asyncio
    async def test_single_page_retry_on_failure(self):
        """Test that crawl_single_page retries on failure."""
        # Create mock crawler
        mock_crawler = AsyncMock()
        
        # Create service with mock crawler and Supabase client
        mock_supabase = Mock()
        service = CrawlingService(crawler=mock_crawler, supabase_client=mock_supabase)
        
        # Mock failed result followed by success
        failed_result = Mock(success=False, error_message="Network error")
        success_result = Mock(
            success=True,
            markdown="# Test Content\n\nThis is test content that is long enough.",
            title="Test Page",
            links={"internal": [], "external": []}
        )
        
        # Configure mock to fail twice then succeed
        mock_crawler.arun.side_effect = [failed_result, failed_result, success_result]
        
        # Call with retry
        result = await service.crawl_single_page("https://example.com", retry_count=3)
        
        # Verify success after retries
        assert result["success"] is True
        assert result["markdown"] == success_result.markdown
        assert mock_crawler.arun.call_count == 3
    
    @pytest.mark.asyncio
    async def test_single_page_max_retries_exceeded(self):
        """Test that crawl fails after max retries."""
        mock_crawler = AsyncMock()
        # Mock Supabase client
        mock_supabase = Mock()
        service = CrawlingService(crawler=mock_crawler, supabase_client=mock_supabase)
        
        # Always fail
        failed_result = Mock(success=False, error_message="Persistent error")
        mock_crawler.arun.return_value = failed_result
        
        # Call with retry - note retry_count is the max attempts, not additional retries
        result = await service.crawl_single_page("https://example.com", retry_count=2)
        
        # Verify failure
        assert result["success"] is False
        assert "after 2 attempts" in result["error"] or "Persistent error" in result["error"]
        assert mock_crawler.arun.call_count == 2
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling in crawl."""
        mock_crawler = AsyncMock()
        mock_supabase = Mock()
        service = CrawlingService(crawler=mock_crawler, supabase_client=mock_supabase)
        
        # Simulate timeout
        mock_crawler.arun.side_effect = asyncio.TimeoutError()
        
        # Call with retry
        result = await service.crawl_single_page("https://example.com", retry_count=1)
        
        # Verify timeout error
        assert result["success"] is False
        assert "Timeout" in result["error"]
    
    @pytest.mark.asyncio
    async def test_insufficient_content_retry(self):
        """Test retry when content is insufficient."""
        mock_crawler = AsyncMock()
        mock_supabase = Mock()
        service = CrawlingService(crawler=mock_crawler, supabase_client=mock_supabase)
        
        # First return insufficient content, then good content
        insufficient_result = Mock(
            success=True,
            markdown="Too short",
            title="Test",
            links={}
        )
        good_result = Mock(
            success=True,
            markdown="# Good Content\n\n" + "This is sufficient content. " * 10,
            title="Test Page",
            links={"internal": [], "external": []}
        )
        
        mock_crawler.arun.side_effect = [insufficient_result, good_result]
        
        # Call with retry
        result = await service.crawl_single_page("https://example.com", retry_count=2)
        
        # Verify success with good content
        assert result["success"] is True
        assert result["markdown"] == good_result.markdown
        assert mock_crawler.arun.call_count == 2


class TestBatchCrawling:
    """Test batch crawling improvements."""
    
    @pytest.mark.asyncio
    async def test_smaller_batch_sizes(self):
        """Test that batch sizes are properly limited."""
        mock_crawler = AsyncMock()
        mock_supabase = Mock()
        service = CrawlingService(crawler=mock_crawler, supabase_client=mock_supabase)
        
        # Mock successful results
        success_result = Mock(
            success=True,
            url="https://example.com",
            markdown="# Content\n\n" + "Test content. " * 20,
            title="Test"
        )
        
        # Create 25 URLs
        urls = [f"https://example.com/page{i}" for i in range(25)]
        
        # Mock arun_many to track batch sizes
        batch_sizes = []
        
        async def mock_arun_many(urls, **kwargs):
            batch_sizes.append(len(urls))
            return [success_result] * len(urls)
        
        mock_crawler.arun_many = mock_arun_many
        
        # Crawl with progress callback
        progress_updates = []
        
        async def progress_callback(status, percentage, message, **kwargs):
            progress_updates.append({
                "status": status,
                "percentage": percentage,
                "message": message
            })
        
        # Run batch crawl
        results = await service.crawl_batch_with_progress(
            urls, 
            max_concurrent=15,  # Should limit batch to 15
            progress_callback=progress_callback
        )
        
        # Verify batch sizes - CrawlingService uses max_concurrent as batch size
        assert all(size <= 15 for size in batch_sizes), f"Batch sizes: {batch_sizes}"
        assert len(results) == 25
        
        # Verify progress updates
        assert len(progress_updates) > 0
        assert any("completed" in update["message"].lower() for update in progress_updates)


@pytest.mark.asyncio
async def test_integration_crawl_flow():
    """Test the full crawl flow with WebSocket and retries."""
    
    # This would be an integration test that requires running services
    # Skipping for unit tests, but included as example
    
    # Steps:
    # 1. Start a crawl via API
    # 2. Connect WebSocket
    # 3. Verify connection is established before crawling starts
    # 4. Simulate some failures and verify retries
    # 5. Complete crawl and verify cleanup
    
    pass


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])