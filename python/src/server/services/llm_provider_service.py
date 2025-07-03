"""
LLM Provider Service

Provides a unified interface for creating OpenAI-compatible clients for different LLM providers.
Supports OpenAI, OpenRouter, Ollama, and Google Gemini.
"""
import os
import openai
from typing import Optional, Union
from contextlib import asynccontextmanager

from ..config.logfire_config import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def get_llm_client():
    """
    Create an async OpenAI-compatible client based on the configured provider.
    
    This context manager handles client creation for different LLM providers
    that support the OpenAI API format.
    
    Yields:
        openai.AsyncOpenAI: An OpenAI-compatible client configured for the selected provider
    """
    # Get the configured provider from environment
    provider = os.getenv("LLM_PROVIDER", "openai")
    logger.info(f"Creating LLM client for provider: {provider}")
    
    client = None
    
    try:
        if provider == "openai":
            # Use OpenAI directly with API key from environment
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key not found in environment")
            
            client = openai.AsyncOpenAI(api_key=api_key)
            logger.info("OpenAI client created successfully")
            
        elif provider == "openrouter":
            # Use OpenRouter with their API endpoint
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OpenRouter API key not found in environment")
            
            client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1"
            )
            logger.info("OpenRouter client created successfully")
            
        elif provider == "ollama":
            # Use Ollama with local endpoint
            base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
            
            # Ollama requires an API key in the client but doesn't actually use it
            client = openai.AsyncOpenAI(
                api_key="ollama",  # Required but unused by Ollama
                base_url=base_url
            )
            logger.info(f"Ollama client created successfully with base URL: {base_url}")
            
        elif provider == "google":
            # Use Google Gemini with their OpenAI-compatible endpoint
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("Google API key not found in environment")
            
            client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            logger.info("Google Gemini client created successfully")
            
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        
        yield client
        
    except Exception as e:
        logger.error(f"Error creating LLM client for provider {provider}: {e}")
        raise
    finally:
        # Cleanup if needed
        pass


def get_llm_client_sync():
    """
    Create a synchronous OpenAI-compatible client based on the configured provider.
    
    This is a synchronous wrapper for backward compatibility with ThreadPoolExecutor.
    
    Returns:
        openai.OpenAI: An OpenAI-compatible client configured for the selected provider
    """
    # For sync version, we'll check the cache or use defaults
    # This is a simplified version that doesn't do async credential lookups
    
    # Try to get provider from environment or use default
    provider = os.getenv("LLM_PROVIDER", "openai")
    
    try:
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key not found in environment")
            
            return openai.OpenAI(api_key=api_key)
            
        elif provider == "openrouter":
            # For sync, we need the API key in environment
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OpenRouter API key not found in environment")
            
            return openai.OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1"
            )
            
        elif provider == "ollama":
            base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
            
            return openai.OpenAI(
                api_key="ollama",  # Required but unused
                base_url=base_url
            )
            
        elif provider == "google":
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("Google API key not found in environment")
            
            return openai.OpenAI(
                api_key=api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            
        else:
            # Fallback to OpenAI
            logger.warning(f"Unsupported provider {provider}, falling back to OpenAI")
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key not found in environment")
            
            return openai.OpenAI(api_key=api_key)
            
    except Exception as e:
        logger.error(f"Error creating sync LLM client: {e}")
        raise


async def get_embedding_model() -> str:
    """
    Get the configured embedding model based on the provider.
    
    Returns:
        str: The embedding model to use
    """
    provider = os.getenv("LLM_PROVIDER", "openai")
    
    # Get custom embedding model if set
    custom_model = os.getenv("EMBEDDING_MODEL")
    if custom_model:
        return custom_model
    
    # Return provider-specific defaults
    if provider == "openai":
        return "text-embedding-3-small"
    elif provider == "openrouter":
        # OpenRouter supports OpenAI's embedding models
        return "openai/text-embedding-3-small"
    elif provider == "ollama":
        # Ollama default embedding model
        return "nomic-embed-text"
    elif provider == "google":
        # Google's embedding model
        return "text-embedding-004"
    else:
        # Fallback to OpenAI's model
        return "text-embedding-3-small"


def get_embedding_model_sync() -> str:
    """
    Get the configured embedding model synchronously.
    
    Returns:
        str: The embedding model to use
    """
    provider = os.getenv("LLM_PROVIDER", "openai")
    
    # Check for custom model in environment
    custom_model = os.getenv("EMBEDDING_MODEL")
    if custom_model:
        return custom_model
    
    # Return provider-specific defaults
    if provider == "openai":
        return "text-embedding-3-small"
    elif provider == "openrouter":
        return "openai/text-embedding-3-small"
    elif provider == "ollama":
        return "nomic-embed-text"
    elif provider == "google":
        return "text-embedding-004"
    else:
        return "text-embedding-3-small"