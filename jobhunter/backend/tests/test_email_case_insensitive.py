"""Email case-insensitive login / register / forgot-password."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate import Candidate

API = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_register_stores_email_lowercased(
    client: AsyncClient, db_session: AsyncSession, invite_code: str
):
    mixed = f"MiXeDcAsE-{uuid.uuid4().hex[:6]}@Example.COM"
    resp = await client.post(
        f"{API}/auth/register",
        json={
            "email": mixed,
            "password": "Regpass1",
            "full_name": "Case User",
            "invite_code": invite_code,
        },
    )
    assert resp.status_code in (200, 201)

    candidate = (
        await db_session.execute(select(Candidate).where(Candidate.email == mixed.lower()))
    ).scalar_one_or_none()
    assert candidate is not None


@pytest.mark.asyncio
async def test_login_accepts_any_case(
    client: AsyncClient, db_session: AsyncSession, invite_code: str
):
    email = f"login-{uuid.uuid4().hex[:6]}@example.com"
    password = "Loginpass1"
    await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "full_name": "L", "invite_code": invite_code},
    )

    resp = await client.post(
        f"{API}/auth/login",
        json={"email": email.upper(), "password": password},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_duplicate_registration_case_insensitive(
    client: AsyncClient, invite_code: str, db_session: AsyncSession
):
    from tests.conftest import _create_invite_code

    email = f"dup-{uuid.uuid4().hex[:6]}@example.com"
    first = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "Dup1pass", "full_name": "Dup", "invite_code": invite_code},
    )
    assert first.status_code in (200, 201)

    code2 = await _create_invite_code(db_session)
    second = await client.post(
        f"{API}/auth/register",
        json={"email": email.upper(), "password": "Dup1pass", "full_name": "Dup", "invite_code": code2},
    )
    assert second.status_code == 409
