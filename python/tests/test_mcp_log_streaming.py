import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import WebSocket


class TestMCPLogStreaming:
    """Test MCP server log streaming functionality."""
    
    @pytest.fixture
    def mock_mcp_manager(self):
        """Mock the MCP server manager."""
        with patch('src.api_wrapper.mcp_manager') as mock:
            mock.process = Mock()
            mock.process.stdout = Mock()
            mock.process.stderr = Mock()
            yield mock
    
    def test_websocket_endpoint_exists(self, test_client):
        """Test that WebSocket endpoint for logs exists."""
        # This should fail as endpoint doesn't exist yet
        with test_client.websocket_connect("/api/mcp/logs/stream") as websocket:
            data = websocket.receive_json()
            assert data is not None
    
    def test_get_historical_logs(self, test_client):
        """Test fetching historical logs."""
        response = test_client.get("/api/mcp/logs?limit=50")
        assert response.status_code == 200
        
        logs = response.json()
        assert isinstance(logs, list)
        assert len(logs) <= 50
        
        if logs:
            assert all(
                'timestamp' in log and 'level' in log and 'message' in log 
                for log in logs
            )
    
    def test_clear_logs(self, test_client):
        """Test clearing server logs."""
        response = test_client.delete("/api/mcp/logs")
        assert response.status_code == 200
        
        result = response.json()
        assert result['success'] is True
        assert 'message' in result
    
    @pytest.mark.asyncio
    async def test_websocket_streams_logs(self, test_app):
        """Test that WebSocket streams logs from the MCP process."""
        # Mock log lines
        mock_logs = [
            b'[INFO] Server starting...\n',
            b'[INFO] Loading configuration...\n',
            b'[INFO] Server ready\n'
        ]
        
        with patch('src.api_wrapper.mcp_manager') as mock_manager:
            # Setup mock process with stdout
            mock_process = Mock()
            mock_stdout = AsyncMock()
            mock_stdout.readline = AsyncMock(side_effect=mock_logs)
            mock_process.stdout = mock_stdout
            mock_manager.process = mock_process
            
            # Connect to WebSocket
            async with test_app.websocket("/api/mcp/logs/stream") as websocket:
                # Should receive the logs
                for expected_log in mock_logs:
                    data = await websocket.receive_json()
                    assert data['level'] == 'INFO'
                    assert expected_log.decode().strip() in data['message']
                    assert 'timestamp' in data
    
    @pytest.mark.asyncio
    async def test_websocket_handles_stderr(self, test_app):
        """Test that WebSocket also streams stderr logs."""
        mock_error = b'[ERROR] Connection failed\n'
        
        with patch('src.api_wrapper.mcp_manager') as mock_manager:
            # Setup mock process with stderr
            mock_process = Mock()
            mock_stdout = AsyncMock()
            mock_stdout.readline = AsyncMock(return_value=b'')
            mock_stderr = AsyncMock()
            mock_stderr.readline = AsyncMock(return_value=mock_error)
            
            mock_process.stdout = mock_stdout
            mock_process.stderr = mock_stderr
            mock_manager.process = mock_process
            
            async with test_app.websocket("/api/mcp/logs/stream") as websocket:
                data = await websocket.receive_json()
                assert data['level'] == 'ERROR'
                assert 'Connection failed' in data['message']
    
    @pytest.mark.asyncio
    async def test_websocket_handles_disconnection(self, test_app):
        """Test WebSocket handles client disconnection gracefully."""
        with patch('src.api_wrapper.mcp_manager') as mock_manager:
            mock_manager.process = Mock()
            
            async with test_app.websocket("/api/mcp/logs/stream") as websocket:
                # Close the connection
                await websocket.close()
                
                # Server should handle this gracefully
                # (This test ensures no unhandled exceptions)
    
    @pytest.mark.asyncio
    async def test_websocket_handles_process_termination(self, test_app):
        """Test WebSocket handles MCP process termination."""
        with patch('src.api_wrapper.mcp_manager') as mock_manager:
            mock_process = Mock()
            mock_stdout = AsyncMock()
            # Simulate process ending (readline returns empty)
            mock_stdout.readline = AsyncMock(return_value=b'')
            mock_process.stdout = mock_stdout
            mock_process.poll = Mock(return_value=0)  # Process has exited
            mock_manager.process = mock_process
            
            async with test_app.websocket("/api/mcp/logs/stream") as websocket:
                # Should receive a termination message
                data = await websocket.receive_json()
                assert data['level'] in ['INFO', 'WARNING']
                assert 'terminated' in data['message'].lower() or 'ended' in data['message'].lower()
    
    def test_log_buffer_management(self, test_client, mock_mcp_manager):
        """Test that server maintains a log buffer for historical logs."""
        # Start the server to generate logs
        mock_mcp_manager.logs = [
            f'[{i}] Log message {i}' for i in range(100)
        ]
        
        # Get logs with limit
        response = test_client.get("/api/mcp/logs?limit=10")
        assert response.status_code == 200
        
        logs = response.json()
        assert len(logs) == 10
        # Should return the most recent logs
        assert logs[0]['message'] == '[99] Log message 99'
        assert logs[9]['message'] == '[90] Log message 90'
    
    @pytest.mark.asyncio
    async def test_multiple_websocket_connections(self, test_app):
        """Test that multiple clients can connect to log stream."""
        with patch('src.api_wrapper.mcp_manager') as mock_manager:
            mock_process = Mock()
            mock_stdout = AsyncMock()
            mock_stdout.readline = AsyncMock(return_value=b'[INFO] Test log\n')
            mock_process.stdout = mock_stdout
            mock_manager.process = mock_process
            
            # Connect multiple clients
            async with test_app.websocket("/api/mcp/logs/stream") as ws1:
                async with test_app.websocket("/api/mcp/logs/stream") as ws2:
                    # Both should receive logs
                    data1 = await ws1.receive_json()
                    data2 = await ws2.receive_json()
                    
                    assert data1['message'] == data2['message']
                    assert 'Test log' in data1['message']
    
    def test_log_parsing(self):
        """Test log line parsing functionality."""
        from src.api_wrapper import parse_log_line
        
        # Test standard log formats
        test_cases = [
            ("[INFO] Server started", "INFO", "Server started"),
            ("[ERROR] Connection failed", "ERROR", "Connection failed"),
            ("[WARNING] Low memory", "WARNING", "Low memory"),
            ("[DEBUG] Processing request", "DEBUG", "Processing request"),
            ("Regular output without level", "INFO", "Regular output without level"),
            ("", "INFO", ""),  # Empty line
        ]
        
        for line, expected_level, expected_message in test_cases:
            level, message = parse_log_line(line)
            assert level == expected_level
            assert message == expected_message 