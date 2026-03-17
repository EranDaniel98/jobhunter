"""Tests for candidate profile endpoints (GET /me, PATCH /me, POST /me/password, email verification)."""
import uuid

import pytest
from httpx import AsyncClient

from app.config import settings
from app.utils.security import create_verification_token

API = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_get_profile_unauthenticated(client: AsyncClient):
    """GET /me without auth returns 401."""
    resp = await client.get(f"{API}/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_profile_returns_all_fields(client: AsyncClient, auth_headers: dict):
    """GET /me returns expected profile fields."""
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    for key in ("id", "email", "full_name", "is_admin", "email_verified", "plan_tier"):
        assert key in data, f"Missing field: {key}"
    assert data["plan_tier"] == "free"
    assert data["is_admin"] is False


@pytest.mark.asyncio
async def test_update_profile_headline_and_location(client: AsyncClient, auth_headers: dict):
    """PATCH /me can update headline and location."""
    resp = await client.patch(
        f"{API}/auth/me",
        headers=auth_headers,
        json={"headline": "Senior Backend Engineer", "location": "Tel Aviv, Israel"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["headline"] == "Senior Backend Engineer"
    assert data["location"] == "Tel Aviv, Israel"


@pytest.mark.asyncio
async def test_update_profile_preferences(client: AsyncClient, auth_headers: dict):
    """PATCH /me can update nested preferences object."""
    resp = await client.patch(
        f"{API}/auth/me",
        headers=auth_headers,
        json={"preferences": {"email_notifications": False, "theme": "dark", "language": "en"}},
    )
    assert resp.status_code == 200
    prefs = resp.json()["preferences"]
    assert prefs["email_notifications"] is False
    assert prefs["theme"] == "dark"


@pytest.mark.asyncio
async def test_update_profile_partial_no_overwrite(client: AsyncClient, auth_headers: dict):
    """PATCH /me with partial data does not null out other fields."""
    # Set initial values
    await client.patch(
        f"{API}/auth/me",
        headers=auth_headers,
        json={"headline": "Engineer", "salary_min": 100000, "salary_max": 200000},
    )
    # Update only headline
    resp = await client.patch(
        f"{API}/auth/me",
        headers=auth_headers,
        json={"headline": "Staff Engineer"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["headline"] == "Staff Engineer"
    assert data["salary_min"] == 100000  # unchanged


@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient, invite_code: str):
    """POST /me/password with correct current password succeeds."""
    email = f"pwchange-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "oldpass123", "full_name": "PW User", "invite_code": invite_code},
    )
    login_resp = await client.post(f"{API}/auth/login", json={"email": email, "password": "oldpass123"})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    resp = await client.post(
        f"{API}/auth/me/password",
        headers=headers,
        json={"current_password": "oldpass123", "new_password": "newpass456"},
    )
    assert resp.status_code == 204

    # Verify new password works
    login_resp2 = await client.post(f"{API}/auth/login", json={"email": email, "password": "newpass456"})
    assert login_resp2.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(client: AsyncClient, auth_headers: dict):
    """POST /me/password with wrong current password returns 400."""
    resp = await client.post(
        f"{API}/auth/me/password",
        headers=auth_headers,
        json={"current_password": "wrongcurrent", "new_password": "newpass456"},
    )
    assert resp.status_code == 400
    assert "incorrect" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_email_valid_token(client: AsyncClient, auth_headers: dict):
    """POST /verify with valid verification token sets email_verified=true."""
    me_resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    candidate_id = me_resp.json()["id"]

    token = create_verification_token(candidate_id)
    resp = await client.post(f"{API}/auth/verify", params={"token": token})
    assert resp.status_code == 200
    assert resp.json()["message"] == "Email verified successfully"


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client: AsyncClient):
    """POST /verify with garbage token returns 400."""
    resp = await client.post(f"{API}/auth/verify", params={"token": "not-a-real-token"})
    assert resp.status_code == 400
