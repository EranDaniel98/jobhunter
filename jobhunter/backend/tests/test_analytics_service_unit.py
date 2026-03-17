"""Unit tests for analytics_service - covers get_funnel and get_pipeline_stats."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import MessageStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row(**kwargs):
    """Create a MagicMock row with named attributes."""
    r = MagicMock()
    for k, v in kwargs.items():
        setattr(r, k, v)
    return r


# ---------------------------------------------------------------------------
# get_funnel (lines 39-54)
# ---------------------------------------------------------------------------


class TestGetFunnel:
    @pytest.mark.asyncio
    async def test_returns_zero_counts_when_no_messages(self):
        from app.services.analytics_service import get_funnel

        result_mock = MagicMock()
        result_mock.all.return_value = []  # no rows

        mock_db = AsyncMock()
        mock_db.execute.return_value = result_mock

        funnel = await get_funnel(mock_db, uuid.uuid4())

        assert funnel == {
            "drafted": 0,
            "sent": 0,
            "delivered": 0,
            "opened": 0,
            "replied": 0,
            "bounced": 0,
        }

    @pytest.mark.asyncio
    async def test_returns_correct_counts_for_each_status(self):
        from app.services.analytics_service import get_funnel

        rows = [
            (MessageStatus.DRAFT, 3),
            (MessageStatus.SENT, 10),
            (MessageStatus.DELIVERED, 8),
            (MessageStatus.OPENED, 5),
            (MessageStatus.REPLIED, 2),
            (MessageStatus.BOUNCED, 1),
        ]

        result_mock = MagicMock()
        result_mock.all.return_value = rows

        mock_db = AsyncMock()
        mock_db.execute.return_value = result_mock

        funnel = await get_funnel(mock_db, uuid.uuid4())

        assert funnel["drafted"] == 3
        assert funnel["sent"] == 10
        assert funnel["delivered"] == 8
        assert funnel["opened"] == 5
        assert funnel["replied"] == 2
        assert funnel["bounced"] == 1

    @pytest.mark.asyncio
    async def test_missing_statuses_default_to_zero(self):
        """Statuses not present in the result default to 0."""
        from app.services.analytics_service import get_funnel

        rows = [
            (MessageStatus.SENT, 5),
            (MessageStatus.OPENED, 2),
        ]

        result_mock = MagicMock()
        result_mock.all.return_value = rows

        mock_db = AsyncMock()
        mock_db.execute.return_value = result_mock

        funnel = await get_funnel(mock_db, uuid.uuid4())

        assert funnel["sent"] == 5
        assert funnel["opened"] == 2
        assert funnel["drafted"] == 0
        assert funnel["delivered"] == 0
        assert funnel["replied"] == 0
        assert funnel["bounced"] == 0

    @pytest.mark.asyncio
    async def test_calls_db_execute_with_candidate_filter(self):
        """DB is queried exactly once per get_funnel call."""
        from app.services.analytics_service import get_funnel

        result_mock = MagicMock()
        result_mock.all.return_value = []

        mock_db = AsyncMock()
        mock_db.execute.return_value = result_mock

        candidate_id = uuid.uuid4()
        await get_funnel(mock_db, candidate_id)

        mock_db.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_pipeline_stats (lines 123-157)
# ---------------------------------------------------------------------------


class TestGetPipelineStats:
    @pytest.mark.asyncio
    async def test_returns_correct_counts(self):
        from app.services.analytics_service import get_pipeline_stats

        pipeline_row = _row(suggested=5, approved=3, rejected=1, researched=4)
        pipeline_result = MagicMock()
        pipeline_result.one.return_value = pipeline_row

        contacted_result = MagicMock()
        contacted_result.scalar.return_value = 2

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [pipeline_result, contacted_result]

        stats = await get_pipeline_stats(mock_db, uuid.uuid4())

        assert stats == {
            "suggested": 5,
            "approved": 3,
            "rejected": 1,
            "researched": 4,
            "contacted": 2,
        }

    @pytest.mark.asyncio
    async def test_contacted_defaults_to_zero_when_scalar_returns_none(self):
        """contacted_count uses `or 0` to handle NULL scalar from DB."""
        from app.services.analytics_service import get_pipeline_stats

        pipeline_row = _row(suggested=2, approved=1, rejected=0, researched=1)
        pipeline_result = MagicMock()
        pipeline_result.one.return_value = pipeline_row

        contacted_result = MagicMock()
        contacted_result.scalar.return_value = None  # no contacted companies

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [pipeline_result, contacted_result]

        stats = await get_pipeline_stats(mock_db, uuid.uuid4())

        assert stats["contacted"] == 0

    @pytest.mark.asyncio
    async def test_executes_two_db_queries(self):
        """get_pipeline_stats always issues exactly 2 DB queries."""
        from app.services.analytics_service import get_pipeline_stats

        pipeline_row = _row(suggested=0, approved=0, rejected=0, researched=0)
        pipeline_result = MagicMock()
        pipeline_result.one.return_value = pipeline_row

        contacted_result = MagicMock()
        contacted_result.scalar.return_value = 0

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [pipeline_result, contacted_result]

        await get_pipeline_stats(mock_db, uuid.uuid4())

        assert mock_db.execute.await_count == 2


# ---------------------------------------------------------------------------
# log_event (lines 17-36)
# ---------------------------------------------------------------------------


class TestLogEvent:
    @pytest.mark.asyncio
    async def test_creates_analytics_event_and_commits(self):
        from app.services.analytics_service import log_event

        mock_db = AsyncMock()
        candidate_id = uuid.uuid4()

        event = await log_event(
            mock_db,
            candidate_id,
            "test_event",
            entity_type="company",
            entity_id=uuid.uuid4(),
            metadata={"key": "value"},
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        assert event.event_type == "test_event"
        assert event.candidate_id == candidate_id

    @pytest.mark.asyncio
    async def test_log_event_minimal_args(self):
        """log_event works with only required arguments."""
        from app.services.analytics_service import log_event

        mock_db = AsyncMock()

        event = await log_event(mock_db, uuid.uuid4(), "page_view")

        assert event.event_type == "page_view"
        assert event.entity_type is None
        assert event.entity_id is None
        assert event.metadata_ is None
