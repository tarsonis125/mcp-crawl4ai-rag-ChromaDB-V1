"""
Background Task Manager

Manages background task execution with progress tracking using ThreadPoolExecutor.
Ensures long-running operations don't block the main event loop.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import Dict, Any, Optional, Callable
import uuid
from datetime import datetime

from ..config.logfire_config import get_logger

logger = get_logger(__name__)


class BackgroundTaskManager:
    """Manages background task execution with progress tracking"""
    
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_tasks: Dict[str, asyncio.Future] = {}
        self.progress_queues: Dict[str, Queue] = {}
        self.task_metadata: Dict[str, Dict[str, Any]] = {}
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None
        logger.info(f"BackgroundTaskManager initialized with {max_workers} workers")
    
    def set_main_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the main event loop for the task manager"""
        self.main_loop = loop
        # Also set it in blocking_helpers for global access
        from .blocking_helpers import set_main_event_loop
        set_main_event_loop(loop)
        logger.info("Main event loop set in BackgroundTaskManager")
    
    async def submit_task(
        self,
        task_func: Callable,
        task_args: tuple,
        task_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> str:
        """Submit a blocking task for background execution"""
        task_id = task_id or str(uuid.uuid4())
        
        # Create progress queue
        progress_queue = Queue()
        self.progress_queues[task_id] = progress_queue
        
        # Store metadata
        self.task_metadata[task_id] = {
            'created_at': datetime.utcnow(),
            'status': 'running',
            'progress': 0
        }
        
        logger.info(f"Submitting task {task_id} for background execution")
        
        # Start progress emitter if callback provided
        if progress_callback:
            asyncio.create_task(
                self._emit_progress(task_id, progress_queue, progress_callback)
            )
        
        # Submit to executor
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(
            self.executor,
            self._run_with_progress,
            task_func,
            task_args,
            progress_queue,
            task_id
        )
        
        self.active_tasks[task_id] = future
        return task_id
    
    def _run_with_progress(
        self,
        task_func: Callable,
        task_args: tuple,
        progress_queue: Queue,
        task_id: str
    ) -> Any:
        """Wrapper to inject progress queue into task function"""
        try:
            logger.info(f"Starting execution of task {task_id}")
            # Inject progress_queue as first argument
            result = task_func(progress_queue, *task_args)
            progress_queue.put({
                'status': 'complete',
                'percentage': 100,
                'result': result
            })
            logger.info(f"Task {task_id} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Task {task_id} failed with error: {e}")
            progress_queue.put({
                'status': 'error',
                'percentage': -1,
                'error': str(e)
            })
            raise
    
    async def _emit_progress(
        self,
        task_id: str,
        queue: Queue,
        callback: Callable
    ):
        """Emit progress updates from queue"""
        logger.debug(f"Starting progress emitter for task {task_id}")
        
        last_heartbeat = datetime.utcnow()
        heartbeat_interval = 30  # Send heartbeat every 30 seconds
        
        while True:
            try:
                if not queue.empty():
                    update = queue.get_nowait()
                    logger.info(f"Progress update from queue for task {task_id}: status={update.get('status')}, percentage={update.get('percentage')}")
                    
                    # Update metadata with all progress information
                    # Store the complete update for reconnection purposes
                    if 'percentage' in update:
                        self.task_metadata[task_id].update({
                            'status': update.get('status', 'running'),
                            'progress': update.get('percentage', 0),
                            'last_update': update  # Store complete update for reconnections
                        })
                    else:
                        # Only update status if no percentage
                        self.task_metadata[task_id]['status'] = update.get('status', 'running')
                        self.task_metadata[task_id]['last_update'] = update
                    
                    # Call callback with error handling to prevent Socket.IO failures from crashing tasks
                    logger.info(f"Calling progress callback for task {task_id}")
                    try:
                        await callback(task_id, update)
                        logger.info(f"Progress callback completed for task {task_id}")
                    except Exception as callback_error:
                        # Log but don't crash - Socket.IO failures shouldn't kill background tasks
                        logger.error(f"Progress callback error for task {task_id}: {callback_error}")
                        logger.error(f"Continuing task execution despite callback failure")
                    
                    # Exit on completion
                    if update.get('status') in ['complete', 'error']:
                        logger.debug(f"Task {task_id} reached terminal state: {update.get('status')}")
                        break
                    
                    # Reset heartbeat timer after sending an update
                    last_heartbeat = datetime.utcnow()
                else:
                    # Check if we need to send a heartbeat
                    time_since_heartbeat = (datetime.utcnow() - last_heartbeat).total_seconds()
                    if time_since_heartbeat >= heartbeat_interval:
                        # Send heartbeat to keep connection alive
                        metadata = self.task_metadata.get(task_id, {})
                        heartbeat_update = {
                            'status': metadata.get('status', 'running'),
                            'percentage': metadata.get('progress', 0),
                            'heartbeat': True,
                            'log': 'Background task still running...'
                        }
                        
                        logger.debug(f"Sending heartbeat for task {task_id}")
                        try:
                            await callback(task_id, heartbeat_update)
                        except Exception as e:
                            logger.error(f"Heartbeat callback error for task {task_id}: {e}")
                        
                        last_heartbeat = datetime.utcnow()
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Progress emission error for task {task_id}: {e}")
                break
        
        # Cleanup
        if task_id in self.progress_queues:
            del self.progress_queues[task_id]
            logger.debug(f"Cleaned up progress queue for task {task_id}")
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get current status of a task"""
        if task_id not in self.active_tasks:
            return {"error": "Task not found"}
        
        metadata = self.task_metadata.get(task_id, {})
        future = self.active_tasks[task_id]
        
        if future.done():
            try:
                result = future.result()
                metadata['result'] = result
            except Exception as e:
                metadata['error'] = str(e)
        
        return metadata
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        if task_id in self.active_tasks:
            logger.info(f"Cancelling task {task_id}")
            self.active_tasks[task_id].cancel()
            del self.active_tasks[task_id]
            self.task_metadata[task_id]['status'] = 'cancelled'
            return True
        return False
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Shutting down BackgroundTaskManager")
        self.executor.shutdown(wait=True)


# Global instance
_task_manager: Optional[BackgroundTaskManager] = None


def get_task_manager() -> BackgroundTaskManager:
    """Get or create the global task manager instance"""
    global _task_manager
    if _task_manager is None:
        _task_manager = BackgroundTaskManager()
    return _task_manager


async def cleanup_task_manager():
    """Cleanup the global task manager instance"""
    global _task_manager
    if _task_manager:
        await _task_manager.cleanup()
        _task_manager = None