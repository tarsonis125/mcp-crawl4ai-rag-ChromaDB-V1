"""
Basic tests to verify pytest setup is working correctly.
"""
import pytest
from unittest.mock import MagicMock


def test_pytest_working():
    """Test that pytest is working correctly."""
    assert True


@pytest.mark.unit
def test_mock_supabase_client(mock_supabase_client):
    """Test that Supabase client mock is working."""
    assert mock_supabase_client is not None
    assert hasattr(mock_supabase_client, 'table')


@pytest.mark.unit
def test_sample_crawl_result(sample_crawl_result):
    """Test that sample crawl result fixture works."""
    assert sample_crawl_result["success"] is True
    assert "markdown" in sample_crawl_result
    assert "Test Page" in sample_crawl_result["markdown"]


@pytest.mark.unit
def test_environment_vars(sample_env_vars):
    """Test that environment variables are set correctly."""
    import os
    assert os.getenv("OPENAI_API_KEY") == "test-api-key"
    assert os.getenv("SUPABASE_URL") == "https://test.supabase.co" 