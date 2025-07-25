import os
from unittest.mock import patch
import pytest

from src.server.config.config import (
    load_environment_config,
    ConfigurationError,
    validate_openai_api_key,
    validate_supabase_url,
    get_rag_strategy_config,
)


def test_load_environment_config_success():
    with patch.dict(os.environ, {
        'OPENAI_API_KEY': 'sk-test123',
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_SERVICE_KEY': 'test-service-key',
        'HOST': '0.0.0.0',
        'PORT': '8051'
    }):
        cfg = load_environment_config()
        assert cfg.openai_api_key == 'sk-test123'
        assert cfg.supabase_url == 'https://test.supabase.co'
        assert cfg.supabase_service_key == 'test-service-key'
        assert cfg.host == '0.0.0.0'
        assert cfg.port == 8051


def test_load_environment_config_missing_required():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ConfigurationError) as exc:
            load_environment_config()
        assert 'SUPABASE_URL' in str(exc.value)


def test_load_environment_config_invalid_port():
    with patch.dict(os.environ, {
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_SERVICE_KEY': 'test-service-key',
        'PORT': 'invalid'
    }):
        with pytest.raises(ConfigurationError) as exc:
            load_environment_config()
        assert 'PORT' in str(exc.value)


def test_validate_openai_api_key():
    assert validate_openai_api_key('sk-test123') is True
    with pytest.raises(ConfigurationError):
        validate_openai_api_key('')
    with pytest.raises(ConfigurationError):
        validate_openai_api_key('badkey')


def test_validate_supabase_url():
    assert validate_supabase_url('https://test.supabase.co') is True
    with pytest.raises(ConfigurationError):
        validate_supabase_url('')
    with pytest.raises(ConfigurationError):
        validate_supabase_url('not-a-url')
    with pytest.raises(ConfigurationError):
        validate_supabase_url('http://example.com')


def test_get_rag_strategy_config():
    with patch.dict(os.environ, {
        'USE_CONTEXTUAL_EMBEDDINGS': 'true',
        'USE_HYBRID_SEARCH': 'false',
        'USE_AGENTIC_RAG': 'true',
        'USE_RERANKING': 'false',
    }):
        cfg = get_rag_strategy_config()
        assert cfg.use_contextual_embeddings is True
        assert cfg.use_hybrid_search is False
        assert cfg.use_agentic_rag is True
        assert cfg.use_reranking is False


def test_get_rag_strategy_config_defaults():
    with patch.dict(os.environ, {}, clear=True):
        cfg = get_rag_strategy_config()
        assert cfg.use_contextual_embeddings is False
        assert cfg.use_hybrid_search is False
        assert cfg.use_agentic_rag is False
        assert cfg.use_reranking is False
