"""
RAG Utilities Module for Archon

This module contains helper functions and utilities specifically for RAG operations
that can be shared across different parts of the system.
"""

import re
import logging
import os
import traceback
from typing import List, Dict, Any
from urllib.parse import urlparse, urldefrag
from xml.etree import ElementTree
import requests

logger = logging.getLogger(__name__)


def smart_chunk_markdown(text: str, chunk_size: int = 5000) -> List[str]:
    """
    Split text into chunks intelligently with error handling.
    
    This function implements a context-aware chunking strategy that:
    1. Preserves code blocks (```) as complete units when possible
    2. Prefers to break at paragraph boundaries (\\n\\n)
    3. Falls back to sentence boundaries (. ) if needed
    4. Only splits mid-content when absolutely necessary
    """
    if not text or not isinstance(text, str):
        logger.warning("Invalid text provided for chunking")
        return []
        
    try:
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            # Calculate end position
            end = start + chunk_size

            # If we're at the end of the text, just take what's left
            if end >= text_length:
                remaining = text[start:].strip()
                if remaining:
                    chunks.append(remaining)
                break

            # Try to find a code block boundary first (```)
            chunk = text[start:end]
            code_block = chunk.rfind('```')
            if code_block != -1 and code_block > chunk_size * 0.3:
                end = start + code_block

            # If no code block, try to break at a paragraph
            elif '\n\n' in chunk:
                last_break = chunk.rfind('\n\n')
                if last_break > chunk_size * 0.3:
                    end = start + last_break

            # If no paragraph break, try to break at a sentence
            elif '. ' in chunk:
                last_period = chunk.rfind('. ')
                if last_period > chunk_size * 0.3:
                    end = start + last_period + 1

            # Extract chunk and clean it up
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position for next chunk
            start = end

        logger.debug(f"Successfully chunked text into {len(chunks)} chunks")
        return chunks
        
    except Exception as e:
        logger.error(f"Error in smart chunking: {e}")
        logger.error(traceback.format_exc())
        # Fallback to simple chunking
        try:
            return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        except Exception as fallback_error:
            logger.error(f"Even fallback chunking failed: {fallback_error}")
            return [text] if text else []


def extract_section_info(chunk: str) -> Dict[str, Any]:
    """Extracts headers and stats from a chunk with error handling."""
    try:
        headers = re.findall(r'^(#+)\s+(.+)$', chunk, re.MULTILINE)
        header_str = '; '.join([f'{h[0]} {h[1]}' for h in headers]) if headers else ''

        return {
            "headers": header_str,
            "char_count": len(chunk),
            "word_count": len(chunk.split())
        }
    except Exception as e:
        logger.warning(f"Error extracting section info: {e}")
        return {
            "headers": "",
            "char_count": len(chunk) if chunk else 0,
            "word_count": len(chunk.split()) if chunk else 0
        }


def is_sitemap(url: str) -> bool:
    """Check if a URL is a sitemap with error handling."""
    try:
        return url.endswith('sitemap.xml') or 'sitemap' in urlparse(url).path
    except Exception as e:
        logger.warning(f"Error checking if URL is sitemap: {e}")
        return False


def is_txt(url: str) -> bool:
    """Check if a URL is a text file with error handling."""
    try:
        return url.endswith('.txt')
    except Exception as e:
        logger.warning(f"Error checking if URL is text file: {e}")
        return False


def safe_parse_sitemap(sitemap_url: str) -> List[str]:
    """Parse a sitemap and extract URLs with comprehensive error handling."""
    urls = []
    
    try:
        logger.info(f"Parsing sitemap: {sitemap_url}")
        resp = requests.get(sitemap_url, timeout=30)
        
        if resp.status_code != 200:
            logger.error(f"Failed to fetch sitemap: HTTP {resp.status_code}")
            return urls
            
        try:
            tree = ElementTree.fromstring(resp.content)
            urls = [loc.text for loc in tree.findall('.//{*}loc') if loc.text]
            logger.info(f"Successfully extracted {len(urls)} URLs from sitemap")
            
        except ElementTree.ParseError as e:
            logger.error(f"Error parsing sitemap XML: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing sitemap: {e}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching sitemap: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in sitemap parsing: {e}")
        logger.error(traceback.format_exc())

    return urls


def normalize_url(url: str) -> str:
    """Normalize a URL by removing fragments."""
    try:
        return urldefrag(url)[0]
    except Exception as e:
        logger.warning(f"Error normalizing URL {url}: {e}")
        return url


def get_domain_from_url(url: str) -> str:
    """Extract domain from URL with error handling."""
    try:
        parsed = urlparse(url)
        return parsed.netloc or parsed.path
    except Exception as e:
        logger.warning(f"Error extracting domain from URL {url}: {e}")
        return url


def validate_url(url: str) -> bool:
    """Validate if a string is a valid URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def get_setting_from_env(key: str, default: str = "false") -> str:
    """Get a setting from environment variables with fallback."""
    return os.getenv(key, default)


def get_bool_setting_from_env(key: str, default: bool = False) -> bool:
    """Get a boolean setting from environment variables."""
    value = get_setting_from_env(key, "false" if not default else "true")
    return value.lower() in ("true", "1", "yes", "on")


def safe_json_loads(json_str: str, default=None):
    """Safely parse JSON string with fallback."""
    try:
        import json
        return json.loads(json_str)
    except Exception as e:
        logger.warning(f"Error parsing JSON: {e}")
        return default or {}


def truncate_content(content: str, max_length: int = 1000) -> str:
    """Truncate content to a maximum length with ellipsis."""
    if len(content) <= max_length:
        return content
    return content[:max_length] + "..."


def clean_text(text: str) -> str:
    """Clean text by removing extra whitespace and normalizing."""
    if not text:
        return ""
    
    try:
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text
    except Exception as e:
        logger.warning(f"Error cleaning text: {e}")
        return text


def extract_code_language(code_block: str) -> str:
    """Extract programming language from a code block."""
    try:
        # Look for language specification after opening ```
        match = re.match(r'^```(\w+)', code_block.strip())
        if match:
            return match.group(1)
        return "unknown"
    except Exception as e:
        logger.warning(f"Error extracting code language: {e}")
        return "unknown"


def estimate_reading_time(text: str, words_per_minute: int = 200) -> int:
    """Estimate reading time in minutes for given text."""
    try:
        word_count = len(text.split())
        reading_time = max(1, word_count // words_per_minute)
        return reading_time
    except Exception as e:
        logger.warning(f"Error estimating reading time: {e}")
        return 1


def create_content_summary(content: str, max_length: int = 200) -> str:
    """Create a brief summary of content."""
    try:
        # Take first paragraph or first few sentences
        content = clean_text(content)
        
        # Try to find first paragraph
        first_paragraph = content.split('\n\n')[0]
        if len(first_paragraph) <= max_length:
            return first_paragraph
        
        # Try to find first few sentences
        sentences = first_paragraph.split('. ')
        summary = ""
        for sentence in sentences:
            if len(summary + sentence + '. ') <= max_length:
                summary += sentence + '. '
            else:
                break
        
        return summary.strip() or truncate_content(content, max_length)
        
    except Exception as e:
        logger.warning(f"Error creating content summary: {e}")
        return truncate_content(content, max_length)