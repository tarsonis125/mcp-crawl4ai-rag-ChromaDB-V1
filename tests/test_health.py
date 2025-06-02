import pytest

@pytest.mark.asyncio
async def test_docs_endpoint(async_client):
    response = await async_client.get('/docs')
    assert response.status_code == 200

