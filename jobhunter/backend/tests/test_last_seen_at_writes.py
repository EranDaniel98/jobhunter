"""Verify login + refresh update candidate.last_seen_at."""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.candidate import Candidate
from app.schemas.auth import LoginRequest
from app.services import auth_service
from app.utils.security import create_refresh_token, hash_password


async def _seed_candidate(db_session, *, email: str, password: str = "correctpass"):
    cand = Candidate(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(password),
        full_name="Test User",
        is_active=True,
        email_verified=True,
    )
    db_session.add(cand)
    await db_session.commit()
    return cand


@pytest.mark.asyncio
async def test_login_sets_last_seen_at(db_session):
    cand = await _seed_candidate(db_session, email=f"login-{uuid.uuid4()}@t.co")
    assert cand.last_seen_at is None

    await auth_service.login(db_session, LoginRequest(email=cand.email, password="correctpass"))

    refreshed = (await db_session.execute(
        select(Candidate).where(Candidate.id == cand.id)
    )).scalar_one()
    assert refreshed.last_seen_at is not None
    assert (datetime.now(UTC) - refreshed.last_seen_at) < timedelta(seconds=5)


@pytest.mark.asyncio
async def test_refresh_updates_last_seen_at(db_session):
    cand = await _seed_candidate(db_session, email=f"refresh-{uuid.uuid4()}@t.co")
    assert cand.last_seen_at is None

    token, _ = create_refresh_token(str(cand.id))
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.setex = AsyncMock()

    with patch("app.services.auth_service.get_redis", return_value=mock_redis):
        await auth_service.refresh_token(db_session, token)

    refreshed = (await db_session.execute(
        select(Candidate).where(Candidate.id == cand.id)
    )).scalar_one()
    assert refreshed.last_seen_at is not None
    assert (datetime.now(UTC) - refreshed.last_seen_at) < timedelta(seconds=5)
