import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.redis_client import get_redis
from app.models.candidate import Candidate

API = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_list_plans_returns_three_plans(client: AsyncClient):
    """GET /plans is public (no auth) and returns 3 plans without openai."""
    resp = await client.get(f"{API}/plans")
    assert resp.status_code == 200
    plans = resp.json()
    assert len(plans) == 3

    tiers = {p["tier"] for p in plans}
    assert tiers == {"free", "explorer", "hunter"}

    # openai should not be in any plan's limits
    for plan in plans:
        assert "openai" not in plan["limits"]
        assert "discovery" in plan["limits"]
        assert "email" in plan["limits"]


@pytest.mark.asyncio
async def test_usage_returns_new_shape_with_plan_tier(client: AsyncClient, auth_headers: dict):
    """GET /candidates/me/usage returns plan_tier and quotas dict."""
    resp = await client.get(f"{API}/candidates/me/usage", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "plan_tier" in data
    assert data["plan_tier"] == "free"
    assert "quotas" in data

    for key in ("discovery", "research", "hunter", "email"):
        assert key in data["quotas"]
        assert "used" in data["quotas"][key]
        assert "limit" in data["quotas"][key]
        assert data["quotas"][key]["used"] == 0

    # openai should NOT be in user-facing quotas
    assert "openai" not in data["quotas"]


@pytest.mark.asyncio
async def test_quota_uses_tier_specific_limits(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Free plan has discovery limit of 3. Verify usage reflects this."""
    resp = await client.get(f"{API}/candidates/me/usage", headers=auth_headers)
    data = resp.json()
    assert data["quotas"]["discovery"]["limit"] == 3


@pytest.mark.asyncio
async def test_429_response_is_structured_json(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """When quota is exceeded, the quota service returns structured JSON.

    Note: The /companies/discover endpoint also has a slowapi rate limiter (3/hour)
    which may return a plain-text 429 before the quota check runs. This test calls
    the quota service directly to verify the structured response.
    """
    from app.services.quota_service import check_and_increment
    from fastapi import HTTPException

    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    candidate_id = resp.json()["id"]

    # Set the discovery counter to the free limit (3)
    from datetime import datetime, timezone
    redis = get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"quota:{candidate_id}:discovery:{today}"
    await redis.set(key, "3")

    # Directly call quota service to verify the structured 429
    import pytest as _pytest
    with _pytest.raises(HTTPException) as exc_info:
        await check_and_increment(candidate_id, "discovery", "free")

    assert exc_info.value.status_code == 429
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["quota_type"] == "discovery"
    assert detail["limit"] == 3
    assert detail["plan_tier"] == "free"
    assert "resets_at" in detail


@pytest.mark.asyncio
async def test_me_endpoint_includes_plan_tier(client: AsyncClient, auth_headers: dict):
    """GET /auth/me should include plan_tier in response."""
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "plan_tier" in data
    assert data["plan_tier"] == "free"


@pytest.mark.asyncio
async def test_admin_can_change_user_plan(client: AsyncClient, db_session: AsyncSession, auth_headers: dict):
    """Admin can PATCH /admin/users/{id}/plan to change a user's tier."""
    # Get the current user id
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    user_id = resp.json()["id"]

    # Make the user an admin
    result = await db_session.execute(select(Candidate).where(Candidate.id == uuid.UUID(user_id)))
    candidate = result.scalar_one()
    candidate.is_admin = True
    await db_session.commit()

    # Change own plan to explorer
    resp = await client.patch(
        f"{API}/admin/users/{user_id}/plan",
        headers=auth_headers,
        json={"plan_tier": "explorer"},
    )
    assert resp.status_code == 200

    # Verify usage now reflects explorer limits
    # Note: admin users always see hunter-tier limits in usage (generous caps for admins)
    resp = await client.get(f"{API}/candidates/me/usage", headers=auth_headers)
    data = resp.json()
    assert data["plan_tier"] == "explorer"
    assert data["quotas"]["discovery"]["limit"] == 50


@pytest.mark.asyncio
async def test_admin_rejects_invalid_plan_tier(client: AsyncClient, db_session: AsyncSession, auth_headers: dict):
    """Admin PATCH with invalid tier returns 400."""
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    user_id = resp.json()["id"]

    result = await db_session.execute(select(Candidate).where(Candidate.id == uuid.UUID(user_id)))
    candidate = result.scalar_one()
    candidate.is_admin = True
    await db_session.commit()

    resp = await client.patch(
        f"{API}/admin/users/{user_id}/plan",
        headers=auth_headers,
        json={"plan_tier": "mega_plan"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_billing_stubs_return_coming_soon(client: AsyncClient, auth_headers: dict):
    """Billing endpoints return coming_soon status."""
    resp = await client.post(
        f"{API}/billing/create-checkout-session",
        headers=auth_headers,
        json={"tier": "explorer"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "coming_soon"

    resp = await client.get(f"{API}/billing/portal", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "coming_soon"
