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
    def test_start_mcp_server_endpoint(self):
        """Test the /api/mcp/start endpoint."""
        from src.api_wrapper import app
        
        client = TestClient(app)
        
        with patch('src.api_wrapper.mcp_manager') as mock_manager:
            mock_manager.start_server.return_value = {
                'success': True, 
                'status': 'starting',
                'message': 'MCP server is starting'
            }
            
            response = client.post("/api/mcp/start")
            
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert data['status'] == 'starting'
            mock_manager.start_server.assert_called_once()
    
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
    def test_server_management_error_handling(self):
        """Test error handling in server management endpoints."""
        from src.api_wrapper import app
        
        client = TestClient(app)
        
        with patch('src.api_wrapper.mcp_manager') as mock_manager:
            mock_manager.start_server.side_effect = Exception("Server start failed")
            
            response = client.post("/api/mcp/start")
            
            assert response.status_code == 500
            data = response.json()
            assert 'detail' in data
            assert 'error' in data['detail']
            assert 'Server start failed' in data['detail']['error']


class TestCrawlingEndpoints:
    """Tests for crawling operation endpoints."""
    
    @pytest.mark.unit
    def test_crawl_single_page_endpoint(self):
        """Test the /api/crawl/single endpoint."""
        from src.api_wrapper import app, mcp_client
        
        client = TestClient(app)
        
        with patch.object(mcp_client, 'call_tool') as mock_call_tool:
            mock_call_tool.return_value = {
                'success': True,
                'url': 'https://example.com',
                'chunks_stored': 5,
                'content_length': 1500
            }
            
            response = client.post("/api/crawl/single", 
                                 json={'url': 'https://example.com'})
            
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert data['url'] == 'https://example.com'
            assert data['chunks_stored'] == 5
            mock_call_tool.assert_called_once_with(
                'crawl_single_page',
                {'url': 'https://example.com/'}  # Pydantic HttpUrl adds trailing slash
            )
    
    @pytest.mark.unit
    def test_smart_crawl_url_endpoint(self):
        """Test the /api/crawl/smart endpoint."""
        from src.api_wrapper import app, mcp_client
        
        client = TestClient(app)
        
        with patch.object(mcp_client, 'call_tool') as mock_call_tool:
            mock_call_tool.return_value = {
                'success': True,
                'crawl_type': 'webpage',
                'urls_processed': 10,
                'total_chunks': 50
            }
            
            payload = {
                'url': 'https://example.com',
                'max_depth': 2,
                'max_concurrent': 5
            }
            
            response = client.post("/api/crawl/smart", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert data['urls_processed'] == 10
            mock_call_tool.assert_called_once_with(
                'smart_crawl_url',
                {
                    'url': 'https://example.com/',  # Pydantic HttpUrl adds trailing slash
                    'max_depth': 2,
                    'max_concurrent': 5,
                    'chunk_size': 5000  # Default value from the model
                }
            )
    
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
    def test_rag_query_endpoint(self):
        """Test the /api/rag/query endpoint."""
        from src.api_wrapper import app, mcp_client
        
        client = TestClient(app)
        
        with patch.object(mcp_client, 'call_tool') as mock_call_tool:
            mock_call_tool.return_value = {
                'results': [
                    {'content': 'Relevant content 1', 'score': 0.95},
                    {'content': 'Relevant content 2', 'score': 0.87}
                ],
                'query': 'test query'
            }
            
            payload = {
                'query': 'test query',
                'source': 'example.com'
            }
            
            response = client.post("/api/rag/query", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert len(data['results']) == 2
            assert data['results'][0]['score'] == 0.95
            mock_call_tool.assert_called_once_with(
                'perform_rag_query',
                {
                    'query': 'test query',
                    'source': 'example.com',
                    'match_count': 5  # Default value from the model
                }
            )
    
    @pytest.mark.unit
    def test_get_sources_endpoint(self):
        """Test the /api/rag/sources endpoint."""
        from src.api_wrapper import app, mcp_client
        
        client = TestClient(app)
        
        with patch.object(mcp_client, 'call_tool') as mock_call_tool:
            mock_call_tool.return_value = {
                'sources': ['example.com', 'docs.example.com', 'blog.example.com']
            }
            
            response = client.get("/api/rag/sources")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data['sources']) == 3
            assert 'example.com' in data['sources']
            mock_call_tool.assert_called_once_with(
                'get_available_sources',
                {}
            )


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
    @patch('subprocess.Popen')
    def test_start_server(self, mock_popen, mock_config):
        """Test starting the MCP server process."""
        from src.api_wrapper import MCPServerManager
        
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is running
        mock_popen.return_value = mock_process
        
        manager = MCPServerManager()
        result = manager.start_server()
        
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
    def test_mcp_server_connection_error(self):
        """Test handling when MCP server is not available."""
        from src.api_wrapper import app
        
        client = TestClient(app)
        
        with patch('src.api_wrapper.mcp_client') as mock_client:
            mock_client.call_tool.side_effect = ConnectionError("MCP server not available")
            
            response = client.post("/api/crawl/single", 
                                 json={'url': 'https://example.com'})
            
            assert response.status_code == 503  # Service unavailable
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