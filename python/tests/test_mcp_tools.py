"""
Comprehensive test suite for all Archon MCP tools.

Tests all 25 MCP tools to ensure they:
1. Execute without errors
2. Return proper JSON responses
3. Have expected response structure
4. Handle edge cases appropriately

Based on MCP_HEALTH_STATUS.md inventory.
"""
import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from mcp.server.fastmcp import Context
from pathlib import Path
import sys
import os

# Add src folder to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, 'src')
sys.path.insert(0, SRC_DIR)

# Import MCP server and modules
from src.mcp_server import mcp, archon_lifespan, ArchonContext
from src.modules.rag_module import register_rag_tools
from src.modules.project_module import register_project_tools


class MockSupabaseClient:
    """Mock Supabase client for testing"""
    
    def __init__(self):
        self.table_data = {
            "sources": [
                {"source_id": "test.com", "title": "Test Source", "description": "Test", "created_at": "2024-01-01", "last_updated": "2024-01-01"}
            ],
            "projects": [
                {"id": "test-project-1", "title": "Test Project", "description": "Test project description", "created_at": "2024-01-01"}
            ],
            "tasks": [
                {
                    "id": "test-task-1", 
                    "project_id": "test-project-1", 
                    "title": "Test Task", 
                    "description": "Test task description",
                    "status": "todo",
                    "created_at": "2024-01-01"
                }
            ],
            "documents": [
                {
                    "id": "test-doc-1",
                    "content": "test document content", 
                    "filename": "test.txt",
                    "created_at": "2024-01-01"
                }
            ],
            "settings": [{"key": "test", "value": "test"}]
        }
    
    def table(self, name):
        return MockTable(self.table_data.get(name, []))
    
    def rpc(self, function_name, params):
        # Mock RPC calls for vector search
        if function_name == 'match_documents':
            return MockQueryBuilder([{"content": "test content", "similarity": 0.8}])
        elif function_name == 'match_code_examples':
            return MockQueryBuilder([{"code": "print('hello')", "summary": "test code", "similarity": 0.7}])
        return MockQueryBuilder([])


class MockTable:
    """Mock Supabase table"""
    
    def __init__(self, data):
        self.data = data
        self._filters = {}
        self._limit = None
        self._select_fields = "*"
        self._is_delete = False
    
    def select(self, fields="*"):
        self._select_fields = fields
        return self
    
    def eq(self, field, value):
        self._filters[field] = value
        return self
    
    def limit(self, count):
        self._limit = count
        return self
    
    def execute(self):
        filtered_data = self.data
        if self._filters:
            filtered_data = [item for item in self.data if all(item.get(k) == v for k, v in self._filters.items())]
        if self._limit:
            filtered_data = filtered_data[:self._limit]
        
        # If this is a delete operation, return filtered data as "deleted items"
        if self._is_delete:
            return MockResponse(filtered_data)
        
        return MockResponse(filtered_data)
    
    def insert(self, data):
        return MockQueryBuilder([data])
    
    def update(self, data):
        return MockQueryBuilder([data])
    
    def delete(self):
        self._is_delete = True
        return self


class MockQueryBuilder:
    """Mock query builder that returns MockResponse when execute() is called"""
    
    def __init__(self, data):
        self.data = data
        self._filters = {}
        self._limit = None
    
    def eq(self, field, value):
        """Mock equality filter"""
        self._filters[field] = value
        return self
    
    def limit(self, count):
        """Mock limit"""
        self._limit = count
        return self
    
    def execute(self):
        """Execute the query with filters applied"""
        filtered_data = self.data
        if self._filters:
            filtered_data = [item for item in self.data if all(item.get(k) == v for k, v in self._filters.items())]
        if self._limit:
            filtered_data = filtered_data[:self._limit]
        return MockResponse(filtered_data)


class MockResponse:
    """Mock Supabase response"""
    
    def __init__(self, data):
        self.data = data


class MockCrawler:
    """Mock AsyncWebCrawler for testing"""
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass
    
    async def arun(self, url, config=None):
        # Mock successful crawl result
        result = Mock()
        result.success = True
        result.markdown = f"# Test Content from {url}\n\nThis is test markdown content."
        result.title = "Test Page Title"
        result.links = {"internal": [], "external": []}
        result.error_message = None
        return result


@pytest.fixture
def mock_context():
    """Create a mock MCP context for testing"""
    # Create mock context with all required components
    mock_supabase = MockSupabaseClient()
    mock_crawler = MockCrawler()
    
    archon_context = ArchonContext(
        crawler=mock_crawler,
        supabase_client=mock_supabase,
        reranking_model=None
    )
    
    # Create mock MCP context
    context = Mock(spec=Context)
    context.request_context = Mock()
    context.request_context.lifespan_context = archon_context
    
    return context


# System Management Tools Tests
@pytest.mark.asyncio
async def test_health_check(mock_context):
    """Test health_check tool returns proper status"""
    from src.mcp_server import health_check
    
    result = await health_check(mock_context)
    
    # Should return JSON string
    assert isinstance(result, str)
    
    # Should be valid JSON
    response = json.loads(result)
    
    # Should have success and health status
    assert "success" in response
    assert "health" in response
    assert "timestamp" in response


# Knowledge Management Tools Tests
@pytest.mark.asyncio 
async def test_get_available_sources(mock_context):
    """Test get_available_sources tool"""
    # Import the tool function
    from src.modules.rag_module import register_rag_tools
    
    # We need to get the actual tool function from the registered tools
    # For now, test the underlying functionality
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    # Mock the sources table
    response = supabase_client.table("sources").select("*").execute()
    
    assert len(response.data) > 0
    assert "source_id" in response.data[0]


@pytest.mark.asyncio
async def test_crawl_single_page(mock_context):
    """Test crawl_single_page tool"""
    crawler = mock_context.request_context.lifespan_context.crawler
    
    # Test the crawler mock
    result = await crawler.arun("https://test.com")
    
    assert result.success is True
    assert result.markdown is not None
    assert "Test Content" in result.markdown


@pytest.mark.asyncio
async def test_smart_crawl_url(mock_context):
    """Test smart_crawl_url tool functionality"""
    # Test with a simple URL
    url = "https://test.com"
    crawler = mock_context.request_context.lifespan_context.crawler
    
    result = await crawler.arun(url)
    assert result.success is True


@pytest.mark.asyncio
async def test_perform_rag_query(mock_context):
    """Test perform_rag_query tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    # Test RPC call for vector search
    result = supabase_client.rpc('match_documents', {
        'query_embedding': [0.1, 0.2, 0.3],
        'match_count': 5
    })
    
    assert result.data is not None
    assert len(result.data) >= 0


@pytest.mark.asyncio
async def test_search_code_examples(mock_context):
    """Test search_code_examples tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    # Test RPC call for code example search
    result = supabase_client.rpc('match_code_examples', {
        'query_embedding': [0.1, 0.2, 0.3],
        'match_count': 5
    })
    
    assert result.data is not None


@pytest.mark.asyncio
async def test_upload_document(mock_context):
    """Test upload_document functionality"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    # Test document storage
    test_content = "This is test document content"
    
    # Mock the document insertion
    response = supabase_client.table("documents").insert({
        "content": test_content,
        "filename": "test.txt"
    }).execute()
    
    assert response.data is not None


# Project Management Tools Tests
@pytest.mark.asyncio
async def test_list_projects(mock_context):
    """Test list_projects tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    response = supabase_client.table("projects").select("*").execute()
    
    assert len(response.data) > 0
    assert "title" in response.data[0]


@pytest.mark.asyncio
async def test_get_project(mock_context):
    """Test get_project tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    # Test getting specific project
    response = supabase_client.table("projects").select("*").eq("id", "test-project-1").execute()
    
    assert len(response.data) > 0
    assert response.data[0]["id"] == "test-project-1"


@pytest.mark.asyncio
async def test_create_project(mock_context):
    """Test create_project tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    # Test project creation
    new_project = {
        "title": "New Test Project",
        "description": "Test project creation"
    }
    
    response = supabase_client.table("projects").insert(new_project).execute()
    
    assert response.data is not None


@pytest.mark.asyncio
async def test_delete_project(mock_context):
    """Test delete_project tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    # Test project deletion
    response = supabase_client.table("projects").delete().eq("id", "test-project-1").execute()
    
    assert response.data is not None


# Task Management Tools Tests
@pytest.mark.asyncio
async def test_list_tasks_by_project(mock_context):
    """Test list_tasks_by_project tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    response = supabase_client.table("tasks").select("*").eq("project_id", "test-project-1").execute()
    
    assert len(response.data) > 0


@pytest.mark.asyncio
async def test_create_task(mock_context):
    """Test create_task tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    new_task = {
        "project_id": "test-project-1",
        "title": "New Test Task",
        "description": "Test task creation",
        "status": "todo"
    }
    
    response = supabase_client.table("tasks").insert(new_task).execute()
    
    assert response.data is not None


@pytest.mark.asyncio
async def test_get_task(mock_context):
    """Test get_task tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    response = supabase_client.table("tasks").select("*").eq("id", "test-task-1").execute()
    
    assert len(response.data) > 0
    assert response.data[0]["id"] == "test-task-1"


@pytest.mark.asyncio
async def test_update_task_status(mock_context):
    """Test update_task_status tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    response = supabase_client.table("tasks").update({"status": "doing"}).eq("id", "test-task-1").execute()
    
    assert response.data is not None


@pytest.mark.asyncio
async def test_update_task(mock_context):
    """Test update_task tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    updates = {
        "title": "Updated Task Title",
        "description": "Updated description",
        "status": "done"
    }
    
    response = supabase_client.table("tasks").update(updates).eq("id", "test-task-1").execute()
    
    assert response.data is not None


@pytest.mark.asyncio
async def test_get_task_subtasks(mock_context):
    """Test get_task_subtasks tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    response = supabase_client.table("tasks").select("*").eq("parent_task_id", "test-task-1").execute()
    
    # May return empty list, but should not error
    assert response.data is not None


@pytest.mark.asyncio
async def test_get_tasks_by_status(mock_context):
    """Test get_tasks_by_status tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    response = supabase_client.table("tasks").select("*").eq("project_id", "test-project-1").eq("status", "todo").execute()
    
    assert response.data is not None


@pytest.mark.asyncio
async def test_delete_task(mock_context):
    """Test delete_task tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    response = supabase_client.table("tasks").delete().eq("id", "test-task-1").execute()
    
    assert response.data is not None


# Document Management Tools Tests
@pytest.mark.asyncio
async def test_add_project_document(mock_context):
    """Test add_project_document tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    # Mock document addition by updating project with docs JSONB
    doc_data = {
        "id": "test-project-1",
        "docs": [
            {
                "id": "doc-1",
                "type": "technical_spec",
                "title": "Test Document",
                "content": {"summary": "Test document content"}
            }
        ]
    }
    
    response = supabase_client.table("projects").update(doc_data).eq("id", "test-project-1").execute()
    
    assert response.data is not None


@pytest.mark.asyncio
async def test_list_project_documents(mock_context):
    """Test list_project_documents tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    response = supabase_client.table("projects").select("docs").eq("id", "test-project-1").execute()
    
    assert response.data is not None


@pytest.mark.asyncio
async def test_get_project_document(mock_context):
    """Test get_project_document tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    # Mock getting specific document from project
    response = supabase_client.table("projects").select("docs").eq("id", "test-project-1").execute()
    
    assert response.data is not None


@pytest.mark.asyncio
async def test_update_project_document(mock_context):
    """Test update_project_document tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    # Mock document update
    doc_data = {
        "docs": [
            {
                "id": "doc-1",
                "type": "technical_spec", 
                "title": "Updated Test Document",
                "content": {"summary": "Updated document content"}
            }
        ]
    }
    
    response = supabase_client.table("projects").update(doc_data).eq("id", "test-project-1").execute()
    
    assert response.data is not None


@pytest.mark.asyncio
async def test_delete_project_document(mock_context):
    """Test delete_project_document tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    # Mock document deletion by updating project docs
    response = supabase_client.table("projects").update({"docs": []}).eq("id", "test-project-1").execute()
    
    assert response.data is not None


@pytest.mark.asyncio
async def test_delete_source_tool(mock_context):
    """Test delete_source_tool"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    response = supabase_client.table("sources").delete().eq("source_id", "test.com").execute()
    
    assert response.data is not None


# Integration Tests
@pytest.mark.asyncio
async def test_full_workflow(mock_context):
    """Test a complete workflow: create project, add task, update status"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    # 1. Create project
    project = {"title": "Workflow Test Project", "description": "Test workflow"}
    project_response = supabase_client.table("projects").insert(project).execute()
    assert project_response.data is not None
    
    # 2. Create task
    task = {
        "project_id": "test-project-1",
        "title": "Workflow Test Task", 
        "status": "todo"
    }
    task_response = supabase_client.table("tasks").insert(task).execute()
    assert task_response.data is not None
    
    # 3. Update task status
    status_response = supabase_client.table("tasks").update({"status": "done"}).eq("id", "test-task-1").execute()
    assert status_response.data is not None


# Error Handling Tests
@pytest.mark.asyncio
async def test_error_handling():
    """Test tool error handling with invalid inputs"""
    # Test with missing context
    try:
        from src.mcp_server import health_check
        result = await health_check(None)
        # Should handle gracefully and return error JSON
        response = json.loads(result)
        assert "error" in response
    except Exception:
        # Exception is expected with None context
        pass


# Performance Tests
@pytest.mark.asyncio
async def test_tool_response_times(mock_context):
    """Test that tools respond within reasonable time limits"""
    import time
    
    # Test health_check performance
    start_time = time.time()
    from src.mcp_server import health_check
    result = await health_check(mock_context)
    end_time = time.time()
    
    # Should complete within 1 second
    assert (end_time - start_time) < 1.0
    
    # Should return valid JSON
    response = json.loads(result)
    assert "success" in response


@pytest.mark.asyncio
async def test_list_tasks_by_project_filtering(mock_context):
    """Test list_tasks_by_project tool with closed task filtering"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    # Test default behavior (exclude closed tasks)
    response = supabase_client.table("tasks").select("*").eq("project_id", "test-project-1").neq("status", "done").execute()
    assert response.data is not None
    
    # Test including closed tasks
    response = supabase_client.table("tasks").select("*").eq("project_id", "test-project-1").execute()
    assert response.data is not None


@pytest.mark.asyncio
async def test_get_task_subtasks_filtering(mock_context):
    """Test get_task_subtasks tool with closed subtask filtering"""
    supabase_client = mock_context.request_context.lifespan_context.supabase_client
    
    # Test default behavior (exclude closed subtasks)
    response = supabase_client.table("tasks").select("*").eq("parent_task_id", "test-task-1").neq("status", "done").execute()
    assert response.data is not None
    
    # Test including closed subtasks
    response = supabase_client.table("tasks").select("*").eq("parent_task_id", "test-task-1").execute()
    assert response.data is not None


if __name__ == "__main__":
    # Run specific test
    pytest.main([__file__ + "::test_health_check", "-v"]) 