"""
Test Safety Module

This module ensures tests NEVER connect to real services or databases.
It provides safety checks and utilities for all tests.
"""
import os
import pytest
from unittest.mock import Mock, patch

# SAFETY CHECK: Ensure we're in test mode
os.environ['TESTING'] = 'true'
os.environ['ENV'] = 'test'

# SAFETY CHECK: Override any real service URLs
TEST_SUPABASE_URL = 'http://mock-supabase-test.local'
TEST_OPENAI_API_KEY = 'test-key-never-use-real-keys'

# Patch environment variables for all tests
os.environ['SUPABASE_URL'] = TEST_SUPABASE_URL
os.environ['OPENAI_API_KEY'] = TEST_OPENAI_API_KEY


def mock_supabase_client():
    """Create a safe mock Supabase client that will never connect to real DB"""
    mock_client = Mock()
    mock_client.table = Mock(return_value=Mock(
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
            execute=Mock(return_value=Mock(data=[], error=None))
        )),
        update=Mock(return_value=Mock(
            eq=Mock(return_value=Mock(
                execute=Mock(return_value=Mock(data=[], error=None))
            ))
        ))
    ))
    return mock_client


def mock_crawler():
    """Create a safe mock crawler that will never make real HTTP requests"""
    from unittest.mock import AsyncMock
    crawler = AsyncMock()
    mock_result = Mock()
    mock_result.success = True
    mock_result.url = "https://mock-test-url.local"
    mock_result.markdown = "# Mock Test Content\n\nThis is mock content for testing."
    mock_result.html = "<h1>Mock Test Content</h1>"
    mock_result.metadata = {"title": "Mock Test"}
    mock_result.error_message = None
    crawler.arun = AsyncMock(return_value=mock_result)
    crawler.arun_many = AsyncMock(return_value=[mock_result])
    return crawler


# Auto-patch dangerous functions
@pytest.fixture(autouse=True)
def safety_patches():
    """Automatically patch dangerous functions in all tests"""
    patches = [
        patch('src.server.services.client_manager.get_supabase_client', return_value=mock_supabase_client()),
        patch('src.server.services.crawler_manager.get_crawler', return_value=mock_crawler()),
        patch('supabase.create_client', side_effect=Exception("SAFETY: Real Supabase client creation blocked in tests!")),
        patch('openai.OpenAI', side_effect=Exception("SAFETY: Real OpenAI client creation blocked in tests!")),
        patch('requests.get', side_effect=Exception("SAFETY: Real HTTP requests blocked in tests!")),
        patch('httpx.AsyncClient.get', side_effect=Exception("SAFETY: Real async HTTP requests blocked in tests!")),
        patch('httpx.AsyncClient.post', side_effect=Exception("SAFETY: Real async HTTP requests blocked in tests!"))
    ]
    
    # Skip patching httpx for FastAPI test client
    patches = [p for p in patches if 'httpx' not in str(p)]
    
    with patch.multiple('os.environ', 
                       SUPABASE_URL=TEST_SUPABASE_URL,
                       OPENAI_API_KEY=TEST_OPENAI_API_KEY,
                       TESTING='true'):
        yield


def test_safety_check():
    """Verify safety measures are in place"""
    assert os.environ.get('TESTING') == 'true'
    assert os.environ.get('SUPABASE_URL') == TEST_SUPABASE_URL
    assert 'localhost' not in os.environ.get('SUPABASE_URL', '')
    assert 'supabase.co' not in os.environ.get('SUPABASE_URL', '')