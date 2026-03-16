"""Extended unit tests for email_service - focus on send_outreach, webhook, warmup.

Does NOT overlap with test_email_service_unit.py which already covers:
- generate_unsubscribe_link / verify_unsubscribe_token / _sign_email
- process_unsubscribe
"""

import uuid
from datetime import UTC, datetime, timedelta
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
    m.external_message_id = None
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


# ---------------------------------------------------------------------------
# Warmup tracking
# ---------------------------------------------------------------------------


class TestGetWarmupLimit:
    @pytest.mark.asyncio
    async def test_new_domain_records_start_date_and_returns_conservative_limit(self):
        from app.services.email_service import get_warmup_limit

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # never seen before
        mock_redis.set.return_value = True

        with patch("app.services.email_service.get_redis", return_value=mock_redis):
            limit = await get_warmup_limit("newdomain.com")

        # Day 1 falls in the first schedule bucket (threshold=3, limit=5)
        assert limit == 5
        mock_redis.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_old_domain_returns_graduated_limit(self):
        from app.services.email_service import WARMUP_GRADUATED_LIMIT, get_warmup_limit

        mock_redis = AsyncMock()
        # 20 days ago - past all thresholds
        old_date = (datetime.now(UTC) - timedelta(days=20)).date().isoformat()
        mock_redis.get.return_value = old_date

        with patch("app.services.email_service.get_redis", return_value=mock_redis):
            limit = await get_warmup_limit("olddomain.com")

        assert limit == WARMUP_GRADUATED_LIMIT

    @pytest.mark.asyncio
    async def test_domain_within_schedule_returns_correct_limit(self):
        from app.services.email_service import get_warmup_limit

        mock_redis = AsyncMock()
        # 5 days ago -> day 6, falls in threshold=7, limit=15 bucket
        five_days_ago = (datetime.now(UTC) - timedelta(days=5)).date().isoformat()
        mock_redis.get.return_value = five_days_ago

        with patch("app.services.email_service.get_redis", return_value=mock_redis):
            limit = await get_warmup_limit("domain.com")

        assert limit == 15


class TestCheckWarmupQuota:
    @pytest.mark.asyncio
    async def test_raises_when_limit_reached(self):
        from app.services.email_service import check_warmup_quota

        mock_redis = AsyncMock()
        mock_redis.get.return_value = "5"  # current count

        with (
            patch("app.services.email_service.get_redis", return_value=mock_redis),
            patch("app.services.email_service.get_warmup_limit", new_callable=AsyncMock, return_value=5),
            pytest.raises(ValueError, match="warm-up limit reached"),
        ):
            await check_warmup_quota("domain.com")

    @pytest.mark.asyncio
    async def test_does_not_raise_when_under_limit(self):
        from app.services.email_service import check_warmup_quota

        mock_redis = AsyncMock()
        mock_redis.get.return_value = "3"  # current count

        with (
            patch("app.services.email_service.get_redis", return_value=mock_redis),
            patch("app.services.email_service.get_warmup_limit", new_callable=AsyncMock, return_value=5),
        ):
            # Should not raise
            await check_warmup_quota("domain.com")

    @pytest.mark.asyncio
    async def test_does_not_raise_when_no_counter_yet(self):
        from app.services.email_service import check_warmup_quota

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # no counter

        with (
            patch("app.services.email_service.get_redis", return_value=mock_redis),
            patch("app.services.email_service.get_warmup_limit", new_callable=AsyncMock, return_value=5),
        ):
            await check_warmup_quota("domain.com")  # should not raise


# ---------------------------------------------------------------------------
# send_outreach
# ---------------------------------------------------------------------------


class TestSendOutreach:
    @pytest.mark.asyncio
    async def test_raises_when_message_not_found(self):
        from app.services.email_service import send_outreach

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(None)

        with pytest.raises(ValueError, match="Message not found"):
            await send_outreach(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_when_status_already_sent(self):
        from app.models.enums import MessageStatus
        from app.services.email_service import send_outreach

        msg = _make_message(status="sent")
        msg.status = MessageStatus.SENT
        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(msg)

        with pytest.raises(ValueError, match="already sent"):
            await send_outreach(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_when_contact_has_no_email(self):
        from app.services.email_service import send_outreach

        msg = _make_message()
        contact = _make_contact(email=None)
        contact.email = None

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(msg),
            _scalar(contact),  # contact fetch -> no email
        ]

        with pytest.raises(ValueError, match="no email"):
            await send_outreach(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_when_email_suppressed(self):
        from app.services.email_service import send_outreach

        msg = _make_message()
        contact = _make_contact()
        suppression = MagicMock()  # non-None -> suppressed

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            _scalar(msg),
            _scalar(contact),
            _scalar(suppression),
        ]

        with pytest.raises(ValueError, match="suppression list"):
            await send_outreach(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_when_no_subject(self):
        from app.services.email_service import send_outreach

        msg = _make_message()
        msg.subject = None
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

        with (
            patch("app.services.quota_service.check_and_increment", new_callable=AsyncMock),
            patch("app.services.email_service.check_warmup_quota", new_callable=AsyncMock),
            patch("app.services.email_service.settings") as ms,
        ):
            ms.SENDER_EMAIL = "noreply@example.com"
            ms.SENDER_NAME = "JobHunter"
            ms.PHYSICAL_ADDRESS = "123 Main St"
            ms.FRONTEND_URL = "https://app.example.com"
            ms.UNSUBSCRIBE_SECRET = "secret"
            with pytest.raises(ValueError, match="subject"):
                await send_outreach(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_sends_successfully(self):
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
        mock_email_client.send.return_value = {"id": "ext-123"}

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
            ms.SENDER_EMAIL = "noreply@example.com"
            ms.SENDER_NAME = "JobHunter"
            ms.PHYSICAL_ADDRESS = "123 Main St"
            ms.FRONTEND_URL = "https://app.example.com"
            ms.UNSUBSCRIBE_SECRET = "secret"
            await send_outreach(mock_db, msg.id)

        assert msg.status == MessageStatus.SENT
        assert msg.external_message_id == "ext-123"

    @pytest.mark.asyncio
    async def test_sets_failed_on_send_error(self):
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
            _scalar(None),
            cand_email_result,
        ]

        mock_email_client = AsyncMock()
        mock_email_client.send.side_effect = Exception("Network error")

        redis_mock = AsyncMock()
        redis_mock.decr = AsyncMock()

        with (
            patch("app.services.quota_service.check_and_increment", new_callable=AsyncMock),
            patch("app.services.email_service.check_warmup_quota", new_callable=AsyncMock),
            patch("app.services.email_service.get_email_client", return_value=mock_email_client),
            patch("app.infrastructure.redis_client.get_redis", return_value=redis_mock),
            patch("app.services.email_service.settings") as ms,
        ):
            ms.SENDER_EMAIL = "noreply@example.com"
            ms.SENDER_NAME = "JobHunter"
            ms.PHYSICAL_ADDRESS = "123 Main St"
            ms.FRONTEND_URL = "https://app.example.com"
            ms.UNSUBSCRIBE_SECRET = "secret"
            with pytest.raises(ValueError, match="Failed to send email"):
                await send_outreach(mock_db, msg.id)

        assert msg.status == MessageStatus.FAILED


# ---------------------------------------------------------------------------
# handle_resend_webhook
# ---------------------------------------------------------------------------


class TestHandleResendWebhook:
    @pytest.mark.asyncio
    async def test_no_op_when_missing_email_id(self):
        from app.services.email_service import handle_resend_webhook

        mock_db = AsyncMock()
        mock_redis = AsyncMock()

        with patch("app.services.email_service.get_redis", return_value=mock_redis):
            await handle_resend_webhook(mock_db, {"type": "email.delivered", "data": {}})

        mock_db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_duplicate_events(self):
        from app.services.email_service import handle_resend_webhook

        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.set.return_value = None  # already seen -> set returns None (falsy)

        payload = {
            "type": "email.delivered",
            "data": {"email_id": "ext-123"},
        }

        with (
            patch("app.services.email_service.get_redis", return_value=mock_redis),
            patch("app.services.email_service.settings") as ms,
        ):
            ms.REDIS_WEBHOOK_DEDUP_TTL = 86400
            await handle_resend_webhook(mock_db, payload)

        mock_db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_processes_delivered_event(self):
        from app.models.enums import MessageStatus
        from app.services.email_service import handle_resend_webhook

        msg = _make_message()
        msg.status = MessageStatus.SENT

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(msg)

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True  # not seen before

        payload = {
            "type": "email.delivered",
            "data": {"email_id": "ext-123"},
        }

        with (
            patch("app.services.email_service.get_redis", return_value=mock_redis),
            patch("app.services.email_service.settings") as ms,
            patch("app.infrastructure.websocket_manager.ws_manager") as mock_ws,
        ):
            ms.REDIS_WEBHOOK_DEDUP_TTL = 86400
            mock_ws.broadcast = AsyncMock()
            await handle_resend_webhook(mock_db, payload)

        assert msg.status == MessageStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_processes_opened_event(self):
        from app.models.enums import MessageStatus
        from app.services.email_service import handle_resend_webhook

        msg = _make_message()
        msg.status = MessageStatus.DELIVERED
        msg.opened_at = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(msg)

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        with (
            patch("app.services.email_service.get_redis", return_value=mock_redis),
            patch("app.services.email_service.settings") as ms,
            patch("app.infrastructure.websocket_manager.ws_manager") as mock_ws,
        ):
            ms.REDIS_WEBHOOK_DEDUP_TTL = 86400
            mock_ws.broadcast = AsyncMock()
            await handle_resend_webhook(mock_db, {"type": "email.opened", "data": {"email_id": "ext-456"}})

        assert msg.status == MessageStatus.OPENED
        assert msg.opened_at is not None

    @pytest.mark.asyncio
    async def test_processes_bounced_event_and_auto_suppresses(self):
        from app.models.enums import MessageStatus
        from app.services.email_service import handle_resend_webhook

        msg = _make_message()
        msg.status = MessageStatus.SENT

        # db.execute: first for message fetch, second for existing suppression check
        no_suppression = _scalar(None)
        mock_db = AsyncMock()
        mock_db.execute.side_effect = [_scalar(msg), no_suppression]

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        payload = {
            "type": "email.bounced",
            "data": {"email_id": "ext-789", "to": "bounced@example.com"},
        }

        with (
            patch("app.services.email_service.get_redis", return_value=mock_redis),
            patch("app.services.email_service.settings") as ms,
            patch("app.infrastructure.websocket_manager.ws_manager") as mock_ws,
        ):
            ms.REDIS_WEBHOOK_DEDUP_TTL = 86400
            mock_ws.broadcast = AsyncMock()
            await handle_resend_webhook(mock_db, payload)

        assert msg.status == MessageStatus.BOUNCED
        # Auto-suppress should add a suppression record
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_no_op_for_unknown_event_type(self):
        from app.services.email_service import handle_resend_webhook

        msg = _make_message()
        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar(msg)

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        with (
            patch("app.services.email_service.get_redis", return_value=mock_redis),
            patch("app.services.email_service.settings") as ms,
        ):
            ms.REDIS_WEBHOOK_DEDUP_TTL = 86400
            await handle_resend_webhook(mock_db, {"type": "email.unknown_event", "data": {"email_id": "x"}})

        # No commit since no status update happened for unknown event
        mock_db.commit.assert_not_awaited()
