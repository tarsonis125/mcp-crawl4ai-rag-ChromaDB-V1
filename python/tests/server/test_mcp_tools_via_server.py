"""
Test MCP Tools via Server API

These tests verify that the Server correctly interacts with MCP tools
through API endpoints and service clients. We mock MCP responses based
on the actual MCP server implementation.
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime


class TestMCPToolsViaServer:
    """Test MCP tools through Server API endpoints."""
    
    @pytest.mark.asyncio
    async def test_health_check_tool(self, async_client):
        """Test MCP health_check tool via Server."""
        # The Server's /api/mcp/status endpoint indirectly uses MCP health
        response = await async_client.get('/api/mcp/status')
        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        assert 'mcp_available' in data
    
    @pytest.mark.asyncio
    async def test_get_available_sources(self, async_client):
        """Test get_available_sources through Server API."""
        # Mock the source management service response
        mock_sources = [
            {"source_id": "docs.python.org", "title": "Python Docs"},
            {"source_id": "api.example.com", "title": "Example API"}
        ]
        
        with patch('src.server.services.source_management_service.SourceManagementService.get_all_sources',
                   new=AsyncMock(return_value=mock_sources)):
            response = await async_client.get('/api/knowledge-items/sources')
            assert response.status_code == 200
            sources = response.json()
            assert len(sources) == 2
            assert sources[0]["source_id"] == "docs.python.org"
    
    @pytest.mark.asyncio
    async def test_crawl_single_page(self, async_client):
        """Test crawl_single_page through Server API."""
        mock_progress_id = "crawl-progress-123"
        
        with patch('src.server.services.rag.crawling_service.CrawlingService.crawl_single_page',
                   new=AsyncMock(return_value={
                       "success": True,
                       "progressId": mock_progress_id,
                       "message": "Crawling started"
                   })):
            response = await async_client.post(
                '/api/knowledge-items/crawl',
                json={
                    "url": "https://docs.python.org",
                    "knowledge_type": "documentation",
                    "tags": ["python", "docs"]
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["progressId"] == mock_progress_id
    
    @pytest.mark.asyncio
    async def test_perform_rag_query(self, async_client):
        """Test perform_rag_query through Server API."""
        mock_results = [
            {
                "content": "Python is a high-level programming language...",
                "source": "docs.python.org",
                "similarity": 0.92,
                "metadata": {"section": "introduction"}
            }
        ]
        
        with patch('src.server.services.rag.search_service.SearchService.search',
                   new=AsyncMock(return_value=mock_results)):
            response = await async_client.post(
                '/api/knowledge-items/search',
                json={"query": "What is Python?"}
            )
            
            assert response.status_code == 200
            results = response.json()
            assert len(results) == 1
            assert results[0]["content"].startswith("Python is")
            assert results[0]["similarity"] == 0.92
    
    @pytest.mark.asyncio
    async def test_manage_project_operations(self, async_client):
        """Test manage_project tool operations through Server API."""
        # Test LIST action
        mock_projects = [
            {
                "id": "proj-1",
                "title": "Test Project 1",
                "created_at": datetime.now().isoformat()
            }
        ]
        
        with patch('src.server.services.projects.project_service.ProjectService.get_all_projects',
                   new=AsyncMock(return_value=mock_projects)):
            response = await async_client.get('/api/projects')
            assert response.status_code == 200
            projects = response.json()
            assert len(projects) == 1
            assert projects[0]["title"] == "Test Project 1"
        
        # Test CREATE action
        new_project_id = "proj-2"
        with patch('src.server.services.projects.project_service.ProjectService.create_project',
                   new=AsyncMock(return_value={
                       "id": new_project_id,
                       "title": "New Project",
                       "created_at": datetime.now().isoformat()
                   })):
            response = await async_client.post(
                '/api/projects',
                json={"title": "New Project"}
            )
            assert response.status_code == 200
            project = response.json()
            assert project["id"] == new_project_id
            assert project["title"] == "New Project"
    
    @pytest.mark.asyncio
    async def test_manage_task_operations(self, async_client):
        """Test manage_task tool operations through Server API."""
        project_id = "proj-1"
        task_id = "task-1"
        
        # Test CREATE action
        with patch('src.server.services.projects.task_service.TaskService.create_task',
                   new=AsyncMock(return_value={
                       "id": task_id,
                       "project_id": project_id,
                       "title": "Implement feature",
                       "status": "todo",
                       "assignee": "User",
                       "created_at": datetime.now().isoformat()
                   })):
            response = await async_client.post(
                f'/api/projects/{project_id}/tasks',
                json={
                    "title": "Implement feature",
                    "description": "Add new functionality",
                    "assignee": "User"
                }
            )
            assert response.status_code == 200
            task = response.json()
            assert task["id"] == task_id
            assert task["status"] == "todo"
        
        # Test UPDATE action
        with patch('src.server.services.projects.task_service.TaskService.update_task',
                   new=AsyncMock(return_value={
                       "id": task_id,
                       "status": "doing",
                       "updated_at": datetime.now().isoformat()
                   })):
            response = await async_client.patch(
                f'/api/projects/{project_id}/tasks/{task_id}',
                json={"status": "doing"}
            )
            assert response.status_code == 200
            updated_task = response.json()
            assert updated_task["status"] == "doing"
    
    @pytest.mark.asyncio
    async def test_search_code_examples(self, async_client):
        """Test search_code_examples through Server API."""
        mock_code_results = [
            {
                "code": "def hello_world():\n    print('Hello, World!')",
                "summary": "Basic hello world function",
                "source": "examples.python.org",
                "similarity": 0.88
            }
        ]
        
        # When Server implements code search endpoint, test it here
        # For now, this is a placeholder for future implementation
        pass
    
    @pytest.mark.asyncio
    async def test_delete_source(self, async_client):
        """Test delete_source operation through Server API."""
        source_to_delete = "old.example.com"
        
        with patch('src.server.services.source_management_service.SourceManagementService.delete_source',
                   new=AsyncMock(return_value={"deleted": 5})):
            # When Server implements source deletion endpoint
            # response = await async_client.delete(f'/api/knowledge-items/sources/{source_to_delete}')
            # assert response.status_code == 200
            pass
    
    @pytest.mark.asyncio
    async def test_mcp_error_propagation(self, async_client):
        """Test that MCP errors are properly propagated through Server."""
        # Test timeout errors
        with patch('src.server.services.rag.crawling_service.CrawlingService.crawl_single_page',
                   side_effect=TimeoutError("Crawl operation timed out")):
            response = await async_client.post(
                '/api/knowledge-items/crawl',
                json={"url": "https://slow-site.com", "knowledge_type": "documentation"}
            )
            assert response.status_code == 500
            assert "error" in response.json()["detail"]
        
        # Test validation errors
        response = await async_client.post(
            '/api/knowledge-items/crawl',
            json={"url": "not-a-valid-url", "knowledge_type": "documentation"}
        )
        assert response.status_code in [400, 422]  # Bad request or validation error