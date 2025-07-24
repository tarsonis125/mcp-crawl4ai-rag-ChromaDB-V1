"""
Blocking Helpers

Helper functions and classes for converting async operations to blocking
for use in ThreadPoolExecutor background tasks.
"""
import asyncio
from typing import Any, Coroutine, List, Dict, Optional
from queue import Queue
import threading
from urllib.parse import urlparse

from ..config.logfire_config import get_logger

logger = get_logger(__name__)

# Store the main event loop reference
_main_event_loop: Optional[asyncio.AbstractEventLoop] = None
_main_loop_thread_id: Optional[int] = None


def set_main_event_loop(loop: asyncio.AbstractEventLoop):
    """
    Set the main event loop reference for use in background threads.
    Should be called from the main thread during application startup.
    """
    global _main_event_loop, _main_loop_thread_id
    _main_event_loop = loop
    _main_loop_thread_id = threading.current_thread().ident
    logger.info(f"Main event loop set for thread {_main_loop_thread_id}")


def run_async_in_thread(coro: Coroutine, timeout: float = 30.0) -> Any:
    """
    Run an async coroutine from a thread pool executor.
    
    This function attempts to run the coroutine in the main event loop if available,
    otherwise creates a new event loop in the current thread (with warnings about limitations).
    
    Args:
        coro: The coroutine to run
        timeout: Maximum time to wait for the coroutine (default: 30 seconds)
        
    Returns:
        The result of the coroutine
        
    Raises:
        asyncio.TimeoutError: If the coroutine takes longer than timeout
        Exception: Any exception raised by the coroutine
    """
    current_thread_id = threading.current_thread().ident
    
    # Check if we're in the main thread (shouldn't happen in ThreadPoolExecutor)
    if current_thread_id == _main_loop_thread_id:
        logger.warning("run_async_in_thread called from main thread, running directly")
        loop = asyncio.get_running_loop()
        return loop.run_until_complete(coro)
    
    # Try to use the main event loop if available
    if _main_event_loop and not _main_event_loop.is_closed():
        logger.info(f"run_async_in_thread: Using main event loop via run_coroutine_threadsafe (loop={_main_event_loop})")
        try:
            future = asyncio.run_coroutine_threadsafe(coro, _main_event_loop)
            result = future.result(timeout=timeout)
            logger.info("run_async_in_thread: Successfully completed via main event loop")
            return result
        except Exception as e:
            logger.error(f"run_async_in_thread: Error using main event loop: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Fall through to create new event loop
    else:
        logger.warning(f"run_async_in_thread: Main event loop not available - loop={_main_event_loop}, closed={_main_event_loop.is_closed() if _main_event_loop else 'N/A'}")
    
    # No fallback - if main event loop is not available, fail fast
    logger.error("run_async_in_thread: Main event loop not available - cannot run async code in thread!")
    raise RuntimeError(
        "Cannot run async code in thread without main event loop. "
        "Ensure set_main_event_loop() was called during startup."
    )


# BlockingCrawlWrapper removed - browser operations should stay in the main event loop
# Only CPU-intensive operations should use blocking helpers


class BlockingEmbeddingWrapper:
    """Wrapper for blocking embedding operations"""
    
    @staticmethod
    def generate_embeddings_batch(texts: List[str], progress_queue: Queue) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts with progress reporting.
        
        Args:
            texts: List of texts to embed
            progress_queue: Queue for progress updates
            
        Returns:
            List of embedding vectors
        """
        async def _embed():
            from ..embeddings.embedding_service import create_embeddings_batch_async
            
            embeddings = []
            batch_size = 10
            total_batches = (len(texts) + batch_size - 1) // batch_size
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_embeddings = await create_embeddings_batch_async(batch)
                embeddings.extend(batch_embeddings)
                
                # Report progress
                current_batch = (i // batch_size) + 1
                progress = int((current_batch / total_batches) * 100)
                progress_queue.put({
                    'percentage': progress,
                    'log': f'Generated embeddings for batch {current_batch}/{total_batches}'
                })
            
            return embeddings
        
        return run_async_in_thread(_embed())


class BlockingStorageWrapper:
    """Wrapper for blocking storage operations"""
    
    def __init__(self, supabase_client):
        """
        Initialize with a Supabase client.
        
        Args:
            supabase_client: The Supabase client instance
        """
        self.client = supabase_client
    
    def store_documents_batch(
        self, 
        documents: List[Dict[str, Any]], 
        progress_queue: Queue,
        batch_size: int = 10
    ) -> int:
        """
        Store documents in batches with progress reporting.
        
        Args:
            documents: List of documents to store
            progress_queue: Queue for progress updates
            batch_size: Size of each batch
            
        Returns:
            Number of documents stored
        """
        total_docs = len(documents)
        stored_count = 0
        
        for i in range(0, total_docs, batch_size):
            batch = documents[i:i + batch_size]
            
            try:
                # Store batch in Supabase
                response = self.client.table('documents').insert(batch).execute()
                stored_count += len(batch)
                
                # Report progress
                progress = int((stored_count / total_docs) * 100)
                progress_queue.put({
                    'percentage': progress,
                    'log': f'Stored {stored_count}/{total_docs} documents'
                })
                
            except Exception as e:
                logger.error(f"Error storing document batch: {e}")
                # Continue with next batch
        
        return stored_count