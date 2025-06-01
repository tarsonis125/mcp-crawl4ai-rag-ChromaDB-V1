"""
Tests for environment configuration management.
These tests will initially fail until the configuration module is implemented.
"""
import pytest
import os
from unittest.mock import patch, MagicMock


@pytest.mark.unit
def test_load_environment_config_success():
    """Test successful loading of environment configuration."""
    # This will fail until we create the config module
    from src.config import load_environment_config
    
    with patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_SERVICE_KEY': 'test-service-key',
        'HOST': '0.0.0.0',
        'PORT': '8051'
    }):
        config = load_environment_config()
        
        assert config.openai_api_key == 'test-key'
        assert config.supabase_url == 'https://test.supabase.co'
        assert config.supabase_service_key == 'test-service-key'
        assert config.host == '0.0.0.0'
        assert config.port == 8051


@pytest.mark.unit
def test_load_environment_config_missing_required():
    """Test that missing required environment variables raise an error."""
    from src.config import load_environment_config, ConfigurationError
    
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ConfigurationError) as exc_info:
            load_environment_config()
        
        assert "OPENAI_API_KEY" in str(exc_info.value)


@pytest.mark.unit
def test_load_environment_config_invalid_port():
    """Test that invalid port values raise an error."""
    from src.config import load_environment_config, ConfigurationError
    
    with patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_SERVICE_KEY': 'test-service-key',
        'PORT': 'invalid-port'
    }):
        with pytest.raises(ConfigurationError) as exc_info:
            load_environment_config()
        
        assert "PORT" in str(exc_info.value)


@pytest.mark.unit
def test_validate_openai_api_key():
    """Test OpenAI API key validation."""
    from src.config import validate_openai_api_key, ConfigurationError
    
    # Valid key
    assert validate_openai_api_key("sk-test123") is True
    
    # Invalid keys
    with pytest.raises(ConfigurationError):
        validate_openai_api_key("")
    
    with pytest.raises(ConfigurationError):
        validate_openai_api_key("invalid-key")


@pytest.mark.unit
def test_validate_supabase_url():
    """Test Supabase URL validation."""
    from src.config import validate_supabase_url, ConfigurationError
    
    # Valid URL
    assert validate_supabase_url("https://test.supabase.co") is True
    
    # Invalid URLs
    with pytest.raises(ConfigurationError):
        validate_supabase_url("")
    
    with pytest.raises(ConfigurationError):
        validate_supabase_url("not-a-url")
    
    with pytest.raises(ConfigurationError):
        validate_supabase_url("http://test.supabase.co")  # Must be HTTPS


@pytest.mark.unit
def test_get_rag_strategy_config():
    """Test RAG strategy configuration parsing."""
    from src.config import get_rag_strategy_config
    
    with patch.dict(os.environ, {
        'USE_CONTEXTUAL_EMBEDDINGS': 'true',
        'USE_HYBRID_SEARCH': 'false',
        'USE_AGENTIC_RAG': 'true',
        'USE_RERANKING': 'false'
    }):
        config = get_rag_strategy_config()
        
        assert config.use_contextual_embeddings is True
        assert config.use_hybrid_search is False
        assert config.use_agentic_rag is True
        assert config.use_reranking is False


@pytest.mark.unit
def test_get_rag_strategy_config_defaults():
    """Test RAG strategy configuration with default values."""
    from src.config import get_rag_strategy_config
    
    with patch.dict(os.environ, {}, clear=True):
        config = get_rag_strategy_config()
        
        # All should default to False
        assert config.use_contextual_embeddings is False
        assert config.use_hybrid_search is False
        assert config.use_agentic_rag is False
        assert config.use_reranking is False 