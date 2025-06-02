"""
Tests for the backend API wrapper that provides REST endpoints for the React app.
These tests will initially fail until the API wrapper is implemented.
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.fixture
def mock_config():
    """Mock environment configuration."""
    with patch('src.api_wrapper.load_environment_config') as mock_load_config, \
         patch('src.api_wrapper.get_rag_strategy_config') as mock_rag_config:
        
        # Mock the config objects
        mock_env_config = MagicMock()
        mock_env_config.openai_api_key = "sk-test123"
        mock_env_config.supabase_url = "https://test.supabase.co"
        mock_env_config.supabase_service_key = "test-service-key"
        mock_env_config.host = "localhost"
        mock_env_config.port = 8051
        mock_env_config.transport = "stdio"
        mock_env_config.model_choice = "gpt-4"
        
        mock_rag_config_obj = MagicMock()
        mock_rag_config_obj.use_contextual_embeddings = True
        mock_rag_config_obj.use_hybrid_search = True
        mock_rag_config_obj.use_agentic_rag = False
        mock_rag_config_obj.use_reranking = True
        
        mock_load_config.return_value = mock_env_config
        mock_rag_config.return_value = mock_rag_config_obj
        
        yield mock_env_config, mock_rag_config_obj


@pytest.mark.unit
def test_api_wrapper_imports():
    """Test that the API wrapper module can be imported."""
    # This will fail until we create the api_wrapper module
    from src.api_wrapper import app, MCPServerManager
    
    assert app is not None
    assert MCPServerManager is not None


@pytest.mark.unit 
def test_create_test_client():
    """Test that we can create a test client for the API wrapper."""
    from src.api_wrapper import app
    
    client = TestClient(app)
    assert client is not None


class TestMCPServerManagement:
    """Tests for MCP server process management."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_start_mcp_server_endpoint(self, async_client):
        """Test the /api/mcp/start endpoint."""
        # Patch the MCPServerManager class method directly
        with patch('src.api_wrapper.MCPServerManager.start_server') as mock_start_server:
            mock_start_server.return_value = {
                'success': True, 
                'status': 'starting',
                'message': 'MCP server is starting'
            }
            
            response = await async_client.post("/api/mcp/start")
            
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert data['status'] == 'starting'
            mock_start_server.assert_called_once()
    
    @pytest.mark.unit
    def test_stop_mcp_server_endpoint(self):
        """Test the /api/mcp/stop endpoint."""
        from src.api_wrapper import app
        
        client = TestClient(app)
        
        with patch('src.api_wrapper.mcp_manager') as mock_manager:
            mock_manager.stop_server.return_value = {
                'success': True,
                'status': 'stopped',
                'message': 'MCP server stopped'
            }
            
            response = client.post("/api/mcp/stop")
            
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert data['status'] == 'stopped'
            mock_manager.stop_server.assert_called_once()
    
    @pytest.mark.unit
    def test_get_mcp_server_status_endpoint(self):
        """Test the /api/mcp/status endpoint."""
        from src.api_wrapper import app
        
        client = TestClient(app)
        
        with patch('src.api_wrapper.mcp_manager') as mock_manager:
            mock_manager.get_status.return_value = {
                'status': 'running',
                'uptime': 3600,
                'logs': ['Server started', 'Ready to accept connections']
            }
            
            response = client.get("/api/mcp/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'running'
            assert data['uptime'] == 3600
            assert len(data['logs']) == 2
            mock_manager.get_status.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_server_management_error_handling(self, async_client):
        """Test error handling in server management endpoints."""
        with patch('src.api_wrapper.mcp_manager') as mock_manager:
            # Mock the async start_server method to raise an exception
            mock_manager.start_server = AsyncMock(side_effect=Exception("Server start failed"))
            
            response = await async_client.post("/api/mcp/start")
            
            assert response.status_code == 500
            data = response.json()
            assert 'detail' in data
            assert 'error' in data['detail']
            assert 'Server start failed' in data['detail']['error']


class TestCrawlingEndpoints:
    """Tests for crawling operation endpoints."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_crawl_single_page_endpoint(self, async_client):
        """Test the /api/crawl/single endpoint."""
        # Mock the direct function call that the endpoint now uses
        with patch('src.api_wrapper.mcp_crawl_single_page') as mock_crawl_function:
            mock_crawl_function.return_value = {
                'success': True,
                'url': 'https://example.com',
                'chunks_stored': 5,
                'content_length': 1500
            }
            
            # Mock the crawling context
            with patch('src.api_wrapper.crawling_context') as mock_context:
                mock_context.create_context.return_value = MagicMock()
                
                response = await async_client.post("/api/crawl/single", 
                                             json={'url': 'https://example.com'})
                
                assert response.status_code == 200
                data = response.json()
                assert data['success'] is True
                assert data['url'] == 'https://example.com'
                assert data['chunks_stored'] == 5
                mock_crawl_function.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_smart_crawl_url_endpoint(self, async_client):
        """Test the /api/crawl/smart endpoint."""
        # Mock the direct function call that the endpoint now uses
        with patch('src.api_wrapper.mcp_smart_crawl_url') as mock_smart_crawl:
            mock_smart_crawl.return_value = {
                'success': True,
                'crawl_type': 'webpage',
                'urls_processed': 10,
                'total_chunks': 50
            }
            
            # Mock the crawling context
            with patch('src.api_wrapper.crawling_context') as mock_context:
                mock_context.create_context.return_value = MagicMock()
                
                payload = {
                    'url': 'https://example.com',
                    'max_depth': 2,
                    'max_concurrent': 5
                }
                
                response = await async_client.post("/api/crawl/smart", json=payload)
                
                assert response.status_code == 200
                data = response.json()
                assert data['success'] is True
                assert data['urls_processed'] == 10
                mock_smart_crawl.assert_called_once()
    
    @pytest.mark.unit
    def test_crawl_endpoint_validation(self):
        """Test request validation for crawling endpoints."""
        from src.api_wrapper import app
        
        client = TestClient(app)
        
        # Test missing URL
        response = client.post("/api/crawl/single", json={})
        assert response.status_code == 422  # Validation error
        
        # Test invalid URL format
        response = client.post("/api/crawl/single", 
                             json={'url': 'not-a-url'})
        assert response.status_code == 422


class TestRAGEndpoints:
    """Tests for RAG operation endpoints."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rag_query_endpoint(self, async_client):
        """Test the /api/rag/query endpoint."""
        # Mock the direct function call that the endpoint now uses
        with patch('src.api_wrapper.mcp_perform_rag_query') as mock_rag_query:
            mock_rag_query.return_value = {
                'results': [
                    {'content': 'Relevant content 1', 'score': 0.95},
                    {'content': 'Relevant content 2', 'score': 0.87}
                ],
                'query': 'test query'
            }
            
            # Mock the crawling context
            with patch('src.api_wrapper.crawling_context') as mock_context:
                mock_context._initialized = True
                mock_context.create_context.return_value = MagicMock()
                
                payload = {
                    'query': 'test query',
                    'source': 'example.com'
                }
                
                response = await async_client.post("/api/rag/query", json=payload)
                
                assert response.status_code == 200
                data = response.json()
                assert len(data['results']) == 2
                assert data['results'][0]['score'] == 0.95
                mock_rag_query.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_sources_endpoint(self, async_client):
        """Test the /api/rag/sources endpoint."""
        # Mock the direct function call that the endpoint now uses
        with patch('src.api_wrapper.mcp_get_available_sources') as mock_get_sources:
            mock_get_sources.return_value = {
                'sources': ['example.com', 'docs.example.com', 'blog.example.com']
            }
            
            # Mock the crawling context
            with patch('src.api_wrapper.crawling_context') as mock_context:
                mock_context._initialized = True
                mock_context.create_context.return_value = MagicMock()
                
                response = await async_client.get("/api/rag/sources")
                
                assert response.status_code == 200
                data = response.json()
                assert len(data['sources']) == 3
                assert 'example.com' in data['sources']
                mock_get_sources.assert_called_once()


class TestDatabaseEndpoints:
    """Tests for database metrics endpoints."""
    
    @pytest.mark.unit
    def test_database_metrics_endpoint(self):
        """Test the /api/database/metrics endpoint."""
        from src.api_wrapper import app
        
        client = TestClient(app)
        
        with patch('src.api_wrapper.get_database_metrics') as mock_metrics:
            mock_metrics.return_value = {
                'documents': 256,
                'storage_used': '1.2 GB',
                'last_sync': '2024-01-20T10:30:00Z'
            }
            
            response = client.get("/api/database/metrics")
            
            assert response.status_code == 200
            data = response.json()
            assert data['documents'] == 256
            assert data['storage_used'] == '1.2 GB'
            mock_metrics.assert_called_once()


class TestMCPServerManager:
    """Tests for the MCPServerManager class."""
    
    @pytest.mark.unit
    def test_mcp_server_manager_init(self):
        """Test MCPServerManager initialization."""
        from src.api_wrapper import MCPServerManager
        
        manager = MCPServerManager()
        assert manager.process is None
        assert manager.status == 'stopped'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch('subprocess.Popen')
    async def test_start_server(self, mock_popen, mock_config):
        """Test starting the MCP server process."""
        from src.api_wrapper import MCPServerManager
        
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is running
        mock_popen.return_value = mock_process
        
        # Mock credential service calls
        with patch('src.api_wrapper.credential_service') as mock_credential_service:
            mock_credential_service.get_credential = AsyncMock(side_effect=[
                'sk-test123',  # OPENAI_API_KEY
                'gpt-4o-mini',  # MODEL_CHOICE
                'sse',  # TRANSPORT
                'localhost',  # HOST
                '8051',  # PORT
                'false',  # USE_CONTEXTUAL_EMBEDDINGS
                'false',  # USE_HYBRID_SEARCH
                'false',  # USE_AGENTIC_RAG
                'false',  # USE_RERANKING
            ])
            
            manager = MCPServerManager()
            result = await manager.start_server()
            
            assert result['success'] is True
            assert result['status'] == 'starting'
            assert manager.process is not None
            mock_popen.assert_called_once()
    
    @pytest.mark.unit
    def test_stop_server(self):
        """Test stopping the MCP server process."""
        from src.api_wrapper import MCPServerManager
        
        manager = MCPServerManager()
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.wait.return_value = None
        manager.process = mock_process
        manager.status = 'running'
        
        result = manager.stop_server()
        
        assert result['success'] is True
        assert result['status'] == 'stopped'
        mock_process.terminate.assert_called_once()
    
    @pytest.mark.unit
    def test_get_status(self):
        """Test getting server status."""
        from src.api_wrapper import MCPServerManager
        
        manager = MCPServerManager()
        manager.status = 'running'
        manager.start_time = 1234567890
        manager.logs = ['Server started', 'Ready']
        
        with patch('time.time', return_value=1234567890 + 3600):
            status = manager.get_status()
        
        assert status['status'] == 'running'
        assert status['uptime'] == 3600
        assert len(status['logs']) == 2


class TestErrorHandling:
    """Tests for API error handling."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_mcp_server_connection_error(self, async_client):
        """Test handling when MCP server is not available."""
        # Mock the crawl function to raise a connection error
        with patch('src.api_wrapper.mcp_crawl_single_page') as mock_crawl:
            mock_crawl.side_effect = ConnectionError("MCP server not available")
            
            # Mock the crawling context
            with patch('src.api_wrapper.crawling_context') as mock_context:
                mock_context.create_context.return_value = MagicMock()
                
                response = await async_client.post("/api/crawl/single", 
                                             json={'url': 'https://example.com'})
                
                assert response.status_code == 500  # Internal server error (not 503)
                data = response.json()
                assert 'detail' in data
                assert 'error' in data['detail']
                assert 'MCP server not available' in data['detail']['error']
    
    @pytest.mark.unit
    def test_invalid_json_request(self):
        """Test handling invalid JSON requests."""
        from src.api_wrapper import app
        
        client = TestClient(app)
        
        response = client.post("/api/crawl/single",
                             data="invalid json",
                             headers={'Content-Type': 'application/json'})
        
        assert response.status_code == 422 