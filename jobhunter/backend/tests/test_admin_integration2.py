"""Integration tests for admin API routes — covering uncovered lines.

Targets:
  - update_user_plan: valid tier, invalid tier, user not found
  - get_api_costs: with user_id filter
  - clear_dossier_cache
  - waitlist management: list with status filter, invite not-found,
    batch > 50 IDs, batch with already-invited entries
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate import Candidate
from app.models.waitlist import WaitlistEntry
from app.utils.security import hash_password

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_email(prefix: str = "adm2") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.com"


async def _create_user(
    db: AsyncSession,
    email: str | None = None,
    full_name: str = "Test User",
    is_admin: bool = False,
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


async def _make_admin_headers(client: AsyncClient, db: AsyncSession) -> dict:
    admin = await _create_user(db, full_name="Adm2 Admin", is_admin=True)
    await db.flush()
    return await _login(client, admin.email)


async def _seed_waitlist_entry(
    db: AsyncSession,
    email: str | None = None,
    status: str = "pending",
) -> WaitlistEntry:
    entry = WaitlistEntry(
        email=email or f"wl2-{uuid.uuid4().hex[:8]}@example.com",
        source="landing_page",
        status=status,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# PATCH /admin/users/{id}/plan  — update_user_plan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_plan_valid_tier(client: AsyncClient, db_session: AsyncSession):
    """Changing a user's plan tier succeeds with a valid tier."""
    headers = await _make_admin_headers(client, db_session)
    target = await _create_user(db_session, full_name="Plan Target")

    resp = await client.patch(
        f"{API}/admin/users/{target.id}/plan",
        headers=headers,
        json={"plan_tier": "explorer"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(target.id)
    assert "email" in data


@pytest.mark.asyncio
async def test_update_plan_all_tiers(client: AsyncClient, db_session: AsyncSession):
    """All valid plan tiers should be accepted."""
    headers = await _make_admin_headers(client, db_session)
    target = await _create_user(db_session, full_name="All Tiers Target")

    for tier in ("free", "explorer", "hunter"):
        resp = await client.patch(
            f"{API}/admin/users/{target.id}/plan",
            headers=headers,
            json={"plan_tier": tier},
        )
        assert resp.status_code == 200, f"Tier {tier!r} should be accepted, got {resp.status_code}"


@pytest.mark.asyncio
async def test_update_plan_invalid_tier(client: AsyncClient, db_session: AsyncSession):
    """An invalid plan tier string returns 400."""
    headers = await _make_admin_headers(client, db_session)
    target = await _create_user(db_session, full_name="Invalid Tier Target")

    resp = await client.patch(
        f"{API}/admin/users/{target.id}/plan",
        headers=headers,
        json={"plan_tier": "ultraplan_xyz"},
    )
    assert resp.status_code == 400
    assert "Invalid plan tier" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_plan_user_not_found(client: AsyncClient, db_session: AsyncSession):
    """Updating plan for a non-existent user returns 404."""
    headers = await _make_admin_headers(client, db_session)

    resp = await client.patch(
        f"{API}/admin/users/{uuid.uuid4()}/plan",
        headers=headers,
        json={"plan_tier": "explorer"},
    )
    assert resp.status_code == 404
    assert "User not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_update_plan_requires_admin(client: AsyncClient, db_session: AsyncSession):
    """Non-admin users cannot update plans."""
    non_admin = await _create_user(db_session, full_name="Non Admin Update Plan")
    headers = await _login(client, non_admin.email)
    target = await _create_user(db_session, full_name="Plan Target2")

    resp = await client.patch(
        f"{API}/admin/users/{target.id}/plan",
        headers=headers,
        json={"plan_tier": "hunter"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /admin/api-costs — get_api_costs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_costs_empty_returns_list(client: AsyncClient, db_session: AsyncSession):
    """GET /admin/api-costs returns an empty list when there are no records."""
    headers = await _make_admin_headers(client, db_session)
    resp = await client.get(f"{API}/admin/api-costs", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_api_costs_with_user_id_filter(client: AsyncClient, db_session: AsyncSession):
    """GET /admin/api-costs?user_id=<uuid> filters by candidate."""
    headers = await _make_admin_headers(client, db_session)
    target = await _create_user(db_session, full_name="API Cost Target")

    resp = await client.get(
        f"{API}/admin/api-costs",
        headers=headers,
        params={"user_id": str(target.id)},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_api_costs_with_days_param(client: AsyncClient, db_session: AsyncSession):
    headers = await _make_admin_headers(client, db_session)
    resp = await client.get(f"{API}/admin/api-costs", headers=headers, params={"days": 14})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_costs_invalid_days_too_low(client: AsyncClient, db_session: AsyncSession):
    headers = await _make_admin_headers(client, db_session)
    resp = await client.get(f"{API}/admin/api-costs", headers=headers, params={"days": 0})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_costs_invalid_days_too_high(client: AsyncClient, db_session: AsyncSession):
    headers = await _make_admin_headers(client, db_session)
    resp = await client.get(f"{API}/admin/api-costs", headers=headers, params={"days": 91})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /admin/cache/dossier/{domain} — clear_dossier_cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_dossier_cache_returns_deleted_count(client: AsyncClient, db_session: AsyncSession):
    """DELETE /admin/cache/dossier/{domain} returns deleted count and domain."""
    headers = await _make_admin_headers(client, db_session)
    resp = await client.delete(
        f"{API}/admin/cache/dossier/somecompany.com",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "deleted" in data
    assert data["domain"] == "somecompany.com"


@pytest.mark.asyncio
async def test_clear_dossier_cache_requires_admin(client: AsyncClient, db_session: AsyncSession):
    non_admin = await _create_user(db_session, full_name="Dossier No Admin")
    headers = await _login(client, non_admin.email)
    resp = await client.delete(
        f"{API}/admin/cache/dossier/somecompany.com",
        headers=headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /admin/waitlist — list_waitlist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_waitlist_empty(client: AsyncClient, db_session: AsyncSession):
    headers = await _make_admin_headers(client, db_session)
    resp = await client.get(f"{API}/admin/waitlist", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_list_waitlist_with_entries(client: AsyncClient, db_session: AsyncSession):
    headers = await _make_admin_headers(client, db_session)
    entry = await _seed_waitlist_entry(db_session)

    resp = await client.get(f"{API}/admin/waitlist", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    emails = [e["email"] for e in data["entries"]]
    assert entry.email in emails


@pytest.mark.asyncio
async def test_list_waitlist_status_filter_pending(client: AsyncClient, db_session: AsyncSession):
    """?status=pending only returns pending entries."""
    headers = await _make_admin_headers(client, db_session)
    pending_entry = await _seed_waitlist_entry(db_session, status="pending")
    invited_entry = await _seed_waitlist_entry(db_session, status="invited")

    resp = await client.get(
        f"{API}/admin/waitlist",
        headers=headers,
        params={"status": "pending"},
    )
    assert resp.status_code == 200
    data = resp.json()
    emails = [e["email"] for e in data["entries"]]
    assert pending_entry.email in emails
    assert invited_entry.email not in emails


@pytest.mark.asyncio
async def test_list_waitlist_status_filter_invited(client: AsyncClient, db_session: AsyncSession):
    """?status=invited only returns invited entries."""
    headers = await _make_admin_headers(client, db_session)
    invited_entry = await _seed_waitlist_entry(db_session, status="invited")
    pending_entry = await _seed_waitlist_entry(db_session, status="pending")

    resp = await client.get(
        f"{API}/admin/waitlist",
        headers=headers,
        params={"status": "invited"},
    )
    assert resp.status_code == 200
    data = resp.json()
    emails = [e["email"] for e in data["entries"]]
    assert invited_entry.email in emails
    assert pending_entry.email not in emails


@pytest.mark.asyncio
async def test_list_waitlist_pagination(client: AsyncClient, db_session: AsyncSession):
    headers = await _make_admin_headers(client, db_session)
    for _ in range(5):
        await _seed_waitlist_entry(db_session)

    await db_session.flush()
    resp = await client.get(
        f"{API}/admin/waitlist",
        headers=headers,
        params={"skip": 0, "limit": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) <= 2


@pytest.mark.asyncio
async def test_list_waitlist_requires_admin(client: AsyncClient, db_session: AsyncSession):
    non_admin = await _create_user(db_session, full_name="WL No Admin")
    headers = await _login(client, non_admin.email)
    resp = await client.get(f"{API}/admin/waitlist", headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /admin/waitlist/{id}/invite — invite_waitlist_entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invite_entry_not_found(client: AsyncClient, db_session: AsyncSession, redis):
    """POST /admin/waitlist/99999/invite with missing entry returns 404."""
    headers = await _make_admin_headers(client, db_session)
    resp = await client.post(
        f"{API}/admin/waitlist/99999/invite",
        headers=headers,
    )
    assert resp.status_code == 404
    assert "Waitlist entry not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_invite_entry_success(client: AsyncClient, db_session: AsyncSession, redis):
    headers = await _make_admin_headers(client, db_session)
    entry = await _seed_waitlist_entry(db_session)
    await db_session.flush()

    resp = await client.post(
        f"{API}/admin/waitlist/{entry.id}/invite",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "code" in data
    assert data["email"] == entry.email


@pytest.mark.asyncio
async def test_invite_already_invited_is_idempotent(client: AsyncClient, db_session: AsyncSession, redis):
    """Inviting twice returns the same invite code."""
    headers = await _make_admin_headers(client, db_session)
    entry = await _seed_waitlist_entry(db_session)
    await db_session.flush()

    resp1 = await client.post(
        f"{API}/admin/waitlist/{entry.id}/invite",
        headers=headers,
    )
    assert resp1.status_code == 200
    code1 = resp1.json()["code"]

    resp2 = await client.post(
        f"{API}/admin/waitlist/{entry.id}/invite",
        headers=headers,
    )
    assert resp2.status_code == 200
    code2 = resp2.json()["code"]

    assert code1 == code2


# ---------------------------------------------------------------------------
# POST /admin/waitlist/invite-batch — invite_waitlist_batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_exceeds_50_returns_400(client: AsyncClient, db_session: AsyncSession, redis):
    """Batch with > 50 IDs returns 400."""
    headers = await _make_admin_headers(client, db_session)
    ids = list(range(1, 52))  # 51 IDs
    resp = await client.post(
        f"{API}/admin/waitlist/invite-batch",
        json={"ids": ids},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "cannot exceed 50" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_batch_invite_success(client: AsyncClient, db_session: AsyncSession, redis):
    """Batch invite of 3 new entries returns invited=3."""
    headers = await _make_admin_headers(client, db_session)
    entries = [await _seed_waitlist_entry(db_session) for _ in range(3)]
    await db_session.flush()

    ids = [e.id for e in entries]
    resp = await client.post(
        f"{API}/admin/waitlist/invite-batch",
        json={"ids": ids},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["invited"] == 3
    assert data["skipped"] == 0
    assert "daily_quota_remaining" in data


@pytest.mark.asyncio
async def test_batch_skips_already_invited(client: AsyncClient, db_session: AsyncSession, redis):
    """Batch invite skips entries that are already invited."""
    headers = await _make_admin_headers(client, db_session)
    new_entry = await _seed_waitlist_entry(db_session, status="pending")
    already_invited = await _seed_waitlist_entry(db_session, status="invited")
    await db_session.flush()

    resp = await client.post(
        f"{API}/admin/waitlist/invite-batch",
        json={"ids": [new_entry.id, already_invited.id]},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["invited"] == 1
    assert data["skipped"] == 1


@pytest.mark.asyncio
async def test_batch_skips_nonexistent_ids(client: AsyncClient, db_session: AsyncSession, redis):
    """Batch invite skips IDs that don't exist and records errors."""
    headers = await _make_admin_headers(client, db_session)
    entry = await _seed_waitlist_entry(db_session)
    await db_session.flush()

    resp = await client.post(
        f"{API}/admin/waitlist/invite-batch",
        json={"ids": [entry.id, 999999]},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["invited"] == 1
    assert data["skipped"] == 1
    assert any("not found" in e.lower() for e in data["errors"])
