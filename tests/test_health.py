import pytest

@pytest.mark.asyncio
async def test_docs_endpoint(client):
    response = await client.get('/docs')
    assert response.status_code == 200

