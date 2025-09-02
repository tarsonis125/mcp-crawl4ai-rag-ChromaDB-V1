"""
MCP server for web crawling with Crawl4AI.

This server provides tools to crawl websites using Crawl4AI, automatically detecting
the appropriate crawl method based on URL type (sitemap, txt file, or regular webpage).
Also includes AI hallucination detection and repository parsing tools using Neo4j knowledge graphs.
"""

# ==== ADDED IMPORTS ====
from .vector_db_adapter import get_vector_db, VectorDBAdapter
import os

from mcp.server.fastmcp import FastMCP, Context
from sentence_transformers import CrossEncoder
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urldefrag
from xml.etree import ElementTree
from dotenv import load_dotenv
from pathlib import Path
import requests
import asyncio
import json
import re
import concurrent.futures
import sys
import logging

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, MemoryAdaptiveDispatcher

# Add knowledge_graphs folder to path for importing knowledge graph modules
knowledge_graphs_path = Path(__file__).resolve().parent.parent / 'knowledge_graphs'
sys.path.append(str(knowledge_graphs_path))

from utils import (
    extract_code_blocks,
    generate_code_example_summary,
    update_source_info,
    extract_source_summary,
)

# Import knowledge graph modules
from knowledge_graph_validator import KnowledgeGraphValidator
from parse_repo_into_neo4j import DirectNeo4jExtractor
from ai_script_analyzer import AIScriptAnalyzer
from hallucination_reporter import HallucinationReporter

# Logging setup
logger = logging.getLogger("crawl4ai_mcp")
logging.basicConfig(level=logging.INFO)

# Load environment variables from the project root .env file
project_root = Path(__file__).resolve().parent.parent
dotenv_path = project_root / '.env'
load_dotenv(dotenv_path, override=True)

# ==== VECTOR DB INITIALIZATION ====
try:
    vector_db = get_vector_db()
    logger.info(f"Vector database initialized: {type(vector_db).__name__}")
except Exception as e:
    logger.error(f"Failed to initialize vector database: {e}")
    raise

# ==== VECTOR DB HELPER FUNCTIONS ====
def store_content_embeddings(documents: List[str], embeddings: List[List[float]], metadata: List[Dict]):
    """Store content embeddings using the configured vector database"""
    return vector_db.store_embeddings(documents, embeddings, metadata, collection_type="content")

def store_code_embeddings(documents: List[str], embeddings: List[List[float]], metadata: List[Dict]):
    """Store code example embeddings using the configured vector database"""
    return vector_db.store_embeddings(documents, embeddings, metadata, collection_type="code")

def search_content(query_embedding: List[float], limit: int = 10, source_filter: Optional[str] = None):
    """Search content using the configured vector database"""
    return vector_db.search_similar(query_embedding, limit, source_filter, collection_type="content")

def search_code_examples(query_embedding: List[float], limit: int = 10, source_filter: Optional[str] = None):
    """Search code examples using the configured vector database"""
    return vector_db.search_similar(query_embedding, limit, source_filter, collection_type="code")

def get_available_sources():
    """Get available sources from the configured vector database"""
    return vector_db.get_sources()

# Helper functions for Neo4j validation and error handling
def validate_neo4j_connection() -> bool:
    return all([
        os.getenv("NEO4J_URI"),
        os.getenv("NEO4J_USER"),
        os.getenv("NEO4J_PASSWORD")
    ])

def format_neo4j_error(error: Exception) -> str:
    error_str = str(error).lower()
    if "authentication" in error_str or "unauthorized" in error_str:
        return "Neo4j authentication failed. Check NEO4J_USER and NEO4J_PASSWORD."
    elif "connection" in error_str or "refused" in error_str or "timeout" in error_str:
        return "Cannot connect to Neo4j. Check NEO4J_URI and ensure Neo4j is running."
    elif "database" in error_str:
        return "Neo4j database error. Check if the database exists and is accessible."
    else:
        return f"Neo4j error: {str(error)}"

def validate_script_path(script_path: str) -> Dict[str, Any]:
    if not script_path or not isinstance(script_path, str):
        return {"valid": False, "error": "Script path is required"}
    if not os.path.exists(script_path):
        return {"valid": False, "error": f"Script not found: {script_path}"}
    if not script_path.endswith('.py'):
        return {"valid": False, "error": "Only Python (.py) files are supported"}
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            f.read(1)
        return {"valid": True}
    except Exception as e:
        return {"valid": False, "error": f"Cannot read script file: {str(e)}"}

def validate_github_url(repo_url: str) -> Dict[str, Any]:
    if not repo_url or not isinstance(repo_url, str):
        return {"valid": False, "error": "Repository URL is required"}
    repo_url = repo_url.strip()
    if not ("github.com" in repo_url.lower() or repo_url.endswith(".git")):
        return {"valid": False, "error": "Please provide a valid GitHub repository URL"}
    if not (repo_url.startswith("https://") or repo_url.startswith("git@")):
        return {"valid": False, "error": "Repository URL must start with https:// or git@"}
    return {"valid": True, "repo_name": repo_url.split('/')[-1].replace('.git', '')}

@dataclass
class Crawl4AIContext:
    crawler: AsyncWebCrawler
    reranking_model: Optional[CrossEncoder] = None
    knowledge_validator: Optional[Any] = None
    repo_extractor: Optional[Any] = None

@asynccontextmanager
async def crawl4ai_lifespan(server: FastMCP) -> AsyncIterator[Crawl4AIContext]:
    browser_config = BrowserConfig(
        headless=True,
        verbose=False
    )
    crawler = AsyncWebCrawler(config=browser_config)
    await crawler.__aenter__()
    reranking_model = None
    if os.getenv("USE_RERANKING", "false") == "true":
        try:
            reranking_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception as e:
            logger.error(f"Failed to load reranking model: {e}")
            reranking_model = None
    knowledge_validator = None
    repo_extractor = None
    knowledge_graph_enabled = os.getenv("USE_KNOWLEDGE_GRAPH", "false") == "true"
    if knowledge_graph_enabled:
        neo4j_uri = os.getenv("NEO4J_URI")
        neo4j_user = os.getenv("NEO4J_USER")
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        if neo4j_uri and neo4j_user and neo4j_password:
            try:
                logger.info("Initializing knowledge graph components...")
                knowledge_validator = KnowledgeGraphValidator(neo4j_uri, neo4j_user, neo4j_password)
                await knowledge_validator.initialize()
                logger.info("✓ Knowledge graph validator initialized")
                repo_extractor = DirectNeo4jExtractor(neo4j_uri, neo4j_user, neo4j_password)
                await repo_extractor.initialize()
                logger.info("✓ Repository extractor initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Neo4j components: {format_neo4j_error(e)}")
                knowledge_validator = None
                repo_extractor = None
        else:
            logger.warning("Neo4j credentials not configured - knowledge graph tools will be unavailable")
    else:
        logger.info("Knowledge graph functionality disabled - set USE_KNOWLEDGE_GRAPH=true to enable")
    try:
        yield Crawl4AIContext(
            crawler=crawler,
            reranking_model=reranking_model,
            knowledge_validator=knowledge_validator,
            repo_extractor=repo_extractor
        )
    finally:
        await crawler.__aexit__(None, None, None)
        if knowledge_validator:
            try:
                await knowledge_validator.close()
                logger.info("✓ Knowledge graph validator closed")
            except Exception as e:
                logger.error(f"Error closing knowledge validator: {e}")
        if repo_extractor:
            try:
                await repo_extractor.close()
                logger.info("✓ Repository extractor closed")
            except Exception as e:
                logger.error(f"Error closing repository extractor: {e}")

mcp = FastMCP(
    "mcp-crawl4ai-rag",
    description="MCP server for RAG and web crawling with Crawl4AI",
    lifespan=crawl4ai_lifespan,
    host=os.getenv("HOST", "0.0.0.0"),
    port=os.getenv("PORT", "8051")
)

def rerank_results(model: CrossEncoder, query: str, results: List[Dict[str, Any]], content_key: str = "content") -> List[Dict[str, Any]]:
    if not model or not results:
        return results
    try:
        texts = [result.get(content_key, "") for result in results]
        pairs = [[query, text] for text in texts]
        scores = model.predict(pairs)
        for i, result in enumerate(results):
            result["rerank_score"] = float(scores[i])
        reranked = sorted(results, key=lambda x: x.get("rerank_score", 0), reverse=True)
        return reranked
    except Exception as e:
        logger.error(f"Error during reranking: {e}")
        return results

def is_sitemap(url: str) -> bool:
    return url.endswith('sitemap.xml') or 'sitemap' in urlparse(url).path

def is_txt(url: str) -> bool:
    return url.endswith('.txt')

def parse_sitemap(sitemap_url: str) -> List[str]:
    resp = requests.get(sitemap_url)
    urls = []
    if resp.status_code == 200:
        try:
            tree = ElementTree.fromstring(resp.content)
            urls = [loc.text for loc in tree.findall('.//{*}loc')]
        except Exception as e:
            logger.error(f"Error parsing sitemap XML: {e}")
    return urls

def smart_chunk_markdown(text: str, chunk_size: int = 5000) -> List[str]:
    chunks = []
    start = 0
    text_length = len(text)
    while start < text_length:
        end = start + chunk_size
        if end >= text_length:
            chunks.append(text[start:].strip())
            break
        chunk = text[start:end]
        code_block = chunk.rfind('```')
        if code_block != -1 and code_block > chunk_size * 0.3:
            end = start + code_block
        elif '\n\n' in chunk:
            last_break = chunk.rfind('\n\n')
            if last_break > chunk_size * 0.3:
                end = start + last_break
        elif '. ' in chunk:
            last_period = chunk.rfind('. ')
            if last_period > chunk_size * 0.3:
                end = start + last_period + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks

def extract_section_info(chunk: str) -> Dict[str, Any]:
    headers = re.findall(r'^(#+)\s+(.+)$', chunk, re.MULTILINE)
    header_str = '; '.join([f'{h[0]} {h[1]}' for h in headers]) if headers else ''
    return {
        "headers": header_str,
        "char_count": len(chunk),
        "word_count": len(chunk.split())
    }

def process_code_example(args):
    code, context_before, context_after = args
    return generate_code_example_summary(code, context_before, context_after)

# ==== EXAMPLE: perform_rag_query TOOL USING VECTOR DB ====
# NOTE: get_embedding should be defined elsewhere in your codebase.
@mcp.tool()
async def perform_rag_query(query: str, source_filter: Optional[str] = None, max_results: int = 10) -> str:
    """
    Search for relevant content using semantic search with optional source filtering.

    Args:
        query: The search query
        source_filter: Optional domain/source to filter results (e.g., "example.com")
        max_results: Maximum number of results to return (default: 10)
    """
    try:
        # Generate query embedding
        query_embedding = get_embedding(query)
        results = search_content(query_embedding, max_results, source_filter)
        if not results:
            return f"No relevant content found for query: {query}"
        formatted_results = []
        for i, result in enumerate(results, 1):
            formatted_results.append(
                f"Result {i} (Score: {result['similarity']:.3f}):\n"
                f"Source: {result['source']}\n"
                f"Content: {result['content'][:500]}...\n"
            )
        return "\n---\n".join(formatted_results)
    except Exception as e:
        logger.error(f"Error in RAG query: {e}")
        return f"Error performing search: {str(e)}"

# ==== UPDATE OTHER TOOL FUNCTIONS ====
# In all other MCP tools, replace Supabase-specific calls:
# - supabase.table(...).insert(...) → store_content_embeddings() or store_code_embeddings()
# - supabase.rpc(...) calls → search_content() or search_code_examples()
# - supabase.table(...).select(...) calls → get_available_sources()
# This will let you use the vector database backend instead of Supabase.

# ... [rest of the file remains unchanged, but update all storage/search calls as above] ...

async def main():
    transport = os.getenv("TRANSPORT", "sse")
    if transport == 'sse':
        await mcp.run_sse_async()
    else:
        await mcp.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(main())
