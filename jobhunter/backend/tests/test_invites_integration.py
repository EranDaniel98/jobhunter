"""Integration tests for invites API endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

API = settings.API_V1_PREFIX


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_candidate_id(client: AsyncClient, auth_headers: dict) -> uuid.UUID:
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    return uuid.UUID(resp.json()["id"])


# ── POST /invites ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_invite(client: AsyncClient, auth_headers: dict):
    """POST /invites creates an invite code and returns URL."""
    resp = await client.post(f"{API}/invites", headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "code" in data
    assert "invite_url" in data
    assert "expires_at" in data
    assert len(data["code"]) > 0
    assert data["code"] in data["invite_url"]


@pytest.mark.asyncio
async def test_create_invite_url_format(client: AsyncClient, auth_headers: dict):
    """Invite URL should contain the code as a query parameter."""
    resp = await client.post(f"{API}/invites", headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "invite=" in data["invite_url"]


# ── GET /invites ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_invites_empty(client: AsyncClient, auth_headers: dict):
    """GET /invites returns empty list when no invites created yet."""
    resp = await client.get(f"{API}/invites", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_invites_returns_created(client: AsyncClient, auth_headers: dict):
    """GET /invites returns invite codes created by the user."""
    # Create two invites
    await client.post(f"{API}/invites", headers=auth_headers)
    await client.post(f"{API}/invites", headers=auth_headers)

    resp = await client.get(f"{API}/invites", headers=auth_headers)
    assert resp.status_code == 200
    invites = resp.json()
    assert len(invites) >= 2


@pytest.mark.asyncio
async def test_list_invites_shape(client: AsyncClient, auth_headers: dict):
    """Each invite item has the expected fields."""
    await client.post(f"{API}/invites", headers=auth_headers)

    resp = await client.get(f"{API}/invites", headers=auth_headers)
    assert resp.status_code == 200
    invites = resp.json()
    assert len(invites) >= 1
    invite = invites[0]
    for field in ("id", "code", "is_used", "expires_at", "created_at"):
        assert field in invite, f"Missing field: {field}"
    assert invite["is_used"] is False
    assert invite["used_by_email"] is None


@pytest.mark.asyncio
async def test_list_invites_tenant_scoped(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """User A's invites are not visible to User B."""
    # Create invite as User A
    await client.post(f"{API}/invites", headers=auth_headers)

    # Register and login as User B
    from tests.conftest import _create_invite_code

    code_b = await _create_invite_code(db_session)
    email_b = f"inviteb-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        f"{API}/auth/register",
        json={"email": email_b, "password": "Testpass123", "full_name": "Invite B", "invite_code": code_b},
    )
    login_b = await client.post(f"{API}/auth/login", json={"email": email_b, "password": "Testpass123"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    resp_b = await client.get(f"{API}/invites", headers=headers_b)
    assert resp_b.status_code == 200
    # User B has no invites
    assert resp_b.json() == []


# ── GET /invites/{code}/validate ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_invite_valid(client: AsyncClient, auth_headers: dict):
    """GET /invites/{code}/validate returns valid=True for a fresh invite."""
    create_resp = await client.post(f"{API}/invites", headers=auth_headers)
    code = create_resp.json()["code"]

    resp = await client.get(f"{API}/invites/{code}/validate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert "invited_by_name" in data


@pytest.mark.asyncio
async def test_validate_invite_invalid_code(client: AsyncClient):
    """GET /invites/{bad}/validate returns 404 for unknown code."""
    resp = await client.get(f"{API}/invites/totally-fake-code-xyz/validate")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_validate_invite_invited_by_name(client: AsyncClient, auth_headers: dict):
    """The validate response contains the inviter's full name."""
    create_resp = await client.post(f"{API}/invites", headers=auth_headers)
    code = create_resp.json()["code"]

    resp = await client.get(f"{API}/invites/{code}/validate")
    assert resp.status_code == 200
    data = resp.json()
    # invited_by_name should be the registering user's full_name (e.g. "Test User")
    assert data["invited_by_name"] is not None
    assert len(data["invited_by_name"]) > 0


@pytest.mark.asyncio
async def test_validate_used_invite(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """After an invite is consumed during registration, validating it returns 400/410."""
    create_resp = await client.post(f"{API}/invites", headers=auth_headers)
    code = create_resp.json()["code"]

    # Consume the invite by registering a new user
    await client.post(
        f"{API}/auth/register",
        json={
            "email": f"consumer-{uuid.uuid4().hex[:8]}@example.com",
            "password": "Testpass123",
            "full_name": "Consumer",
            "invite_code": code,
        },
    )

    # Now the invite is used — validate should fail
    resp = await client.get(f"{API}/invites/{code}/validate")
    assert resp.status_code in (400, 410)
