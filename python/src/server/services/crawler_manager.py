"""
Crawler Manager Service

Handles initialization and management of the Crawl4AI crawler instance.
This avoids circular imports by providing a service-level access to the crawler.
"""
import os
from typing import Optional

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig
except ImportError:
    AsyncWebCrawler = None
    BrowserConfig = None
    
from ..config.logfire_config import safe_logfire_info, safe_logfire_error


class CrawlerManager:
    """Manages the global crawler instance."""
    
    _instance: Optional['CrawlerManager'] = None
    _crawler: Optional[AsyncWebCrawler] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_crawler(self) -> AsyncWebCrawler:
        """Get or create the crawler instance."""
        if not self._initialized:
            await self.initialize()
        return self._crawler
    
    async def initialize(self):
        """Initialize the crawler if not already initialized."""
        if self._initialized:
            safe_logfire_info("Crawler already initialized, skipping")
            return
            
        try:
            safe_logfire_info("Initializing Crawl4AI crawler...")
            print("=== CRAWLER INITIALIZATION START ===")
            
            # Check if crawl4ai is available
            if not AsyncWebCrawler or not BrowserConfig:
                print("ERROR: crawl4ai not available")
                print(f"AsyncWebCrawler: {AsyncWebCrawler}")
                print(f"BrowserConfig: {BrowserConfig}")
                raise ImportError("crawl4ai is not installed or available")
            
            # Check for Docker environment
            in_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', False)
            
            # Initialize browser config - same for Docker and local
            # crawl4ai/Playwright will handle Docker-specific settings internally
            browser_config = BrowserConfig(
                headless=True,
                verbose=False,
                # Set viewport for proper rendering
                viewport_width=1920,
                viewport_height=1080,
                # Add user agent to appear as a real browser
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                # Set browser type
                browser_type="chromium",
                # Extra args for Chromium
                extra_args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            )
            
            safe_logfire_info(f"Creating AsyncWebCrawler with config | in_docker={in_docker}")
            
            # Initialize crawler with the correct parameter name
            self._crawler = AsyncWebCrawler(config=browser_config)
            safe_logfire_info("AsyncWebCrawler instance created, entering context...")
            await self._crawler.__aenter__()
            self._initialized = True
            safe_logfire_info(f"Crawler entered context successfully | crawler={self._crawler}")
            
            safe_logfire_info("✅ Crawler initialized successfully")
            print("=== CRAWLER INITIALIZATION SUCCESS ===")
            print(f"Crawler instance: {self._crawler}")
            print(f"Initialized: {self._initialized}")
            
        except Exception as e:
            safe_logfire_error(f"Failed to initialize crawler: {e}")
            import traceback
            tb = traceback.format_exc()
            safe_logfire_error(f"Crawler initialization traceback: {tb}")
            # Also print to stdout for Docker logs
            print(f"=== CRAWLER INITIALIZATION ERROR ===")
            print(f"Error: {e}")
            print(f"Traceback:\n{tb}")
            print("=== END CRAWLER ERROR ===")
            # Don't mark as initialized if the crawler is None
            # This allows retries and proper error propagation
            self._crawler = None
            self._initialized = False
            raise Exception(f"Failed to initialize Crawl4AI crawler: {e}")
    
    async def cleanup(self):
        """Clean up the crawler resources."""
        if self._crawler and self._initialized:
            try:
                await self._crawler.__aexit__(None, None, None)
                safe_logfire_info("Crawler cleaned up successfully")
            except Exception as e:
                safe_logfire_error(f"Error cleaning up crawler: {e}")
            finally:
                self._crawler = None
                self._initialized = False


# Global instance
_crawler_manager = CrawlerManager()


async def get_crawler() -> Optional[AsyncWebCrawler]:
    """Get the global crawler instance."""
    global _crawler_manager
    crawler = await _crawler_manager.get_crawler()
    if crawler is None:
        print("WARNING: get_crawler() returning None")
        print(f"_crawler_manager: {_crawler_manager}")
        print(f"_crawler_manager._crawler: {_crawler_manager._crawler if _crawler_manager else 'N/A'}")
        print(f"_crawler_manager._initialized: {_crawler_manager._initialized if _crawler_manager else 'N/A'}")
    return crawler


async def initialize_crawler():
    """Initialize the global crawler."""
    await _crawler_manager.initialize()


async def cleanup_crawler():
    """Clean up the global crawler."""
    await _crawler_manager.cleanup()