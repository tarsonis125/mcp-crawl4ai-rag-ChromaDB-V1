"""
Knowledge Management API Module

This module handles all knowledge base operations including:
- Crawling and indexing web content
- Document upload and processing  
- RAG (Retrieval Augmented Generation) queries
- Knowledge item management and search
- Real-time progress tracking via WebSockets
"""

import asyncio
import json
import os
import secrets
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Request
from pydantic import BaseModel, HttpUrl
from pathlib import Path
import traceback

from ..services.client_manager import get_supabase_client
from ..services.storage import (
    add_documents_to_supabase,
    extract_code_blocks,
    generate_code_example_summary,
    add_code_examples_to_supabase
)
from ..services.source_management_service import extract_source_summary, SourceManagementService
from ..services.storage import DocumentStorageService
from ..services.rag.crawling_service import CrawlingService
from ..services.search import SearchService

# Import unified logging
from ..config.logfire_config import safe_logfire_info, safe_logfire_error
from ..utils.document_processing import extract_text_from_document
from .socketio_handlers import (
    start_crawl_progress,
    update_crawl_progress,
    complete_crawl_progress,
    error_crawl_progress
)
from ..socketio_app import get_socketio_instance

import io

# Create router
router = APIRouter(prefix="/api", tags=["knowledge"])

# Get Socket.IO instance
sio = get_socketio_instance()


# Get the global crawling context from main.py
def get_crawling_context():
    """Get the global crawling context from the app state."""
    from fastapi import Request
    import inspect
    
    # Try to get the context from the current request
    frame = inspect.currentframe()
    try:
        # Walk up the call stack to find the app instance
        while frame:
            if 'app' in frame.f_locals and hasattr(frame.f_locals['app'], 'state'):
                app = frame.f_locals['app']
                if hasattr(app.state, 'crawling_context'):
                    return app.state.crawling_context
            frame = frame.f_back
    finally:
        del frame
    
    # Fallback - import directly from main
    try:
        from ..main import crawling_context
        return crawling_context
    except ImportError:
        # Create a minimal context if we can't get the global one
        class MinimalContext:
            def __init__(self):
                self._initialized = False
                self.supabase_client = get_supabase_client()
        return MinimalContext()

# Request Models
class KnowledgeItemRequest(BaseModel):
    url: str
    knowledge_type: str = 'technical'
    tags: List[str] = []
    update_frequency: int = 7
    max_depth: int = 2  # Maximum crawl depth (1-5)

class CrawlRequest(BaseModel):
    url: str
    knowledge_type: str = 'general'
    tags: List[str] = []
    update_frequency: int = 7
    max_depth: int = 2  # Maximum crawl depth (1-5)

class RagQueryRequest(BaseModel):
    query: str
    source: Optional[str] = None
    match_count: int = 5


async def get_available_sources_direct() -> Dict[str, Any]:
    """Get all available sources from the sources table directly."""
    try:
        supabase_client = get_supabase_client()
        
        # Query the sources table directly
        result = supabase_client.from_('sources')\
            .select('*')\
            .order('source_id')\
            .execute()
        
        # Format the sources with their details
        sources = []
        if result.data:
            for source in result.data:
                sources.append({
                    "source_id": source.get("source_id"),
                    "title": source.get("title", source.get("summary", "Untitled")),
                    "summary": source.get("summary"),
                    "metadata": source.get("metadata", {}),
                    "total_words": source.get("total_words", source.get("total_word_count", 0)),
                    "update_frequency": source.get("update_frequency", 7),  # Include frequency from sources table
                    "created_at": source.get("created_at"),
                    "updated_at": source.get("updated_at", source.get("created_at"))
                })
        
        return {
            "success": True,
            "sources": sources,
            "count": len(sources)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/test-socket-progress/{progress_id}")
async def test_socket_progress(progress_id: str):
    """Test endpoint to verify Socket.IO crawl progress is working."""
    try:
        # Send a test progress update
        test_data = {
            'progressId': progress_id,
            'status': 'testing',
            'percentage': 50,
            'message': 'Test progress update from API',
            'currentStep': 'Testing Socket.IO connection',
            'logs': ['Test log entry 1', 'Test log entry 2']
        }
        
        await update_crawl_progress(progress_id, test_data)
        
        return {
            'success': True,
            'message': f'Test progress sent to room {progress_id}',
            'data': test_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/knowledge-items")
async def get_knowledge_items(
    page: int = 1,
    per_page: int = 20,
    knowledge_type: Optional[str] = None,
    search: Optional[str] = None
):
    """Get knowledge items with pagination and filtering."""
    try:
        safe_logfire_info(f"Getting knowledge items | page={page} | per_page={per_page} | knowledge_type={knowledge_type} | search={search}")
        
        # Ensure crawling context is initialized once  
        crawling_context = get_crawling_context()
        if not crawling_context._initialized:
            await crawling_context.initialize()
        
        # Get all sources directly 
        sources_result = await get_available_sources_direct()
        
        # Parse the JSON response
        if isinstance(sources_result, str):
            sources_data = json.loads(sources_result)
        else:
            sources_data = sources_result
        
        # Transform the data to match frontend expectations
        items = []
        for source in sources_data.get('sources', []):
                # Use title and metadata from sources table
                source_metadata = source.get('metadata', {})
                source_id = source['source_id']
                
                # Get first page URL if available - simplified query
                supabase_client = crawling_context.supabase_client or get_supabase_client()
                try:
                    pages_response = supabase_client.from_('crawled_pages')\
                        .select('url')\
                        .eq('source_id', source_id)\
                        .limit(1)\
                        .execute()
                    
                    first_page = pages_response.data[0] if pages_response.data else {}
                    first_page_url = first_page.get('url', f"source://{source_id}")
                except:
                    first_page_url = f"source://{source_id}"
                
                # Determine source type - if metadata has source_type='file', use it; otherwise check URL pattern
                stored_source_type = source_metadata.get('source_type')
                if stored_source_type:
                    source_type = stored_source_type
                else:
                    # Legacy fallback - check URL pattern
                    source_type = 'file' if first_page_url.startswith('file://') else 'url'
                
                # Get code examples for this source - simplified query for now
                code_examples = []
                try:
                    code_examples_response = supabase_client.from_('code_examples')\
                        .select('id, summary, metadata')\
                        .eq('source_id', source_id)\
                        .execute()
                    
                    code_examples = code_examples_response.data if code_examples_response.data else []
                except:
                    code_examples = []
                
                item = {
                    'id': source_id,
                    'title': source.get('title', source.get('summary', 'Untitled')),
                    'url': first_page_url,
                    'source_id': source_id,
                    'code_examples': code_examples,  # Include code examples data
                    'metadata': {
                        'knowledge_type': source_metadata.get('knowledge_type', 'technical'),
                        'tags': source_metadata.get('tags', []),
                        'source_type': source_type,
                        'status': 'active',
                        'description': source_metadata.get('description', source.get('summary', '')),
                        'chunks_count': source.get('total_words', 0),
                        'word_count': source.get('total_words', 0),
                        'last_scraped': source.get('updated_at'),
                        'file_name': source_metadata.get('file_name'),
                        'file_type': source_metadata.get('file_type'),
                        'update_frequency': source.get('update_frequency', 7),  # Include frequency from sources table
                        'code_examples_count': len(code_examples),  # Add count for easy access
                        **source_metadata
                    },
                    'created_at': source.get('created_at'),
                    'updated_at': source.get('updated_at')
                }
                items.append(item)
        
        # Filter by search term if provided
        if search:
            search_lower = search.lower()
            items = [
                item for item in items 
                if search_lower in item['title'].lower() 
                or search_lower in item['metadata'].get('description', '').lower()
                or any(search_lower in tag.lower() for tag in item['metadata'].get('tags', []))
            ]
        
        # Filter by knowledge type if provided
        if knowledge_type:
            items = [
                item for item in items 
                if item['metadata'].get('knowledge_type') == knowledge_type
            ]
        
        # Apply pagination
        total = len(items)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_items = items[start_idx:end_idx]
        
        safe_logfire_info(f"Knowledge items retrieved | total={total} | page={page} | filtered_count={len(paginated_items)}")
        
        return {
            'items': paginated_items,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page
        }
            
    except Exception as e:
        safe_logfire_error(f"Failed to get knowledge items | error={str(e)} | page={page} | per_page={per_page}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.put("/knowledge-items/{source_id}")
async def update_knowledge_item(source_id: str, updates: dict):
    """Update a knowledge item's metadata."""
    try:
        safe_logfire_info(f"Updating knowledge item | source_id={source_id} | updates={updates}")
        # Get Supabase client
        supabase_client = get_supabase_client()
        # Prepare the update data
        update_data = {}
        # Handle title updates
        if 'title' in updates:
            update_data['title'] = updates['title']
        # Handle description updates (stored in metadata)
        if 'description' in updates:
            # Get current metadata first
            current_response = supabase_client.table("sources").select("metadata").eq("source_id", source_id).execute()
            if current_response.data:
                current_metadata = current_response.data[0].get('metadata', {})
                current_metadata['description'] = updates['description']
                update_data['metadata'] = current_metadata
            else:
                # If no current metadata, create new
                update_data['metadata'] = {'description': updates['description']}
        # Handle other metadata updates
        metadata_fields = ['knowledge_type', 'tags', 'status', 'update_frequency']
        for field in metadata_fields:
            if field in updates:
                if 'metadata' not in update_data:
                    # Get current metadata first
                    current_response = supabase_client.table("sources").select("metadata").eq("source_id", source_id).execute()
                    current_metadata = current_response.data[0].get('metadata', {}) if current_response.data else {}
                    update_data['metadata'] = current_metadata
                update_data['metadata'][field] = updates[field]
        # Perform the update
        result = supabase_client.table("sources").update(update_data).eq("source_id", source_id).execute()
        if result.data:
            safe_logfire_info(f"Knowledge item updated successfully | source_id={source_id}")
            return {
                'success': True,
                'message': f'Successfully updated knowledge item {source_id}',
                'source_id': source_id
            }
        else:
            safe_logfire_error(f"Knowledge item not found | source_id={source_id}")
            raise HTTPException(status_code=404, detail={'error': f'Knowledge item {source_id} not found'})
    except Exception as e:
        safe_logfire_error(f"Failed to update knowledge item | error={str(e)} | source_id={source_id}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.delete("/knowledge-items/{source_id}")
async def delete_knowledge_item(source_id: str):
    """Delete a knowledge item from the database."""
    try:
        print(f"DEBUG: Starting delete_knowledge_item for source_id: {source_id}")
        safe_logfire_info(f"Deleting knowledge item | source_id={source_id}")
        
        # Use SourceManagementService directly instead of going through MCP
        print(f"DEBUG: Creating SourceManagementService...")
        from ..services.source_management_service import SourceManagementService
        source_service = SourceManagementService(get_supabase_client())
        print(f"DEBUG: Successfully created SourceManagementService")
        
        print(f"DEBUG: Calling delete_source function...")
        success, result_data = source_service.delete_source(source_id)
        print(f"DEBUG: delete_source returned: success={success}, data={result_data}")
        
        # Convert to expected format
        result = {
            'success': success,
            'error': result_data.get('error') if not success else None,
            **result_data
        }
        
        if result.get('success'):
            safe_logfire_info(f"Knowledge item deleted successfully | source_id={source_id}")
            
            return {
                'success': True,
                'message': f'Successfully deleted knowledge item {source_id}'
            }
        else:
            safe_logfire_error(f"Knowledge item deletion failed | source_id={source_id} | error={result.get('error')}")
            raise HTTPException(status_code=500, detail={'error': result.get('error', 'Deletion failed')})
                
    except Exception as e:
        print(f"ERROR: Exception in delete_knowledge_item: {e}")
        print(f"ERROR: Exception type: {type(e)}")
        import traceback
        print(f"ERROR: Traceback: {traceback.format_exc()}")
        safe_logfire_error(f"Failed to delete knowledge item | error={str(e)} | source_id={source_id}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.post("/knowledge-items/crawl")
async def crawl_knowledge_item(request: KnowledgeItemRequest):
    """Crawl a URL and add it to the knowledge base with progress tracking."""
    try:
        safe_logfire_info(f"Starting knowledge item crawl | url={str(request.url)} | knowledge_type={request.knowledge_type} | tags={request.tags}")
        # Generate unique progress ID
        progress_id = str(uuid.uuid4())
        # Start progress tracking with initial state
        await start_crawl_progress(progress_id, {
            'progressId': progress_id,
            'currentUrl': str(request.url),
            'totalPages': 0,
            'processedPages': 0,
            'percentage': 0,
            'status': 'starting',
            'logs': [f'Starting crawl of {request.url}'],
            'eta': 'Calculating...'
        })
        # Start background task IMMEDIATELY (like the old API)
        asyncio.create_task(_perform_crawl_with_progress(progress_id, request))
        safe_logfire_info(f"Crawl started successfully | progress_id={progress_id} | url={str(request.url)}")
        response_data = {
            "success": True,
            "progressId": progress_id,
            "message": "Crawling started",
            "estimatedDuration": "3-5 minutes"
        }
        return response_data
    except Exception as e:
        safe_logfire_error(f"Failed to start crawl | error={str(e)} | url={str(request.url)}")
        raise HTTPException(status_code=500, detail=str(e))

async def _perform_crawl_with_progress(progress_id: str, request: KnowledgeItemRequest):
    """Perform the actual crawl operation with progress tracking using service layer."""
    try:
        safe_logfire_info(f"Starting crawl with progress tracking | progress_id={progress_id} | url={str(request.url)}")
        
        # Socket.IO handles connection automatically - no need to wait
        
        # Emit initial progress directly via Socket.IO
        await update_crawl_progress(progress_id, {
            'status': 'analyzing',
            'percentage': 0,
            'currentUrl': str(request.url),
            'log': f'Analyzing URL type for {request.url}'
        })
        
        # Get crawling context and ensure it's initialized
        crawling_context = get_crawling_context()
        if not crawling_context._initialized:
            await crawling_context.initialize()
        
        # Create service instances
        # Get crawler directly from crawling context instead of nested mock objects
        crawler = crawling_context.crawler
        safe_logfire_info(f"Crawler status | crawler_exists={(crawler is not None)} | initialized={crawling_context._initialized}")
        supabase_client = get_supabase_client()
        crawling_service = CrawlingService(crawler=crawler, supabase_client=supabase_client)
        doc_storage_service = DocumentStorageService(supabase_client)
        
        # Perform smart crawl using service
        crawl_results = []
        crawl_type = None
        
        if crawling_service.is_txt(str(request.url)):
            # For text files
            await update_crawl_progress(progress_id, {
                'status': 'crawling', 'percentage': 10, 
                'log': f'Detected text file, fetching content...'
            })
            crawl_results = await crawling_service.crawl_markdown_file(str(request.url))
            crawl_type = "text_file"
        elif crawling_service.is_sitemap(str(request.url)):
            # For sitemaps
            await update_crawl_progress(progress_id, {
                'status': 'crawling', 'percentage': 10,
                'log': f'Detected sitemap, parsing URLs...'
            })
            sitemap_urls = crawling_service.parse_sitemap(str(request.url))
            if sitemap_urls:
                await update_crawl_progress(progress_id, {
                    'status': 'crawling', 'percentage': 20,
                    'log': f'Found {len(sitemap_urls)} URLs in sitemap'
                })
                crawl_results = await crawling_service.crawl_batch_with_progress(
                    sitemap_urls, 
                    max_concurrent=5,
                    progress_callback=None,  # Emit progress manually
                    start_progress=20,
                    end_progress=60
                )
            crawl_type = "sitemap"
        else:
            # For regular URLs
            await update_crawl_progress(progress_id, {
                'status': 'crawling', 'percentage': 10,
                'log': f'Starting recursive crawl of webpage...'
            })
            crawl_results = await crawling_service.crawl_recursive_with_progress(
                [str(request.url)],
                max_depth=request.max_depth,
                max_concurrent=5,
                progress_callback=None,  # Emit progress manually
                start_progress=15,
                end_progress=60
            )
            crawl_type = "webpage"
        
        if not crawl_results:
            await error_crawl_progress(progress_id, "No content found to crawl")
            return
        
        # Process and store crawl results
        await update_crawl_progress(progress_id, {
            'status': 'processing', 'percentage': 30,
            'log': f'Processing {len(crawl_results)} pages...',
            'processedPages': len(crawl_results),
            'totalPages': len(crawl_results)
        })
        
        # Prepare data for storage
        from ..services.source_management_service import extract_source_summary, update_source_info
        from urllib.parse import urlparse
        import concurrent.futures
        
        urls = []
        chunk_numbers = []
        contents = []
        metadatas = []
        chunk_count = 0
        source_content_map = {}
        source_word_counts = {}
        
        # Process documentation chunks
        for doc in crawl_results:
            source_url = doc['url']
            md = doc['markdown']
            chunks = doc_storage_service.smart_chunk_markdown(md, chunk_size=5000)
            
            parsed_url = urlparse(source_url)
            source_id = parsed_url.netloc or parsed_url.path
            
            if source_id not in source_content_map:
                source_content_map[source_id] = md[:5000]
                source_word_counts[source_id] = 0
            
            for i, chunk in enumerate(chunks):
                urls.append(source_url)
                chunk_numbers.append(i)
                contents.append(chunk)
                
                meta = doc_storage_service.extract_section_info(chunk)
                meta.update({
                    "chunk_index": i,
                    "url": source_url,
                    "source": source_id,
                    "crawl_type": crawl_type,
                    "source_id": source_id,
                    "knowledge_type": request.knowledge_type,
                    "tags": request.tags,
                    "update_frequency": request.update_frequency
                })
                metadatas.append(meta)
                source_word_counts[source_id] += meta.get("word_count", 0)
                chunk_count += 1
        
        # Create url_to_full_document mapping
        url_to_full_document = {doc['url']: doc['markdown'] for doc in crawl_results}
        
        await update_crawl_progress(progress_id, {
            'status': 'storing', 'percentage': 70,
            'log': f'Updating source information...'
        })
        
        # Update source information
        # Get max workers from credential service (defaults to 3 if not set)
        try:
            max_workers_str = await credential_service.get_credential("CONTEXTUAL_EMBEDDINGS_MAX_WORKERS", "3", decrypt=False)
            max_workers = int(max_workers_str)
        except:
            max_workers = 3
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            source_summary_args = [(source_id, content) for source_id, content in source_content_map.items()]
            source_summaries = list(executor.map(lambda args: extract_source_summary(args[0], args[1]), source_summary_args))
        
        for (source_id, _), summary in zip(source_summary_args, source_summaries):
            word_count = source_word_counts.get(source_id, 0)
            update_source_info(supabase_client, source_id, summary, word_count)
        
        # Source creation phase
        await update_crawl_progress(progress_id, {
            'status': 'source_creation', 'percentage': 40,
            'log': f'Creating source records for {len(source_content_map)} sources...'
        })
        
        # Create progress callback for batch updates
        total_batches = (len(contents) + 20 - 1) // 20  # batch_size = 20
        
        async def batch_progress_callback(message: str, percentage: int, batch_info: dict = None):
            progress_data = {
                'status': 'document_storage',
                'percentage': 45 + int(percentage * 0.45),  # 45% to 90%
                'log': message
            }
            if batch_info:
                progress_data.update({
                    'completed_batches': batch_info.get('completed_batches', 0),
                    'total_batches': total_batches,
                    'current_batch': batch_info.get('current_batch', 0),
                    'active_workers': batch_info.get('active_workers', 1),
                    'chunks_in_batch': batch_info.get('chunks_in_batch', 0),
                    'total_chunks_in_batch': batch_info.get('total_chunks_in_batch', 0)
                })
            await update_crawl_progress(progress_id, progress_data)
        
        # Document storage phase with progress
        await update_crawl_progress(progress_id, {
            'status': 'document_storage', 'percentage': 45,
            'log': f'Starting document storage for {chunk_count} chunks...',
            'total_batches': total_batches,
            'completed_batches': 0
        })
        
        # Store documents with embeddings
        await add_documents_to_supabase(
            supabase_client, 
            urls, 
            chunk_numbers, 
            contents, 
            metadatas, 
            url_to_full_document, 
            batch_size=20,
            progress_callback=batch_progress_callback
        )
        
        # Code storage phase
        await update_crawl_progress(progress_id, {
            'status': 'code_storage', 'percentage': 90,
            'log': 'Checking for code examples...'
        })
        
        # Check if code extraction is enabled
        from ..services.credential_service import credential_service
        try:
            extract_code_examples = await credential_service.get_credential("USE_AGENTIC_RAG", "false", decrypt=True)
            if isinstance(extract_code_examples, str):
                extract_code_examples = extract_code_examples.lower() == "true"
        except:
            extract_code_examples = False
        
        if extract_code_examples:
            await update_crawl_progress(progress_id, {
                'status': 'code_storage', 'percentage': 91,
                'log': 'Extracting code examples from crawled content...'
            })
            
            # Code extraction utilities are already imported at the top
            
            # Prepare arrays for code examples storage
            code_urls = []
            code_chunk_numbers = []
            code_examples = []
            code_summaries = []
            code_metadatas = []
            total_docs = len(crawl_results)
            
            # Process each document for code examples
            for idx, doc in enumerate(crawl_results):
                try:
                    source_url = doc['url']
                    md = doc.get('markdown', '')
                    
                    # Extract code blocks from markdown
                    code_blocks = extract_code_blocks(md)
                    
                    if code_blocks:
                        # Get source_id for this document
                        parsed_url = urlparse(source_url)
                        source_id = parsed_url.netloc or parsed_url.path
                        
                        # Generate summaries for each code block
                        for block in code_blocks:
                            # Generate summary using AI
                            summary = generate_code_example_summary(
                                block['code'], 
                                block['context_before'], 
                                block['context_after']
                            )
                            
                            # Add to arrays
                            code_urls.append(source_url)
                            code_chunk_numbers.append(len(code_examples))  # Use global code example index
                            code_examples.append(block['code'])
                            code_summaries.append(summary)
                            
                            # Create metadata for code example
                            code_meta = {
                                "chunk_index": len(code_examples) - 1,
                                "url": source_url,
                                "source": source_id,
                                "source_id": source_id,
                                "language": block.get('language', ''),
                                "char_count": len(block['code']),
                                "word_count": len(block['code'].split())
                            }
                            code_metadatas.append(code_meta)
                    
                    # Update progress
                    if idx % 5 == 0:  # Update every 5 documents
                        progress = 91 + int((idx / total_docs) * 4)  # Progress from 91 to 95
                        await update_crawl_progress(progress_id, {
                            'status': 'code_storage', 
                            'percentage': progress,
                            'log': f'Processing code from document {idx + 1}/{total_docs}...'
                        })
                        
                except Exception as e:
                    safe_logfire_error(f"Error processing code from document | url={doc.get('url')} | error={str(e)}")
            
            # Store all code examples if any were found
            if code_examples:
                await update_crawl_progress(progress_id, {
                    'status': 'code_storage', 'percentage': 95,
                    'log': f'Storing {len(code_examples)} code examples...'
                })
                
                try:
                    # Use the proper storage function with correct parameters
                    add_code_examples_to_supabase(
                        client=supabase_client,
                        urls=code_urls,
                        chunk_numbers=code_chunk_numbers,
                        code_examples=code_examples,
                        summaries=code_summaries,
                        metadatas=code_metadatas,
                        batch_size=20,
                        url_to_full_document=url_to_full_document
                    )
                    
                    safe_logfire_info(f"Successfully stored {len(code_examples)} code examples | progress_id={progress_id}")
                    
                except Exception as e:
                    safe_logfire_error(f"Error storing code examples | error={str(e)}")
                    
            else:
                safe_logfire_info(f"No code examples found in crawled content | progress_id={progress_id}")
        
        # Finalization phase
        await update_crawl_progress(progress_id, {
            'status': 'finalization', 'percentage': 99,
            'log': 'Finalizing crawl results...'
        })
        
        # Complete crawl
        completion_data = {
            'chunksStored': chunk_count,
            'wordCount': sum(source_word_counts.values()),
            'codeExamplesStored': len(code_examples) if extract_code_examples else 0,
            'log': 'All processing completed successfully',
            'processedPages': len(crawl_results),
            'totalPages': len(crawl_results)
        }
        await complete_crawl_progress(progress_id, completion_data)
        
        safe_logfire_info(f"Crawl completed successfully | progress_id={progress_id} | chunks_stored={chunk_count} | code_examples_stored={len(code_examples) if extract_code_examples else 0}")
        
    except Exception as e:
        error_message = f'Crawling failed: {str(e)}'
        safe_logfire_error(f"Crawl failed | progress_id={progress_id} | error={error_message} | exception_type={type(e).__name__}")
        import traceback
        tb = traceback.format_exc()
        # Ensure the error is visible in Docker logs
        print(f"=== CRAWL ERROR FOR {progress_id} ===")
        print(f"Error: {error_message}")
        print(f"Exception Type: {type(e).__name__}")
        print(f"Traceback:\n{tb}")
        print("=== END CRAWL ERROR ===")
        safe_logfire_error(f"Crawl exception traceback | traceback={tb}")
        await error_crawl_progress(progress_id, error_message)

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
    knowledge_type: Optional[str] = Form("technical")
):
    """Upload and process a document with progress tracking."""
    try:
        safe_logfire_info(f"Starting document upload | filename={file.filename} | content_type={file.content_type} | knowledge_type={knowledge_type}")
            
        # Generate unique progress ID
        progress_id = str(uuid.uuid4())
        
        # Parse tags
        tag_list = json.loads(tags) if tags else []
        
        # Read file content immediately to avoid closed file issues
        file_content = await file.read()
        file_metadata = {
            'filename': file.filename,
            'content_type': file.content_type,
            'size': len(file_content)
        }
        # Start progress tracking
        await start_crawl_progress(progress_id, {
            'progressId': progress_id,
            'status': 'starting',
            'percentage': 0,
            'currentUrl': f"file://{file.filename}",
            'logs': [f'Starting upload of {file.filename}'],
            'uploadType': 'document',
            'fileName': file.filename,
            'fileType': file.content_type
        })
        # Start background task for processing with file content and metadata
        asyncio.create_task(_perform_upload_with_progress(progress_id, file_content, file_metadata, tag_list, knowledge_type))
        safe_logfire_info(f"Document upload started successfully | progress_id={progress_id} | filename={file.filename}")
        return {
            "success": True,
            "progressId": progress_id,
            "message": "Document upload started",
            "filename": file.filename
        }
            
    except Exception as e:
        safe_logfire_error(f"Failed to start document upload | error={str(e)} | filename={file.filename} | error_type={type(e).__name__}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

async def _perform_upload_with_progress(progress_id: str, file_content: bytes, file_metadata: dict, tag_list: List[str], knowledge_type: str):
    """Perform document upload with progress tracking using service layer."""
    try:
        filename = file_metadata['filename']
        content_type = file_metadata['content_type']
        file_size = file_metadata['size']
        
        safe_logfire_info(f"Starting document upload with progress tracking | progress_id={progress_id} | filename={filename} | content_type={content_type}")
        
        # Socket.IO handles connection automatically - no need to wait
        
        # Extract text from document with progress
        await update_crawl_progress(progress_id, {
            'status': 'processing',
            'percentage': 10,
            'currentUrl': f"file://{filename}",
            'log': f'Reading {filename}...'
        })
        
        try:
            extracted_text = extract_text_from_document(file_content, filename, content_type)
            safe_logfire_info(f"Document text extracted | filename={filename} | extracted_length={len(extracted_text)} | content_type={content_type}")
        except Exception as e:
            await error_crawl_progress(progress_id, f"Failed to extract text: {str(e)}")
            return
        
        # Use DocumentStorageService to handle the upload
        doc_storage_service = DocumentStorageService(get_supabase_client())
        
        # Call the service's upload_document method
        success, result = await doc_storage_service.upload_document(
            file_content=extracted_text,
            filename=filename,
            knowledge_type=knowledge_type,
            tags=tag_list,
            chunk_size=5000,
            progress_callback=None  # Emit progress manually
        )
        
        if success:
            # Complete the upload
            await complete_crawl_progress(progress_id, {
                'chunksStored': result.get('chunks_stored', 0),
                'wordCount': result.get('total_word_count', 0),
                'sourceId': result.get('source_id'),
                'log': f'Document upload completed successfully!'
            })
            
            safe_logfire_info(f"Document uploaded successfully | progress_id={progress_id} | source_id={result.get('source_id')} | chunks_stored={result.get('chunks_stored')}")
        else:
            error_msg = result.get('error', 'Unknown error')
            await error_crawl_progress(progress_id, error_msg)
        
    except Exception as e:
        error_msg = f"Upload failed: {str(e)}"
        safe_logfire_error(f"Document upload failed | progress_id={progress_id} | filename={file_metadata.get('filename', 'unknown')} | error={str(e)}")
        await error_crawl_progress(progress_id, error_msg)

@router.post("/rag/query")
async def perform_rag_query(request: RagQueryRequest):
    """Perform a RAG query on the knowledge base using service layer."""
    try:
        # Use SearchService for RAG query
        search_service = SearchService(get_supabase_client())
        success, result = search_service.perform_rag_query(
            query=request.query,
            source=request.source,
            match_count=request.match_count
        )
        
        if success:
            # Add success flag to match expected API response format
            result['success'] = True
            return result
        else:
            raise HTTPException(
                status_code=500, 
                detail={'error': result.get('error', 'RAG query failed')}
            )
    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"RAG query failed | error={str(e)} | query={request.query[:50]} | source={request.source}")
        raise HTTPException(status_code=500, detail={'error': f"RAG query failed: {str(e)}"})

@router.get("/rag/sources")
async def get_available_sources():
    """Get all available sources for RAG queries."""
    try:
        # Use the direct function which provides the detailed format expected by frontend
        # This maintains backward compatibility while we transition to services
        result = await get_available_sources_direct()
        
        # Parse result if it's a string
        if isinstance(result, str):
            result = json.loads(result)
        
        sources_count = len(result.get('sources', []))
        
        return result
    except Exception as e:
        safe_logfire_error(f"Failed to get available sources | error={str(e)}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    """Delete a source and all its associated data."""
    try:
        safe_logfire_info(f"Deleting source | source_id={source_id}")
        
        # Use SourceManagementService directly
        from ..services.source_management_service import SourceManagementService
        source_service = SourceManagementService(get_supabase_client())
        
        success, result_data = source_service.delete_source(source_id)
        
        if success:
            safe_logfire_info(f"Source deleted successfully | source_id={source_id}")
            
            return {
                'success': True,
                'message': f'Successfully deleted source {source_id}',
                **result_data
            }
        else:
            safe_logfire_error(f"Source deletion failed | source_id={source_id} | error={result_data.get('error')}")
            raise HTTPException(status_code=500, detail={'error': result_data.get('error', 'Deletion failed')})
    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"Failed to delete source | error={str(e)} | source_id={source_id}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

# WebSocket Endpoints

@router.get("/database/metrics")
async def get_database_metrics():
    """Get database metrics and statistics."""
    try:
        safe_logfire_info("Getting database metrics")
        supabase_client = get_supabase_client()
        
        # Get counts from various tables
        sources_count = supabase_client.table("sources").select("*", count="exact").execute()
        pages_count = supabase_client.table("crawled_pages").select("*", count="exact").execute()
        
        sources_count_val = sources_count.count if sources_count.count else 0
        pages_count_val = pages_count.count if pages_count.count else 0
        
        safe_logfire_info(f"Database metrics retrieved | sources_count={sources_count_val} | pages_count={pages_count_val}")
        
        return {
            "sources_count": sources_count_val,
            "pages_count": pages_count_val,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        safe_logfire_error(f"Failed to get database metrics | error={str(e)}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.get("/health")
async def knowledge_health():
    """Knowledge API health check."""
    # Removed health check logging to reduce console noise
    result = {
        "status": "healthy",
        "service": "knowledge-api",
        "timestamp": datetime.now().isoformat()
    }
    
    return result 

