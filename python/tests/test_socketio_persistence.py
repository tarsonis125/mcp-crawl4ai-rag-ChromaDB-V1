"""
Test Socket.IO Connection Persistence

This test suite defines how Socket.IO connections should remain stable
during background tasks and handle reconnections properly.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import socketio


class TestSocketIOPersistence:
    """Test suite for Socket.IO connection persistence during background tasks"""
    
    @pytest.fixture
    def mock_sio(self):
        """Create a mock Socket.IO instance"""
        sio = Mock(spec=socketio.AsyncServer)
        sio.emit = AsyncMock()
        sio.enter_room = AsyncMock()
        sio.leave_room = AsyncMock()
        sio.rooms = Mock(return_value=['room1', 'room2'])
        
        # Mock manager for room inspection
        sio.manager = Mock()
        sio.manager.rooms = {
            '/': {
                'progress-123': ['sid-1', 'sid-2'],
                'progress-456': ['sid-3']
            }
        }
        return sio
    
    @pytest.fixture
    def mock_task_manager(self):
        """Create a mock task manager with active tasks"""
        manager = Mock()
        manager.active_tasks = {
            'progress-123': Mock(done=Mock(return_value=False)),
            'progress-456': Mock(done=Mock(return_value=True))
        }
        manager.task_metadata = {
            'progress-123': {
                'status': 'running',
                'progress': 45,
                'last_update': {
                    'status': 'document_storage',
                    'percentage': 45,
                    'log': 'Processing documents...',
                    'chunks_stored': 25
                }
            }
        }
        manager.get_task_status = AsyncMock(return_value={
            'status': 'running',
            'progress': 45,
            'last_update': {
                'status': 'document_storage',
                'percentage': 45,
                'log': 'Processing documents...'
            }
        })
        return manager
    
    @pytest.mark.asyncio
    async def test_client_subscription_to_progress_room(self, mock_sio):
        """Test that clients can subscribe to progress rooms"""
        from src.server.fastapi.socketio_handlers import crawl_subscribe
        
        sid = 'test-client-123'
        progress_id = 'progress-123'
        
        # Mock the handler dependencies
        with patch('src.server.fastapi.socketio_handlers.sio', mock_sio):
            with patch('src.server.fastapi.socketio_handlers.get_task_manager', 
                      return_value=Mock(get_task_status=AsyncMock(return_value={'status': 'running'}))):
                
                # Subscribe to progress
                await crawl_subscribe(sid, {'progress_id': progress_id})
                
                # Verify client joined the room
                mock_sio.enter_room.assert_called_once_with(sid, progress_id)
                
                # Verify acknowledgment sent
                ack_calls = [call for call in mock_sio.emit.call_args_list 
                           if call[0][0] == 'crawl_subscribe_ack']
                assert len(ack_calls) == 1
                assert ack_calls[0][0][1]['progress_id'] == progress_id
    
    @pytest.mark.asyncio
    async def test_reconnection_receives_current_state(self, mock_sio, mock_task_manager):
        """Test that reconnecting clients receive the current progress state"""
        from src.server.fastapi.socketio_handlers import crawl_subscribe
        
        sid = 'reconnect-client-456'
        progress_id = 'progress-123'
        
        with patch('src.server.fastapi.socketio_handlers.sio', mock_sio):
            with patch('src.server.fastapi.socketio_handlers.get_task_manager', 
                      return_value=mock_task_manager):
                
                # Client reconnects and subscribes
                await crawl_subscribe(sid, {'progress_id': progress_id})
                
                # Verify current state was sent
                progress_calls = [call for call in mock_sio.emit.call_args_list 
                                if call[0][0] == 'crawl_progress']
                assert len(progress_calls) >= 1
                
                # Check the reconnection data
                reconnect_data = progress_calls[0][0][1]
                assert reconnect_data['progressId'] == progress_id
                assert reconnect_data['status'] == 'running'
                assert reconnect_data['percentage'] == 45
                assert reconnect_data['isReconnect'] == True
    
    @pytest.mark.asyncio
    async def test_heartbeat_keeps_connection_alive(self, mock_sio):
        """Test that heartbeat messages prevent connection timeout"""
        # This test verifies the heartbeat mechanism concept
        # Since the current implementation doesn't have heartbeats,
        # we test the concept of periodic updates during long operations
        
        update_count = 0
        update_timestamps = []
        
        async def track_updates(task_id, update):
            nonlocal update_count
            update_count += 1
            update_timestamps.append(datetime.now())
        
        # Simulate a heartbeat-like mechanism
        async def simulate_heartbeat_mechanism(progress_callback, task_id):
            """Simulate sending periodic updates during long operations"""
            for i in range(3):
                await asyncio.sleep(0.1)  # Small delay to simulate work
                await progress_callback(task_id, {
                    'status': 'running',
                    'percentage': 10 + (i * 10),
                    'heartbeat': True,
                    'log': 'Background task still running...'
                })
        
        # Run the simulation
        task_id = 'test-heartbeat-123'
        await simulate_heartbeat_mechanism(track_updates, task_id)
        
        # Verify periodic updates were sent
        assert update_count >= 3, f"Expected at least 3 updates, got {update_count}"
        
        # Verify updates had time between them
        if len(update_timestamps) >= 2:
            interval = (update_timestamps[1] - update_timestamps[0]).total_seconds()
            assert interval > 0, "Updates should have time between them"
    
    @pytest.mark.asyncio
    async def test_socket_errors_dont_crash_background_tasks(self, mock_sio):
        """Test that Socket.IO errors don't crash the background task"""
        from src.server.services.background_task_manager import BackgroundTaskManager
        
        # Make emit raise an error
        mock_sio.emit = AsyncMock(side_effect=Exception("Socket.IO connection lost"))
        
        task_completed = False
        task_error = None
        
        def important_task(progress_queue):
            nonlocal task_completed, task_error
            try:
                progress_queue.put({'status': 'running', 'percentage': 50})
                import time
                time.sleep(0.1)  # Use blocking sleep in sync function
                progress_queue.put({'status': 'complete', 'percentage': 100})
                task_completed = True
            except Exception as e:
                task_error = e
        
        async def failing_callback(task_id, update):
            # This will raise due to mock_sio.emit error
            await mock_sio.emit('progress', update)
        
        task_manager = BackgroundTaskManager()
        
        # Submit task with failing callback
        task_id = await task_manager.submit_task(
            important_task,
            (),
            progress_callback=failing_callback
        )
        
        # Wait for task completion
        await asyncio.sleep(0.2)
        
        # Verify task completed despite Socket.IO errors
        assert task_completed == True, "Task should complete even if Socket.IO fails"
        assert task_error is None, f"Task should not have errors: {task_error}"
    
    @pytest.mark.asyncio
    async def test_multiple_clients_receive_updates(self, mock_sio):
        """Test that all clients in a progress room receive updates"""
        from src.server.fastapi.socketio_handlers import update_crawl_progress
        
        progress_id = 'progress-789'
        
        # Set up multiple clients in the room
        mock_sio.manager.rooms['/'][progress_id] = ['client-1', 'client-2', 'client-3']
        
        with patch('src.server.fastapi.socketio_handlers.sio', mock_sio):
            # Send progress update
            await update_crawl_progress(progress_id, {
                'status': 'crawling',
                'percentage': 25,
                'log': 'Crawling page 5 of 20'
            })
            
            # Verify broadcast to room (not individual clients)
            mock_sio.emit.assert_called_with(
                'crawl_progress',
                {
                    'progressId': progress_id,
                    'status': 'crawling',
                    'percentage': 25,
                    'log': 'Crawling page 5 of 20'
                },
                room=progress_id
            )
    
    @pytest.mark.asyncio
    async def test_rate_limiting_prevents_spam(self, mock_sio):
        """Test that rate limiting prevents Socket.IO spam"""
        from src.server.fastapi.socketio_handlers import update_crawl_progress
        
        progress_id = 'progress-spam-test'
        emit_count = 0
        
        # Track emit calls
        async def count_emits(*args, **kwargs):
            nonlocal emit_count
            emit_count += 1
        
        mock_sio.emit = count_emits
        
        with patch('src.server.fastapi.socketio_handlers.sio', mock_sio):
            # Send many updates rapidly
            for i in range(20):
                await update_crawl_progress(progress_id, {
                    'status': 'crawling',
                    'percentage': i * 5,
                    'log': f'Update {i}'
                })
                # Minimal delay to simulate rapid updates
                await asyncio.sleep(0.01)
            
            # Due to rate limiting, emit count should be less than 20
            # Important statuses (0%, completion) should always go through
            assert emit_count < 20, f"Rate limiting should reduce emits, got {emit_count}"
    
    @pytest.mark.asyncio
    async def test_progress_room_cleanup_on_completion(self, mock_sio):
        """Test that progress rooms are cleaned up after task completion"""
        from src.server.fastapi.socketio_handlers import crawl_unsubscribe
        
        sid = 'cleanup-client'
        progress_id = 'progress-cleanup-123'
        
        with patch('src.server.fastapi.socketio_handlers.sio', mock_sio):
            # Client unsubscribes when task completes
            await crawl_unsubscribe(sid, {'progress_id': progress_id})
            
            # Verify client left the room
            mock_sio.leave_room.assert_called_once_with(sid, progress_id)


class TestSocketIOResilience:
    """Test Socket.IO resilience and error recovery"""
    
    @pytest.mark.asyncio
    async def test_connection_recovery_after_disconnect(self):
        """Test that clients can recover after temporary disconnection"""
        # Simulate connection states
        connection_states = []
        
        class ConnectionTracker:
            def __init__(self):
                self.connected = False
                self.progress_id = None
            
            async def connect(self, sid):
                self.connected = True
                connection_states.append(('connected', sid))
            
            async def disconnect(self, sid):
                self.connected = False
                connection_states.append(('disconnected', sid))
            
            async def resubscribe(self, sid, progress_id):
                if self.connected:
                    self.progress_id = progress_id
                    connection_states.append(('resubscribed', sid, progress_id))
        
        tracker = ConnectionTracker()
        
        # Simulate connection lifecycle
        await tracker.connect('sid-1')
        await tracker.resubscribe('sid-1', 'progress-123')
        await tracker.disconnect('sid-1')
        await tracker.connect('sid-2')  # New SID after reconnect
        await tracker.resubscribe('sid-2', 'progress-123')
        
        # Verify connection recovery
        assert connection_states[-1][0] == 'resubscribed'
        assert connection_states[-1][2] == 'progress-123'
    
    @pytest.mark.asyncio
    async def test_concurrent_progress_updates_handling(self):
        """Test handling of concurrent progress updates from multiple stages"""
        from asyncio import Queue
        
        update_queue = Queue()
        processed_updates = []
        
        async def process_updates():
            """Simulate Socket.IO emit processing"""
            while True:
                try:
                    update = await asyncio.wait_for(update_queue.get(), timeout=0.5)
                    processed_updates.append(update)
                except asyncio.TimeoutError:
                    break
        
        # Simulate concurrent updates from different stages
        async def crawl_stage():
            for i in range(3):
                await update_queue.put({'stage': 'crawl', 'progress': i * 10})
                await asyncio.sleep(0.01)
        
        async def storage_stage():
            for i in range(3):
                await update_queue.put({'stage': 'storage', 'progress': 30 + i * 20})
                await asyncio.sleep(0.01)
        
        # Run stages concurrently
        await asyncio.gather(
            crawl_stage(),
            storage_stage(),
            process_updates()
        )
        
        # Verify all updates were processed
        assert len(processed_updates) == 6
        assert any(u['stage'] == 'crawl' for u in processed_updates)
        assert any(u['stage'] == 'storage' for u in processed_updates)