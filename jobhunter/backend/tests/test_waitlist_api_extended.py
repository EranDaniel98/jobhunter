"""Extended tests for the public waitlist signup endpoint."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.waitlist import WaitlistEntry

API = settings.API_V1_PREFIX


# ── POST /waitlist ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_join_waitlist_success(client: AsyncClient, db_session: AsyncSession):
    """POST /waitlist adds a new email and returns welcome message."""
    email = f"newuser-{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(f"{API}/waitlist", json={"email": email})
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    assert "waitlist" in data["message"].lower()

    # Verify entry was created in DB
    result = await db_session.execute(select(WaitlistEntry).where(WaitlistEntry.email == email))
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.email == email
    assert entry.source == "landing_page"


@pytest.mark.asyncio
async def test_join_waitlist_custom_source(client: AsyncClient, db_session: AsyncSession):
    """POST /waitlist with custom source stores it correctly."""
    email = f"sourceduser-{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(f"{API}/waitlist", json={"email": email, "source": "twitter_ad"})
    assert resp.status_code == 200

    result = await db_session.execute(select(WaitlistEntry).where(WaitlistEntry.email == email))
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.source == "twitter_ad"


@pytest.mark.asyncio
async def test_join_waitlist_duplicate_email(client: AsyncClient, db_session: AsyncSession):
    """POST /waitlist with duplicate email returns already-on-waitlist message."""
    email = f"dup-{uuid.uuid4().hex[:8]}@example.com"

    # First signup
    resp1 = await client.post(f"{API}/waitlist", json={"email": email})
    assert resp1.status_code == 200
    assert "added" in resp1.json()["message"].lower() or "waitlist" in resp1.json()["message"].lower()

    # Second signup with same email
    resp2 = await client.post(f"{API}/waitlist", json={"email": email})
    assert resp2.status_code == 200
    assert "already" in resp2.json()["message"].lower()


@pytest.mark.asyncio
async def test_join_waitlist_invalid_email(client: AsyncClient):
    """POST /waitlist with invalid email format returns 422."""
    resp = await client.post(f"{API}/waitlist", json={"email": "not-an-email"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_join_waitlist_missing_email(client: AsyncClient):
    """POST /waitlist with no email field returns 422."""
    resp = await client.post(f"{API}/waitlist", json={"source": "landing_page"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_join_waitlist_default_source(client: AsyncClient, db_session: AsyncSession):
    """POST /waitlist without source defaults to 'landing_page'."""
    email = f"nosource-{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(f"{API}/waitlist", json={"email": email})
    assert resp.status_code == 200

    result = await db_session.execute(select(WaitlistEntry).where(WaitlistEntry.email == email))
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.source == "landing_page"


@pytest.mark.asyncio
async def test_join_waitlist_sets_pending_status(client: AsyncClient, db_session: AsyncSession):
    """POST /waitlist creates entry with status=pending."""
    email = f"pendingtest-{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(f"{API}/waitlist", json={"email": email})
    assert resp.status_code == 200

    result = await db_session.execute(select(WaitlistEntry).where(WaitlistEntry.email == email))
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.status == "pending"


@pytest.mark.asyncio
async def test_join_waitlist_response_shape(client: AsyncClient):
    """POST /waitlist response has 'message' field."""
    email = f"shape-{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(f"{API}/waitlist", json={"email": email})
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    assert isinstance(data["message"], str)
    assert len(data["message"]) > 0
