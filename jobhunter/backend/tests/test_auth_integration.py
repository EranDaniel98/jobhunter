"""Integration tests for auth API endpoints — covers uncovered lines in app/api/auth.py."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

API = settings.API_V1_PREFIX


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _register_and_login(client: AsyncClient, db_session: AsyncSession) -> tuple[str, str, str, str]:
    """Register a fresh user and return (email, password, access_token, refresh_token)."""
    from tests.conftest import _create_invite_code

    code = await _create_invite_code(db_session)
    email = f"authtest-{uuid.uuid4().hex[:8]}@example.com"
    password = "testpass123"
    await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "full_name": "Auth Test User", "invite_code": code},
    )
    resp = await client.post(f"{API}/auth/login", json={"email": email, "password": password})
    tokens = resp.json()
    return email, password, tokens["access_token"], tokens["refresh_token"]


# ── POST /auth/refresh ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """A valid refresh token returns new access + refresh tokens."""
    _, _, _, refresh_token = await _register_and_login(client, db_session)

    resp = await client.post(
        f"{API}/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_refresh_token_invalid(client: AsyncClient):
    """An invalid refresh token returns 401."""
    resp = await client.post(
        f"{API}/auth/refresh",
        json={"refresh_token": "not.a.valid.token"},
    )
    assert resp.status_code == 401


# ── POST /auth/logout ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_logout_blacklists_access_token(client: AsyncClient, auth_headers: dict):
    """After logout the access token is no longer valid."""
    # Confirm token works before logout
    pre = await client.get(f"{API}/auth/me", headers=auth_headers)
    assert pre.status_code == 200

    resp = await client.post(f"{API}/auth/logout", headers=auth_headers)
    assert resp.status_code == 204

    # Token should now be blacklisted
    post = await client.get(f"{API}/auth/me", headers=auth_headers)
    assert post.status_code == 401


@pytest.mark.asyncio
async def test_logout_with_refresh_token(client: AsyncClient, db_session: AsyncSession):
    """Logout with refresh_token body also succeeds (204)."""
    _, _, access, refresh = await _register_and_login(client, db_session)
    headers = {"Authorization": f"Bearer {access}"}

    resp = await client.post(
        f"{API}/auth/logout",
        headers=headers,
        json={"refresh_token": refresh},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_logout_no_token_is_204(client: AsyncClient):
    """Logout without any Authorization header should return 204 (no-op)."""
    resp = await client.post(f"{API}/auth/logout")
    assert resp.status_code == 204


# ── PATCH /auth/me — update profile ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_profile_full_name(client: AsyncClient, auth_headers: dict):
    resp = await client.patch(
        f"{API}/auth/me",
        headers=auth_headers,
        json={"full_name": "Updated Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_profile_preferences(client: AsyncClient, auth_headers: dict):
    resp = await client.patch(
        f"{API}/auth/me",
        headers=auth_headers,
        json={"preferences": {"email_notifications": False}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["preferences"]["email_notifications"] is False


@pytest.mark.asyncio
async def test_update_profile_multiple_fields(client: AsyncClient, auth_headers: dict):
    resp = await client.patch(
        f"{API}/auth/me",
        headers=auth_headers,
        json={
            "full_name": "Multi Update",
            "headline": "Senior Engineer",
            "location": "Tel Aviv",
            "target_roles": ["Staff Engineer"],
            "salary_min": 200000,
            "salary_max": 300000,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["full_name"] == "Multi Update"
    assert data["headline"] == "Senior Engineer"
    assert data["location"] == "Tel Aviv"
    assert data["salary_min"] == 200000


# ── POST /auth/me/password — change password ──────────────────────────────────


@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient, db_session: AsyncSession):
    _, password, access, _ = await _register_and_login(client, db_session)
    headers = {"Authorization": f"Bearer {access}"}

    resp = await client.post(
        f"{API}/auth/me/password",
        headers=headers,
        json={"current_password": password, "new_password": "newpass456"},
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_change_password_wrong_current(client: AsyncClient, db_session: AsyncSession):
    _, _, access, _ = await _register_and_login(client, db_session)
    headers = {"Authorization": f"Bearer {access}"}

    resp = await client.post(
        f"{API}/auth/me/password",
        headers=headers,
        json={"current_password": "wrongpassword", "new_password": "newpass456"},
    )
    assert resp.status_code == 400
    assert "incorrect" in resp.json()["detail"].lower()


# ── POST /auth/complete-onboarding ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_onboarding(client: AsyncClient, auth_headers: dict):
    resp = await client.post(f"{API}/auth/complete-onboarding", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["onboarding_completed"] is True
    assert data["onboarding_completed_at"] is not None


@pytest.mark.asyncio
async def test_complete_onboarding_idempotent(client: AsyncClient, auth_headers: dict):
    """Calling complete-onboarding twice should succeed both times."""
    resp1 = await client.post(f"{API}/auth/complete-onboarding", headers=auth_headers)
    resp2 = await client.post(f"{API}/auth/complete-onboarding", headers=auth_headers)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    # Timestamp should remain the same after second call
    assert resp1.json()["onboarding_completed_at"] == resp2.json()["onboarding_completed_at"]


# ── POST /auth/complete-tour ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_tour(client: AsyncClient, auth_headers: dict):
    resp = await client.post(f"{API}/auth/complete-tour", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tour_completed"] is True
    assert data["tour_completed_at"] is not None


@pytest.mark.asyncio
async def test_complete_tour_idempotent(client: AsyncClient, auth_headers: dict):
    resp1 = await client.post(f"{API}/auth/complete-tour", headers=auth_headers)
    resp2 = await client.post(f"{API}/auth/complete-tour", headers=auth_headers)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["tour_completed_at"] == resp2.json()["tour_completed_at"]


# ── POST /auth/resend-verification ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resend_verification_unverified(client: AsyncClient, auth_headers: dict):
    """Resending verification for an unverified account returns 200."""
    resp = await client.post(f"{API}/auth/resend-verification", headers=auth_headers)
    # Either sent (200) or already verified (200)
    assert resp.status_code == 200
    assert "message" in resp.json()


@pytest.mark.asyncio
async def test_resend_verification_already_verified(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """If the account is already verified, returns a friendly 200 message."""
    # Mark the candidate as verified
    from sqlalchemy import update

    from app.models.candidate import Candidate

    me = await client.get(f"{API}/auth/me", headers=auth_headers)
    candidate_id = uuid.UUID(me.json()["id"])
    await db_session.execute(update(Candidate).where(Candidate.id == candidate_id).values(email_verified=True))
    await db_session.commit()

    resp = await client.post(f"{API}/auth/resend-verification", headers=auth_headers)
    assert resp.status_code == 200
    assert "already verified" in resp.json()["message"].lower()


# ── GET /auth/me/api-usage ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_api_usage_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"{API}/auth/me/api-usage", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data
    assert "total" in data
    assert data["records"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_api_usage_pagination(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"{API}/auth/me/api-usage?skip=0&limit=5", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data
    assert isinstance(data["records"], list)


# ── POST /auth/verify ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client: AsyncClient):
    resp = await client.post(f"{API}/auth/verify?token=not.a.valid.token")
    assert resp.status_code == 400
    assert "invalid" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_email_wrong_type(client: AsyncClient, db_session: AsyncSession):
    """Token with wrong type (not 'verify') should return 400."""

    _, _, access, _ = await _register_and_login(client, db_session)
    # Access token has type 'access', not 'verify'
    resp = await client.post(f"{API}/auth/verify?token={access}")
    assert resp.status_code == 400
