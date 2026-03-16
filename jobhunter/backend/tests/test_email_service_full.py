"""Full coverage tests for email_service - fills remaining gaps.

Does NOT overlap with:
- test_email_service_unit.py  (generate_unsubscribe_link, verify_unsubscribe_token)
- test_email_service_extended.py (warmup helpers, basic send_outreach, webhook dedup,
                                   delivered/opened/bounced events, process_unsubscribe basics)
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_message(
    status="draft",
    message_type="initial",
    subject="Hello",
    contact_id=None,
    candidate_id=None,
    channel="email",
    external_message_id=None,
):
    from app.models.enums import MessageStatus

    m = MagicMock()
    m.id = uuid.uuid4()
    m.contact_id = contact_id or uuid.uuid4()
    m.candidate_id = candidate_id or uuid.uuid4()
    m.channel = channel
    m.message_type = message_type
    m.subject = subject
    m.body = "Dear Hiring Manager..."
    m.status = getattr(MessageStatus, status.upper(), status)
    m.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    m.external_message_id = external_message_id
    return m


def _make_contact(email="contact@company.com", email_verified=True):
    c = MagicMock()
    c.id = uuid.uuid4()
    c.email = email
    c.email_verified = email_verified
    return c


def _scalar(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _base_send_patches(ms):
    ms.SENDER_EMAIL = "noreply@example.com"
    ms.SENDER_NAME = "JobHunter"
    ms.PHYSICAL_ADDRESS = "123 Main St"
    ms.FRONTEND_URL = "https://app.example.com"
    ms.UNSUBSCRIBE_SECRET = "secret"
    ms.REDIS_WEBHOOK_DEDUP_TTL = 86400


# ---------------------------------------------------------------------------
# send_outreach - followup sequence enforcement (lines 127-145)
# ---------------------------------------------------------------------------


class TestSendOutreachFollowupSequence:
    @pytest.mark.asyncio
    async def test_raises_when_followup_previous_message_not_sent(self):
        """Followup cannot be sent if previous message is still DRAFT."""
        from app.models.enums import MessageStatus
        from app.services.email_service import send_outreach

        contact_id = uuid.uuid4()
        candidate_id = uuid.uuid4()
        msg = _make_message(
            status="draft",
            message_type="followup",
            contact_id=contact_id,
            candidate_id=candidate_id,
        )
        contact = _make_contact()

        prev_msg = MagicMock()
        prev_msg.id = uuid.uuid4()
        prev_msg.status = MessageStatus.DRAFT  # not sent

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(msg),  # main message
            _scalar(prev_msg),  # previous message
            _scalar(contact),  # contact
        ]

        with pytest.raises(ValueError, match="Cannot send followup"):
            await send_outreach(mock_db, msg.id)

    @pytest.mark.asyncio
    async def test_allows_followup_when_previous_message_sent(self):
        """Followup is allowed when previous message has status SENT."""
        from app.models.enums import MessageStatus
        from app.services.email_service import send_outreach

        contact_id = uuid.uuid4()
        candidate_id = uuid.uuid4()
        msg = _make_message(
            status="draft",
            message_type="followup",
            contact_id=contact_id,
            candidate_id=candidate_id,
        )
        contact = _make_contact()
        prev_msg = MagicMock()
        prev_msg.id = uuid.uuid4()
        prev_msg.status = MessageStatus.SENT
        prev_msg.external_message_id = None  # no threading

        cand_email_result = MagicMock()
        cand_email_result.scalar_one_or_none.return_value = "cand@example.com"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(msg),
            _scalar(prev_msg),
            _scalar(contact),
            _scalar(None),  # no suppression
            cand_email_result,
        ]

        mock_email_client = AsyncMock()
        mock_email_client.send.return_value = {"id": "ext-abc"}
        mock_bus = MagicMock()
        mock_bus.publish = AsyncMock()

        with (
            patch("app.services.quota_service.check_and_increment", new_callable=AsyncMock),
            patch("app.services.email_service.check_warmup_quota", new_callable=AsyncMock),
            patch("app.services.email_service.increment_warmup_count", new_callable=AsyncMock),
            patch("app.services.email_service.get_email_client", return_value=mock_email_client),
            patch("app.infrastructure.websocket_manager.ws_manager") as mock_ws,
            patch("app.events.bus.get_event_bus", return_value=mock_bus),
            patch("app.services.email_service.settings") as ms,
        ):
            mock_ws.broadcast = AsyncMock()
            _base_send_patches(ms)
            result = await send_outreach(mock_db, msg.id)

        assert result.status == MessageStatus.SENT

    @pytest.mark.asyncio
    async def test_allows_followup_when_no_previous_message(self):
        """If no previous message found, followup is allowed (first in channel)."""
        from app.models.enums import MessageStatus
        from app.services.email_service import send_outreach

        msg = _make_message(status="draft", message_type="followup")
        contact = _make_contact()
        cand_email_result = MagicMock()
        cand_email_result.scalar_one_or_none.return_value = "cand@example.com"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(msg),
            _scalar(None),  # no previous message
            _scalar(contact),
            _scalar(None),  # no suppression
            cand_email_result,
        ]

        mock_email_client = AsyncMock()
        mock_email_client.send.return_value = {"id": "ext-xyz"}
        mock_bus = MagicMock()
        mock_bus.publish = AsyncMock()

        with (
            patch("app.services.quota_service.check_and_increment", new_callable=AsyncMock),
            patch("app.services.email_service.check_warmup_quota", new_callable=AsyncMock),
            patch("app.services.email_service.increment_warmup_count", new_callable=AsyncMock),
            patch("app.services.email_service.get_email_client", return_value=mock_email_client),
            patch("app.infrastructure.websocket_manager.ws_manager") as mock_ws,
            patch("app.events.bus.get_event_bus", return_value=mock_bus),
            patch("app.services.email_service.settings") as ms,
        ):
            mock_ws.broadcast = AsyncMock()
            _base_send_patches(ms)
            result = await send_outreach(mock_db, msg.id)

        assert result.status == MessageStatus.SENT


# ---------------------------------------------------------------------------
# send_outreach - warmup quota ValueError propagation (lines 179-183)
# ---------------------------------------------------------------------------


class TestSendOutreachWarmupQuotaPropagation:
    @pytest.mark.asyncio
    async def test_warmup_value_error_propagates(self):
        """Warmup ValueError is re-raised as-is, not swallowed."""
        from app.services.email_service import send_outreach

        msg = _make_message()
        contact = _make_contact()

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(msg),
            _scalar(contact),
            _scalar(None),  # no suppression
        ]

        with (
            patch("app.services.quota_service.check_and_increment", new_callable=AsyncMock),
            patch(
                "app.services.email_service.check_warmup_quota",
                new_callable=AsyncMock,
                side_effect=ValueError("warm-up limit reached"),
            ),
            patch("app.services.email_service.settings") as ms,
        ):
            _base_send_patches(ms)
            with pytest.raises(ValueError, match="warm-up limit reached"):
                await send_outreach(mock_db, msg.id)

    @pytest.mark.asyncio
    async def test_warmup_generic_exception_is_logged_and_ignored(self):
        """Non-ValueError exceptions from warmup check are logged but do not block send."""
        from app.models.enums import MessageStatus
        from app.services.email_service import send_outreach

        msg = _make_message()
        contact = _make_contact()
        cand_email_result = MagicMock()
        cand_email_result.scalar_one_or_none.return_value = "cand@example.com"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(msg),
            _scalar(contact),
            _scalar(None),  # no suppression
            cand_email_result,
        ]

        mock_email_client = AsyncMock()
        mock_email_client.send.return_value = {"id": "ext-ok"}
        mock_bus = MagicMock()
        mock_bus.publish = AsyncMock()

        with (
            patch("app.services.quota_service.check_and_increment", new_callable=AsyncMock),
            patch(
                "app.services.email_service.check_warmup_quota",
                new_callable=AsyncMock,
                side_effect=RuntimeError("redis timeout"),
            ),
            patch("app.services.email_service.increment_warmup_count", new_callable=AsyncMock),
            patch("app.services.email_service.get_email_client", return_value=mock_email_client),
            patch("app.infrastructure.websocket_manager.ws_manager") as mock_ws,
            patch("app.events.bus.get_event_bus", return_value=mock_bus),
            patch("app.services.email_service.settings") as ms,
        ):
            mock_ws.broadcast = AsyncMock()
            _base_send_patches(ms)
            result = await send_outreach(mock_db, msg.id)

        # Send still happened despite warmup check failure
        assert result.status == MessageStatus.SENT


# ---------------------------------------------------------------------------
# send_outreach - resume attachment (lines 204-220)
# ---------------------------------------------------------------------------


class TestSendOutreachResumeAttachment:
    @pytest.mark.asyncio
    async def test_resume_attached_when_primary_resume_exists(self):
        """When attach_resume=True and primary resume exists, attachment is included."""
        from app.models.enums import MessageStatus
        from app.services.email_service import send_outreach

        msg = _make_message()
        contact = _make_contact()

        resume = MagicMock()
        resume.file_path = "resumes/cv.pdf"

        cand_email_result = MagicMock()
        cand_email_result.scalar_one_or_none.return_value = "cand@example.com"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(msg),
            _scalar(contact),
            _scalar(None),  # no suppression
            _scalar(resume),  # primary resume
            cand_email_result,
        ]

        mock_storage = AsyncMock()
        mock_storage.download.return_value = b"PDF_BYTES"
        mock_email_client = AsyncMock()
        mock_email_client.send.return_value = {"id": "ext-attach"}
        mock_bus = MagicMock()
        mock_bus.publish = AsyncMock()

        with (
            patch("app.services.quota_service.check_and_increment", new_callable=AsyncMock),
            patch("app.services.email_service.check_warmup_quota", new_callable=AsyncMock),
            patch("app.services.email_service.increment_warmup_count", new_callable=AsyncMock),
            patch("app.services.email_service.get_email_client", return_value=mock_email_client),
            patch("app.infrastructure.storage.get_storage", return_value=mock_storage),
            patch("app.infrastructure.websocket_manager.ws_manager") as mock_ws,
            patch("app.events.bus.get_event_bus", return_value=mock_bus),
            patch("app.services.email_service.settings") as ms,
        ):
            mock_ws.broadcast = AsyncMock()
            _base_send_patches(ms)
            result = await send_outreach(mock_db, msg.id, attach_resume=True)

        assert result.status == MessageStatus.SENT
        # Verify attachments were passed to email client
        call_kwargs = mock_email_client.send.call_args.kwargs
        assert call_kwargs["attachments"] is not None
        assert call_kwargs["attachments"][0]["filename"] == "cv.pdf"

    @pytest.mark.asyncio
    async def test_resume_download_failure_does_not_block_send(self):
        """If resume download fails, send continues without attachment."""
        from app.models.enums import MessageStatus
        from app.services.email_service import send_outreach

        msg = _make_message()
        contact = _make_contact()

        resume = MagicMock()
        resume.file_path = "resumes/cv.pdf"

        cand_email_result = MagicMock()
        cand_email_result.scalar_one_or_none.return_value = "cand@example.com"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(msg),
            _scalar(contact),
            _scalar(None),  # no suppression
            _scalar(resume),  # primary resume
            cand_email_result,
        ]

        mock_storage = AsyncMock()
        mock_storage.download.side_effect = Exception("S3 error")
        mock_email_client = AsyncMock()
        mock_email_client.send.return_value = {"id": "ext-no-attach"}
        mock_bus = MagicMock()
        mock_bus.publish = AsyncMock()

        with (
            patch("app.services.quota_service.check_and_increment", new_callable=AsyncMock),
            patch("app.services.email_service.check_warmup_quota", new_callable=AsyncMock),
            patch("app.services.email_service.increment_warmup_count", new_callable=AsyncMock),
            patch("app.services.email_service.get_email_client", return_value=mock_email_client),
            patch("app.infrastructure.storage.get_storage", return_value=mock_storage),
            patch("app.infrastructure.websocket_manager.ws_manager") as mock_ws,
            patch("app.events.bus.get_event_bus", return_value=mock_bus),
            patch("app.services.email_service.settings") as ms,
        ):
            mock_ws.broadcast = AsyncMock()
            _base_send_patches(ms)
            result = await send_outreach(mock_db, msg.id, attach_resume=True)

        # Send still succeeded, attachments=None
        assert result.status == MessageStatus.SENT
        call_kwargs = mock_email_client.send.call_args.kwargs
        assert call_kwargs["attachments"] is None

    @pytest.mark.asyncio
    async def test_attach_resume_no_primary_resume(self):
        """When attach_resume=True but no primary resume exists, send proceeds without attachment."""
        from app.models.enums import MessageStatus
        from app.services.email_service import send_outreach

        msg = _make_message()
        contact = _make_contact()
        cand_email_result = MagicMock()
        cand_email_result.scalar_one_or_none.return_value = "cand@example.com"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(msg),
            _scalar(contact),
            _scalar(None),  # no suppression
            _scalar(None),  # no primary resume
            cand_email_result,
        ]

        mock_email_client = AsyncMock()
        mock_email_client.send.return_value = {"id": "ext-no-resume"}
        mock_bus = MagicMock()
        mock_bus.publish = AsyncMock()

        with (
            patch("app.services.quota_service.check_and_increment", new_callable=AsyncMock),
            patch("app.services.email_service.check_warmup_quota", new_callable=AsyncMock),
            patch("app.services.email_service.increment_warmup_count", new_callable=AsyncMock),
            patch("app.services.email_service.get_email_client", return_value=mock_email_client),
            patch("app.infrastructure.websocket_manager.ws_manager") as mock_ws,
            patch("app.events.bus.get_event_bus", return_value=mock_bus),
            patch("app.services.email_service.settings") as ms,
        ):
            mock_ws.broadcast = AsyncMock()
            _base_send_patches(ms)
            result = await send_outreach(mock_db, msg.id, attach_resume=True)

        assert result.status == MessageStatus.SENT
        call_kwargs = mock_email_client.send.call_args.kwargs
        assert call_kwargs["attachments"] is None


# ---------------------------------------------------------------------------
# send_outreach - email threading headers (lines 236-237)
# ---------------------------------------------------------------------------


class TestSendOutreachEmailThreadingHeaders:
    @pytest.mark.asyncio
    async def test_in_reply_to_header_set_for_followup_with_previous_external_id(self):
        """In-Reply-To and References headers are set for followups when prev has external_message_id."""
        from app.models.enums import MessageStatus
        from app.services.email_service import send_outreach

        msg = _make_message(status="draft", message_type="followup")
        contact = _make_contact()

        prev_msg = MagicMock()
        prev_msg.id = uuid.uuid4()
        prev_msg.status = MessageStatus.SENT
        prev_msg.external_message_id = "original-msg-id-123"

        cand_email_result = MagicMock()
        cand_email_result.scalar_one_or_none.return_value = "cand@example.com"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(msg),
            _scalar(prev_msg),
            _scalar(contact),
            _scalar(None),  # no suppression
            cand_email_result,
        ]

        mock_email_client = AsyncMock()
        mock_email_client.send.return_value = {"id": "ext-followup"}
        mock_bus = MagicMock()
        mock_bus.publish = AsyncMock()

        with (
            patch("app.services.quota_service.check_and_increment", new_callable=AsyncMock),
            patch("app.services.email_service.check_warmup_quota", new_callable=AsyncMock),
            patch("app.services.email_service.increment_warmup_count", new_callable=AsyncMock),
            patch("app.services.email_service.get_email_client", return_value=mock_email_client),
            patch("app.infrastructure.websocket_manager.ws_manager") as mock_ws,
            patch("app.events.bus.get_event_bus", return_value=mock_bus),
            patch("app.services.email_service.settings") as ms,
        ):
            mock_ws.broadcast = AsyncMock()
            _base_send_patches(ms)
            await send_outreach(mock_db, msg.id)

        call_kwargs = mock_email_client.send.call_args.kwargs
        headers = call_kwargs["headers"]
        assert "In-Reply-To" in headers
        assert "original-msg-id-123" in headers["In-Reply-To"]
        assert "References" in headers
        assert "original-msg-id-123" in headers["References"]

    @pytest.mark.asyncio
    async def test_no_threading_headers_for_initial_message(self):
        """Initial messages do not get In-Reply-To or References headers."""
        from app.services.email_service import send_outreach

        msg = _make_message(status="draft", message_type="initial")
        contact = _make_contact()
        cand_email_result = MagicMock()
        cand_email_result.scalar_one_or_none.return_value = "cand@example.com"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(msg),
            _scalar(contact),
            _scalar(None),  # no suppression
            cand_email_result,
        ]

        mock_email_client = AsyncMock()
        mock_email_client.send.return_value = {"id": "ext-initial"}
        mock_bus = MagicMock()
        mock_bus.publish = AsyncMock()

        with (
            patch("app.services.quota_service.check_and_increment", new_callable=AsyncMock),
            patch("app.services.email_service.check_warmup_quota", new_callable=AsyncMock),
            patch("app.services.email_service.increment_warmup_count", new_callable=AsyncMock),
            patch("app.services.email_service.get_email_client", return_value=mock_email_client),
            patch("app.infrastructure.websocket_manager.ws_manager") as mock_ws,
            patch("app.events.bus.get_event_bus", return_value=mock_bus),
            patch("app.services.email_service.settings") as ms,
        ):
            mock_ws.broadcast = AsyncMock()
            _base_send_patches(ms)
            await send_outreach(mock_db, msg.id)

        call_kwargs = mock_email_client.send.call_args.kwargs
        headers = call_kwargs["headers"]
        assert "In-Reply-To" not in headers
        assert "References" not in headers


# ---------------------------------------------------------------------------
# send_outreach - warmup increment failure (lines 308-309)
# ---------------------------------------------------------------------------


class TestSendOutreachWarmupIncrementFailure:
    @pytest.mark.asyncio
    async def test_warmup_increment_failure_is_warning_only(self):
        """Failure to increment warmup counter logs a warning but does not fail the send."""
        from app.models.enums import MessageStatus
        from app.services.email_service import send_outreach

        msg = _make_message()
        contact = _make_contact()
        cand_email_result = MagicMock()
        cand_email_result.scalar_one_or_none.return_value = "cand@example.com"

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(msg),
            _scalar(contact),
            _scalar(None),  # no suppression
            cand_email_result,
        ]

        mock_email_client = AsyncMock()
        mock_email_client.send.return_value = {"id": "ext-incr-fail"}
        mock_bus = MagicMock()
        mock_bus.publish = AsyncMock()

        with (
            patch("app.services.quota_service.check_and_increment", new_callable=AsyncMock),
            patch("app.services.email_service.check_warmup_quota", new_callable=AsyncMock),
            patch(
                "app.services.email_service.increment_warmup_count",
                new_callable=AsyncMock,
                side_effect=Exception("Redis down"),
            ),
            patch("app.services.email_service.get_email_client", return_value=mock_email_client),
            patch("app.infrastructure.websocket_manager.ws_manager") as mock_ws,
            patch("app.events.bus.get_event_bus", return_value=mock_bus),
            patch("app.services.email_service.settings") as ms,
        ):
            mock_ws.broadcast = AsyncMock()
            _base_send_patches(ms)
            result = await send_outreach(mock_db, msg.id)

        # Should still succeed
        assert result.status == MessageStatus.SENT


# ---------------------------------------------------------------------------
# handle_resend_webhook - bounced event auto_suppress (lines 360-361)
# ---------------------------------------------------------------------------


class TestHandleResendWebhookBounced:
    @pytest.mark.asyncio
    async def test_bounced_event_with_to_list_auto_suppresses(self):
        """Bounced event with 'to' as a list extracts first email and auto-suppresses."""
        from app.models.enums import MessageStatus
        from app.services.email_service import handle_resend_webhook

        msg = _make_message()
        msg.status = MessageStatus.SENT

        mock_db = AsyncMock()
        # message fetch + suppression check (no existing)
        mock_db.execute.side_effect = [_scalar(msg), _scalar(None)]

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True  # not seen before

        with (
            patch("app.services.email_service.get_redis", return_value=mock_redis),
            patch("app.services.email_service.settings") as ms,
            patch("app.infrastructure.websocket_manager.ws_manager") as mock_ws,
        ):
            ms.REDIS_WEBHOOK_DEDUP_TTL = 86400
            mock_ws.broadcast = AsyncMock()
            await handle_resend_webhook(
                mock_db,
                {
                    "type": "email.bounced",
                    "data": {
                        "email_id": "ext-bounce",
                        "to": ["victim@example.com"],
                    },
                },
            )

        assert msg.status == MessageStatus.BOUNCED
        # db.add should have been called for the suppression
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_bounced_event_with_to_string_auto_suppresses(self):
        """Bounced event with 'to' as a plain string also triggers auto_suppress."""
        from app.models.enums import MessageStatus
        from app.services.email_service import handle_resend_webhook

        msg = _make_message()
        msg.status = MessageStatus.SENT

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [_scalar(msg), _scalar(None)]

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        with (
            patch("app.services.email_service.get_redis", return_value=mock_redis),
            patch("app.services.email_service.settings") as ms,
            patch("app.infrastructure.websocket_manager.ws_manager") as mock_ws,
        ):
            ms.REDIS_WEBHOOK_DEDUP_TTL = 86400
            mock_ws.broadcast = AsyncMock()
            await handle_resend_webhook(
                mock_db,
                {
                    "type": "email.bounced",
                    "data": {
                        "email_id": "ext-bounce2",
                        "to": "victim@example.com",
                    },
                },
            )

        assert msg.status == MessageStatus.BOUNCED


# ---------------------------------------------------------------------------
# _auto_suppress - existing suppression (lines 401-403)
# ---------------------------------------------------------------------------


class TestAutoSuppress:
    @pytest.mark.asyncio
    async def test_auto_suppress_skips_duplicate(self):
        """_auto_suppress does not create duplicate suppression if one already exists."""
        from app.services.email_service import _auto_suppress

        existing = MagicMock()  # existing suppression
        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(existing)

        await _auto_suppress(mock_db, "dup@example.com", "bounce")

        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_suppress_creates_new_suppression(self):
        """_auto_suppress adds a new suppression when none exists."""
        from app.services.email_service import _auto_suppress

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(None)

        await _auto_suppress(mock_db, "new@example.com", "complaint")

        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_suppress_no_op_when_email_is_none(self):
        """_auto_suppress is a no-op when email is None."""
        from app.services.email_service import _auto_suppress

        mock_db = AsyncMock()
        await _auto_suppress(mock_db, None, "bounce")

        mock_db.execute.assert_not_awaited()
        mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# process_unsubscribe - already suppressed (line 425)
# ---------------------------------------------------------------------------


class TestProcessUnsubscribeExistingSuppression:
    @pytest.mark.asyncio
    async def test_process_unsubscribe_already_suppressed_returns_true_no_duplicate(self):
        """process_unsubscribe returns True but does not add a duplicate suppression."""
        # Build a valid token via generate_unsubscribe_link
        from app.services.email_service import generate_unsubscribe_link, process_unsubscribe

        existing = MagicMock()
        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(existing)

        with patch("app.services.email_service.settings") as ms:
            ms.UNSUBSCRIBE_SECRET = "test-secret"
            ms.FRONTEND_URL = "https://app.example.com"
            link = generate_unsubscribe_link("user@example.com")
            token = link.split("/unsubscribe/")[1]
            # process_unsubscribe calls verify_unsubscribe_token which also reads settings
            result = await process_unsubscribe(mock_db, token)

        assert result is True
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_process_unsubscribe_invalid_token_returns_false(self):
        """process_unsubscribe returns False for an invalid/tampered token."""
        from app.services.email_service import process_unsubscribe

        mock_db = AsyncMock()

        with patch("app.services.email_service.settings") as ms:
            ms.UNSUBSCRIBE_SECRET = "secret"
            result = await process_unsubscribe(mock_db, "invalid:token:data")

        assert result is False
        mock_db.execute.assert_not_awaited()
