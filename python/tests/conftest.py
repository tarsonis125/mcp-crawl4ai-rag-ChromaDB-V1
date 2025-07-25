import sys, os
import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import Mock, AsyncMock, MagicMock

# Add src folder to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, 'src')
sys.path.insert(0, SRC_DIR)

# Import the FastAPI application from the server module
from src.server.main import app

@pytest_asyncio.fixture
async def async_client():
    """Async client for testing FastAPI endpoints"""
    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

@pytest.fixture 
def sync_client():
    """Sync client for testing non-async endpoints"""
    from fastapi.testclient import TestClient
    with TestClient(app) as tc:
        yield tc

@pytest.fixture
def mock_progress_mapper():
    """Mock ProgressMapper for testing progress tracking"""
    from src.server.services.knowledge.progress_mapper import ProgressMapper
    mapper = Mock(spec=ProgressMapper)
    mapper.map_progress = Mock(side_effect=lambda stage, progress: min(100, max(0, progress)))
    mapper.last_overall_progress = 0
    mapper.current_stage = 'starting'
    return mapper

@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing"""
    client = Mock()
    client.table = Mock(return_value=Mock(
        insert=Mock(return_value=Mock(
            execute=Mock(return_value=Mock(data=[]))
        )),
        delete=Mock(return_value=Mock(
            in_=Mock(return_value=Mock(
                execute=Mock(return_value=Mock(data=[]))
            )),
            eq=Mock(return_value=Mock(
                execute=Mock(return_value=Mock(data=[]))
            ))
        )),
        select=Mock(return_value=Mock(
            execute=Mock(return_value=Mock(data=[]))
        ))
    ))
    return client

@pytest.fixture
def mock_crawler():
    """Mock Crawl4AI crawler for testing"""
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
def mock_socketio():
    """Mock Socket.IO for testing"""
    sio = Mock()
    sio.emit = AsyncMock()
    sio.enter_room = AsyncMock()
    sio.leave_room = AsyncMock()
    return sio
