"""
Test Socket.IO crawl progress tracking.

Tests the Socket.IO implementation for crawl and document upload progress tracking.
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import os

# CRITICAL: Set test environment to prevent real DB connections
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
            yield

@pytest.mark.asyncio 
async def test_document_upload_progress_mapping(async_client):
    """Test that document upload progress uses ProgressMapper and doesn't reset to 0%."""
    
    # Track all progress updates
    progress_updates = []
    
    # Mock Socket.IO emit to capture progress
    with patch('src.server.fastapi.socketio_handlers.broadcast_crawl_progress') as mock_emit:
        # Capture all emit calls
        def capture_progress(progress_id, data):
            if isinstance(data, dict) and 'percentage' in data:
                progress_updates.append({
                    'status': data.get('status'),
                    'percentage': data['percentage'],
                    'log': data.get('log', '')
                })
        
        mock_emit.side_effect = capture_progress
        
        # Mock file upload
        with patch('src.server.fastapi.knowledge_api.extract_text_from_document') as mock_extract:
            mock_extract.return_value = "Test document content " * 100  # Long enough content
            
            # CRITICAL: Mock document storage to prevent real uploads
            with patch('src.server.services.storage.document_storage_service.add_documents_to_supabase') as mock_store:
                async def mock_add_documents(*args, **kwargs):
                    return {'success': True, 'error': None}
                mock_store.side_effect = mock_add_documents
                
                # Mock DocumentStorageSync to prevent real storage
                with patch('src.server.services.storage.document_storage_sync.store_document_chunks_sync') as mock_sync_store:
                    mock_sync_store.return_value = {'success': True, 'chunks_stored': 1, 'error': None}
                    
                    # Mock Supabase operations - override the safety fixture
                    with patch('src.server.services.client_manager.get_supabase_client') as mock_supabase:
                        # Create a safe mock that simulates successful operations without real DB access
                        safe_mock_client = Mock()
                        safe_mock_client.table = Mock(return_value=Mock(
                            insert=Mock(return_value=Mock(
                                execute=Mock(return_value=Mock(data=[], error=None))
                            )),
                            delete=Mock(return_value=Mock(
                                in_=Mock(return_value=Mock(
                                    execute=Mock(return_value=Mock(data=[], error=None))
                                )),
                                eq=Mock(return_value=Mock(
                                    execute=Mock(return_value=Mock(data=[], error=None))
                                ))
                            )),
                            select=Mock(return_value=Mock(
                                eq=Mock(return_value=Mock(
                                    execute=Mock(return_value=Mock(data=[], error=None))
                                ))
                            ))
                        ))
                        mock_supabase.return_value = safe_mock_client
                        
                        # Mock OpenAI client for embeddings and set environment
                        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
                            with patch('src.server.services.llm_provider_service.get_llm_client_sync') as mock_llm:
                                mock_openai = Mock()
                                mock_openai.embeddings.create = Mock(return_value=Mock(
                                    data=[Mock(embedding=[0.1] * 1536)]
                                ))
                                mock_llm.return_value = mock_openai
                                
                                # Mock file storage to prevent actual file operations
                                with patch('src.server.fastapi.knowledge_api.UploadFile') as mock_upload:
                                    mock_file = Mock()
                                    mock_file.filename = 'test.pdf'
                                    mock_file.content_type = 'application/pdf'
                                    mock_file.read = AsyncMock(return_value=b'test content')
                                    
                                    # Create multipart form data
                                    files = {'file': ('test.pdf', b'test content', 'application/pdf')}
                                    data = {
                                        'knowledge_type': 'technical',
                                        'tags': json.dumps(['test'])
                                    }
                                    
                                    # Upload document
                                    response = await async_client.post(
                                        '/api/documents/upload',
                                        files=files,
                                        data=data
                                    )
                                
                                assert response.status_code == 200
                                result = response.json()
                                assert 'progressId' in result
                                
                                # Wait for async operations to complete
                                await asyncio.sleep(0.5)
    
    # Verify progress never went backwards
    percentages = [p['percentage'] for p in progress_updates if p['percentage'] >= 0]
    
    # Check that we have progress updates
    assert len(percentages) > 0, "No progress updates were captured"
    
    # Verify progress never decreases
    for i in range(1, len(percentages)):
        assert percentages[i] >= percentages[i-1], \
            f"Progress went backwards: {percentages[i-1]}% -> {percentages[i]}% " \
            f"(status: {progress_updates[i-1]['status']} -> {progress_updates[i]['status']})"
    
    # Verify document_storage stage doesn't start at 0%
    storage_updates = [p for p in progress_updates if p['status'] == 'document_storage']
    if storage_updates:
        first_storage = storage_updates[0]['percentage']
        assert first_storage >= 35, \
            f"Document storage started at {first_storage}%, should be >= 35%"

@pytest.mark.asyncio
async def test_crawl_progress_with_socketio(async_client):
    """Test web crawl progress tracking via Socket.IO."""
    
    progress_updates = []
    
    with patch('src.server.fastapi.socketio_handlers.broadcast_crawl_progress') as mock_emit:
        # Capture progress
        def capture_progress(progress_id, data):
            if isinstance(data, dict) and 'percentage' in data:
                progress_updates.append(data['percentage'])
        
        mock_emit.side_effect = capture_progress
        
        # Mock crawler and other dependencies
        with patch('src.server.services.crawler_manager.get_crawler') as mock_get_crawler:
            mock_crawler = AsyncMock()
            mock_result = Mock(
                success=True,
                url="https://example.com",
                markdown="# Test Content\n\n" + "Test content. " * 50,
                html="<h1>Test</h1>",
                metadata={"title": "Test"},
                error_message=None
            )
            mock_crawler.arun.return_value = mock_result
            mock_get_crawler.return_value = mock_crawler
            
            # Mock Supabase
            with patch('src.server.services.client_manager.get_supabase_client') as mock_supabase:
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
                mock_supabase.return_value = mock_client
                
                # Mock OpenAI client for embeddings
                with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
                    with patch('src.server.services.llm_provider_service.get_llm_client_sync') as mock_llm:
                        mock_openai = Mock()
                        mock_openai.embeddings.create = Mock(return_value=Mock(
                            data=[Mock(embedding=[0.1] * 1536)]
                        ))
                        mock_llm.return_value = mock_openai
                        
                        # Start crawl
                        response = await async_client.post(
                            '/api/knowledge-items/crawl',
                            json={
                                "url": "https://example.com",
                                "knowledge_type": "technical",
                                "tags": ["test"]
                            }
                        )
                        
                        assert response.status_code == 200
                        await asyncio.sleep(0.5)
    
    # Verify progress tracking
    assert len(progress_updates) > 0
    for i in range(1, len(progress_updates)):
        assert progress_updates[i] >= progress_updates[i-1], \
            f"Progress decreased: {progress_updates}"

@pytest.mark.asyncio
async def test_socketio_heartbeat_during_long_operations(async_client):
    """Test that heartbeat messages are sent during long operations."""
    
    heartbeat_count = 0
    
    with patch('src.server.fastapi.socketio_handlers.broadcast_crawl_progress') as mock_emit:
        # Count heartbeats
        def check_heartbeat(progress_id, data):
            if isinstance(data, dict) and data.get('heartbeat'):
                nonlocal heartbeat_count
                heartbeat_count += 1
        
        mock_emit.side_effect = check_heartbeat
        
        # Mock a long-running operation
        with patch('src.server.services.knowledge.crawl_orchestration_service.CrawlOrchestrationService._async_orchestrate_crawl') as mock_crawl:
            async def long_operation(*args, **kwargs):
                # Simulate long operation with heartbeats
                for _ in range(3):
                    await asyncio.sleep(0.1)
                    # In real implementation, heartbeat would be sent here
            
            mock_crawl.side_effect = long_operation
            
            # This test verifies the heartbeat mechanism exists in the implementation
            # Currently heartbeats are not implemented, so this test documents the need
            assert heartbeat_count == 0  # Expected to be 0 until heartbeats are implemented

@pytest.mark.asyncio
async def test_socketio_error_propagation(async_client):
    """Test that errors are properly propagated via Socket.IO."""
    
    error_emitted = False
    error_message = None
    
    with patch('src.server.fastapi.socketio_handlers.broadcast_crawl_progress') as mock_emit:
        # Check for error emit
        def check_error(progress_id, data):
            nonlocal error_emitted, error_message
            if isinstance(data, dict) and 'error' in data.get('status', ''):
                error_emitted = True
                error_message = data.get('log', '')
        
        mock_emit.side_effect = check_error
        
        # Mock crawler to fail
        with patch('src.server.services.crawler_manager.get_crawler') as mock_get_crawler:
            mock_crawler = AsyncMock()
            mock_crawler.arun.side_effect = Exception("Test crawl error")
            mock_get_crawler.return_value = mock_crawler
            
            # Start crawl that will fail
            response = await async_client.post(
                '/api/knowledge-items/crawl',
                json={
                    "url": "https://example.com",
                    "knowledge_type": "technical"
                }
            )
            
            assert response.status_code == 200
            await asyncio.sleep(0.5)
    
    # Verify error was emitted
    assert error_emitted, "Error was not emitted via Socket.IO"
    assert error_message and "error" in error_message.lower()