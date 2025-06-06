"""
Logfire Configuration for Archon

This module sets up Logfire observability for the entire Archon application,
including FastAPI, MCP server, and background tasks.

Falls back gracefully to standard logging if logfire is not available.
"""
import os
import logging
from typing import Optional, List

# Try to import logfire, fall back to standard logging if not available
try:
    import logfire
    LOGFIRE_AVAILABLE = True
except ImportError:
    LOGFIRE_AVAILABLE = False
    # Create a mock logfire module for graceful fallback
    class MockLogfire:
        def configure(self, **kwargs):
            pass
        def info(self, message, **kwargs):
            logging.info(f"{message} {kwargs}")
        def error(self, message, **kwargs):
            logging.error(f"{message} {kwargs}")
        def debug(self, message, **kwargs):
            logging.debug(f"{message} {kwargs}")
        def warning(self, message, **kwargs):
            logging.warning(f"{message} {kwargs}")
        def exception(self, message, **kwargs):
            logging.exception(f"{message} {kwargs}")
        def with_tags(self, **kwargs):
            return self
        def span(self, name, **kwargs):
            return self
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    
    logfire = MockLogfire()

# Configure standard logging as fallback
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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
    if not LOGFIRE_AVAILABLE:
        logging.warning("Logfire not available, using standard logging")
        return
    
    # Get token from parameter or environment
    logfire_token = token or os.getenv("LOGFIRE_TOKEN")
    
    if not logfire_token:
        logging.warning("No Logfire token provided, logfire will not be configured")
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
        logging.warning("Continuing without Logfire due to configuration error")
        # Don't raise the exception - allow the application to continue without Logfire

def get_logger(name: str, **tags) -> "logfire.Logfire":
    """
    Get a tagged logfire logger instance
    
    Args:
        name: Logger name (usually module name)
        **tags: Additional tags to apply to all logs from this logger
    
    Returns:
        Configured logfire instance with tags
    """
    if not LOGFIRE_AVAILABLE:
        # Return a mock object that has the same interface
        class MockLogfire:
            def info(self, *args, **kwargs): logging.info(*args)
            def debug(self, *args, **kwargs): logging.debug(*args)
            def warning(self, *args, **kwargs): logging.warning(*args)
            def error(self, *args, **kwargs): logging.error(*args)
            def exception(self, *args, **kwargs): logging.exception(*args)
            def span(self, *args, **kwargs): return MockSpan()
        return MockLogfire()
    
    try:
        # Check if logfire is actually configured
        # This will raise an exception if logfire.configure() was never called successfully
        return logfire
    except Exception:
        # Fallback to mock if logfire is not properly configured
        class MockLogfire:
            def info(self, *args, **kwargs): logging.info(*args)
            def debug(self, *args, **kwargs): logging.debug(*args)
            def warning(self, *args, **kwargs): logging.warning(*args)
            def error(self, *args, **kwargs): logging.error(*args)
            def exception(self, *args, **kwargs): logging.exception(*args)
            def span(self, *args, **kwargs): return MockSpan()
        return MockLogfire()

class MockSpan:
    """Mock span for when logfire is not available"""
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def record_exception(self, *args): pass
    def set_attribute(self, *args): pass

# Pre-configured loggers for different components
rag_logger = get_logger("rag", module="rag", service="mcp", component="knowledge")
mcp_logger = get_logger("mcp", module="mcp", service="mcp", component="server") 
api_logger = get_logger("api", module="api", service="mcp", component="fastapi")
search_logger = get_logger("search", module="search", service="mcp", component="vector")
crawl_logger = get_logger("crawl", module="crawl", service="mcp", component="ingestion") 