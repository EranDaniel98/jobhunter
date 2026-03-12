"""Tests for per-user API cost tracking endpoints (/me/api-usage, /admin/api-costs)."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.billing import ApiUsageRecord
from app.models.candidate import Candidate
from app.models.invite import InviteCode
from app.utils.security import hash_password

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_invite(db: AsyncSession) -> str:
    """Create an invite code for registration."""
    # Ensure seed inviter exists
    result = await db.execute(
        select(Candidate).where(Candidate.email == "seed-inviter-usage@test.local")
    )
    inviter = result.scalar_one_or_none()
    if not inviter:
        inviter = Candidate(
            id=uuid.uuid4(),
            email="seed-inviter-usage@test.local",
            password_hash=hash_password("testpass123"),
            full_name="Seed Inviter",
        )
        db.add(inviter)
        await db.flush()

    code = secrets.token_urlsafe(8)
    invite = InviteCode(
        id=uuid.uuid4(),
        code=code,
        invited_by_id=inviter.id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(invite)
    await db.flush()
    return code


async def _register_and_login(
    client: AsyncClient,
    db: AsyncSession,
    *,
    full_name: str = "Test User",
    is_admin: bool = False,
) -> tuple[Candidate, dict]:
    """Register a user via the API and return (candidate, auth_headers)."""
    code = await _create_invite(db)
    await db.commit()
    email = f"{uuid.uuid4().hex[:8]}@test.local"
    password = "testpass123"

    await client.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "invite_code": code,
        },
    )

    # If admin, update directly in DB
    if is_admin:
        result = await db.execute(select(Candidate).where(Candidate.email == email))
        candidate = result.scalar_one()
        candidate.is_admin = True
        await db.commit()
    else:
        result = await db.execute(select(Candidate).where(Candidate.email == email))
        candidate = result.scalar_one()

    resp = await client.post(
        f"{API}/auth/login", json={"email": email, "password": password}
    )
    tokens = resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return candidate, headers


async def _seed_usage(db: AsyncSession, candidate_id: uuid.UUID, count: int = 3) -> None:
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
    user, headers = await _register_and_login(
        client, db_session, full_name="Usage User"
    )
    await _seed_usage(db_session, user.id, count=5)
    await db_session.commit()
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
    resp = await client.get(f"{API}/auth/me/api-usage?skip=2&limit=2", headers=headers)
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
    user_a, headers_a = await _register_and_login(
        client, db_session, full_name="User A"
    )
    user_b, headers_b = await _register_and_login(
        client, db_session, full_name="User B"
    )
    await _seed_usage(db_session, user_a.id, count=3)
    await _seed_usage(db_session, user_b.id, count=7)
    await db_session.commit()

    resp = await client.get(f"{API}/auth/me/api-usage", headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3  # Only user A's records

    resp = await client.get(f"{API}/auth/me/api-usage", headers=headers_b)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 7  # Only user B's records


# ---------------------------------------------------------------------------
# /admin/api-costs
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def admin_with_costs(db_session: AsyncSession, client: AsyncClient):
    """Create an admin and some users with usage records."""
    admin, admin_headers = await _register_and_login(
        client, db_session, full_name="Admin", is_admin=True
    )
    user1, _ = await _register_and_login(client, db_session, full_name="User 1")
    user2, _ = await _register_and_login(client, db_session, full_name="User 2")
    await _seed_usage(db_session, user1.id, count=3)
    await _seed_usage(db_session, user2.id, count=5)
    await db_session.commit()
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

    # Verify response structure
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
    resp = await client.get(f"{API}/admin/api-costs?user_id={user1.id}", headers=headers)
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
    # All records were just created, so they should all appear within 1 day
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
    _, headers = await _register_and_login(
        client, db_session, full_name="Regular", is_admin=False
    )
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
