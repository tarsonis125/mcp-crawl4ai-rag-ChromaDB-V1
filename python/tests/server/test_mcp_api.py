import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_mcp_status(async_client):
    response = await async_client.get('/api/mcp/status')
    assert response.status_code == 200
    assert 'status' in response.json()


@pytest.mark.asyncio
async def test_start_server_endpoint(async_client):
    with patch('src.server.fastapi.mcp_api.mcp_manager.start_server', new=AsyncMock(return_value={'success': True, 'status': 'running', 'message': 'ok', 'pid': 1})) as mock_start:
        resp = await async_client.post('/api/mcp/start')
        assert resp.status_code == 200
        assert resp.json()['status'] == 'running'
        mock_start.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_server_endpoint(async_client):
    with patch('src.server.fastapi.mcp_api.mcp_manager.stop_server', new=AsyncMock(return_value={'success': True, 'status': 'stopped', 'message': 'stopped'})) as mock_stop:
        resp = await async_client.post('/api/mcp/stop')
        assert resp.status_code == 200
        assert resp.json()['status'] == 'stopped'
        mock_stop.assert_awaited_once()
