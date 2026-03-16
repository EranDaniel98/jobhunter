"""Unit tests for approval_service - no real DB required."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import ActionStatus
from app.services.approval_service import (
    approve_action,
    count_pending,
    create_pending_action,
    expire_stale_actions,
    reject_action,
)


def _scalar_result(value):
    """Return a mock execute result whose scalar_one_or_none returns value."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalar.return_value = value
    return r


def _scalars_result(items):
    """Return a mock execute result whose scalars().all() returns items."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    r = MagicMock()
    r.scalars.return_value = scalars_mock
    return r


# ---------------------------------------------------------------------------
# create_pending_action
# ---------------------------------------------------------------------------


class TestCreatePendingAction:
    @pytest.mark.asyncio
    async def test_create_pending_action(self):
        """Creates PendingAction with PENDING status and correct fields."""
        db = AsyncMock()

        candidate_id = uuid.uuid4()
        entity_id = uuid.uuid4()

        await create_pending_action(
            db,
            candidate_id=candidate_id,
            action_type="send_email",
            entity_id=entity_id,
            ai_reasoning="Drafted email looks good",
            metadata={"key": "value"},
        )

        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()

        added = db.add.call_args[0][0]
        assert added.candidate_id == candidate_id
        assert added.action_type == "send_email"
        assert added.entity_id == entity_id
        assert added.status == ActionStatus.PENDING
        assert added.ai_reasoning == "Drafted email looks good"
        assert added.metadata_ == {"key": "value"}


# ---------------------------------------------------------------------------
# approve_action
# ---------------------------------------------------------------------------


class TestApproveAction:
    @pytest.mark.asyncio
    async def test_approve_action_success(self):
        """PENDING action is set to APPROVED with reviewed_at timestamp."""
        action = MagicMock()
        action.status = ActionStatus.PENDING
        action.id = uuid.uuid4()

        db = AsyncMock()
        db.execute.return_value = _scalar_result(action)

        await approve_action(db, action.id, uuid.uuid4())

        assert action.status == ActionStatus.APPROVED
        assert action.reviewed_at is not None
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_approve_action_not_found(self):
        """Non-existent action returns None."""
        db = AsyncMock()
        db.execute.return_value = _scalar_result(None)

        result = await approve_action(db, uuid.uuid4(), uuid.uuid4())

        assert result is None
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_approve_action_already_processed(self):
        """Non-PENDING action is returned as-is without any change."""
        action = MagicMock()
        action.status = ActionStatus.REJECTED

        db = AsyncMock()
        db.execute.return_value = _scalar_result(action)

        result = await approve_action(db, uuid.uuid4(), uuid.uuid4())

        # Status should NOT have changed
        assert result.status == ActionStatus.REJECTED
        db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# reject_action
# ---------------------------------------------------------------------------


class TestRejectAction:
    @pytest.mark.asyncio
    async def test_reject_action_success(self):
        """PENDING action is set to REJECTED."""
        action = MagicMock()
        action.status = ActionStatus.PENDING
        action.id = uuid.uuid4()

        db = AsyncMock()
        db.execute.return_value = _scalar_result(action)

        await reject_action(db, action.id, uuid.uuid4())

        assert action.status == ActionStatus.REJECTED
        assert action.reviewed_at is not None
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reject_action_not_found(self):
        """Non-existent action returns None."""
        db = AsyncMock()
        db.execute.return_value = _scalar_result(None)

        result = await reject_action(db, uuid.uuid4(), uuid.uuid4())

        assert result is None


# ---------------------------------------------------------------------------
# count_pending
# ---------------------------------------------------------------------------


class TestCountPending:
    @pytest.mark.asyncio
    async def test_count_pending(self):
        """Returns scalar count from DB."""
        db = AsyncMock()
        db.execute.return_value = _scalar_result(7)

        count = await count_pending(db, uuid.uuid4())

        assert count == 7

    @pytest.mark.asyncio
    async def test_count_pending_zero_when_none(self):
        """Returns 0 when DB returns None."""
        db = AsyncMock()
        db.execute.return_value = _scalar_result(None)

        count = await count_pending(db, uuid.uuid4())

        assert count == 0


# ---------------------------------------------------------------------------
# expire_stale_actions
# ---------------------------------------------------------------------------


class TestExpireStaleActions:
    @pytest.mark.asyncio
    async def test_expire_stale_actions(self):
        """Old PENDING actions are set to EXPIRED and commit is called."""
        old_action1 = MagicMock()
        old_action1.status = ActionStatus.PENDING
        old_action1.created_at = datetime.now(UTC) - timedelta(days=40)

        old_action2 = MagicMock()
        old_action2.status = ActionStatus.PENDING
        old_action2.created_at = datetime.now(UTC) - timedelta(days=35)

        db = AsyncMock()
        db.execute.return_value = _scalars_result([old_action1, old_action2])

        count = await expire_stale_actions(db, max_age_days=30)

        assert count == 2
        assert old_action1.status == ActionStatus.EXPIRED
        assert old_action2.status == ActionStatus.EXPIRED
        assert old_action1.reviewed_at is not None
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_expire_stale_actions_none_expired(self):
        """No stale actions → returns 0 and no commit."""
        db = AsyncMock()
        db.execute.return_value = _scalars_result([])

        count = await expire_stale_actions(db, max_age_days=30)

        assert count == 0
        db.commit.assert_not_awaited()
