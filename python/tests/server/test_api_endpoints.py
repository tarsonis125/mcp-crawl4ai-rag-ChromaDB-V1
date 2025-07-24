"""
Simple API endpoint tests for Server container.

These tests verify basic functionality without complex mocking.
"""
import pytest


class TestAPIEndpoints:
    """Test basic API endpoints."""
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self, async_client):
        """Test root endpoint returns API info."""
        response = await async_client.get('/')
        assert response.status_code == 200
        data = response.json()
        assert 'name' in data
        assert 'status' in data
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self, async_client):
        """Test health endpoint."""
        response = await async_client.get('/health')
        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        # Status can be initializing, healthy, or degraded
        assert data['status'] in ['initializing', 'healthy', 'degraded']
    
    @pytest.mark.asyncio
    async def test_docs_available(self, async_client):
        """Test that API docs are available."""
        response = await async_client.get('/docs')
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_mcp_status_endpoint(self, async_client):
        """Test MCP status endpoint."""
        response = await async_client.get('/api/mcp/status')
        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        # Updated to match actual response fields
        assert data['status'] in ['running', 'stopped', 'error']
        assert 'container_status' in data
    
    @pytest.mark.asyncio
    async def test_projects_list_endpoint(self, async_client):
        """Test projects list endpoint."""
        response = await async_client.get('/api/projects')
        # Should return 200 even if no projects exist
        assert response.status_code == 200
        # Response should be a list
        assert isinstance(response.json(), list)
    
    @pytest.mark.asyncio
    async def test_knowledge_sources_endpoint(self, async_client):
        """Test knowledge sources endpoint."""
        response = await async_client.get('/api/knowledge-items/sources')
        assert response.status_code == 200
        # Response should be a list
        assert isinstance(response.json(), list)
    
    @pytest.mark.asyncio
    async def test_invalid_endpoint(self, async_client):
        """Test that invalid endpoints return 404."""
        response = await async_client.get('/api/nonexistent')
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_crawl_endpoint_validation(self, async_client):
        """Test crawl endpoint input validation."""
        # Missing required fields
        response = await async_client.post(
            '/api/knowledge-items/crawl',
            json={}
        )
        assert response.status_code in [400, 422]  # Bad request or validation error
        
        # Invalid URL
        response = await async_client.post(
            '/api/knowledge-items/crawl',
            json={
                "url": "not-a-url",
                "knowledge_type": "documentation"
            }
        )
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_search_endpoint_validation(self, async_client):
        """Test search endpoint input validation."""
        # Missing query
        response = await async_client.post(
            '/api/knowledge-items/search',
            json={}
        )
        assert response.status_code in [400, 422]
        
        # Empty query
        response = await async_client.post(
            '/api/knowledge-items/search',
            json={"query": ""}
        )
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_project_creation_validation(self, async_client):
        """Test project creation validation."""
        # Missing title
        response = await async_client.post(
            '/api/projects',
            json={}
        )
        assert response.status_code in [400, 422]
        
        # Empty title
        response = await async_client.post(
            '/api/projects',
            json={"title": ""}
        )
        assert response.status_code in [400, 422]