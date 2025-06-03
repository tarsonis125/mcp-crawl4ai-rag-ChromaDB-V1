import pytest

@pytest.mark.asyncio
async def test_mcp_status(client):
    response = await client.get('/api/mcp/status')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
