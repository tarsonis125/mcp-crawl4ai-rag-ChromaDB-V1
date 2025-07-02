import pytest

@pytest.mark.asyncio
async def test_root_endpoint(async_client):
    response = await async_client.get('/')
    assert response.status_code == 200
    data = response.json()
    assert data['name'] == 'Archon Knowledge Engine API'
    assert data['status'] == 'healthy'

@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    response = await async_client.get('/health')
    assert response.status_code == 200
    status = response.json()['status']
    # Health can be 'initializing' or 'healthy' depending on service state
    assert status in ['initializing', 'healthy', 'degraded']
