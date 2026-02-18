import pytest
from httpx import AsyncClient

from app.config import settings

API = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": "new@example.com", "password": "securepass1", "full_name": "New User"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new@example.com"
    assert data["full_name"] == "New User"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {"email": "dup@example.com", "password": "securepass1", "full_name": "Dup User"}
    await client.post(f"{API}/auth/register", json=payload)
    resp = await client.post(f"{API}/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": "weak@example.com", "password": "short", "full_name": "Weak User"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post(
        f"{API}/auth/register",
        json={"email": "login@example.com", "password": "securepass1", "full_name": "Login User"},
    )
    resp = await client.post(
        f"{API}/auth/login",
        json={"email": "login@example.com", "password": "securepass1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        f"{API}/auth/register",
        json={"email": "wrong@example.com", "password": "securepass1", "full_name": "Wrong User"},
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
async def test_refresh_token(client: AsyncClient):
    await client.post(
        f"{API}/auth/register",
        json={"email": "refresh@example.com", "password": "securepass1", "full_name": "Refresh User"},
    )
    login_resp = await client.post(
        f"{API}/auth/login",
        json={"email": "refresh@example.com", "password": "securepass1"},
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
