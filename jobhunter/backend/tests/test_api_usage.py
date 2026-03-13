"""Tests for per-user API cost tracking endpoints (/me/api-usage, /admin/api-costs)."""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.billing import ApiUsageRecord
from app.models.candidate import Candidate
from app.utils.security import hash_password

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers — matches test_admin.py pattern (direct DB insert + login)
# ---------------------------------------------------------------------------


def _unique_email(prefix: str = "usage") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.local"


async def _create_user(
    db: AsyncSession,
    *,
    full_name: str = "Test User",
    is_admin: bool = False,
    email: str | None = None,
) -> Candidate:
    candidate = Candidate(
        id=uuid.uuid4(),
        email=email or _unique_email(),
        password_hash=hash_password("testpass123"),
        full_name=full_name,
        is_admin=is_admin,
    )
    db.add(candidate)
    await db.flush()
    return candidate


async def _login(client: AsyncClient, email: str) -> dict:
    resp = await client.post(
        f"{API}/auth/login",
        json={"email": email, "password": "testpass123"},
    )
    tokens = resp.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _seed_usage(
    db: AsyncSession, candidate_id: uuid.UUID, count: int = 3
) -> None:
    """Insert sample API usage records."""
    for i in range(count):
        record = ApiUsageRecord(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            service="openai",
            model="gpt-4o",
            tokens_in=1000 + i * 100,
            tokens_out=500 + i * 50,
            estimated_cost_cents=10 + i,
            endpoint=f"/api/v1/test/endpoint-{i}",
        )
        db.add(record)
    await db.flush()


# ---------------------------------------------------------------------------
# /me/api-usage
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def user_with_usage(db_session: AsyncSession, client: AsyncClient):
    """Create a user with seeded API usage records."""
    user = await _create_user(db_session, full_name="Usage User")
    await _seed_usage(db_session, user.id, count=5)
    await db_session.commit()
    headers = await _login(client, user.email)
    return user, headers


@pytest.mark.asyncio
async def test_get_my_api_usage(client: AsyncClient, user_with_usage):
    """Authenticated user can see their own usage records."""
    _user, headers = user_with_usage
    resp = await client.get(f"{API}/auth/me/api-usage", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data
    assert "total" in data
    assert data["total"] == 5
    assert len(data["records"]) == 5

    # Verify record structure
    record = data["records"][0]
    assert "id" in record
    assert "service" in record
    assert "model" in record
    assert "tokens_in" in record
    assert "tokens_out" in record
    assert "estimated_cost_cents" in record
    assert "endpoint" in record
    assert "created_at" in record


@pytest.mark.asyncio
async def test_get_my_api_usage_pagination(client: AsyncClient, user_with_usage):
    """Pagination with skip/limit works correctly."""
    _, headers = user_with_usage
    resp = await client.get(
        f"{API}/auth/me/api-usage?skip=2&limit=2", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["records"]) == 2
    assert data["total"] == 5  # Total count unchanged


@pytest.mark.asyncio
async def test_get_my_api_usage_empty(client: AsyncClient, auth_headers: dict):
    """User with no usage records gets empty list."""
    resp = await client.get(f"{API}/auth/me/api-usage", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["records"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_my_api_usage_unauthenticated(client: AsyncClient):
    """Unauthenticated request should return 401."""
    resp = await client.get(f"{API}/auth/me/api-usage")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_my_api_usage_isolation(
    client: AsyncClient, db_session: AsyncSession
):
    """User A cannot see user B's usage records."""
    user_a = await _create_user(db_session, full_name="User A")
    user_b = await _create_user(db_session, full_name="User B")
    await _seed_usage(db_session, user_a.id, count=3)
    await _seed_usage(db_session, user_b.id, count=7)
    await db_session.commit()

    headers_a = await _login(client, user_a.email)
    resp = await client.get(f"{API}/auth/me/api-usage", headers=headers_a)
    assert resp.status_code == 200
    assert resp.json()["total"] == 3

    headers_b = await _login(client, user_b.email)
    resp = await client.get(f"{API}/auth/me/api-usage", headers=headers_b)
    assert resp.status_code == 200
    assert resp.json()["total"] == 7


# ---------------------------------------------------------------------------
# /admin/api-costs
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def admin_with_costs(db_session: AsyncSession, client: AsyncClient):
    """Create an admin and some users with usage records."""
    admin = await _create_user(db_session, full_name="Admin", is_admin=True)
    user1 = await _create_user(db_session, full_name="User 1")
    user2 = await _create_user(db_session, full_name="User 2")
    await _seed_usage(db_session, user1.id, count=3)
    await _seed_usage(db_session, user2.id, count=5)
    await db_session.commit()
    admin_headers = await _login(client, admin.email)
    return admin, admin_headers, user1, user2


@pytest.mark.asyncio
async def test_admin_api_costs(client: AsyncClient, admin_with_costs):
    """Admin can see aggregated API costs."""
    _, headers, _, _ = admin_with_costs
    resp = await client.get(f"{API}/admin/api-costs", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2  # Two users with usage

    entry = data[0]
    assert "candidate_id" in entry
    assert "total_tokens_in" in entry
    assert "total_tokens_out" in entry
    assert "total_cost_cents" in entry
    assert "request_count" in entry


@pytest.mark.asyncio
async def test_admin_api_costs_filter_by_user(client: AsyncClient, admin_with_costs):
    """Admin can filter costs by specific user_id."""
    _, headers, user1, _ = admin_with_costs
    resp = await client.get(
        f"{API}/admin/api-costs?user_id={user1.id}", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["candidate_id"] == str(user1.id)
    assert data[0]["request_count"] == 3


@pytest.mark.asyncio
async def test_admin_api_costs_days_filter(client: AsyncClient, admin_with_costs):
    """Days parameter should filter by time range."""
    _, headers, _, _ = admin_with_costs
    resp = await client.get(f"{API}/admin/api-costs?days=1", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_admin_api_costs_days_validation(client: AsyncClient, admin_with_costs):
    """Days parameter should be validated (1-90)."""
    _, headers, _, _ = admin_with_costs
    resp = await client.get(f"{API}/admin/api-costs?days=0", headers=headers)
    assert resp.status_code == 422

    resp = await client.get(f"{API}/admin/api-costs?days=91", headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_admin_api_costs_non_admin_rejected(
    client: AsyncClient, db_session: AsyncSession
):
    """Non-admin users should be rejected with 403."""
    user = await _create_user(db_session, full_name="Regular", is_admin=False)
    await db_session.commit()
    headers = await _login(client, user.email)
    resp = await client.get(f"{API}/admin/api-costs", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_api_costs_unauthenticated(client: AsyncClient):
    """Unauthenticated requests should return 401."""
    resp = await client.get(f"{API}/admin/api-costs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_api_costs_ordered_by_cost(client: AsyncClient, admin_with_costs):
    """Results should be ordered by total cost descending."""
    _, headers, _user1, _user2 = admin_with_costs
    resp = await client.get(f"{API}/admin/api-costs", headers=headers)
    data = resp.json()
    if len(data) >= 2:
        assert data[0]["total_cost_cents"] >= data[1]["total_cost_cents"]
