"""
Pytest configuration and fixtures for MCP server testing.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
from typing import AsyncGenerator


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    client = MagicMock()
    client.table.return_value = MagicMock()
    return client


@pytest.fixture
def mock_crawler():
    """Mock AsyncWebCrawler for testing."""
    crawler = AsyncMock()
    return crawler


@pytest.fixture
def sample_crawl_result():
    """Sample crawl result for testing."""
    return {
        "success": True,
        "markdown": "# Test Page\n\nThis is test content.",
        "links": {
            "internal": ["https://example.com/page1"],
            "external": ["https://external.com"]
        },
        "error_message": None
    }


@pytest.fixture
def sample_env_vars(monkeypatch):
    """Set up sample environment variables for testing."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("USE_CONTEXTUAL_EMBEDDINGS", "false")
    monkeypatch.setenv("USE_HYBRID_SEARCH", "false")
    monkeypatch.setenv("USE_AGENTIC_RAG", "false")
    monkeypatch.setenv("USE_RERANKING", "false") 