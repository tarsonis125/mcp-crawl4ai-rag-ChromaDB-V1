"""
Simple Logfire Configuration for Archon (2025 Best Practices)

This module provides a simplified logging setup using Pydantic Logfire
with automatic instrumentation and minimal boilerplate.
"""
import os
import logging
from typing import Optional

# Configure standard Python logging as fallback
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Try to import and configure logfire
LOGFIRE_AVAILABLE = False
logfire = None

try:
    import logfire
    LOGFIRE_AVAILABLE = True
except ImportError:
    logging.info("Logfire not installed. Using standard Python logging.")

def is_logfire_enabled_in_db() -> Optional[bool]:
    """
    Check if logfire is enabled via database settings.
    
    Returns:
        True if enabled, False if disabled, None if not set in database
    """
    try:
        from ..services.credential_service import credential_service
        if hasattr(credential_service, '_cache') and credential_service._cache_initialized:
            cached_value = credential_service._cache.get("LOGFIRE_ENABLED")
            if cached_value:
                if isinstance(cached_value, dict):
                    value = cached_value.get("value", "true")
                else:
                    value = str(cached_value)
                return value.lower() in ("true", "1", "yes", "on")
    except Exception:
        pass
    return None

def setup_logfire(
    token: Optional[str] = None,
    environment: str = "development",
    service_name: str = "archon-mcp"
) -> None:
    """
    Configure logfire for the application.
    
    Checks in order:
    1. Environment variable LOGFIRE_ENABLED
    2. Database setting LOGFIRE_ENABLED
    3. Environment variable DISABLE_LOGFIRE (for backward compatibility)
    
    Args:
        token: Logfire token (will try to read from env if not provided)
        environment: Environment name (development, staging, production)
        service_name: Name of the service
    """
    if not LOGFIRE_AVAILABLE:
        return
    
    # Check environment variable first (highest priority)
    env_enabled = os.getenv("LOGFIRE_ENABLED", "").lower()
    if env_enabled in ("false", "0", "no", "off"):
        logging.info("Logfire disabled via LOGFIRE_ENABLED environment variable. Using standard logging.")
        return
    if env_enabled in ("true", "1", "yes", "on"):
        # Explicitly enabled, continue with setup
        pass
    else:
        # No explicit env setting, check database
        db_enabled = is_logfire_enabled_in_db()
        if db_enabled is False:
            logging.info("Logfire disabled via database setting. Using standard logging.")
            return
        # If db_enabled is True or None, continue
    
    # Get logfire token
    logfire_token = token or os.getenv("LOGFIRE_TOKEN")
    if not logfire_token:
        logging.info("No LOGFIRE_TOKEN found. Using standard logging.")
        return
    
    try:
        # Simple logfire configuration - let it handle the complexity
        logfire.configure(
            token=logfire_token,
            service_name=service_name,
            environment=environment
        )
        logging.info(f"Logfire configured for {service_name}")
        
        # Set global flag to indicate logfire is active
        global _logfire_configured
        _logfire_configured = True
        
    except Exception as e:
        logging.warning(f"Failed to configure logfire: {e}. Using standard logging.")

# Global variable to track if logfire is actually configured and enabled
_logfire_configured = False

def is_logfire_active() -> bool:
    """Check if logfire is currently active and should be used."""
    return _logfire_configured and LOGFIRE_AVAILABLE and logfire is not None

def get_logger(name: str, **tags) -> logging.Logger:
    """
    Get a logger instance. Uses logfire if available, otherwise standard logging.
    
    Args:
        name: Logger name (usually __name__)
        **tags: Additional tags (ignored for standard logging)
    
    Returns:
        Logger instance
    """
    if is_logfire_active():
        try:
            # Logfire will handle structured logging automatically
            return logfire.get_logger(name)
        except:
            pass
    
    # Fallback to standard logging
    return logging.getLogger(name)

# Pre-configured loggers for different components
rag_logger = get_logger("rag", module="rag", service="mcp", component="knowledge")
mcp_logger = get_logger("mcp", module="mcp", service="mcp", component="server") 
api_logger = get_logger("api", module="api", service="mcp", component="fastapi")
search_logger = get_logger("search", module="search", service="mcp", component="vector")
crawl_logger = get_logger("crawl", module="crawl", service="mcp", component="ingestion")

# Export what's needed
__all__ = [
    'setup_logfire', 
    'get_logger',
    'is_logfire_active',
    'rag_logger', 
    'mcp_logger', 
    'api_logger', 
    'search_logger', 
    'crawl_logger',
    'logfire',  # May be None if not available/disabled
    'LOGFIRE_AVAILABLE'
]