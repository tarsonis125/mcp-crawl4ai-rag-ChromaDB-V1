"""
Modular MCP Server for Archon

This is the main MCP server that coordinates multiple tool modules:
- RAG Module: Web crawling, document storage, and retrieval
- Tasks Module: Project and task management
- Future UI Module: Agent-UI integration

Each module registers its tools with this shared FastMCP instance.
"""
from mcp.server.fastmcp import FastMCP
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Optional
from sentence_transformers import CrossEncoder
from dotenv import load_dotenv
from supabase import Client
from pathlib import Path
import os
import sys
import asyncio

from crawl4ai import AsyncWebCrawler, BrowserConfig

# Add the project root to Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils import get_supabase_client

# Load environment variables from the project root .env file
project_root = Path(__file__).resolve().parent.parent
dotenv_path = project_root / '.env'
load_dotenv(dotenv_path, override=True)

@dataclass
class ArchonContext:
    """
    Shared context for all Archon MCP modules.
    
    This context holds resources that can be used by any module:
    - AsyncWebCrawler for web operations
    - Supabase client for database operations  
    - Optional reranking model for search enhancement
    """
    crawler: AsyncWebCrawler
    supabase_client: Client
    reranking_model: Optional[CrossEncoder] = None

@asynccontextmanager
async def archon_lifespan(server: FastMCP) -> AsyncIterator[ArchonContext]:
    """
    Manages the shared resources lifecycle for all modules.
    
    Initializes and cleans up resources that are shared across
    all MCP tool modules in the Archon system.
    """
    # Create browser configuration
    browser_config = BrowserConfig(
        headless=True,
        verbose=False
    )
    
    # Initialize the crawler
    crawler = AsyncWebCrawler(config=browser_config)
    await crawler.__aenter__()
    
    # Initialize Supabase client
    supabase_client = get_supabase_client()
    
    # Initialize cross-encoder model for reranking if enabled
    reranking_model = None
    if os.getenv("USE_RERANKING", "false") == "true":
        try:
            reranking_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception as e:
            print(f"Failed to load reranking model: {e}")
            reranking_model = None
    
    try:
        yield ArchonContext(
            crawler=crawler,
            supabase_client=supabase_client,
            reranking_model=reranking_model
        )
    finally:
        # Clean up the crawler
        await crawler.__aexit__(None, None, None)

# Initialize the main FastMCP server
mcp = FastMCP(
    "archon-mcp-server",
    description="Modular MCP server for Archon: RAG, Tasks, and UI tools",
    lifespan=archon_lifespan,
    host=os.getenv("HOST", "0.0.0.0"),
    port=os.getenv("PORT", "8051")
)

# Import and register all modules
def register_modules():
    """Register all MCP tool modules with the main server."""
    print("Registering MCP tool modules...")
    
    # Import and register RAG module
    try:
        from src.modules.rag_module import register_rag_tools
        register_rag_tools(mcp)
        print("✓ RAG module registered")
    except ImportError as e:
        print(f"⚠ RAG module not available: {e}")
    
    # Import and register Tasks module  
    try:
        from src.modules.tasks_module import register_task_tools
        register_task_tools(mcp)
        print("✓ Tasks module registered")
    except ImportError as e:
        print(f"⚠ Tasks module not available: {e}")
    
    # Future UI module will be added here
    # try:
    #     from src.modules.ui_module import register_ui_tools
    #     register_ui_tools(mcp)
    #     print("✓ UI module registered") 
    # except ImportError as e:
    #     print(f"⚠ UI module not available: {e}")

# Register all modules when this file is imported
register_modules()

async def main():
    """Main entry point for the MCP server."""
    transport = os.getenv("TRANSPORT", "sse")
    host = os.getenv("HOST", "localhost")
    port = int(os.getenv("PORT", "8051"))
    
    print(f"Starting Archon MCP server with transport: {transport}")
    
    if transport == 'sse':
        print(f"SSE server will be available at: http://{host}:{port}/sse")
        await mcp.run_sse_async()
    elif transport == 'stdio':
        print("Stdio server ready for MCP client connections")
        await mcp.run_stdio_async()
    else:
        raise ValueError(f"Unsupported transport: {transport}. Use 'sse' or 'stdio'")

if __name__ == "__main__":
    asyncio.run(main()) 