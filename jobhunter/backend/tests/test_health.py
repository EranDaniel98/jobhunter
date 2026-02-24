import pytest
from httpx import AsyncClient

from app.config import settings

API = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_health_returns_migration_version(client: AsyncClient):
    resp = await client.get(f"{API}/health")
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "migration_version" in data["checks"]
