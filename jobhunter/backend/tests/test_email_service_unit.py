"""Unit tests for email_service – no real DB/Redis required."""

import hashlib
import hmac
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.email_service import (
    generate_unsubscribe_link,
    verify_unsubscribe_token,
    _sign_email,
)


# ---------------------------------------------------------------------------
# Unsubscribe link generation / verification (pure functions)
# ---------------------------------------------------------------------------

class TestUnsubscribeLinkGeneration:
    def test_generate_unsubscribe_link_contains_frontend_url(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.FRONTEND_URL = "https://app.example.com"
            mock_settings.UNSUBSCRIBE_SECRET = "test-secret"
            link = generate_unsubscribe_link("user@example.com")
            assert link.startswith("https://app.example.com/unsubscribe/")

    def test_generate_unsubscribe_link_contains_signed_token(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.FRONTEND_URL = "https://app.example.com"
            mock_settings.UNSUBSCRIBE_SECRET = "test-secret"
            link = generate_unsubscribe_link("user@example.com")
            token = link.split("/unsubscribe/")[1]
            # Token format: sig:timestamp:email
            parts = token.split(":", 2)
            assert len(parts) == 3
            assert parts[2] == "user@example.com"

    def test_verify_unsubscribe_token_valid(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.UNSUBSCRIBE_SECRET = "test-secret"
            mock_settings.FRONTEND_URL = "https://app.example.com"
            link = generate_unsubscribe_link("user@example.com")
            token = link.split("/unsubscribe/")[1]
            email = verify_unsubscribe_token(token)
            assert email == "user@example.com"

    def test_verify_unsubscribe_token_wrong_secret_returns_none(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.UNSUBSCRIBE_SECRET = "secret-a"
            mock_settings.FRONTEND_URL = "https://app.example.com"
            link = generate_unsubscribe_link("user@example.com")
            token = link.split("/unsubscribe/")[1]

        with patch("app.services.email_service.settings") as mock_settings2:
            mock_settings2.UNSUBSCRIBE_SECRET = "secret-b"
            assert verify_unsubscribe_token(token) is None

    def test_verify_unsubscribe_token_expired_returns_none(self):
        """Tokens older than 90 days should be rejected."""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.UNSUBSCRIBE_SECRET = "test-secret"
            # Build a token with a very old timestamp
            old_ts = str(int(datetime.now(timezone.utc).timestamp()) - 91 * 86400)
            email = "user@example.com"
            msg = f"{old_ts}:{email}"
            sig = hmac.new(b"test-secret", msg.encode(), hashlib.sha256).hexdigest()
            token = f"{sig}:{old_ts}:{email}"
            assert verify_unsubscribe_token(token) is None

    def test_verify_unsubscribe_token_garbage_returns_none(self):
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.UNSUBSCRIBE_SECRET = "test-secret"
            assert verify_unsubscribe_token("totally-garbage") is None

    def test_verify_unsubscribe_legacy_format(self):
        """Legacy 2-part tokens (sig:email) should still be accepted."""
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.UNSUBSCRIBE_SECRET = "test-secret"
            email = "legacy@example.com"
            sig = hmac.new(b"test-secret", email.encode(), hashlib.sha256).hexdigest()
            token = f"{sig}:{email}"
            result = verify_unsubscribe_token(token)
            assert result == email


# ---------------------------------------------------------------------------
# process_unsubscribe (async, needs mocked DB)
# ---------------------------------------------------------------------------

class TestProcessUnsubscribe:
    @pytest.mark.asyncio
    async def test_process_unsubscribe_valid_token(self):
        from app.services.email_service import process_unsubscribe

        mock_db = AsyncMock()
        # simulate no existing suppression
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.UNSUBSCRIBE_SECRET = "test-secret"
            mock_settings.FRONTEND_URL = "https://app.example.com"
            link = generate_unsubscribe_link("user@example.com")
            token = link.split("/unsubscribe/")[1]
            result = await process_unsubscribe(mock_db, token)
            assert result is True
            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_unsubscribe_invalid_token(self):
        from app.services.email_service import process_unsubscribe

        mock_db = AsyncMock()
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.UNSUBSCRIBE_SECRET = "test-secret"
            result = await process_unsubscribe(mock_db, "invalid-token")
            assert result is False
            mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_unsubscribe_already_suppressed(self):
        from app.services.email_service import process_unsubscribe

        mock_db = AsyncMock()
        # simulate existing suppression
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()  # existing record
        mock_db.execute.return_value = mock_result

        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.UNSUBSCRIBE_SECRET = "test-secret"
            mock_settings.FRONTEND_URL = "https://app.example.com"
            link = generate_unsubscribe_link("user@example.com")
            token = link.split("/unsubscribe/")[1]
            result = await process_unsubscribe(mock_db, token)
            assert result is True
            # Should NOT add a new suppression
            mock_db.add.assert_not_called()
