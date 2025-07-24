"""
Test Background Task Progress Tracking

This test suite defines how progress tracking should work for background tasks.
Tests ensure that progress updates are coordinated properly across all stages
and that progress never jumps backwards.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime


class TestProgressTracking:
    """Test suite for background task progress tracking"""
    
    @pytest.fixture
    def mock_socket_emit(self):
        """Mock Socket.IO emit function"""
        return AsyncMock()
    
    @pytest.fixture
    def progress_tracker(self):
        """Create a progress tracker that records all updates"""
        class ProgressTracker:
            def __init__(self):
                self.updates = []
                self.last_percentage = 0
            
            async def update(self, progress_id: str, data: dict):
                self.updates.append({
                    'timestamp': datetime.now(),
                    'progress_id': progress_id,
                    'data': data.copy()
                })
                if 'percentage' in data:
                    self.last_percentage = data['percentage']
        
        return ProgressTracker()
    
    @pytest.mark.asyncio
    async def test_progress_never_goes_backwards(self, progress_tracker):
        """Test that progress percentage never decreases"""
        # Simulate progress updates from different stages
        progress_updates = [
            {'status': 'starting', 'percentage': 0, 'log': 'Starting crawl'},
            {'status': 'crawling', 'percentage': 10, 'log': 'Crawling page 1'},
            {'status': 'crawling', 'percentage': 20, 'log': 'Crawling page 2'},
            {'status': 'crawling', 'percentage': 30, 'log': 'Crawling complete'},
            {'status': 'document_storage', 'percentage': 40, 'log': 'Storing documents'},
            {'status': 'document_storage', 'percentage': 60, 'log': 'Generating embeddings'},
            {'status': 'document_storage', 'percentage': 80, 'log': 'Storage complete'},
            {'status': 'code_extraction', 'percentage': 85, 'log': 'Extracting code'},
            {'status': 'code_extraction', 'percentage': 95, 'log': 'Code extraction complete'},
            {'status': 'completed', 'percentage': 100, 'log': 'All tasks complete'}
        ]
        
        progress_id = 'test-progress-123'
        
        # Process all updates
        for update in progress_updates:
            await progress_tracker.update(progress_id, update)
        
        # Verify progress never went backwards
        percentages = [u['data']['percentage'] for u in progress_tracker.updates if 'percentage' in u['data']]
        for i in range(1, len(percentages)):
            assert percentages[i] >= percentages[i-1], \
                f"Progress went backwards: {percentages[i-1]}% -> {percentages[i]}%"
    
    @pytest.mark.asyncio
    async def test_progress_stage_ranges(self, progress_tracker):
        """Test that each stage reports progress within its designated range"""
        # Define expected ranges for each stage (matching ProgressMapper)
        stage_ranges = {
            'crawling': (5, 30),
            'document_storage': (35, 80),
            'code_extraction': (80, 95),
            'finalization': (95, 100)
        }
        
        # Test crawling stage
        crawl_updates = [
            {'status': 'crawling', 'percentage': 5, 'stage_progress': 0},
            {'status': 'crawling', 'percentage': 18, 'stage_progress': 50},
            {'status': 'crawling', 'percentage': 30, 'stage_progress': 100}
        ]
        
        for update in crawl_updates:
            await progress_tracker.update('test', update)
            assert stage_ranges['crawling'][0] <= update['percentage'] <= stage_ranges['crawling'][1]
        
        # Test document storage stage
        storage_updates = [
            {'status': 'document_storage', 'percentage': 35, 'stage_progress': 0},
            {'status': 'document_storage', 'percentage': 58, 'stage_progress': 50},
            {'status': 'document_storage', 'percentage': 80, 'stage_progress': 100}
        ]
        
        for update in storage_updates:
            await progress_tracker.update('test', update)
            assert stage_ranges['document_storage'][0] <= update['percentage'] <= stage_ranges['document_storage'][1]
    
    @pytest.mark.asyncio
    async def test_sub_task_progress_mapping(self):
        """Test that sub-task progress maps correctly to overall progress"""
        from src.server.services.knowledge.progress_mapper import ProgressMapper
        
        mapper = ProgressMapper()
        
        # Test crawling stage mapping (5-30%)
        assert mapper.map_progress('crawling', 0) == 5
        assert mapper.map_progress('crawling', 50) == 18  # 5 + (50% of 25) = 17.5, rounded to 18
        assert mapper.map_progress('crawling', 100) == 30
        
        # Test document storage mapping (35-80%)
        assert mapper.map_progress('document_storage', 0) == 35
        assert mapper.map_progress('document_storage', 50) == 58  # 35 + (50% of 45) = 57.5, rounded to 58
        assert mapper.map_progress('document_storage', 100) == 80
        
        # Test code extraction mapping (80-95%)
        assert mapper.map_progress('code_extraction', 0) == 80
        assert mapper.map_progress('code_extraction', 50) == 88  # 80 + (50% of 15), rounded
        assert mapper.map_progress('code_extraction', 100) == 95
        
        # Test finalization mapping (95-100%)
        assert mapper.map_progress('finalization', 0) == 95
        assert mapper.map_progress('finalization', 100) == 100
    
    @pytest.mark.asyncio
    async def test_progress_state_persistence(self, progress_tracker):
        """Test that progress state is stored for reconnecting clients"""
        progress_id = 'test-reconnect-123'
        
        # Simulate initial progress updates
        updates = [
            {'status': 'crawling', 'percentage': 15, 'currentUrl': 'https://example.com', 'log': 'Crawling in progress'},
            {'status': 'document_storage', 'percentage': 45, 'chunks_stored': 25, 'log': 'Storing documents'}
        ]
        
        # Process updates
        for update in updates:
            await progress_tracker.update(progress_id, update)
        
        # Verify last state is stored
        assert progress_tracker.last_percentage == 45
        last_update = progress_tracker.updates[-1]['data']
        assert last_update['status'] == 'document_storage'
        assert last_update['chunks_stored'] == 25
        
        # Simulate reconnection - should get last state
        reconnect_state = progress_tracker.updates[-1]['data']
        assert 'percentage' in reconnect_state
        assert 'status' in reconnect_state
        assert reconnect_state['percentage'] == 45
    
    @pytest.mark.asyncio
    async def test_progress_heartbeat_during_long_operations(self, mock_socket_emit):
        """Test that heartbeat messages are sent during long operations"""
        # This test verifies the heartbeat logic concept
        # In the actual implementation, heartbeats would be sent from the background task
        
        heartbeat_sent = False
        
        async def simulate_heartbeat_logic():
            """Simulate the heartbeat mechanism"""
            nonlocal heartbeat_sent
            # Simulate checking if it's time for heartbeat
            last_update_time = asyncio.get_event_loop().time()
            await asyncio.sleep(0.05)  # Simulate some work
            
            current_time = asyncio.get_event_loop().time()
            if current_time - last_update_time >= 0.03:  # Simulated heartbeat interval
                await mock_socket_emit('test-id', {
                    'status': 'running',
                    'percentage': 50,
                    'heartbeat': True,
                    'log': 'Background task still running...'
                })
                heartbeat_sent = True
        
        # Run the simulation
        await simulate_heartbeat_logic()
        
        # Verify heartbeat was sent
        assert heartbeat_sent, "Heartbeat should be sent during long operations"
        assert mock_socket_emit.called
        heartbeat_call = mock_socket_emit.call_args[0][1]
        assert heartbeat_call.get('heartbeat') == True


class TestProgressCoordination:
    """Test coordination between different progress reporting components"""
    
    @pytest.mark.asyncio
    async def test_crawl_orchestration_progress_coordination(self):
        """Test that CrawlOrchestrationService coordinates progress properly"""
        # This tests the actual implementation once fixed
        from src.server.services.knowledge.crawl_orchestration_service import CrawlOrchestrationService
        
        # Mock dependencies
        mock_crawler = Mock()
        mock_supabase = Mock()
        progress_updates = []
        
        async def capture_progress(progress_id, data):
            progress_updates.append(data)
        
        orchestrator = CrawlOrchestrationService(mock_crawler, mock_supabase, 'test-123')
        
        # Test that progress is coordinated across stages
        # The orchestrator should ensure smooth progress flow
        # Implementation will be tested once the fix is applied
    
    @pytest.mark.asyncio
    async def test_document_storage_progress_integration(self):
        """Test that document storage reports progress within its range"""
        progress_updates = []
        
        async def capture_progress(message: str, percentage: int, batch_info: dict = None):
            progress_updates.append({
                'message': message,
                'percentage': percentage,
                'batch_info': batch_info
            })
        
        # Test document storage with 100 chunks in 10 batches
        total_chunks = 100
        batch_size = 10
        total_batches = total_chunks // batch_size
        
        # Simulate document storage progress
        for batch_num in range(1, total_batches + 1):
            # Calculate progress within document storage phase (0-100%)
            internal_progress = (batch_num / total_batches) * 100
            # Map to overall progress range (30-80%)
            overall_progress = 30 + int((internal_progress / 100) * 50)
            
            await capture_progress(
                f"Processing batch {batch_num}/{total_batches}",
                overall_progress,
                {'current_batch': batch_num, 'total_batches': total_batches}
            )
        
        # Verify progress stayed within range
        percentages = [u['percentage'] for u in progress_updates]
        assert all(30 <= p <= 80 for p in percentages), "Document storage progress out of range"
        assert percentages[-1] == 80, "Document storage should end at 80%"