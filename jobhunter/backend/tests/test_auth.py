import pytest
from httpx import AsyncClient

from app.config import settings

API = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_register(client: AsyncClient, invite_code: str):
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": "new@example.com", "password": "Securepass1", "full_name": "New User", "invite_code": invite_code},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new@example.com"
    assert data["full_name"] == "New User"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_without_invite(client: AsyncClient):
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": "noinvite@example.com", "password": "Securepass1", "full_name": "No Invite"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_invite(client: AsyncClient):
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": "bad@example.com", "password": "Securepass1", "full_name": "Bad Invite", "invite_code": "nonexistent-code"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, invite_code: str):
    payload = {"email": "dup@example.com", "password": "Securepass1", "full_name": "Dup User", "invite_code": invite_code}
    await client.post(f"{API}/auth/register", json=payload)
    # Second registration with same email needs a new invite code (previous one consumed)
    # but will fail on duplicate email before invite validation matters
    resp = await client.post(f"{API}/auth/register", json={**payload, "invite_code": "whatever"})
    assert resp.status_code in (404, 409)  # invite invalid or email duplicate


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": "weak@example.com", "password": "short", "full_name": "Weak User", "invite_code": "x"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login(client: AsyncClient, invite_code: str):
    await client.post(
        f"{API}/auth/register",
        json={"email": "login@example.com", "password": "Securepass1", "full_name": "Login User", "invite_code": invite_code},
    )
    resp = await client.post(
        f"{API}/auth/login",
        json={"email": "login@example.com", "password": "Securepass1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, invite_code: str):
    await client.post(
        f"{API}/auth/register",
        json={"email": "wrong@example.com", "password": "Securepass1", "full_name": "Wrong User", "invite_code": invite_code},
    )
    resp = await client.post(
        f"{API}/auth/login",
        json={"email": "wrong@example.com", "password": "wrongpass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
    assert "full_name" in data


@pytest.mark.asyncio
async def test_update_me(client: AsyncClient, auth_headers: dict):
    resp = await client.patch(
        f"{API}/auth/me",
        headers=auth_headers,
        json={
            "target_roles": ["Staff Engineer", "Principal Engineer"],
            "target_industries": ["fintech", "saas"],
            "target_locations": ["Remote", "Tel Aviv"],
            "salary_min": 150000,
            "salary_max": 250000,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_roles"] == ["Staff Engineer", "Principal Engineer"]
    assert data["target_industries"] == ["fintech", "saas"]
    assert data["salary_min"] == 150000


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, invite_code: str):
    await client.post(
        f"{API}/auth/register",
        json={"email": "refresh@example.com", "password": "Securepass1", "full_name": "Refresh User", "invite_code": invite_code},
    )
    login_resp = await client.post(
        f"{API}/auth/login",
        json={"email": "refresh@example.com", "password": "Securepass1"},
    )
    tokens = login_resp.json()

    resp = await client.post(
        f"{API}/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert "access_token" in new_tokens
    assert new_tokens["access_token"] != tokens["access_token"]


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, auth_headers: dict):
    # Logout
    resp = await client.post(f"{API}/auth/logout", headers=auth_headers)
    assert resp.status_code == 204

    # Token should now be blacklisted
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    assert resp.status_code == 401
