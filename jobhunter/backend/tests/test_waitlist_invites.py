import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate import Candidate
from app.models.waitlist import WaitlistEntry
from app.services.invite_service import create_system_invite
from app.utils.security import hash_password

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------

async def _create_admin(db: AsyncSession) -> Candidate:
    admin = Candidate(
        id=uuid.uuid4(),
        email=f"admin-wl-{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("testpass123"),
        full_name="Admin Waitlist",
        is_admin=True,
    )
    db.add(admin)
    await db.flush()
    return admin


async def _login(client: AsyncClient, email: str, password: str = "testpass123") -> dict:
    resp = await client.post(
        f"{API}/auth/login",
        json={"email": email, "password": password},
    )
    tokens = resp.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _seed_waitlist_entry(db: AsyncSession, email: str | None = None, status: str = "pending") -> WaitlistEntry:
    entry = WaitlistEntry(
        email=email or f"wl-{uuid.uuid4().hex[:8]}@example.com",
        source="landing_page",
        status=status,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> Candidate:
    return await _create_admin(db_session)


@pytest_asyncio.fixture
async def authenticated_admin_client(client: AsyncClient, admin_user: Candidate) -> tuple[AsyncClient, dict]:
    headers = await _login(client, admin_user.email)
    return client, headers


# ---------------------------------------------------------------------------
# Original test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_system_invite(db_session):
    """System invite has no invited_by and stores email."""
    invite = await create_system_invite(db_session, "test@example.com")

    assert invite.code is not None
    assert len(invite.code) > 0
    assert invite.invited_by_id is None
    assert invite.email == "test@example.com"
    assert invite.is_used is False
    assert invite.expires_at > datetime.now(UTC)


# ---------------------------------------------------------------------------
# Admin waitlist API tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_list_waitlist(
    authenticated_admin_client: tuple[AsyncClient, dict],
    db_session: AsyncSession,
):
    """GET /admin/waitlist returns seeded entry with 200."""
    client, headers = authenticated_admin_client
    entry = await _seed_waitlist_entry(db_session)
    await db_session.commit()

    resp = await client.get(f"{API}/admin/waitlist", headers=headers)
    assert resp.status_code == 200

    data = resp.json()
    assert "entries" in data
    assert "total" in data
    emails = [e["email"] for e in data["entries"]]
    assert entry.email in emails


@pytest.mark.asyncio
async def test_admin_invite_waitlist_entry(
    authenticated_admin_client: tuple[AsyncClient, dict],
    db_session: AsyncSession,
    redis,
):
    """POST /admin/waitlist/{id}/invite returns code and marks entry as invited."""
    client, headers = authenticated_admin_client
    entry = await _seed_waitlist_entry(db_session)
    await db_session.commit()

    resp = await client.post(f"{API}/admin/waitlist/{entry.id}/invite", headers=headers)
    assert resp.status_code == 200

    data = resp.json()
    assert "code" in data
    assert data["email"] == entry.email
    assert "expires_at" in data

    # Reload entry from DB and verify status updated
    await db_session.refresh(entry)
    assert entry.status == "invited"
    assert entry.invited_at is not None


@pytest.mark.asyncio
async def test_admin_invite_idempotent(
    authenticated_admin_client: tuple[AsyncClient, dict],
    db_session: AsyncSession,
    redis,
):
    """Inviting the same entry twice returns the same invite code."""
    client, headers = authenticated_admin_client
    entry = await _seed_waitlist_entry(db_session)
    await db_session.commit()

    resp1 = await client.post(f"{API}/admin/waitlist/{entry.id}/invite", headers=headers)
    assert resp1.status_code == 200
    code1 = resp1.json()["code"]

    resp2 = await client.post(f"{API}/admin/waitlist/{entry.id}/invite", headers=headers)
    assert resp2.status_code == 200
    code2 = resp2.json()["code"]

    assert code1 == code2


@pytest.mark.asyncio
async def test_admin_invite_batch(
    authenticated_admin_client: tuple[AsyncClient, dict],
    db_session: AsyncSession,
    redis,
):
    """POST /admin/waitlist/invite-batch invites 3 entries and returns invited=3."""
    client, headers = authenticated_admin_client
    entries = [await _seed_waitlist_entry(db_session) for _ in range(3)]
    await db_session.commit()

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
    assert data["failed"] == 0
    assert "daily_quota_remaining" in data


@pytest.mark.asyncio
async def test_admin_invite_quota_exceeded(
    authenticated_admin_client: tuple[AsyncClient, dict],
    db_session: AsyncSession,
    redis,
):
    """When Redis daily quota is exhausted, invite returns 429 with Retry-After header."""
    from datetime import UTC

    client, headers = authenticated_admin_client
    entry = await _seed_waitlist_entry(db_session)
    await db_session.commit()

    # Exhaust the quota
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    quota_key = f"admin:daily_invites:{today}"
    await redis.set(quota_key, settings.MAX_DAILY_INVITES)

    resp = await client.post(f"{API}/admin/waitlist/{entry.id}/invite", headers=headers)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


@pytest.mark.asyncio
async def test_registration_updates_waitlist_status(db_session):
    """Registering with an invite code updates the matching waitlist entry to 'registered'."""
    from app.models.waitlist import WaitlistEntry
    from app.schemas.auth import RegisterRequest
    from app.services.auth_service import register
    from app.services.invite_service import create_system_invite

    entry = WaitlistEntry(email="hook@example.com", source="landing", status="invited")
    db_session.add(entry)
    await db_session.flush()

    invite = await create_system_invite(db_session, "hook@example.com")
    entry.invite_code_id = invite.id
    await db_session.commit()

    req = RegisterRequest(
        email="hook@example.com",
        password="testpass123",
        full_name="Test User",
        invite_code=invite.code,
    )
    candidate = await register(db_session, req)
    assert candidate is not None

    await db_session.refresh(entry)
    assert entry.status == "registered"
