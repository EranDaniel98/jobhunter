"""API endpoint tests for password reset flow (forgot-password, reset-password)."""

import uuid

import pytest
from httpx import AsyncClient

from app.config import settings
from app.utils.security import create_access_token, create_reset_token

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Forgot Password endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forgot_password_returns_200_for_valid_email(client: AsyncClient, auth_headers: dict):
    """POST /forgot-password should always return 200 (no email enumeration)."""
    # Get the registered user's email
    me = await client.get(f"{API}/auth/me", headers=auth_headers)
    email = me.json()["email"]

    resp = await client.post(f"{API}/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200
    assert "reset link" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_forgot_password_returns_200_for_unknown_email(client: AsyncClient):
    """POST /forgot-password returns 200 even for non-existent emails (no enumeration)."""
    resp = await client.post(
        f"{API}/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )
    assert resp.status_code == 200
    assert "reset link" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_forgot_password_rejects_invalid_email(client: AsyncClient):
    """POST /forgot-password should reject malformed email with 422."""
    resp = await client.post(f"{API}/auth/forgot-password", json={"email": "not-an-email"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_forgot_password_rejects_empty_body(client: AsyncClient):
    """POST /forgot-password with no body should return 422."""
    resp = await client.post(f"{API}/auth/forgot-password", json={})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Reset Password endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_password_success(client: AsyncClient, auth_headers: dict):
    """Valid reset token should allow password change, and user can login with new password."""
    # Get user info
    me = await client.get(f"{API}/auth/me", headers=auth_headers)
    user_data = me.json()
    candidate_id = user_data["id"]
    email = user_data["email"]

    # Generate a reset token
    token = create_reset_token(candidate_id)

    # Reset password
    resp = await client.post(
        f"{API}/auth/reset-password",
        json={"token": token, "new_password": "NewSecurePass1"},
    )
    assert resp.status_code == 200
    assert "reset successfully" in resp.json()["message"].lower()

    # Verify can login with new password
    login_resp = await client.post(
        f"{API}/auth/login",
        json={"email": email, "password": "NewSecurePass1"},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client: AsyncClient):
    """Invalid JWT token should return 400."""
    resp = await client.post(
        f"{API}/auth/reset-password",
        json={"token": "invalid.jwt.token", "new_password": "NewSecurePass1"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_wrong_token_type(client: AsyncClient):
    """Access token (not reset token) should be rejected with 400."""
    access_token, _ = create_access_token(str(uuid.uuid4()))
    resp = await client.post(
        f"{API}/auth/reset-password",
        json={"token": access_token, "new_password": "NewSecurePass1"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_nonexistent_user(client: AsyncClient):
    """Reset token for a deleted/nonexistent user should return 400."""
    fake_id = str(uuid.uuid4())
    token = create_reset_token(fake_id)
    resp = await client.post(
        f"{API}/auth/reset-password",
        json={"token": token, "new_password": "NewSecurePass1"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_short_password(client: AsyncClient, auth_headers: dict):
    """Too short password should be rejected by schema validation (422)."""
    me = await client.get(f"{API}/auth/me", headers=auth_headers)
    token = create_reset_token(me.json()["id"])
    resp = await client.post(
        f"{API}/auth/reset-password",
        json={"token": token, "new_password": "short"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reset_password_missing_token(client: AsyncClient):
    """Missing token field should return 422."""
    resp = await client.post(
        f"{API}/auth/reset-password",
        json={"new_password": "NewSecurePass1"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_old_password_no_longer_works_after_reset(client: AsyncClient, auth_headers: dict):
    """After password reset, old password should not work."""
    me = await client.get(f"{API}/auth/me", headers=auth_headers)
    user_data = me.json()

    token = create_reset_token(user_data["id"])
    await client.post(
        f"{API}/auth/reset-password",
        json={"token": token, "new_password": "BrandNewPass1"},
    )

    # Old password should fail
    resp = await client.post(
        f"{API}/auth/login",
        json={"email": user_data["email"], "password": "testpass123"},
    )
    assert resp.status_code == 401
