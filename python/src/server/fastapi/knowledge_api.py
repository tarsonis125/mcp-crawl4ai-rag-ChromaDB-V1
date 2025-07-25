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
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from pathlib import Path

from ..services.client_manager import get_supabase_client
from ..services.storage import DocumentStorageService
from ..services.source_management_service import SourceManagementService
from ..services.search import SearchService
from ..services.knowledge import CrawlOrchestrationService, KnowledgeItemService, DatabaseMetricsService
from ..services.crawler_manager import get_crawler

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

# Create router
router = APIRouter(prefix="/api", tags=["knowledge"])

# Get Socket.IO instance
sio = get_socketio_instance()

# Create a semaphore to limit concurrent crawls
# This prevents the server from becoming unresponsive during heavy crawling
CONCURRENT_CRAWL_LIMIT = 3  # Allow max 3 concurrent crawls
crawl_semaphore = asyncio.Semaphore(CONCURRENT_CRAWL_LIMIT)

# Request Models
class KnowledgeItemRequest(BaseModel):
    url: str
    knowledge_type: str = 'technical'
    tags: List[str] = []
    update_frequency: int = 7
    max_depth: int = 2  # Maximum crawl depth (1-5)
    extract_code_examples: bool = True  # Whether to extract code examples

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
        # Use KnowledgeItemService
        service = KnowledgeItemService(get_supabase_client())
        result = await service.list_items(
            page=page,
            per_page=per_page,
            knowledge_type=knowledge_type,
            search=search
        )
        return result
            
    except Exception as e:
        safe_logfire_error(f"Failed to get knowledge items | error={str(e)} | page={page} | per_page={per_page}")
        raise HTTPException(status_code=500, detail={'error': str(e)})

@router.put("/knowledge-items/{source_id}")
async def update_knowledge_item(source_id: str, updates: dict):
    """Update a knowledge item's metadata."""
    try:
        # Use KnowledgeItemService
        service = KnowledgeItemService(get_supabase_client())
        success, result = await service.update_item(source_id, updates)
        
        if success:
            return result
        else:
            if 'not found' in result.get('error', '').lower():
                raise HTTPException(status_code=404, detail={'error': result.get('error')})
            else:
                raise HTTPException(status_code=500, detail={'error': result.get('error')})
                
    except HTTPException:
        raise
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

@router.post("/knowledge-items/{source_id}/refresh")
async def refresh_knowledge_item(source_id: str):
    """Refresh a knowledge item by re-crawling its URL with the same metadata."""
    try:
        safe_logfire_info(f"Starting knowledge item refresh | source_id={source_id}")
        
        # Get the existing knowledge item
        service = KnowledgeItemService(get_supabase_client())
        existing_item = await service.get_item(source_id)
        
        if not existing_item:
            raise HTTPException(status_code=404, detail={'error': f'Knowledge item {source_id} not found'})
        
        # Extract the URL from the existing item
        url = existing_item.get('url')
        if not url:
            raise HTTPException(status_code=400, detail={'error': 'Knowledge item does not have a URL to refresh'})
        
        # Extract metadata
        metadata = existing_item.get('metadata', {})
        knowledge_type = metadata.get('knowledge_type', 'technical')
        tags = metadata.get('tags', [])
        max_depth = metadata.get('max_depth', 2)
        
        # Generate unique progress ID
        progress_id = str(uuid.uuid4())
        
        # Start progress tracking with initial state
        await start_crawl_progress(progress_id, {
            'progressId': progress_id,
            'currentUrl': url,
            'totalPages': 0,
            'processedPages': 0,
            'percentage': 0,
            'status': 'starting',
            'message': 'Refreshing knowledge item...',
            'logs': [f'Starting refresh for {url}']
        })
        
        # Get crawler from CrawlerManager - same pattern as _perform_crawl_with_progress
        try:
            crawler = await get_crawler()
            if crawler is None:
                raise Exception("Crawler not available - initialization may have failed")
        except Exception as e:
            safe_logfire_error(f"Failed to get crawler | error={str(e)}")
            raise HTTPException(status_code=500, detail={'error': f'Failed to initialize crawler: {str(e)}'})
        
        # Use the same crawl orchestration as regular crawl
        crawl_service = CrawlOrchestrationService(
            crawler=crawler,
            supabase_client=get_supabase_client()
        )
        crawl_service.set_progress_id(progress_id)
        
        # Start the crawl task with proper request format
        request_dict = {
            'url': url,
            'knowledge_type': knowledge_type,
            'tags': tags,
            'max_depth': max_depth,
            'extract_code_examples': True,
            'generate_summary': True
        }
        
        # Create a wrapped task that acquires the semaphore
        async def _perform_refresh_with_semaphore():
            # Add a small delay to allow frontend WebSocket subscription to be established
            # This prevents the "Room has 0 subscribers" issue
            await asyncio.sleep(1.0)
            
            async with crawl_semaphore:
                safe_logfire_info(f"Acquired crawl semaphore for refresh | source_id={source_id}")
                await crawl_service.orchestrate_crawl(request_dict)
        
        asyncio.create_task(_perform_refresh_with_semaphore())
        
        return {
            'progressId': progress_id,
            'message': f'Started refresh for {url}'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"Failed to refresh knowledge item | error={str(e)} | source_id={source_id}")
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
    # Add a small delay to allow frontend WebSocket subscription to be established
    # This prevents the "Room has 0 subscribers" issue
    await asyncio.sleep(1.0)
    
    # Acquire semaphore to limit concurrent crawls
    async with crawl_semaphore:
        safe_logfire_info(f"Acquired crawl semaphore | progress_id={progress_id} | url={str(request.url)}")
        try:
            safe_logfire_info(f"Starting crawl with progress tracking | progress_id={progress_id} | url={str(request.url)}")
            
            # Get crawler from CrawlerManager
            try:
                crawler = await get_crawler()
                if crawler is None:
                    raise Exception("Crawler not available - initialization may have failed")
            except Exception as e:
                safe_logfire_error(f"Failed to get crawler | error={str(e)}")
                await error_crawl_progress(progress_id, f"Failed to initialize crawler: {str(e)}")
                return
                
            supabase_client = get_supabase_client()
            orchestration_service = CrawlOrchestrationService(crawler, supabase_client)
            orchestration_service.set_progress_id(progress_id)
            
            # Convert request to dict for service
            request_dict = {
                'url': str(request.url),
                'knowledge_type': request.knowledge_type,
                'tags': request.tags or [],
                'max_depth': request.max_depth,
                'extract_code_examples': request.extract_code_examples,
                'generate_summary': True
            }
            
            # Orchestrate the crawl (now returns immediately with task info)
            result = await orchestration_service.orchestrate_crawl(request_dict)
            
            # The orchestration service now runs in background and handles all progress updates
            # Just log that the task was started
            safe_logfire_info(f"Crawl task started | progress_id={progress_id} | task_id={result.get('task_id')}")
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
    knowledge_type: str = Form("technical")
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
    # Add a small delay to allow frontend WebSocket subscription to be established
    # This prevents the "Room has 0 subscribers" issue
    await asyncio.sleep(1.0)
    
    # Import ProgressMapper to prevent progress from going backwards
    from ..services.knowledge.progress_mapper import ProgressMapper
    progress_mapper = ProgressMapper()
    
    try:
        filename = file_metadata['filename']
        content_type = file_metadata['content_type']
        # file_size = file_metadata['size']  # Not used currently
        
        safe_logfire_info(f"Starting document upload with progress tracking | progress_id={progress_id} | filename={filename} | content_type={content_type}")
        
        # Socket.IO handles connection automatically - no need to wait
        
        # Extract text from document with progress - use mapper for consistent progress
        mapped_progress = progress_mapper.map_progress('processing', 50)
        await update_crawl_progress(progress_id, {
            'status': 'processing',
            'percentage': mapped_progress,
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
        
        # Generate source_id from filename
        source_id = f"file_{filename.replace(' ', '_').replace('.', '_')}_{int(time.time())}"
        
        # Create progress callback that emits to Socket.IO with mapped progress
        async def document_progress_callback(message: str, percentage: int, batch_info: dict = None):
            """Progress callback that emits to Socket.IO with mapped progress"""
            # Map the document storage progress to overall progress range
            mapped_percentage = progress_mapper.map_progress('document_storage', percentage)
            
            progress_data = {
                'status': 'document_storage',
                'percentage': mapped_percentage,  # Use mapped progress to prevent backwards jumps
                'currentUrl': f"file://{filename}",
                'log': message
            }
            if batch_info:
                progress_data.update(batch_info)
            
            await update_crawl_progress(progress_id, progress_data)
        
        # Call the service's upload_document method
        success, result = await doc_storage_service.upload_document(
            file_content=extracted_text,
            filename=filename,
            source_id=source_id,
            knowledge_type=knowledge_type,
            tags=tag_list,
            progress_callback=document_progress_callback
        )
        
        if success:
            # Complete the upload with 100% progress
            final_progress = progress_mapper.map_progress('completed', 100)
            await update_crawl_progress(progress_id, {
                'status': 'completed',
                'percentage': final_progress,
                'currentUrl': f"file://{filename}",
                'log': f'Document upload completed successfully!'
            })
            
            # Also send the completion event with details
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
        success, result = await search_service.perform_rag_query(
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

@router.post("/rag/code-examples")
async def search_code_examples(request: RagQueryRequest):
    """Search for code examples relevant to the query using dedicated code examples service."""
    try:
        # Use SearchService for code examples search
        search_service = SearchService(get_supabase_client())
        success, result = await search_service.search_code_examples_service(
            query=request.query,
            source_id=request.source,  # This is Optional[str] which matches the method signature
            match_count=request.match_count
        )
        
        if success:
            # Add success flag and reformat to match expected API response format
            return {
                'success': True,
                'results': result.get('results', []),
                'reranked': result.get('reranking_applied', False),
                'error': None
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail={'error': result.get('error', 'Code examples search failed')}
            )
    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"Code examples search failed | error={str(e)} | query={request.query[:50]} | source={request.source}")
        raise HTTPException(status_code=500, detail={'error': f"Code examples search failed: {str(e)}"})

@router.post("/code-examples")
async def search_code_examples_simple(request: RagQueryRequest):
    """Search for code examples - simplified endpoint at /api/code-examples."""
    # Delegate to the existing endpoint handler
    return await search_code_examples(request)

@router.get("/rag/sources")
async def get_available_sources():
    """Get all available sources for RAG queries."""
    try:
        # Use KnowledgeItemService
        service = KnowledgeItemService(get_supabase_client())
        result = await service.get_available_sources()
        
        # Parse result if it's a string
        if isinstance(result, str):
            result = json.loads(result)
        
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
        # Use DatabaseMetricsService
        service = DatabaseMetricsService(get_supabase_client())
        metrics = await service.get_metrics()
        return metrics
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

@router.get("/knowledge-items/task/{task_id}")
async def get_crawl_task_status(task_id: str):
    """Get status of a background crawl task."""
    try:
        from ..services.background_task_manager import get_task_manager
        
        task_manager = get_task_manager()
        status = await task_manager.get_task_status(task_id)
        
        if "error" in status and status["error"] == "Task not found":
            raise HTTPException(status_code=404, detail={'error': 'Task not found'})
        
        return status
    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"Failed to get task status | error={str(e)} | task_id={task_id}")
        raise HTTPException(status_code=500, detail={'error': str(e)}) 

