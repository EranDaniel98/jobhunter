"""Unit tests for app/dependencies.py covering get_db, get_admin_db,
singleton client getters, and get_current_candidate edge cases."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.dependencies as deps
from app.dependencies import (
    get_admin_db,
    get_current_candidate,
    get_db,
    get_email_client,
    get_hunter,
    get_newsapi,
    get_openai,
)

# ---------------------------------------------------------------------------
# get_db / get_admin_db
# ---------------------------------------------------------------------------


class TestGetDb:
    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        """get_db is an async generator that yields a session."""
        mock_session = AsyncMock()

        async def _fake_get_session():
            yield mock_session

        with patch("app.dependencies.get_session", return_value=_fake_get_session()):
            sessions = []
            async for s in get_db():
                sessions.append(s)

        assert len(sessions) == 1
        assert sessions[0] is mock_session

    @pytest.mark.asyncio
    async def test_get_admin_db_yields_session(self):
        """get_admin_db yields a regular session (admin bypasses RLS via TenantMiddleware skip)."""
        mock_session = MagicMock()

        async def _fake_get_session():
            yield mock_session

        with patch("app.dependencies.get_session", return_value=_fake_get_session()):
            sessions = []
            async for s in get_admin_db():
                sessions.append(s)

        assert len(sessions) == 1
        assert sessions[0] is mock_session


# ---------------------------------------------------------------------------
# Singleton client getters
# ---------------------------------------------------------------------------


class TestSingletonGetters:
    def setup_method(self):
        """Reset all singletons before each test."""
        deps._openai_client = None
        deps._hunter_client = None
        deps._email_client = None
        deps._newsapi_client = None

    def test_get_openai_initializes_on_first_call(self):
        """get_openai() creates an OpenAIClient on first call."""
        mock_client = MagicMock()
        with patch("app.infrastructure.openai_client.OpenAIClient", return_value=mock_client):
            result = get_openai()
        assert result is mock_client
        assert deps._openai_client is mock_client

    def test_get_openai_returns_cached_on_second_call(self):
        """get_openai() returns the same instance on subsequent calls."""
        mock_client = MagicMock()
        deps._openai_client = mock_client

        result = get_openai()
        assert result is mock_client

    def test_get_hunter_initializes_on_first_call(self):
        """get_hunter() creates a HunterClient on first call."""
        mock_client = MagicMock()
        with patch("app.infrastructure.hunter_client.HunterClient", return_value=mock_client):
            result = get_hunter()
        assert result is mock_client
        assert deps._hunter_client is mock_client

    def test_get_hunter_returns_cached(self):
        """get_hunter() returns cached instance."""
        mock_client = MagicMock()
        deps._hunter_client = mock_client
        assert get_hunter() is mock_client

    def test_get_newsapi_initializes_on_first_call(self):
        """get_newsapi() creates a NewsAPIClient on first call."""
        mock_client = MagicMock()
        with patch("app.infrastructure.newsapi_client.NewsAPIClient", return_value=mock_client):
            result = get_newsapi()
        assert result is mock_client
        assert deps._newsapi_client is mock_client

    def test_get_newsapi_returns_cached(self):
        """get_newsapi() returns cached instance."""
        mock_client = MagicMock()
        deps._newsapi_client = mock_client
        assert get_newsapi() is mock_client

    def test_get_email_client_initializes_on_first_call(self):
        """get_email_client() creates a ResendClient on first call."""
        mock_client = MagicMock()
        with patch("app.infrastructure.resend_client.ResendClient", return_value=mock_client):
            result = get_email_client()
        assert result is mock_client
        assert deps._email_client is mock_client

    def test_get_email_client_returns_cached(self):
        """get_email_client() returns cached instance."""
        mock_client = MagicMock()
        deps._email_client = mock_client
        assert get_email_client() is mock_client


# ---------------------------------------------------------------------------
# get_current_candidate
# ---------------------------------------------------------------------------


class TestGetCurrentCandidate:
    def _make_credentials(self, token="valid.token"):
        creds = MagicMock()
        creds.credentials = token
        return creds

    def _make_db(self, candidate):
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = candidate
        db.execute.return_value = result
        return db

    @pytest.mark.asyncio
    async def test_invalid_jwt_raises_401(self):
        """Malformed token raises 401."""
        from jwt import PyJWTError

        creds = self._make_credentials("bad.token")
        db = AsyncMock()

        with (
            patch("app.dependencies.decode_token", side_effect=PyJWTError("bad")),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_current_candidate(creds, db)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_non_access_token_type_raises_401(self):
        """Refresh token type is rejected with 401."""
        creds = self._make_credentials()
        db = AsyncMock()

        with (
            patch("app.dependencies.decode_token", return_value={"type": "refresh", "sub": str(uuid.uuid4())}),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_current_candidate(creds, db)

        assert exc_info.value.status_code == 401
        assert "Invalid token type" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_blacklist_check_redis_failure_raises_503(self):
        """Redis failure during blacklist check raises 503."""
        jti = str(uuid.uuid4())
        creds = self._make_credentials()
        db = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis down")

        with (
            patch(
                "app.dependencies.decode_token", return_value={"type": "access", "sub": str(uuid.uuid4()), "jti": jti}
            ),
            patch("app.dependencies.get_redis", return_value=mock_redis),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_current_candidate(creds, db)

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_blacklisted_token_raises_401(self):
        """Blacklisted JTI raises 401 Token has been revoked."""
        jti = str(uuid.uuid4())
        creds = self._make_credentials()
        db = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"1"

        with (
            patch(
                "app.dependencies.decode_token", return_value={"type": "access", "sub": str(uuid.uuid4()), "jti": jti}
            ),
            patch("app.dependencies.get_redis", return_value=mock_redis),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_current_candidate(creds, db)

        assert exc_info.value.status_code == 401
        assert "revoked" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_missing_sub_raises_401(self):
        """Token payload without 'sub' raises 401."""
        creds = self._make_credentials()
        db = AsyncMock()

        with (
            patch("app.dependencies.decode_token", return_value={"type": "access"}),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_current_candidate(creds, db)

        assert exc_info.value.status_code == 401
        assert "Invalid token payload" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_candidate_not_found_raises_401(self):
        """Valid token but candidate missing in DB raises 401."""
        creds = self._make_credentials()
        db = self._make_db(None)

        with (
            patch("app.dependencies.decode_token", return_value={"type": "access", "sub": str(uuid.uuid4())}),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_current_candidate(creds, db)

        assert exc_info.value.status_code == 401
        assert "Candidate not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_token_returns_candidate(self):
        """Valid token with existing candidate returns the candidate."""
        candidate = MagicMock()
        candidate.id = uuid.uuid4()
        candidate_id = str(candidate.id)

        creds = self._make_credentials()
        db = self._make_db(candidate)

        with patch("app.dependencies.decode_token", return_value={"type": "access", "sub": candidate_id}):
            result = await get_current_candidate(creds, db)

        assert result is candidate

    @pytest.mark.asyncio
    async def test_no_jti_skips_blacklist_check(self):
        """Token without jti field skips blacklist check entirely."""
        candidate = MagicMock()
        candidate_id = str(uuid.uuid4())
        creds = self._make_credentials()
        db = self._make_db(candidate)

        mock_redis = AsyncMock()

        with (
            patch("app.dependencies.decode_token", return_value={"type": "access", "sub": candidate_id}),
            patch("app.dependencies.get_redis", return_value=mock_redis),
        ):
            result = await get_current_candidate(creds, db)

        mock_redis.get.assert_not_called()
        assert result is candidate
