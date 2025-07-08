"""
Crawl Orchestration Service

Handles the orchestration of crawling operations with progress tracking.
Extracted from the monolithic _perform_crawl_with_progress function in knowledge_api.py.
"""
from typing import Dict, Any, List
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
    
    def set_progress_id(self, progress_id: str):
        """Set the progress ID for Socket.IO updates."""
        self.progress_id = progress_id
    
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
                await update_crawl_progress(self.progress_id, {
                    'status': 'analyzing',
                    'percentage': 0,
                    'currentUrl': url,
                    'log': f'Analyzing URL type for {url}'
                })
            
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
            
            # Finalize and return results
            if self.progress_id:
                await update_crawl_progress(self.progress_id, {
                    'status': 'finalization',
                    'percentage': 95,
                    'log': 'Finalizing crawl results...'
                })
            
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
                await update_crawl_progress(self.progress_id, {
                    'status': 'crawling',
                    'percentage': 10,
                    'log': 'Detected text file, fetching content...'
                })
            crawl_results = await self.crawling_service.crawl_markdown_file(url)
            crawl_type = "text_file"
            
        elif self.crawling_service.is_sitemap(url):
            # Handle sitemaps
            if self.progress_id:
                await update_crawl_progress(self.progress_id, {
                    'status': 'crawling',
                    'percentage': 10,
                    'log': 'Detected sitemap, parsing URLs...'
                })
            sitemap_urls = self.crawling_service.parse_sitemap(url)
            
            if sitemap_urls:
                # Emit progress before starting batch crawl
                if self.progress_id:
                    await update_crawl_progress(self.progress_id, {
                        'status': 'crawling',
                        'percentage': 15,
                        'log': f'Starting batch crawl of {len(sitemap_urls)} URLs...'
                    })
                
                crawl_results = await self.crawling_service.crawl_batch_with_progress(
                    sitemap_urls,
                    progress_callback=None  # We'll emit directly, not via callback
                )
                crawl_type = "sitemap"
                
        else:
            # Handle regular webpages with recursive crawling
            if self.progress_id:
                await update_crawl_progress(self.progress_id, {
                    'status': 'crawling',
                    'percentage': 10,
                    'log': f'Starting recursive crawl with max depth {request.get("max_depth", 1)}...'
                })
            
            max_depth = request.get('max_depth', 1)
            crawl_results = await self.crawling_service.crawl_recursive_with_progress(
                [url],
                max_depth=max_depth,
                progress_callback=None  # We'll emit directly, not via callback
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
        if self.progress_id:
            await update_crawl_progress(self.progress_id, {
                'status': 'document_storage',
                'percentage': 50,
                'log': f'Processing {len(crawl_results)} documents...'
            })
        
        # Prepare documents for storage
        markdown_docs = []
        source_metadatas = []
        source_word_counts = {}
        url_to_full_document = {}
        
        for doc in crawl_results:
            source_url = doc.get('url', '')
            markdown_content = doc.get('markdown', '')
            
            if not markdown_content:
                continue
            
            # Store full document for code extraction context
            url_to_full_document[source_url] = markdown_content
            
            markdown_docs.append(markdown_content)
            
            # Create metadata
            parsed_url = urlparse(source_url)
            source_id = parsed_url.netloc or parsed_url.path
            word_count = len(markdown_content.split())
            
            metadata = {
                'url': source_url,
                'title': doc.get('title', ''),
                'description': doc.get('description', ''),
                'source_id': source_id,
                'knowledge_type': request.get('knowledge_type', 'documentation'),
                'crawl_type': crawl_type,
                'word_count': word_count,
                'char_count': len(markdown_content),
                'tags': request.get('tags', [])
            }
            
            source_metadatas.append(metadata)
            source_word_counts[source_id] = source_word_counts.get(source_id, 0) + word_count
        
        # Create/update source record FIRST before storing documents
        if markdown_docs and source_metadatas:
            # Get the primary source info (usually from the first document)
            primary_metadata = source_metadatas[0]
            source_id = primary_metadata['source_id']
            
            # Get combined content for summary generation (first 3 docs for context)
            combined_content = ' '.join(markdown_docs[:3])
            
            # Generate summary
            summary = extract_source_summary(source_id, combined_content)
            
            # Update source info in database BEFORE storing documents
            update_source_info(
                client=self.supabase_client,
                source_id=source_id,
                summary=summary,
                word_count=sum(source_word_counts.values()),
                content=combined_content,
                knowledge_type=request.get('knowledge_type', 'technical'),
                tags=request.get('tags', []),
                update_frequency=request.get('update_frequency', 7)
            )
            
            safe_logfire_info(f"Created/updated source record for {source_id}")
        
        # Store documents
        if self.progress_id:
            await update_crawl_progress(self.progress_id, {
                'status': 'document_storage',
                'percentage': 60,
                'log': f'Storing {len(markdown_docs)} documents...'
            })
        
        # Progress update before storing documents
        if self.progress_id:
            total_estimated_chunks = sum(
                max(1, len(doc) // 6000) for doc in markdown_docs
            )
            await update_crawl_progress(self.progress_id, {
                'status': 'document_storage',
                'percentage': 65,
                'log': f'Storing {len(markdown_docs)} documents (estimated {total_estimated_chunks} chunks)...'
            })
        
        # Debug: Force enable contextual embeddings for now
        # The credential service is working but let's ensure it's enabled
        import os
        os.environ['USE_CONTEXTUAL_EMBEDDINGS'] = 'true'
        safe_logfire_info(f"Forcing contextual embeddings ON")
            
        safe_logfire_info(f"url_to_full_document keys: {list(url_to_full_document.keys())[:5]}")
        
        # Prepare data for add_documents_to_supabase
        urls = [metadata['url'] for metadata in source_metadatas]
        chunk_numbers = [1] * len(urls)  # For now, treat each document as a single chunk
        
        safe_logfire_info(f"Document storage | urls={len(urls)} | markdown_docs={len(markdown_docs)} | metadatas={len(source_metadatas)}")
        
        # Call add_documents_to_supabase with the correct parameters
        if self.progress_id:
            await update_crawl_progress(self.progress_id, {
                'status': 'document_storage',
                'percentage': 70,
                'log': f'Calling add_documents_to_supabase with {len(urls)} URLs...'
            })
        
        await add_documents_to_supabase(
            client=self.supabase_client,
            urls=urls,
            chunk_numbers=chunk_numbers,
            contents=markdown_docs,
            metadatas=source_metadatas,
            url_to_full_document=url_to_full_document,
            batch_size=10,
            progress_callback=None,  # We'll emit directly, not via callback
            enable_parallel_batches=True  # Enable parallel processing
        )
        
        if self.progress_id:
            await update_crawl_progress(self.progress_id, {
                'status': 'document_storage',
                'percentage': 75,
                'log': f'Document storage completed for {len(markdown_docs)} documents'
            })
        
        # Calculate chunk count (for now, one chunk per document)
        chunk_count = len(markdown_docs)
        
        # Progress update - source already created above
        if self.progress_id:
            await update_crawl_progress(self.progress_id, {
                'status': 'source_update',
                'percentage': 80,
                'log': f'Source record and documents stored successfully'
            })
        
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
        
        # Emit progress before extraction
        if self.progress_id:
            await update_crawl_progress(self.progress_id, {
                'status': 'code_storage',
                'percentage': 85,
                'log': 'Extracting code examples...'
            })
        
        # Create progress callback for code extraction
        async def code_progress_callback(data: dict):
            if self.progress_id:
                # Update progress within 85-95% range
                percentage = data.get('percentage', 85)
                adjusted_percentage = 85 + int((percentage - 85) * 0.5)  # Scale to 85-90%
                await update_crawl_progress(self.progress_id, {
                    'status': data.get('status', 'code_storage'),
                    'percentage': min(adjusted_percentage, 90),
                    'log': data.get('log', 'Processing code examples...')
                })
        
        result = await code_service.extract_and_store_code_examples(
            crawl_results,
            url_to_full_document,
            code_progress_callback
        )
        
        # Final progress update
        if self.progress_id:
            await update_crawl_progress(self.progress_id, {
                'status': 'code_storage',
                'percentage': 90,
                'log': f'Code extraction completed. Found {result} code examples.'
            })
        
        return result