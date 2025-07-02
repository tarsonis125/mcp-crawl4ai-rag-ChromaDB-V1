"""
Server-side MCP Integration Tests

Tests the Server's interaction with MCP services through API endpoints,
mocking MCP responses based on actual MCP server implementation.
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime


class TestMCPIntegration:
    """Test Server's integration with MCP service."""
    
    @pytest.mark.asyncio
    async def test_mcp_health_endpoint(self, async_client):
        """Test MCP health status endpoint."""
        # Mock the MCP session manager response
        mock_sessions = {
            "active_sessions": {
                "test-session": {
                    "session_id": "test-session",
                    "container_name": "test-container",
                    "status": "running",
                    "created_at": datetime.now().isoformat()
                }
            }
        }
        
        with patch('src.server.fastapi.mcp_api.session_manager.get_all_sessions', 
                   return_value=mock_sessions):
            response = await async_client.get('/api/mcp/status')
            assert response.status_code == 200
            data = response.json()
            assert 'status' in data
            assert 'mcp_available' in data
            assert 'sessions' in data
    
    @pytest.mark.asyncio
    async def test_mcp_tool_execution_health_check(self, async_client):
        """Test executing MCP health_check tool through Server API."""
        # Mock MCP tool response format (based on actual MCP implementation)
        mock_mcp_response = {
            "success": True,
            "health": {
                "status": "healthy",
                "api_service": True,
                "agents_service": True,
                "last_health_check": datetime.now().isoformat()
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # TODO: When Server adds MCP tool execution endpoint, test it here
        # For now, we test the indirect health check through status endpoint
        response = await async_client.get('/api/mcp/status')
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_crawl_single_page_through_api(self, async_client):
        """Test crawling through Server API that delegates to MCP."""
        # Mock the expected MCP response format
        mock_progress_id = "test-progress-123"
        
        with patch('src.server.services.rag.crawling_service.CrawlingService.crawl_single_page',
                   new=AsyncMock(return_value={
                       "success": True,
                       "progressId": mock_progress_id,
                       "message": "Crawling started"
                   })):
            response = await async_client.post(
                '/api/knowledge-items/crawl',
                json={
                    "url": "https://example.com",
                    "knowledge_type": "documentation",
                    "tags": ["test"],
                    "update_frequency": 7
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["progressId"] == mock_progress_id
    
    @pytest.mark.asyncio
    async def test_get_available_sources_mock(self, async_client):
        """Test getting available sources with MCP response format."""
        # Mock MCP get_available_sources response
        mock_sources_response = {
            "success": True,
            "sources": ["docs.example.com", "api.example.com"],
            "count": 2
        }
        
        # When Server implements direct MCP tool calls, test here
        # For now, test through knowledge API
        with patch('src.server.services.source_management_service.SourceManagementService.get_all_sources',
                   new=AsyncMock(return_value=[
                       {"source_id": "docs.example.com"},
                       {"source_id": "api.example.com"}
                   ])):
            response = await async_client.get('/api/knowledge-items/sources')
            assert response.status_code == 200
            # Server returns different format than MCP, but same data
            assert len(response.json()) == 2
    
    @pytest.mark.asyncio
    async def test_perform_rag_query_mock(self, async_client):
        """Test RAG query with MCP response format."""
        # Mock MCP perform_rag_query response
        mock_rag_response = {
            "success": True,
            "results": [
                {
                    "content": "Test content about Python",
                    "source": "docs.example.com",
                    "similarity": 0.85,
                    "metadata": {"page": "intro"}
                }
            ],
            "count": 1,
            "query": "Python basics"
        }
        
        with patch('src.server.services.rag.search_service.SearchService.search',
                   new=AsyncMock(return_value=mock_rag_response["results"])):
            response = await async_client.post(
                '/api/knowledge-items/search',
                json={"query": "Python basics"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["content"] == "Test content about Python"
    
    @pytest.mark.asyncio
    async def test_manage_project_create_mock(self, async_client):
        """Test project creation with MCP response format."""
        # Mock MCP manage_project response for create action
        mock_project_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_mcp_response = {
            "success": True,
            "project": {
                "id": mock_project_id,
                "title": "Test Project",
                "created_at": datetime.now().isoformat(),
                "prd": {"summary": "Test PRD"},
                "github_repo": "https://github.com/test/repo"
            }
        }
        
        with patch('src.server.services.projects.project_service.ProjectService.create_project',
                   new=AsyncMock(return_value=mock_mcp_response["project"])):
            response = await async_client.post(
                '/api/projects',
                json={
                    "title": "Test Project",
                    "prd": {"summary": "Test PRD"},
                    "github_repo": "https://github.com/test/repo"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_project_id
            assert data["title"] == "Test Project"
    
    @pytest.mark.asyncio
    async def test_manage_task_create_mock(self, async_client):
        """Test task creation with MCP response format."""
        # Mock MCP manage_task response for create action
        mock_task_id = "660e8400-e29b-41d4-a716-446655440001"
        mock_project_id = "550e8400-e29b-41d4-a716-446655440000"
        
        mock_mcp_response = {
            "success": True,
            "task": {
                "id": mock_task_id,
                "project_id": mock_project_id,
                "title": "Implement feature",
                "description": "Test task description",
                "status": "todo",
                "assignee": "User",
                "created_at": datetime.now().isoformat()
            }
        }
        
        with patch('src.server.services.projects.task_service.TaskService.create_task',
                   new=AsyncMock(return_value=mock_mcp_response["task"])):
            response = await async_client.post(
                f'/api/projects/{mock_project_id}/tasks',
                json={
                    "title": "Implement feature",
                    "description": "Test task description",
                    "assignee": "User"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_task_id
            assert data["title"] == "Implement feature"
            assert data["status"] == "todo"
    
    @pytest.mark.asyncio
    async def test_mcp_error_handling(self, async_client):
        """Test Server's handling of MCP errors."""
        # Mock MCP error response format
        mock_error_response = {
            "success": False,
            "error": "Failed to connect to database"
        }
        
        with patch('src.server.services.projects.project_service.ProjectService.get_all_projects',
                   side_effect=Exception("Database connection failed")):
            response = await async_client.get('/api/projects')
            # Server should handle the error gracefully
            assert response.status_code == 500
            assert "error" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_mcp_service_client_health_check(self):
        """Test MCPServiceClient health check method."""
        from src.server.services.mcp_service_client import MCPServiceClient
        
        client = MCPServiceClient()
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "api_service": True,
            "agents_service": True
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch('httpx.AsyncClient.get', return_value=mock_response):
            result = await client.health_check()
            assert result["api_service"] is True
            assert result["agents_service"] is True
    
    @pytest.mark.asyncio
    async def test_mcp_service_client_crawl_url(self):
        """Test MCPServiceClient crawl_url method."""
        from src.server.services.mcp_service_client import MCPServiceClient
        
        client = MCPServiceClient()
        test_url = "https://example.com"
        
        # Mock HTTP response matching actual API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "progressId": "test-progress-123",
            "message": "Crawling started"
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            result = await client.crawl_url(test_url, options={"max_depth": 2})
            assert result["success"] is True
            assert result["progressId"] == "test-progress-123"
    
    @pytest.mark.asyncio
    async def test_mcp_service_client_search(self):
        """Test MCPServiceClient search method."""
        from src.server.services.mcp_service_client import MCPServiceClient
        
        client = MCPServiceClient()
        test_query = "test query"
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "content": "Test content",
                    "source": "test.com",
                    "similarity": 0.9
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            result = await client.search(test_query, match_count=5)
            assert "results" in result
            assert len(result["results"]) == 1
            assert result["results"][0]["content"] == "Test content"
    
    @pytest.mark.asyncio
    async def test_mcp_websocket_integration(self, async_client):
        """Test that MCP tools can trigger WebSocket broadcasts."""
        # This tests that when MCP performs actions, the Server properly
        # broadcasts updates through WebSocket/Socket.IO
        
        # Mock Socket.IO broadcast
        with patch('src.server.socketio_app.sio.emit', new=AsyncMock()) as mock_emit:
            # Trigger a crawl that would cause progress updates
            with patch('src.server.services.rag.crawling_service.CrawlingService.crawl_single_page',
                       new=AsyncMock(return_value={
                           "success": True,
                           "progressId": "test-123"
                       })):
                response = await async_client.post(
                    '/api/knowledge-items/crawl',
                    json={"url": "https://example.com", "knowledge_type": "documentation"}
                )
                
                assert response.status_code == 200
                # In a real scenario, the crawling service would emit progress events
                # We're verifying the infrastructure is in place for this


class TestMCPToolValidation:
    """Test validation of MCP tool inputs and outputs."""
    
    @pytest.mark.asyncio
    async def test_manage_project_validation(self):
        """Test validation of manage_project tool parameters."""
        # Test that Server properly validates before calling MCP
        # This ensures bad data doesn't reach MCP
        pass  # Implement when Server adds direct MCP tool execution
    
    @pytest.mark.asyncio  
    async def test_manage_task_validation(self):
        """Test validation of manage_task tool parameters."""
        # Test required fields, valid actions, etc.
        pass  # Implement when Server adds direct MCP tool execution
    
    @pytest.mark.asyncio
    async def test_perform_rag_query_validation(self):
        """Test validation of RAG query parameters."""
        # Test query length, match_count limits, etc.
        pass  # Implement when Server adds direct MCP tool execution


class TestMCPSessionManagement:
    """Test MCP session management functionality."""
    
    @pytest.mark.asyncio
    async def test_mcp_session_creation(self, async_client):
        """Test creating a new MCP session."""
        with patch('src.server.services.mcp_session_manager.MCPSessionManager.create_session',
                   new=AsyncMock(return_value={
                       "session_id": "test-session-123",
                       "container_name": "test-container",
                       "status": "running"
                   })):
            # When Server exposes session creation endpoint
            pass
    
    @pytest.mark.asyncio
    async def test_mcp_session_cleanup(self, async_client):
        """Test MCP session cleanup on disconnect."""
        # Test that sessions are properly cleaned up
        pass