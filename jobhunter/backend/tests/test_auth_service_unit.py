"""Unit tests for auth_service – no real DB/Redis required."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from app.config import settings
from app.schemas.auth import LoginRequest, TokenPair
from app.services.auth_service import (
    TOKEN_BLACKLIST_PREFIX,
    forgot_password,
    login,
    logout,
    refresh_token,
    reset_password,
)
from app.utils.security import (
    create_access_token,
    create_reset_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.utils.security import (
    create_refresh_token as create_refresh,
)

# ---------------------------------------------------------------------------
# Password hashing (pure utility)
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_password_returns_different_from_plain(self):
        hashed = hash_password("mypassword")
        assert hashed != "mypassword"

    def test_verify_password_correct(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_password_wrong(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_hash_password_unique_per_call(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt salts should differ


# ---------------------------------------------------------------------------
# JWT creation / decode
# ---------------------------------------------------------------------------


class TestJWT:
    def test_create_access_token_decodeable(self):
        token, jti = create_access_token("cand-123")
        payload = decode_token(token)
        assert payload["sub"] == "cand-123"
        assert payload["type"] == "access"
        assert payload["jti"] == jti

    def test_create_refresh_token_decodeable(self):
        token, jti = create_refresh("cand-456")
        payload = decode_token(token)
        assert payload["sub"] == "cand-456"
        assert payload["type"] == "refresh"

    def test_decode_token_expired_raises(self):
        payload = {
            "sub": "cand-789",
            "exp": datetime.now(UTC) - timedelta(hours=1),
            "type": "access",
            "jti": str(uuid.uuid4()),
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(token)

    def test_decode_token_wrong_secret_raises(self):
        payload = {
            "sub": "cand-789",
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "type": "access",
        }
        token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
        with pytest.raises(jwt.InvalidSignatureError):
            decode_token(token)


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self):
        candidate = MagicMock()
        candidate.id = uuid.uuid4()
        candidate.email = "user@example.com"
        candidate.password_hash = hash_password("correctpass")
        candidate.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = candidate
        db = AsyncMock()
        db.execute.return_value = mock_result

        data = LoginRequest(email="user@example.com", password="correctpass")
        token_pair = await login(db, data)
        assert token_pair.access_token
        assert token_pair.refresh_token

    @pytest.mark.asyncio
    async def test_login_wrong_password(self):
        candidate = MagicMock()
        candidate.id = uuid.uuid4()
        candidate.email = "user@example.com"
        candidate.password_hash = hash_password("correctpass")
        candidate.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = candidate
        db = AsyncMock()
        db.execute.return_value = mock_result

        data = LoginRequest(email="user@example.com", password="wrongpass")
        with pytest.raises(HTTPException) as exc_info:
            await login(db, data)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_email(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db = AsyncMock()
        db.execute.return_value = mock_result

        data = LoginRequest(email="nobody@example.com", password="whatever")
        with pytest.raises(HTTPException) as exc_info:
            await login(db, data)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_suspended_account(self):
        candidate = MagicMock()
        candidate.id = uuid.uuid4()
        candidate.email = "user@example.com"
        candidate.password_hash = hash_password("correctpass")
        candidate.is_active = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = candidate
        db = AsyncMock()
        db.execute.return_value = mock_result

        data = LoginRequest(email="user@example.com", password="correctpass")
        with pytest.raises(HTTPException) as exc_info:
            await login(db, data)
        assert exc_info.value.status_code == 403
        assert "suspended" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# refresh_token
# ---------------------------------------------------------------------------


class TestRefreshToken:
    @pytest.mark.asyncio
    async def test_refresh_success(self):
        # cand-123 is not a valid UUID, so use a real one for the UPDATE stmt
        cand_id = str(uuid.uuid4())
        token, jti = create_refresh(cand_id)
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # not blacklisted
        db = AsyncMock()

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            result = await refresh_token(db, token)
            assert isinstance(result, TokenPair)
            assert result.access_token
            assert result.refresh_token
            # Old token should be blacklisted
            mock_redis.setex.assert_awaited_once()
            # last_seen_at updated
            db.execute.assert_awaited_once()
            db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_rejects(self):
        """Using an access token for refresh should fail."""
        token, _ = create_access_token("cand-123")
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        db = AsyncMock()

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await refresh_token(db, token)
            assert exc_info.value.status_code == 401
            assert "token type" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_refresh_blacklisted_token_rejects(self):
        token, jti = create_refresh("cand-123")
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "revoked"  # blacklisted
        db = AsyncMock()

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await refresh_token(db, token)
            assert exc_info.value.status_code == 401
            assert "revoked" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_refresh_invalid_token_rejects(self):
        db = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await refresh_token(db, "this.is.garbage")
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# logout
# ---------------------------------------------------------------------------


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_blacklists_access_token(self):
        token, jti = create_access_token("cand-123")
        mock_redis = AsyncMock()

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            await logout(token)
            mock_redis.setex.assert_awaited_once()
            call_args = mock_redis.setex.call_args
            assert TOKEN_BLACKLIST_PREFIX in call_args[0][0]

    @pytest.mark.asyncio
    async def test_logout_blacklists_both_tokens(self):
        access, _ = create_access_token("cand-123")
        refresh, _ = create_refresh("cand-123")
        mock_redis = AsyncMock()

        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            await logout(access, refresh_token=refresh)
            assert mock_redis.setex.await_count == 2

    @pytest.mark.asyncio
    async def test_logout_invalid_token_no_error(self):
        """Logging out with an already-invalid token should not raise."""
        mock_redis = AsyncMock()
        with patch("app.services.auth_service.get_redis", return_value=mock_redis):
            await logout("invalid.token.here")
            # Should not crash, and should not call redis
            mock_redis.setex.assert_not_awaited()


# ---------------------------------------------------------------------------
# forgot_password
# ---------------------------------------------------------------------------


class TestForgotPassword:
    @pytest.mark.asyncio
    async def test_forgot_password_existing_user_sends_email(self):
        """Should send reset email when user exists."""
        candidate = MagicMock()
        candidate.id = uuid.uuid4()
        candidate.email = "user@example.com"
        candidate.full_name = "Test User"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = candidate
        db = AsyncMock()
        db.execute.return_value = mock_result

        mock_email = AsyncMock()
        with patch("app.services.auth_service.get_email_client", return_value=mock_email):
            await forgot_password(db, "user@example.com")

        mock_email.send.assert_awaited_once()
        call_kwargs = mock_email.send.call_args.kwargs
        assert "reset-password" in call_kwargs["body"]

    @pytest.mark.asyncio
    async def test_forgot_password_nonexistent_user_no_error(self):
        """Should silently succeed when user doesn't exist (no enumeration)."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db = AsyncMock()
        db.execute.return_value = mock_result

        # Should not raise
        await forgot_password(db, "nobody@example.com")

    @pytest.mark.asyncio
    async def test_forgot_password_email_failure_no_crash(self):
        """Should not crash if email sending fails."""
        candidate = MagicMock()
        candidate.id = uuid.uuid4()
        candidate.email = "user@example.com"
        candidate.full_name = "Test User"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = candidate
        db = AsyncMock()
        db.execute.return_value = mock_result

        mock_email = AsyncMock()
        mock_email.send.side_effect = Exception("SMTP down")
        with patch("app.services.auth_service.get_email_client", return_value=mock_email):
            await forgot_password(db, "user@example.com")  # Should not raise


# ---------------------------------------------------------------------------
# reset_password
# ---------------------------------------------------------------------------


class TestResetPassword:
    @pytest.mark.asyncio
    async def test_reset_password_success(self):
        """Valid reset token should update password."""
        cand_id = uuid.uuid4()
        token = create_reset_token(str(cand_id))

        candidate = MagicMock()
        candidate.id = cand_id
        candidate.password_hash = "old_hash"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = candidate
        db = AsyncMock()
        db.execute.return_value = mock_result

        await reset_password(db, token, "NewPassword1")
        # Password hash should have been updated
        assert candidate.password_hash != "old_hash"
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reset_password_invalid_token_raises(self):
        """Invalid token should raise 400."""
        db = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await reset_password(db, "invalid.jwt.token", "NewPassword1")
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_reset_password_wrong_token_type_raises(self):
        """Using an access token for reset should fail."""
        token, _ = create_access_token("cand-123")
        db = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await reset_password(db, token, "NewPassword1")
        assert exc_info.value.status_code == 400
        assert "token type" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_reset_password_nonexistent_user_raises(self):
        """Reset token for deleted user should raise 400."""
        token = create_reset_token(str(uuid.uuid4()))

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db = AsyncMock()
        db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await reset_password(db, token, "NewPassword1")
        assert exc_info.value.status_code == 400
