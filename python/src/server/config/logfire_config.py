"""
Logfire Configuration for Archon

This module sets up Logfire observability for the entire Archon application,
including FastAPI, MCP server, and background tasks.

Falls back gracefully to standard logging if logfire is not available or disabled.
"""
import os
import logging
from typing import Optional, Any

# Configure standard logging with better formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)

# Try to import logfire, fall back to standard logging if not available
try:
    import logfire
    LOGFIRE_AVAILABLE = True
except ImportError:
    LOGFIRE_AVAILABLE = False
    logfire = None

def is_logfire_enabled() -> bool:
    """
    Check if logfire is enabled via settings
    
    Returns:
        True if logfire should be used, False to use standard logging
    """
    try:
        # First check environment variable for immediate override
        env_enabled = os.getenv("LOGFIRE_ENABLED", "").lower()
        if env_enabled in ("false", "0", "no", "off"):
            return False
        if env_enabled in ("true", "1", "yes", "on"):
            return True
            
        # Try to get from credential service (database setting)
        try:
            from src.server.services.credential_service import credential_service
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
            
        # Default to True if available and token exists
        return LOGFIRE_AVAILABLE and bool(os.getenv("LOGFIRE_TOKEN"))
    except Exception:
        return False

def setup_logfire(
    token: Optional[str] = None,
    environment: str = "development",
    service_name: str = "archon-mcp"
) -> None:
    """
    Configure logfire for the application
    
    Args:
        token: Logfire token (will try to read from env if not provided)
        environment: Environment name (development, staging, production)
        service_name: Name of the service
    """
    if not is_logfire_enabled():
        logging.info("Logfire disabled via settings, using standard logging")
        return
        
    if not LOGFIRE_AVAILABLE:
        logging.warning("Logfire not available, using standard logging")
        return
    
    # Get token from parameter or environment
    logfire_token = token or os.getenv("LOGFIRE_TOKEN")
    
    if not logfire_token:
        logging.warning("No Logfire token provided, using standard logging")
        return
    
    try:
        # Configure logfire with environment-specific settings
        config_kwargs = {
            "token": logfire_token,
            "environment": environment,
            "service_name": service_name,
        }
        
        # Environment-specific configurations
        if environment == "production":
            # Use sampling in production to reduce costs
            config_kwargs["sampling"] = logfire.SamplingOptions.level_or_duration(
                slow_threshold=2.0  # 2 seconds
            )
        
        # Start with basic configuration without console options
        logfire.configure(**config_kwargs)
        logging.info(f"Logfire configured for {service_name} in {environment}")
        
    except Exception as e:
        logging.error(f"Failed to configure logfire: {e}")
        logging.warning("Continuing with standard logging due to configuration error")
        # Don't raise the exception - allow the application to continue

class LogfireWrapper:
    """
    Wrapper that provides a consistent interface whether using logfire or standard logging
    """
    def __init__(self, name: str, use_logfire: bool = False, **tags):
        self.name = name
        self.use_logfire = use_logfire
        self.tags = tags
        
        if use_logfire and LOGFIRE_AVAILABLE and logfire:
            try:
                self.logger = logfire.with_tags(**tags, logger_name=name)
                self._is_logfire = True
            except Exception:
                # Fall back to standard logging if logfire fails
                self.logger = logging.getLogger(name)
                self._is_logfire = False
        else:
            self.logger = logging.getLogger(name)
            self._is_logfire = False
    
    def info(self, message: str, **kwargs):
        if self._is_logfire:
            self.logger.info(message, **kwargs)
        else:
            if kwargs:
                formatted_kwargs = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
                self.logger.info(f"{message} | {formatted_kwargs}")
            else:
                self.logger.info(message)
    
    def debug(self, message: str, **kwargs):
        if self._is_logfire:
            self.logger.debug(message, **kwargs)
        else:
            if kwargs:
                formatted_kwargs = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
                self.logger.debug(f"{message} | {formatted_kwargs}")
            else:
                self.logger.debug(message)
    
    def warning(self, message: str, **kwargs):
        if self._is_logfire:
            self.logger.warning(message, **kwargs)
        else:
            if kwargs:
                formatted_kwargs = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
                self.logger.warning(f"{message} | {formatted_kwargs}")
            else:
                self.logger.warning(message)
    
    def error(self, message: str, **kwargs):
        if self._is_logfire:
            self.logger.error(message, **kwargs)
        else:
            if kwargs:
                formatted_kwargs = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
                self.logger.error(f"{message} | {formatted_kwargs}")
            else:
                self.logger.error(message)
    
    def exception(self, message: str, **kwargs):
        if self._is_logfire:
            self.logger.exception(message, **kwargs)
        else:
            if kwargs:
                formatted_kwargs = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
                self.logger.exception(f"{message} | {formatted_kwargs}")
            else:
                self.logger.exception(message)
    
    def span(self, name: str, **kwargs):
        if self._is_logfire:
            return self.logger.span(name, **kwargs)
        else:
            # Return a simple context manager that does nothing for standard logging
            return StandardSpan(name)

class StandardSpan:
    """Simple span context manager for standard logging"""
    def __init__(self, name: str):
        self.name = name
        
    def __enter__(self):
        return self
        
    def __exit__(self, *args):
        pass
        
    def set_attribute(self, key: str, value: Any):
        pass  # No-op for standard logging
        
    def record_exception(self, exception: Exception):
        pass  # No-op for standard logging

def get_logger(name: str, **tags) -> LogfireWrapper:
    """
    Get a logger instance that works with both logfire and standard logging
    
    Args:
        name: Logger name (usually module name)
        **tags: Additional tags to apply to all logs from this logger
    
    Returns:
        LogfireWrapper that handles both logfire and standard logging
    """
    use_logfire = is_logfire_enabled() and LOGFIRE_AVAILABLE
    return LogfireWrapper(name, use_logfire=use_logfire, **tags)

# Pre-configured loggers for different components
rag_logger = get_logger("rag", module="rag", service="mcp", component="knowledge")
mcp_logger = get_logger("mcp", module="mcp", service="mcp", component="server") 
api_logger = get_logger("api", module="api", service="mcp", component="fastapi")
search_logger = get_logger("search", module="search", service="mcp", component="vector")
crawl_logger = get_logger("crawl", module="crawl", service="mcp", component="ingestion")

# For backward compatibility, export logfire (real or None)
# Components that need raw logfire access can check if it's None
__all__ = [
    'setup_logfire', 
    'get_logger', 
    'is_logfire_enabled',
    'rag_logger', 
    'mcp_logger', 
    'api_logger', 
    'search_logger', 
    'crawl_logger',
    'logfire'  # May be None if not available/disabled
] 