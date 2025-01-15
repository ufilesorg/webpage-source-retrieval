import httpx
import pytest
from server.config import Settings


@pytest.mark.asyncio
async def test_health(client: httpx.AsyncClient, settings: Settings):
    """Test the /api/v1/health endpoint."""
    response = await client.get(f"{settings.base_path}/health")
    assert response.status_code == 200
    assert response.json().get("status") == "up"
