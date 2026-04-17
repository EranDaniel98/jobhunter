"""Token revocation on password change (#103).

A token issued before the candidate's last password change must be rejected.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate import Candidate
from app.utils.security import create_reset_token

API = settings.API_V1_PREFIX


@pytest.mark.asyncio
async def test_old_token_rejected_after_password_changed_at_advances(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    # Before: valid token works.
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    candidate_id = uuid.UUID(resp.json()["id"])

    # Simulate a password change that happened AFTER this token was issued.
    candidate = (
        await db_session.execute(select(Candidate).where(Candidate.id == candidate_id))
    ).scalar_one()
    candidate.password_changed_at = datetime.now(UTC) + timedelta(hours=1)
    await db_session.commit()

    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    assert resp.status_code == 401
    assert "revoked" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_token_issued_after_password_reset_still_works(
    client: AsyncClient, auth_headers: dict
):
    # Get the candidate.
    me = await client.get(f"{API}/auth/me", headers=auth_headers)
    user = me.json()

    # Reset password via reset token flow.
    reset_token = create_reset_token(user["id"])
    resp = await client.post(
        f"{API}/auth/reset-password",
        json={"token": reset_token, "new_password": "FreshPass1"},
    )
    assert resp.status_code == 200

    # Login with new password — token issued AFTER password_changed_at.
    login = await client.post(
        f"{API}/auth/login",
        json={"email": user["email"], "password": "FreshPass1"},
    )
    assert login.status_code == 200
    new_token = login.json()["access_token"]

    resp = await client.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {new_token}"}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_register_sets_password_changed_at(
    client: AsyncClient, db_session: AsyncSession, invite_code: str
):
    email = f"reg-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "Regpass1",
            "full_name": "Reg User",
            "invite_code": invite_code,
        },
    )
    candidate = (
        await db_session.execute(select(Candidate).where(Candidate.email == email))
    ).scalar_one()
    assert candidate.password_changed_at is not None


@pytest.mark.asyncio
async def test_change_password_advances_password_changed_at(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    me = await client.get(f"{API}/auth/me", headers=auth_headers)
    candidate_id = uuid.UUID(me.json()["id"])

    before = (
        await db_session.execute(select(Candidate).where(Candidate.id == candidate_id))
    ).scalar_one()
    before_ts = before.password_changed_at

    resp = await client.post(
        f"{API}/auth/me/password",
        headers=auth_headers,
        json={"current_password": "Testpass123", "new_password": "Updatedpass1"},
    )
    assert resp.status_code == 204

    db_session.expire_all()
    after = (
        await db_session.execute(select(Candidate).where(Candidate.id == candidate_id))
    ).scalar_one()
    assert after.password_changed_at is not None
    if before_ts is not None:
        assert after.password_changed_at >= before_ts
