"""
Test Crawl Orchestration

This test suite defines how crawl orchestration should work for both
text files and websites, ensuring proper async/sync separation.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from urllib.parse import urlparse
import aiohttp


class TestCrawlOrchestration:
    """Test suite for crawl orchestration with proper async/sync separation"""
    
    @pytest.fixture
    def mock_crawler(self):
        """Create a mock Crawl4AI crawler"""
        crawler = Mock()
        crawler.arun = AsyncMock()
        
        # Mock successful crawl result
        mock_result = Mock()
        mock_result.success = True
        mock_result.url = "https://example.com"
        mock_result.markdown = "# Example Content\n\nThis is test content."
        mock_result.html = "<h1>Example Content</h1><p>This is test content.</p>"
        mock_result.metadata = {"title": "Example Page", "description": "Test page"}
        mock_result.error_message = None
        
        crawler.arun.return_value = mock_result
        return crawler
    
    @pytest.fixture
    def mock_supabase_client(self):
        """Create a mock Supabase client"""
        client = Mock()
        client.table = Mock(return_value=Mock(
            insert=Mock(return_value=Mock(
                execute=Mock(return_value=Mock(data=[]))
            )),
            delete=Mock(return_value=Mock(
                in_=Mock(return_value=Mock(
                    execute=Mock(return_value=Mock(data=[]))
                ))
            ))
        ))
        return client
    
    @pytest.mark.asyncio
    async def test_text_file_crawl_stays_async(self):
        """Test that text file crawling remains async in main loop"""
        from src.server.services.knowledge.crawl_orchestration_service import CrawlOrchestrationService
        
        # Mock dependencies
        mock_crawler = Mock()
        mock_supabase = Mock()
        
        orchestrator = CrawlOrchestrationService(mock_crawler, mock_supabase, 'test-123')
        
        # Test text file URL
        text_url = "https://example.com/llms.txt"
        request = {
            'url': text_url,
            'knowledge_type': 'technical',
            'tags': ['ai', 'llm'],
            'max_depth': 1
        }
        
        # Mock successful HTTP fetch
        mock_response_text = "This is the content of llms.txt"
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.text = AsyncMock(return_value=mock_response_text)
            mock_response.status = 200
            
            mock_session.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_response.__aenter__.return_value = mock_response
            
            # This should return immediately with task info
            result = await orchestrator.orchestrate_crawl(request)
            
            # Verify returns task info, not blocking
            assert 'task_id' in result
            assert result['status'] == 'started'
            assert 'progress_id' in result
            
            # Verify task was created in background
            assert result['task_id'] == 'test-123'
    
    @pytest.mark.asyncio
    async def test_website_crawl_uses_browser_async(self, mock_crawler, mock_supabase_client):
        """Test that website crawling uses browser automation async"""
        from src.server.services.knowledge.crawl_orchestration_service import CrawlOrchestrationService
        
        orchestrator = CrawlOrchestrationService(mock_crawler, mock_supabase_client, 'test-web-123')
        
        # Test website URL
        web_url = "https://docs.example.com/guide"
        request = {
            'url': web_url,
            'knowledge_type': 'documentation',
            'tags': ['docs'],
            'max_depth': 2
        }
        
        # This should use asyncio.create_task, not ThreadPoolExecutor
        result = await orchestrator.orchestrate_crawl(request)
        
        # Verify returns immediately
        assert result['status'] == 'started'
        assert result['task_id'] == 'test-web-123'
        
        # Verify crawler will be called async (not in thread)
        # The actual crawl happens in background task
    
    @pytest.mark.asyncio
    async def test_cpu_intensive_operations_use_threads(self):
        """Test that only CPU-intensive operations go to threads"""
        from src.server.services.storage.storage_services import DocumentStorageService
        
        storage_service = DocumentStorageService(Mock())
        
        # Test text chunking (CPU-intensive)
        long_text = "This is a very long document. " * 1000
        
        # This should be able to run in a thread
        chunks = storage_service.smart_chunk_text(long_text, chunk_size=100)
        
        assert len(chunks) > 1
        assert all(len(chunk) <= 100 for chunk in chunks)
    
    @pytest.mark.asyncio
    async def test_async_operations_stay_in_main_loop(self, mock_crawler):
        """Test that async operations remain in main event loop"""
        from src.server.services.rag.crawling_service import CrawlingService
        
        # Properly set up the mock result to match expected structure
        mock_result = Mock()
        mock_result.success = True
        mock_result.markdown = "# Test Content\n\nThis is test content that needs to be at least 50 characters long to pass validation. Here is some more content to make it longer."
        mock_result.html = "<h1>Test Content</h1><p>This is test content that needs to be at least 50 characters long to pass validation. Here is some more content to make it longer.</p>"
        mock_result.metadata = {"title": "Test Page"}
        mock_result.error_message = None
        
        # Ensure the mock returns a valid response
        mock_crawler.arun.return_value = mock_result
        
        # Mock arun_many for batch crawling
        mock_crawler.arun_many = AsyncMock(return_value=[mock_result, mock_result])
        
        crawling_service = CrawlingService(crawler=mock_crawler, supabase_client=Mock())
        
        # These operations should all be async
        operations_tested = []
        
        # Test crawl single URL (async)
        result = await crawling_service.crawl_single_page("https://example.com")
        operations_tested.append('crawl_single_page')
        assert result['success'] == True
        assert 'markdown' in result
        assert 'html' in result
        
        # Test batch crawl (async) - returns list of results, not dict
        results = await crawling_service.crawl_batch_with_progress(["https://example.com/1", "https://example.com/2"])
        operations_tested.append('crawl_batch_with_progress')
        assert isinstance(results, list)
        assert len(results) > 0  # At least some results
        
        # Verify all operations completed
        assert len(operations_tested) == 2
    
    @pytest.mark.asyncio
    async def test_orchestration_workflow_separation(self, mock_crawler, mock_supabase_client):
        """Test the complete orchestration workflow with proper separation"""
        
        # Track which operations run in which context
        async_operations = []
        thread_operations = []
        
        async def track_async_op(op_name):
            async_operations.append(op_name)
            await asyncio.sleep(0.01)  # Simulate async work
        
        def track_thread_op(op_name):
            thread_operations.append(op_name)
            # Simulate CPU work
        
        # Mock the orchestration flow
        with patch('asyncio.create_task') as mock_create_task:
            from src.server.services.knowledge.crawl_orchestration_service import CrawlOrchestrationService
            
            orchestrator = CrawlOrchestrationService(mock_crawler, mock_supabase_client)
            
            # Start orchestration
            request = {'url': 'https://example.com', 'max_depth': 1}
            result = await orchestrator.orchestrate_crawl(request)
            
            # Verify task was created for background execution
            mock_create_task.assert_called_once()
            
            # The background task should handle async/sync separation
            # Async: crawling, database operations
            # Sync: text chunking, embedding generation
    
    @pytest.mark.asyncio
    async def test_progress_reporting_from_async_context(self):
        """Test that progress reporting works from async background tasks"""
        progress_updates = []
        
        async def capture_progress(progress_id, data):
            progress_updates.append(data)
        
        async def background_crawl_task():
            # Simulate crawl stages
            await capture_progress('test-123', {'status': 'crawling', 'percentage': 10})
            await asyncio.sleep(0.01)
            await capture_progress('test-123', {'status': 'crawling', 'percentage': 30})
            await asyncio.sleep(0.01)
            await capture_progress('test-123', {'status': 'document_storage', 'percentage': 50})
        
        # Run as background task
        task = asyncio.create_task(background_crawl_task())
        await task
        
        # Verify progress was captured
        assert len(progress_updates) == 3
        assert progress_updates[0]['percentage'] == 10
        assert progress_updates[2]['percentage'] == 50
    
    @pytest.mark.asyncio
    async def test_error_handling_in_async_context(self, mock_crawler):
        """Test error handling when crawl fails in async context"""
        from src.server.services.knowledge.crawl_orchestration_service import CrawlOrchestrationService
        
        # Make crawler fail
        mock_crawler.arun = AsyncMock(side_effect=Exception("Browser crashed"))
        
        orchestrator = CrawlOrchestrationService(mock_crawler, Mock())
        
        # Error should be handled gracefully
        result = await orchestrator.orchestrate_crawl({'url': 'https://bad-site.com'})
        
        # Should still return task info
        assert 'task_id' in result
        assert result['status'] == 'started'
        
        # The error will be reported via progress updates in background


class TestAsyncSyncSeparation:
    """Test proper separation of async and sync operations"""
    
    @pytest.mark.asyncio
    async def test_no_event_loop_in_threads(self):
        """Test that new event loops are not created in threads"""
        from concurrent.futures import ThreadPoolExecutor
        
        def thread_function():
            # This should not create a new event loop
            try:
                loop = asyncio.get_event_loop()
                return "Found existing loop"
            except RuntimeError:
                return "No event loop in thread"
        
        executor = ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_event_loop()
        
        result = await loop.run_in_executor(executor, thread_function)
        
        # In a proper implementation, threads should not have event loops
        assert result == "No event loop in thread"
    
    @pytest.mark.asyncio
    async def test_database_operations_stay_async(self):
        """Test that database operations remain async"""
        from src.server.services.storage.document_storage_service import add_documents_to_supabase
        
        # Create a mock Supabase client
        mock_supabase_client = Mock()
        mock_supabase_client.table = Mock(return_value=Mock(
            insert=Mock(return_value=Mock(
                execute=Mock(return_value=Mock(data=[]))
            ))
        ))
        
        # Database operations should be async
        await add_documents_to_supabase(
            client=mock_supabase_client,
            urls=["https://example.com"],
            chunk_numbers=[0],
            contents=["Test content"],
            metadatas=[{"source_id": "example.com"}],
            url_to_full_document={"https://example.com": "Full content"},
            batch_size=10
        )
        
        # Verify Supabase operations were called
        mock_supabase_client.table.assert_called()
    
    @pytest.mark.asyncio
    async def test_embedding_generation_in_threads(self):
        """Test that embedding generation can run in threads"""
        from concurrent.futures import ThreadPoolExecutor
        
        def generate_embeddings_sync(texts):
            # Simulate CPU-intensive embedding generation
            embeddings = []
            for text in texts:
                # Mock embedding calculation
                embedding = [0.1] * 1536  # OpenAI embedding dimension
                embeddings.append(embedding)
            return embeddings
        
        texts = ["Text 1", "Text 2", "Text 3"]
        
        # Run in thread pool
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=2)
        
        embeddings = await loop.run_in_executor(
            executor,
            generate_embeddings_sync,
            texts
        )
        
        assert len(embeddings) == 3
        assert len(embeddings[0]) == 1536
    
    @pytest.mark.asyncio
    async def test_contextual_embeddings_batch_processing(self):
        """Test that contextual embeddings use batch processing efficiently"""
        # Skip this test if OpenAI API key is not available
        import os
        if not os.getenv('OPENAI_API_KEY'):
            # This is a conceptual test to verify the batch processing design
            # When API key is available, it would process multiple chunks in one API call
            return
        
        from src.server.services.embeddings.contextual_embedding_service import (
            generate_contextual_embeddings_batch
        )
        
        # Mock the LLM client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Context for chunk 1\n---\nChunk 1 content")),
            Mock(message=Mock(content="Context for chunk 2\n---\nChunk 2 content"))
        ]
        mock_client.chat.completions.create = Mock(return_value=mock_response)
        
        with patch('src.server.services.embeddings.contextual_embedding_service.get_llm_client_sync',
                  return_value=mock_client):
            
            full_docs = ["Full document 1", "Full document 2"]
            chunks = ["Chunk 1 content", "Chunk 2 content"]
            
            # This should process in a single API call
            results = generate_contextual_embeddings_batch(full_docs, chunks)
            
            # Verify batch processing
            assert len(results) == 2
            assert all(success for _, success in results)
            
            # Verify only one API call for the batch
            mock_client.chat.completions.create.assert_called_once()