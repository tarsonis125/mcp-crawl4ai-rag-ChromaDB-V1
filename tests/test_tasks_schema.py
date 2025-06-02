import pytest, uuid

@pytest.mark.asyncio
async def test_tasks_table_missing(client):
    random_id = uuid.uuid4()
    response = await client.get(f'/tasks/by_project/{random_id}')
    # Expect 500 if table doesn't exist
    assert response.status_code == 500
