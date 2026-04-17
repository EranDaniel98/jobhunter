"""Full coverage tests for auth_service - fills gaps in test_auth_service_unit.py.

Does NOT overlap with test_auth_service_unit.py which already covers:
- Password hashing / verify_password
- JWT creation and decoding
- login (happy path + bad password + inactive account)
- forgot_password (unknown email, email send failure)
- reset_password (invalid token, wrong type, candidate not found, success)
- refresh_token (invalid token, wrong type, blacklisted)
- logout (success)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scalar(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


# ---------------------------------------------------------------------------
# register - verification email failure (line 34, 96-97)
# ---------------------------------------------------------------------------


class TestRegisterVerificationEmail:
    @pytest.mark.asyncio
    async def test_register_raises_409_on_duplicate_email(self):
        """register raises HTTP 409 when email is already taken."""
        from app.schemas.auth import RegisterRequest
        from app.services.auth_service import register

        existing = MagicMock()
        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(existing)

        data = RegisterRequest(
            email="dup@example.com",
            password="Password123",
            full_name="Dup User",
            invite_code="INVITE123",
        )

        with pytest.raises(HTTPException) as exc_info:
            await register(mock_db, data)

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_register_succeeds_even_when_verification_email_fails(self):
        """Verification email failure should not prevent registration from succeeding."""
        from app.models.candidate import Candidate
        from app.schemas.auth import RegisterRequest
        from app.services.auth_service import register

        candidate_obj = MagicMock(spec=Candidate)
        candidate_obj.id = uuid.uuid4()
        candidate_obj.email = "new@example.com"
        candidate_obj.full_name = "New User"
        candidate_obj.is_active = True

        mock_db = AsyncMock()
        # First execute: no duplicate found
        # Subsequent executes: invite_code queries
        mock_db.execute.return_value = _scalar(None)
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", candidate_obj.id))

        mock_email_client = AsyncMock()
        mock_email_client.send.side_effect = Exception("SMTP unavailable")

        with (
            patch("app.services.auth_service.get_email_client", return_value=mock_email_client),
            patch("app.services.auth_service.invite_service.validate_and_consume", new_callable=AsyncMock),
            patch("app.services.auth_service.settings") as ms,
            patch("app.services.auth_service.hash_password", return_value="hashed"),
            patch("app.services.auth_service.create_verification_token", return_value="tok"),
        ):
            ms.FRONTEND_URL = "https://app.example.com"
            ms.SENDER_EMAIL = "noreply@example.com"
            ms.APP_NAME = "JobHunter"
            # Should NOT raise even though email sending fails
            await register(
                mock_db,
                RegisterRequest(
                    email="new@example.com",
                    password="Password123",
                    full_name="New User",
                    invite_code="INVITE456",
                ),
            )

        # Email was attempted
        mock_email_client.send.assert_awaited_once()


# ---------------------------------------------------------------------------
# refresh_token - blacklist check Redis failure (lines 152-154)
# ---------------------------------------------------------------------------


class TestRefreshTokenBlacklistRedisFailure:
    @pytest.mark.asyncio
    async def test_raises_503_when_redis_unavailable_during_blacklist_check(self):
        """If Redis is down during blacklist check, raise HTTP 503."""
        from app.services.auth_service import refresh_token
        from app.utils.security import create_refresh_token

        token, _ = create_refresh_token(str(uuid.uuid4()))
        db = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = RuntimeError("Connection refused")

        with (
            patch("app.services.auth_service.get_redis", return_value=mock_redis),
            pytest.raises(HTTPException) as exc_info,
        ):
            await refresh_token(db, token)

        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# refresh_token - old token blacklist failure (lines 168-169)
# ---------------------------------------------------------------------------


class TestRefreshTokenOldBlacklistFailure:
    @pytest.mark.asyncio
    async def test_refresh_succeeds_even_when_old_token_blacklist_fails(self):
        """If blacklisting the old refresh token fails, refresh still returns new tokens."""
        from app.schemas.auth import TokenPair
        from app.services.auth_service import refresh_token
        from app.utils.security import create_refresh_token

        token, _ = create_refresh_token(str(uuid.uuid4()))
        db = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # not blacklisted
        mock_redis.setex.side_effect = Exception("Redis write failed")

        with (
            patch("app.services.auth_service.get_redis", return_value=mock_redis),
            patch("app.services.auth_service.settings") as ms,
        ):
            ms.JWT_REFRESH_EXPIRE_DAYS = 30
            result = await refresh_token(db, token)

        assert isinstance(result, TokenPair)
        assert result.access_token
        assert result.refresh_token


# ---------------------------------------------------------------------------
# logout - access token blacklist failure (lines 245-246)
# ---------------------------------------------------------------------------


class TestLogoutBlacklistFailure:
    @pytest.mark.asyncio
    async def test_logout_continues_when_access_token_blacklist_fails(self):
        """Logout does not raise if blacklisting the access token fails."""
        from app.services.auth_service import logout
        from app.utils.security import create_access_token

        token, _ = create_access_token(str(uuid.uuid4()))

        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = Exception("Redis unavailable")

        with (
            patch("app.services.auth_service.get_redis", return_value=mock_redis),
            patch("app.services.auth_service.settings") as ms,
        ):
            ms.JWT_ACCESS_EXPIRE_MINUTES = 1440
            ms.JWT_REFRESH_EXPIRE_DAYS = 30
            # Should NOT raise
            await logout(token)

    @pytest.mark.asyncio
    async def test_logout_with_invalid_access_token_is_no_op(self):
        """Logout with a non-decodable token is silently ignored."""
        from app.services.auth_service import logout

        # Should NOT raise
        await logout("not.a.valid.token")


# ---------------------------------------------------------------------------
# logout - refresh token blacklist failure (lines 257-258)
# ---------------------------------------------------------------------------


class TestLogoutRefreshTokenBlacklistFailure:
    @pytest.mark.asyncio
    async def test_logout_continues_when_refresh_token_blacklist_fails(self):
        """Logout handles refresh token blacklist failure gracefully."""
        from app.services.auth_service import logout
        from app.utils.security import create_access_token, create_refresh_token

        access_token, _ = create_access_token(str(uuid.uuid4()))
        refresh_tok, _ = create_refresh_token(str(uuid.uuid4()))

        call_count = 0

        async def flaky_setex(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Redis write failed on refresh blacklist")

        mock_redis = AsyncMock()
        mock_redis.setex = flaky_setex

        with (
            patch("app.services.auth_service.get_redis", return_value=mock_redis),
            patch("app.services.auth_service.settings") as ms,
        ):
            ms.JWT_ACCESS_EXPIRE_MINUTES = 1440
            ms.JWT_REFRESH_EXPIRE_DAYS = 30
            # Should NOT raise
            await logout(access_token, refresh_token=refresh_tok)

    @pytest.mark.asyncio
    async def test_logout_with_invalid_refresh_token_does_not_raise(self):
        """Logout is resilient to an invalid/tampered refresh token."""
        from app.services.auth_service import logout
        from app.utils.security import create_access_token

        access_token, _ = create_access_token(str(uuid.uuid4()))

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()

        with (
            patch("app.services.auth_service.get_redis", return_value=mock_redis),
            patch("app.services.auth_service.settings") as ms,
        ):
            ms.JWT_ACCESS_EXPIRE_MINUTES = 1440
            ms.JWT_REFRESH_EXPIRE_DAYS = 30
            # Invalid refresh token - should not raise
            await logout(access_token, refresh_token="bad.refresh.token")
