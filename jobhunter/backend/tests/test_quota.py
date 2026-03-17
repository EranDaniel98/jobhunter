from datetime import UTC

import pytest
from httpx import AsyncClient

from app.config import settings
from app.infrastructure.redis_client import get_redis

API = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_usage_endpoint_returns_all_quotas(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"{API}/candidates/me/usage", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "plan_tier" in data
    assert "quotas" in data
    for key in ("hunter", "discovery", "research", "email"):
        assert key in data["quotas"]
        assert "used" in data["quotas"][key]
        assert "limit" in data["quotas"][key]
        assert data["quotas"][key]["used"] == 0


@pytest.mark.asyncio
async def test_quota_enforced_returns_429(client: AsyncClient, auth_headers: dict, db_session):
    """When Redis counter is at the limit, next discover call returns 429."""
    from tests.conftest import seed_candidate_dna
    await seed_candidate_dna(db_session, client, auth_headers)

    # Get candidate ID
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    candidate_id = resp.json()["id"]

    # Set the discovery counter to the free plan limit (3)
    from datetime import datetime
    redis = get_redis()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    key = f"quota:{candidate_id}:discovery:{today}"
    await redis.set(key, "3")

    # Next discover call should be rejected (429 from either quota or rate limiter)
    resp = await client.post(f"{API}/companies/discover", headers=auth_headers)
    assert resp.status_code == 429


def test_discovery_rate_limit_is_2_per_hour():
    """Verify the rate-limit decorator is set to 2/hour (aligned with free tier quota)."""
    import inspect

    from app.api import companies

    source = inspect.getsource(companies)
    # The decorator should be @limiter.limit("2/hour"), aligned with daily quota
    assert '"2/hour"' in source or "'2/hour'" in source, (
        "discover endpoint should have 2/hour rate limit"
    )
    assert "1000/hour" not in source, (
        "discover endpoint still has debug 1000/hour rate limit"
    )
