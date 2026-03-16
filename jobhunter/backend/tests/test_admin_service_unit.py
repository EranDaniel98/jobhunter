"""Unit tests for admin_service - no real DB/Redis required."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_candidate(
    id=None,
    email="admin@example.com",
    full_name="Admin User",
    is_admin=False,
    is_active=True,
    created_at=None,
    preferences=None,
):
    c = MagicMock()
    c.id = id or uuid.uuid4()
    c.email = email
    c.full_name = full_name
    c.is_admin = is_admin
    c.is_active = is_active
    c.created_at = created_at or datetime(2026, 1, 1, tzinfo=UTC)
    c.preferences = preferences or {}
    c.plan_tier = "free"
    return c


def _scalar_result(value):
    """Return a MagicMock that mimics AsyncSession.execute() result returning a scalar."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalar.return_value = value
    r.scalars.return_value.all.return_value = [value] if value else []
    r.all.return_value = []
    r.first.return_value = None
    return r


def _scalars_result(values):
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    r.all.return_value = values
    r.scalar.return_value = len(values)
    r.scalar_one_or_none.return_value = None
    r.first.return_value = None
    return r


# ---------------------------------------------------------------------------
# get_user_detail
# ---------------------------------------------------------------------------


class TestGetUserDetail:
    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        from app.services.admin_service import get_user_detail

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar_result(None)

        result = await get_user_detail(mock_db, uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_user_detail_when_found(self):
        from app.services.admin_service import get_user_detail

        candidate = _make_candidate()
        mock_db = AsyncMock()

        # execute calls: candidate fetch, companies count, messages count, invite join
        count_result = MagicMock()
        count_result.scalar.return_value = 3

        invite_result = MagicMock()
        invite_result.first.return_value = None  # no invite

        candidate_result = MagicMock()
        candidate_result.scalar_one_or_none.return_value = candidate

        mock_db.execute.side_effect = [
            candidate_result,
            count_result,
            count_result,
            invite_result,
        ]

        detail = await get_user_detail(mock_db, candidate.id)
        assert detail is not None
        assert detail.email == candidate.email
        assert detail.is_admin == candidate.is_admin

    @pytest.mark.asyncio
    async def test_includes_invite_info(self):
        from app.services.admin_service import get_user_detail

        candidate = _make_candidate()
        mock_db = AsyncMock()

        invite_code = MagicMock()
        invite_code.code = "INVITE123"
        invite_row = MagicMock()
        invite_row.InviteCode = invite_code
        invite_row.inviter_email = "referrer@example.com"

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        invite_result = MagicMock()
        invite_result.first.return_value = invite_row

        candidate_result = MagicMock()
        candidate_result.scalar_one_or_none.return_value = candidate

        mock_db.execute.side_effect = [
            candidate_result,
            count_result,
            count_result,
            invite_result,
        ]

        detail = await get_user_detail(mock_db, candidate.id)
        assert detail.invited_by_email == "referrer@example.com"
        assert detail.invite_code_used == "INVITE123"


# ---------------------------------------------------------------------------
# toggle_user_admin
# ---------------------------------------------------------------------------


class TestToggleUserAdmin:
    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        from app.services.admin_service import toggle_user_admin

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar_result(None)

        result = await toggle_user_admin(mock_db, uuid.uuid4(), True)
        assert result is None

    @pytest.mark.asyncio
    async def test_sets_is_admin_true(self):
        from app.services.admin_service import toggle_user_admin

        candidate = _make_candidate(is_admin=False)
        mock_db = AsyncMock()

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = candidate
        # For audit log call when admin_id is given: we only call execute once for
        # the candidate lookup here (no admin_id provided)
        mock_db.execute.return_value = result_mock

        returned = await toggle_user_admin(mock_db, candidate.id, True)
        assert candidate.is_admin is True
        assert returned is candidate

    @pytest.mark.asyncio
    async def test_creates_audit_log_when_admin_id_provided(self):
        from app.services.admin_service import toggle_user_admin

        candidate = _make_candidate(is_admin=False)
        admin_id = uuid.uuid4()
        mock_db = AsyncMock()

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = candidate
        mock_db.execute.return_value = result_mock

        with patch("app.services.admin_service.create_audit_log", new_callable=AsyncMock) as mock_audit:
            await toggle_user_admin(mock_db, candidate.id, True, admin_id=admin_id)
            mock_audit.assert_awaited_once()
            call_kwargs = mock_audit.call_args
            assert call_kwargs[0][1] == admin_id  # admin_id positional arg


# ---------------------------------------------------------------------------
# toggle_user_active
# ---------------------------------------------------------------------------


class TestToggleUserActive:
    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        from app.services.admin_service import toggle_user_active

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar_result(None)

        result = await toggle_user_active(mock_db, uuid.uuid4(), False)
        assert result is None

    @pytest.mark.asyncio
    async def test_sets_is_active_false(self):
        from app.services.admin_service import toggle_user_active

        candidate = _make_candidate(is_active=True)
        mock_db = AsyncMock()

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = candidate
        mock_db.execute.return_value = result_mock

        returned = await toggle_user_active(mock_db, candidate.id, False)
        assert candidate.is_active is False
        assert returned is candidate


# ---------------------------------------------------------------------------
# delete_user
# ---------------------------------------------------------------------------


class TestDeleteUser:
    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self):
        from app.services.admin_service import delete_user

        mock_db = AsyncMock()
        mock_db.execute.return_value = _scalar_result(None)

        result = await delete_user(mock_db, uuid.uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_deletes_candidate_and_returns_true(self):
        from app.services.admin_service import delete_user

        candidate = _make_candidate()
        mock_db = AsyncMock()

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = candidate
        mock_db.execute.return_value = result_mock

        result = await delete_user(mock_db, candidate.id)
        assert result is True
        mock_db.delete.assert_awaited_once_with(candidate)
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_creates_audit_log_with_admin_id(self):
        from app.services.admin_service import delete_user

        candidate = _make_candidate()
        admin_id = uuid.uuid4()
        mock_db = AsyncMock()

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = candidate
        mock_db.execute.return_value = result_mock

        with patch("app.services.admin_service.create_audit_log", new_callable=AsyncMock) as mock_audit:
            await delete_user(mock_db, candidate.id, admin_id=admin_id)
            mock_audit.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_activity_feed
# ---------------------------------------------------------------------------


class TestGetActivityFeed:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_events(self):
        from app.services.admin_service import get_activity_feed

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_db.execute.return_value = result_mock

        items = await get_activity_feed(mock_db)
        assert items == []

    @pytest.mark.asyncio
    async def test_returns_activity_items(self):
        from app.services.admin_service import get_activity_feed

        row = MagicMock()
        row.id = uuid.uuid4()
        row.user_email = "user@example.com"
        row.user_name = "User"
        row.event_type = "email_sent"
        row.entity_type = "outreach_message"
        row.details = {}
        row.occurred_at = datetime(2026, 1, 1, tzinfo=UTC)

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = [row]
        mock_db.execute.return_value = result_mock

        items = await get_activity_feed(mock_db)
        assert len(items) == 1
        assert items[0].user_email == "user@example.com"
        assert items[0].event_type == "email_sent"


# ---------------------------------------------------------------------------
# export_users_csv
# ---------------------------------------------------------------------------


class TestExportUsersCSV:
    @pytest.mark.asyncio
    async def test_returns_csv_string_with_header(self):
        from app.services.admin_service import export_users_csv

        row = MagicMock()
        row.id = uuid.uuid4()
        row.email = "test@example.com"
        row.full_name = "Test User"
        row.is_admin = False
        row.is_active = True
        row.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        row.companies_count = 2
        row.messages_sent_count = 5

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = [row]
        mock_db.execute.return_value = result_mock

        csv_output = await export_users_csv(mock_db)
        assert "ID" in csv_output
        assert "Email" in csv_output
        assert "test@example.com" in csv_output

    @pytest.mark.asyncio
    async def test_returns_only_header_when_no_users(self):
        from app.services.admin_service import export_users_csv

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_db.execute.return_value = result_mock

        csv_output = await export_users_csv(mock_db)
        lines = [line for line in csv_output.strip().splitlines() if line]
        assert len(lines) == 1  # just the header


# ---------------------------------------------------------------------------
# get_audit_log
# ---------------------------------------------------------------------------


class TestGetAuditLog:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_logs(self):
        from app.services.admin_service import get_audit_log

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_db.execute.return_value = result_mock

        items = await get_audit_log(mock_db)
        assert items == []

    @pytest.mark.asyncio
    async def test_returns_audit_log_items(self):
        from app.services.admin_service import get_audit_log

        row = MagicMock()
        row.id = uuid.uuid4()
        row.admin_email = "admin@example.com"
        row.admin_name = "Admin"
        row.action = "toggle_admin"
        row.target_email = "user@example.com"
        row.target_name = "User"
        row.details = {"is_admin": True}
        row.created_at = datetime(2026, 1, 1, tzinfo=UTC)

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.all.return_value = [row]
        mock_db.execute.return_value = result_mock

        items = await get_audit_log(mock_db)
        assert len(items) == 1
        assert items[0].action == "toggle_admin"


# ---------------------------------------------------------------------------
# broadcast_email
# ---------------------------------------------------------------------------


class TestBroadcastEmail:
    @pytest.mark.asyncio
    async def test_sends_to_all_eligible_candidates(self):
        from app.services.admin_service import broadcast_email

        admin_id = uuid.uuid4()
        candidate1 = _make_candidate(email="a@example.com")
        candidate2 = _make_candidate(email="b@example.com")

        mock_db = AsyncMock()

        # First execute: get suppressed emails subquery / candidates query
        candidates_result = MagicMock()
        candidates_result.scalars.return_value.all.return_value = [candidate1, candidate2]
        mock_db.execute.return_value = candidates_result

        email_client = AsyncMock()
        email_client.send.return_value = None

        with (
            patch("app.services.admin_service.create_audit_log", new_callable=AsyncMock),
            patch("app.config.settings") as mock_settings,
        ):
            mock_settings.SENDER_EMAIL = "noreply@example.com"
            response = await broadcast_email(mock_db, admin_id, "Subject", "Body", email_client)

        assert response.sent_count == 2
        assert response.skipped_count == 0

    @pytest.mark.asyncio
    async def test_skips_candidates_with_email_notifications_disabled(self):
        from app.services.admin_service import broadcast_email

        admin_id = uuid.uuid4()
        candidate_opted_in = _make_candidate(email="a@example.com")
        candidate_opted_out = _make_candidate(email="b@example.com", preferences={"email_notifications": False})

        mock_db = AsyncMock()
        candidates_result = MagicMock()
        candidates_result.scalars.return_value.all.return_value = [
            candidate_opted_in,
            candidate_opted_out,
        ]
        mock_db.execute.return_value = candidates_result

        email_client = AsyncMock()
        email_client.send.return_value = None

        with (
            patch("app.services.admin_service.create_audit_log", new_callable=AsyncMock),
            patch("app.config.settings") as mock_settings,
        ):
            mock_settings.SENDER_EMAIL = "noreply@example.com"
            response = await broadcast_email(mock_db, admin_id, "Subject", "Body", email_client)

        assert response.sent_count == 1
        assert response.skipped_count == 1

    @pytest.mark.asyncio
    async def test_counts_send_failures_as_skipped(self):
        from app.services.admin_service import broadcast_email

        admin_id = uuid.uuid4()
        candidate = _make_candidate(email="a@example.com")

        mock_db = AsyncMock()
        candidates_result = MagicMock()
        candidates_result.scalars.return_value.all.return_value = [candidate]
        mock_db.execute.return_value = candidates_result

        email_client = AsyncMock()
        email_client.send.side_effect = Exception("SMTP error")

        with (
            patch("app.services.admin_service.create_audit_log", new_callable=AsyncMock),
            patch("app.config.settings") as mock_settings,
        ):
            mock_settings.SENDER_EMAIL = "noreply@example.com"
            response = await broadcast_email(mock_db, admin_id, "Subject", "Body", email_client)

        assert response.sent_count == 0
        assert response.skipped_count == 1
