"""
Crawl Orchestration Service

Handles the orchestration of crawling operations with progress tracking.
Extracted from the monolithic _perform_crawl_with_progress function in knowledge_api.py.
"""
import asyncio
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from ...config.logfire_config import safe_logfire_info, safe_logfire_error
from ..rag.crawling_service import CrawlingService
from ..storage.storage_services import DocumentStorageService
from ..storage.document_storage_service import add_documents_to_supabase
from .code_extraction_service import CodeExtractionService
from ...fastapi.socketio_handlers import update_crawl_progress
from ..source_management_service import update_source_info, extract_source_summary


class CrawlOrchestrationService:
    """
    Orchestrates the crawling process for knowledge items.
    Handles URL type detection, crawling, document storage, code extraction, and progress tracking.
    """
    
    def __init__(self, crawler, supabase_client, progress_id=None):
        """
        Initialize the crawl orchestration service.
        
        Args:
            crawler: The Crawl4AI crawler instance
            supabase_client: The Supabase client for database operations
            progress_id: Optional progress ID for Socket.IO updates
        """
        self.crawler = crawler
        self.supabase_client = supabase_client
        self.crawling_service = CrawlingService(crawler=crawler, supabase_client=supabase_client)
        self.doc_storage_service = DocumentStorageService(supabase_client)
        self.progress_id = progress_id
        # Track progress state across all stages to prevent UI resets
        self.progress_state = {}
    
    def set_progress_id(self, progress_id: str):
        """Set the progress ID for Socket.IO updates."""
        self.progress_id = progress_id
    
    def _is_documentation_site(self, url: str) -> bool:
        """Check if URL is a documentation site."""
        doc_patterns = [
            'docs.', 'documentation.', '/docs/', '/documentation/',
            'readthedocs', 'gitbook', 'docusaurus', 'vitepress',
            'docsify', 'mkdocs', 'copilotkit'
        ]
        return any(pattern in url.lower() for pattern in doc_patterns)
    
    async def _create_crawl_progress_callback(self, base_status: str):
        """Create a progress callback for crawling operations."""
        async def callback(status: str, percentage: int, message: str, **kwargs):
            if self.progress_id:
                # Update and preserve progress state
                self.progress_state.update({
                    'status': base_status,
                    'percentage': percentage,
                    'log': message,
                    **kwargs
                })
                safe_logfire_info(f"Emitting crawl progress | progress_id={self.progress_id} | status={base_status} | percentage={percentage}")
                await update_crawl_progress(self.progress_id, self.progress_state)
        return callback

    async def orchestrate_crawl(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main orchestration method that handles the entire crawling process.
        
        Args:
            request: The crawl request containing url, knowledge_type, tags, max_depth, etc.
            
        Returns:
            Dict containing crawl results and statistics
        """
        try:
            url = str(request.get('url', ''))
            safe_logfire_info(f"Starting crawl orchestration | url={url}")
            
            # Initial progress update
            if self.progress_id:
                self.progress_state = {
                    'status': 'analyzing',
                    'percentage': 0,
                    'currentUrl': url,
                    'log': f'Analyzing URL type for {url}'
                }
                await update_crawl_progress(self.progress_id, self.progress_state)
            
            # Detect URL type and perform appropriate crawl
            crawl_results, crawl_type = await self._crawl_by_url_type(url, request)
            
            if not crawl_results:
                raise ValueError("No content was crawled from the provided URL")
            
            # Process and store documents
            storage_results = await self._process_and_store_documents(
                crawl_results, request, crawl_type
            )
            
            # Extract and store code examples if enabled
            code_examples_count = 0
            if request.get('extract_code_examples', True):
                code_examples_count = await self._extract_and_store_code_examples(
                    crawl_results, storage_results['url_to_full_document']
                )
            
            # Finalize and return results with gradual progress
            
            # Progress update: Finalizing results (95% -> 97%)
            if self.progress_id:
                self.progress_state.update({
                    'status': 'finalization',
                    'percentage': 97,
                    'log': 'Finalizing crawl results...',
                    'chunks_stored': storage_results['chunk_count'],
                    'code_examples_found': code_examples_count
                })
                await update_crawl_progress(self.progress_id, self.progress_state)
                # Yield control to prevent blocking
                await asyncio.sleep(0)
            
            # Progress update: Preparing final report (97% -> 99%)
            if self.progress_id:
                self.progress_state.update({
                    'status': 'finalization',
                    'percentage': 99,
                    'log': 'Preparing final report...',
                    'chunks_stored': storage_results['chunk_count'],
                    'code_examples_found': code_examples_count,
                    'processed_pages': len(crawl_results),
                    'total_pages': len(crawl_results)
                })
                await update_crawl_progress(self.progress_id, self.progress_state)
                # Yield control to prevent blocking
                await asyncio.sleep(0)
            
            # Send final progress update to reach 100%
            if self.progress_id:
                self.progress_state.update({
                    'status': 'completed',
                    'percentage': 100,
                    'log': f'Crawl completed successfully: {storage_results["chunk_count"]} chunks stored, {code_examples_count} code examples found',
                    'chunks_stored': storage_results['chunk_count'],
                    'code_examples_found': code_examples_count,
                    'processed_pages': len(crawl_results),
                    'total_pages': len(crawl_results)
                })
                await update_crawl_progress(self.progress_id, self.progress_state)
                # Small delay to ensure Socket.IO message is delivered before function returns
                await asyncio.sleep(0.1)
            
            return {
                'success': True,
                'chunks_stored': storage_results['chunk_count'],
                'word_count': storage_results['total_word_count'],
                'code_examples_stored': code_examples_count,
                'processed_pages': len(crawl_results),
                'total_pages': len(crawl_results)
            }
            
        except Exception as e:
            safe_logfire_error(f"Crawl orchestration failed | error={str(e)}")
            if self.progress_id:
                self.progress_state.update({
                    'status': 'error',
                    'percentage': self.progress_state.get('percentage', 0),
                    'log': f'Crawl failed: {str(e)}'
                })
                await update_crawl_progress(self.progress_id, self.progress_state)
            raise
    
    async def _crawl_by_url_type(self, url: str, request: Dict[str, Any]) -> tuple:
        """
        Detect URL type and perform appropriate crawling.
        
        Returns:
            Tuple of (crawl_results, crawl_type)
        """
        crawl_results = []
        crawl_type = None
        
        if self.crawling_service.is_txt(url):
            # Handle text files
            if self.progress_id:
                self.progress_state.update({
                    'status': 'crawling',
                    'percentage': 10,
                    'log': 'Detected text file, fetching content...'
                })
                await update_crawl_progress(self.progress_id, self.progress_state)
            crawl_results = await self.crawling_service.crawl_markdown_file(
                url,
                progress_callback=await self._create_crawl_progress_callback('crawling'),
                start_progress=10,
                end_progress=20
            )
            crawl_type = "text_file"
            
        elif self.crawling_service.is_sitemap(url):
            # Handle sitemaps
            if self.progress_id:
                self.progress_state.update({
                    'status': 'crawling',
                    'percentage': 10,
                    'log': 'Detected sitemap, parsing URLs...'
                })
                await update_crawl_progress(self.progress_id, self.progress_state)
            sitemap_urls = self.crawling_service.parse_sitemap(url)
            
            if sitemap_urls:
                # Emit progress before starting batch crawl
                if self.progress_id:
                    self.progress_state.update({
                        'status': 'crawling',
                        'percentage': 15,
                        'log': f'Starting batch crawl of {len(sitemap_urls)} URLs...'
                    })
                    await update_crawl_progress(self.progress_id, self.progress_state)
                
                crawl_results = await self.crawling_service.crawl_batch_with_progress(
                    sitemap_urls,
                    progress_callback=await self._create_crawl_progress_callback('crawling'),
                    start_progress=15,
                    end_progress=20
                )
                crawl_type = "sitemap"
                
        else:
            # Handle regular webpages with recursive crawling
            if self.progress_id:
                self.progress_state.update({
                    'status': 'crawling',
                    'percentage': 10,
                    'log': f'Starting recursive crawl with max depth {request.get("max_depth", 1)}...'
                })
                await update_crawl_progress(self.progress_id, self.progress_state)
            
            max_depth = request.get('max_depth', 1)
            # Limit concurrent crawls for better performance
            max_concurrent = 20 if self._is_documentation_site(url) else 10
            
            crawl_results = await self.crawling_service.crawl_recursive_with_progress(
                [url],
                max_depth=max_depth,
                max_concurrent=max_concurrent,
                progress_callback=await self._create_crawl_progress_callback('crawling'),
                start_progress=10,
                end_progress=20
            )
            crawl_type = "webpage"
        
        return crawl_results, crawl_type
    
    async def _process_and_store_documents(self, crawl_results: List[Dict], request: Dict[str, Any], 
                                          crawl_type: str) -> Dict[str, Any]:
        """
        Process crawled documents and store them in the database.
        
        Returns:
            Dict containing storage statistics and document mappings
        """
        # Progress will be reported by document storage service
        
        # Import the document storage service for chunking
        from ..storage.storage_services import DocumentStorageService
        
        # Initialize storage service for chunking
        storage_service = DocumentStorageService(self.supabase_client)
        
        # Prepare data for chunked storage
        all_urls = []
        all_chunk_numbers = []
        all_contents = []
        all_metadatas = []
        source_word_counts = {}
        url_to_full_document = {}
        
        # Process and chunk each document
        for doc_index, doc in enumerate(crawl_results):
            source_url = doc.get('url', '')
            markdown_content = doc.get('markdown', '')
            
            if not markdown_content:
                continue
            
            # Store full document for code extraction context
            url_to_full_document[source_url] = markdown_content
            
            # CHUNK THE CONTENT (restored from old implementation)
            chunks = storage_service.smart_chunk_text(markdown_content, chunk_size=5000)
            
            # Extract source_id
            parsed_url = urlparse(source_url)
            source_id = parsed_url.netloc or parsed_url.path
            safe_logfire_info(f"Extracted source_id '{source_id}' from URL '{source_url}'")
            
            # Process each chunk
            for i, chunk in enumerate(chunks):
                all_urls.append(source_url)
                all_chunk_numbers.append(i)
                all_contents.append(chunk)
                
                # Create metadata for each chunk
                word_count = len(chunk.split())
                metadata = {
                    'url': source_url,
                    'title': doc.get('title', ''),
                    'description': doc.get('description', ''),
                    'source_id': source_id,
                    'knowledge_type': request.get('knowledge_type', 'documentation'),
                    'crawl_type': crawl_type,
                    'word_count': word_count,
                    'char_count': len(chunk),
                    'chunk_index': i,
                    'tags': request.get('tags', [])
                }
                all_metadatas.append(metadata)
                
                # Accumulate word count
                source_word_counts[source_id] = source_word_counts.get(source_id, 0) + word_count
                
                # Yield control every 10 chunks to prevent event loop blocking
                if i > 0 and i % 10 == 0:
                    await asyncio.sleep(0)
            
            # Yield control after processing each document
            if doc_index > 0 and doc_index % 5 == 0:
                await asyncio.sleep(0)
        
        # Create/update source record FIRST before storing documents
        if all_contents and all_metadatas:
            # Get the primary source info (usually from the first metadata)
            primary_metadata = all_metadatas[0]
            source_id = primary_metadata['source_id']
            
            # Get combined content for summary generation (first few chunks for context)
            # Take first 15000 chars (roughly 3 chunks) for summary
            combined_content = ''
            for chunk in all_contents:
                if len(combined_content) + len(chunk) < 15000:
                    combined_content += ' ' + chunk
                else:
                    break
            
            # Generate summary
            summary = extract_source_summary(source_id, combined_content)
            
            # Update source info in database BEFORE storing documents
            safe_logfire_info(f"About to create/update source record for '{source_id}'")
            try:
                update_source_info(
                    client=self.supabase_client,
                    source_id=source_id,
                    summary=summary,
                    word_count=sum(source_word_counts.values()),
                    content=combined_content,
                    knowledge_type=request.get('knowledge_type', 'technical'),
                    tags=request.get('tags', []),
                    update_frequency=0  # Set to 0 since we're using manual refresh
                )
                safe_logfire_info(f"Successfully created/updated source record for '{source_id}'")
            except Exception as e:
                safe_logfire_error(f"Failed to create/update source record for '{source_id}': {str(e)}")
                raise  # Re-raise to stop processing
        
        # Document storage progress will be handled by the callback
        
        # Contextual embeddings will be loaded from credential service in document_storage_service
            
        safe_logfire_info(f"url_to_full_document keys: {list(url_to_full_document.keys())[:5]}")
        
        # Log chunking results
        safe_logfire_info(f"Document storage | documents={len(crawl_results)} | chunks={len(all_contents)} | avg_chunks_per_doc={len(all_contents)/len(crawl_results):.1f}")
        
        # Create a progress callback for document storage
        async def doc_storage_callback(message: str, percentage: int, batch_info: Optional[dict] = None):
            if self.progress_id:
                # Map percentage to document storage range (20-85%)
                mapped_percentage = 20 + int((percentage / 100) * (85 - 20))
                safe_logfire_info(f"Document storage progress mapping: {percentage}% -> {mapped_percentage}%")
                
                # Update progress state while preserving existing fields
                self.progress_state.update({
                    'status': 'document_storage',
                    'percentage': mapped_percentage,
                    'log': message
                })
                
                # Add batch_info fields if provided
                if batch_info:
                    self.progress_state.update(batch_info)
                
                await update_crawl_progress(self.progress_id, self.progress_state)
        
        # Call add_documents_to_supabase with the correct parameters
        # Progress update already handled at start of function
        
        await add_documents_to_supabase(
            client=self.supabase_client,
            urls=all_urls,  # Now has entry per chunk
            chunk_numbers=all_chunk_numbers,  # Proper chunk numbers (0, 1, 2, etc)
            contents=all_contents,  # Individual chunks
            metadatas=all_metadatas,  # Metadata per chunk
            url_to_full_document=url_to_full_document,
            batch_size=10,
            progress_callback=doc_storage_callback,  # Pass the callback for progress updates
            enable_parallel_batches=True  # Enable parallel processing
        )
        
        # Progress will be at 80% after document storage completes
        
        # Calculate actual chunk count
        chunk_count = len(all_contents)
        
        # Source update already done during document storage
        
        return {
            'chunk_count': chunk_count,
            'total_word_count': sum(source_word_counts.values()),
            'url_to_full_document': url_to_full_document
        }
    
    async def _extract_and_store_code_examples(self, crawl_results: List[Dict], 
                                              url_to_full_document: Dict[str, str]) -> int:
        """
        Extract code examples from crawled documents and store them.
        
        Returns:
            Number of code examples stored
        """
        # Use CodeExtractionService
        code_service = CodeExtractionService(self.supabase_client)
        
        # Create progress callback for code extraction
        async def code_progress_callback(data: dict):
            if self.progress_id:
                # Update progress state while preserving existing fields
                self.progress_state.update(data)
                await update_crawl_progress(self.progress_id, self.progress_state)
        
        result = await code_service.extract_and_store_code_examples(
            crawl_results,
            url_to_full_document,
            code_progress_callback,
            start_progress=85,
            end_progress=95
        )
        
        # No need for duplicate progress update here - the code extraction service handles it
        
        return result