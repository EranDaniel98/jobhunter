"""Additional unit tests for approval_service - covers _enrich_context,
list_pending_actions, get_pending_action, and reject_action non-pending path."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import ActionStatus
from app.services.approval_service import (
    _enrich_context,
    get_pending_action,
    list_pending_actions,
    reject_action,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_result(row):
    """Return a mock execute result whose one_or_none() returns row."""
    r = MagicMock()
    r.one_or_none.return_value = row
    return r


def _scalar_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalar.return_value = value
    return r


def _rows_result(rows):
    r = MagicMock()
    r.all.return_value = rows
    return r


def _make_action(**kwargs):
    action = MagicMock()
    action.id = kwargs.get("id", uuid.uuid4())
    action.candidate_id = kwargs.get("candidate_id", uuid.uuid4())
    action.action_type = kwargs.get("action_type", "send_email")
    action.entity_type = kwargs.get("entity_type", "outreach_message")
    action.entity_id = kwargs.get("entity_id", uuid.uuid4())
    action.status = kwargs.get("status", ActionStatus.PENDING)
    action.ai_reasoning = kwargs.get("ai_reasoning")
    action.metadata_ = kwargs.get("metadata_")
    action.reviewed_at = kwargs.get("reviewed_at")
    action.expires_at = kwargs.get("expires_at")
    action.created_at = kwargs.get("created_at", datetime.now(UTC))
    return action


# ---------------------------------------------------------------------------
# _enrich_context
# ---------------------------------------------------------------------------


class TestEnrichContext:
    @pytest.mark.asyncio
    async def test_non_outreach_entity_type_returns_empty(self):
        """Non-outreach entity type returns empty dict without DB calls."""
        action = _make_action(entity_type="job_application")
        db = AsyncMock()

        result = await _enrich_context(db, action)

        assert result == {}
        db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_message_not_found_returns_empty(self):
        """Missing OutreachMessage returns empty dict."""
        action = _make_action(entity_type="outreach_message")
        db = AsyncMock()
        db.execute.return_value = _scalar_result(None)

        result = await _enrich_context(db, action)

        assert result == {}

    @pytest.mark.asyncio
    async def test_message_found_no_contact(self):
        """OutreachMessage exists but no contact returns partial context."""
        action = _make_action(entity_type="outreach_message")

        msg = MagicMock()
        msg.contact_id = uuid.uuid4()
        msg.subject = "Hello"
        msg.body = "Body text"
        msg.message_type = "initial"
        msg.channel = "email"

        db = AsyncMock()
        # First call returns msg, second call returns no contact
        db.execute.side_effect = [
            _scalar_result(msg),
            _scalar_result(None),
        ]

        result = await _enrich_context(db, action)

        assert result["message_subject"] == "Hello"
        assert result["message_body"] == "Body text"
        assert result["contact_name"] is None
        assert result["company_name"] is None
        assert result["message_type"] == "initial"
        assert result["channel"] == "email"

    @pytest.mark.asyncio
    async def test_message_contact_and_company_found(self):
        """Full context with message, contact, and company."""
        action = _make_action(entity_type="outreach_message")

        msg = MagicMock()
        msg.contact_id = uuid.uuid4()
        msg.subject = "Exciting opportunity"
        msg.body = "Long body"
        msg.message_type = "followup_1"
        msg.channel = "email"

        contact = MagicMock()
        contact.company_id = uuid.uuid4()
        contact.full_name = "Jane Doe"

        company = MagicMock()
        company.name = "Acme Corp"

        db = AsyncMock()
        db.execute.side_effect = [
            _scalar_result(msg),
            _scalar_result(contact),
            _scalar_result(company),
        ]

        result = await _enrich_context(db, action)

        assert result["contact_name"] == "Jane Doe"
        assert result["company_name"] == "Acme Corp"
        assert result["message_subject"] == "Exciting opportunity"

    @pytest.mark.asyncio
    async def test_contact_found_but_no_company(self):
        """Contact exists but company is None → company_name is None."""
        action = _make_action(entity_type="outreach_message")

        msg = MagicMock()
        msg.contact_id = uuid.uuid4()
        msg.subject = "Hi"
        msg.body = "Body"
        msg.message_type = "initial"
        msg.channel = "linkedin"

        contact = MagicMock()
        contact.company_id = uuid.uuid4()
        contact.full_name = "Bob Smith"

        db = AsyncMock()
        db.execute.side_effect = [
            _scalar_result(msg),
            _scalar_result(contact),
            _scalar_result(None),  # no company
        ]

        result = await _enrich_context(db, action)

        assert result["contact_name"] == "Bob Smith"
        assert result["company_name"] is None


# ---------------------------------------------------------------------------
# list_pending_actions
# ---------------------------------------------------------------------------


class TestListPendingActions:
    def _db_for_list(self, rows, total=None):
        """Build mock DB that returns total on first call and rows on second."""
        total_val = total if total is not None else len(rows)
        db = AsyncMock()

        count_result = MagicMock()
        count_result.scalar.return_value = total_val

        rows_result = MagicMock()
        rows_result.all.return_value = rows

        db.execute.side_effect = [count_result, rows_result]
        return db

    def _make_row(
        self, action, subject="Sub", body="Body", msg_type="initial", channel="email", contact="Alice", company="Acme"
    ):
        row = MagicMock()
        row.__getitem__ = lambda self, idx: action if idx == 0 else None
        row.msg_subject = subject
        row.msg_body = body
        row.msg_type = msg_type
        row.msg_channel = channel
        row.contact_name = contact
        row.company_name = company
        return row

    @pytest.mark.asyncio
    async def test_returns_list_and_total(self):
        """Returns response list and total count from DB."""
        candidate_id = uuid.uuid4()
        action = _make_action(candidate_id=candidate_id)
        row = self._make_row(action)

        db = self._db_for_list([row], total=1)

        responses, total = await list_pending_actions(db, candidate_id)

        assert total == 1
        assert len(responses) == 1

    @pytest.mark.asyncio
    async def test_empty_returns_zero(self):
        """No actions returns empty list and zero total."""
        candidate_id = uuid.uuid4()
        db = self._db_for_list([], total=0)

        responses, total = await list_pending_actions(db, candidate_id)

        assert total == 0
        assert responses == []

    @pytest.mark.asyncio
    async def test_with_status_filter(self):
        """Status filter is applied (DB is queried twice)."""
        candidate_id = uuid.uuid4()
        db = self._db_for_list([], total=0)

        _responses, _total = await list_pending_actions(db, candidate_id, status="pending")

        assert db.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_with_action_type_filter(self):
        """Action type filter queries DB twice."""
        candidate_id = uuid.uuid4()
        db = self._db_for_list([], total=0)

        _responses, _total = await list_pending_actions(db, candidate_id, action_type="send_email")

        assert db.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_context_mapped_to_response(self):
        """Row fields are mapped into the PendingActionResponse."""
        candidate_id = uuid.uuid4()
        action = _make_action(candidate_id=candidate_id)
        row = self._make_row(
            action,
            subject="Test Subject",
            body="Test Body",
            msg_type="followup_1",
            channel="email",
            contact="John Doe",
            company="MegaCorp",
        )

        db = self._db_for_list([row], total=1)

        responses, _total = await list_pending_actions(db, candidate_id)

        resp = responses[0]
        assert resp.message_subject == "Test Subject"
        assert resp.message_body == "Test Body"
        assert resp.message_type == "followup_1"
        assert resp.channel == "email"
        assert resp.contact_name == "John Doe"
        assert resp.company_name == "MegaCorp"


# ---------------------------------------------------------------------------
# get_pending_action
# ---------------------------------------------------------------------------


class TestGetPendingAction:
    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        """Returns None when action doesn't exist."""
        db = AsyncMock()
        result = MagicMock()
        result.one_or_none.return_value = None
        db.execute.return_value = result

        resp = await get_pending_action(db, uuid.uuid4(), uuid.uuid4())

        assert resp is None

    @pytest.mark.asyncio
    async def test_returns_response_when_found(self):
        """Returns PendingActionResponse with context from joined row."""
        candidate_id = uuid.uuid4()
        action = _make_action(candidate_id=candidate_id)

        row = MagicMock()
        row.__getitem__ = lambda self, idx: action if idx == 0 else None
        row.msg_subject = "Hi"
        row.msg_body = "Body"
        row.msg_type = "initial"
        row.msg_channel = "email"
        row.contact_name = "Alice"
        row.company_name = "Stripe"

        db = AsyncMock()
        result = MagicMock()
        result.one_or_none.return_value = row
        db.execute.return_value = result

        resp = await get_pending_action(db, action.id, candidate_id)

        assert resp is not None
        assert resp.message_subject == "Hi"
        assert resp.contact_name == "Alice"
        assert resp.company_name == "Stripe"


# ---------------------------------------------------------------------------
# reject_action — non-pending path
# ---------------------------------------------------------------------------


class TestRejectActionNonPending:
    @pytest.mark.asyncio
    async def test_reject_action_already_processed(self):
        """Non-PENDING action is returned as-is without any DB write."""
        action = MagicMock()
        action.status = ActionStatus.APPROVED

        db = AsyncMock()
        r = MagicMock()
        r.scalar_one_or_none.return_value = action
        db.execute.return_value = r

        result = await reject_action(db, uuid.uuid4(), uuid.uuid4())

        assert result.status == ActionStatus.APPROVED
        db.commit.assert_not_awaited()
