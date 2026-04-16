"""Verify run_daily_scout filters by last_seen_at and plan-tier frequency.

These tests mock the DB layer (matching test_worker_cron.py style) — the real
SQL `last_seen_at >= cutoff` filter is exercised implicitly via the mocked rows.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_db_mock(rows: list[tuple]):
    """Build a mock `async_session_factory` that returns rows from `.execute().all()`."""
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    result_mock = MagicMock()
    result_mock.all.return_value = rows
    # Also support scalars().all() for the analytics coordinator
    result_mock.scalars.return_value.all.return_value = [r[0] for r in rows]
    mock_db.execute.return_value = result_mock

    return MagicMock(return_value=mock_db)


def _collect_enqueued(mock_redis, job_name: str) -> set:
    out: set = set()
    for call in mock_redis.enqueue_job.call_args_list:
        if call.args[0] == job_name:
            out.update(call.args[1])
    return out


@pytest.mark.asyncio
async def test_paid_tier_is_enqueued():
    """Hunter tier has scout_frequency_days=1 → enqueued every day."""
    from app.worker import run_daily_scout

    cand_id = uuid.uuid4()
    mock_factory = _make_db_mock([(cand_id, "hunter")])
    mock_redis = AsyncMock()

    with (
        patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=True),
        patch("app.infrastructure.database.async_session_factory", mock_factory),
    ):
        await run_daily_scout({"redis": mock_redis})

    assert cand_id in _collect_enqueued(mock_redis, "process_scout_chunk")


@pytest.mark.asyncio
async def test_free_tier_skipped_on_non_monday():
    """Free tier has scout_frequency_days=7 → skipped on non-Monday."""
    from app import worker

    cand_id = uuid.uuid4()
    mock_factory = _make_db_mock([(cand_id, "free")])
    mock_redis = AsyncMock()

    # Wednesday 2026-04-15
    class _Wed(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 15, 9, 0, tzinfo=UTC)

    with (
        patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=True),
        patch("app.infrastructure.database.async_session_factory", mock_factory),
        patch("app.worker.datetime", _Wed),
    ):
        await worker.run_daily_scout({"redis": mock_redis})

    assert cand_id not in _collect_enqueued(mock_redis, "process_scout_chunk")


@pytest.mark.asyncio
async def test_free_tier_runs_on_monday():
    """Free tier is enqueued on Mondays."""
    from app import worker

    cand_id = uuid.uuid4()
    mock_factory = _make_db_mock([(cand_id, "free")])
    mock_redis = AsyncMock()

    # Monday 2026-04-13
    class _Mon(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 13, 9, 0, tzinfo=UTC)

    with (
        patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=True),
        patch("app.infrastructure.database.async_session_factory", mock_factory),
        patch("app.worker.datetime", _Mon),
    ):
        await worker.run_daily_scout({"redis": mock_redis})

    assert cand_id in _collect_enqueued(mock_redis, "process_scout_chunk")


@pytest.mark.asyncio
async def test_unknown_tier_treated_as_free():
    """Unrecognised plan_tier should be safe-defaulted to free (weekly)."""
    from app import worker

    cand_id = uuid.uuid4()
    mock_factory = _make_db_mock([(cand_id, "nonexistent_tier")])
    mock_redis = AsyncMock()

    # Wednesday → free skipped
    class _Wed(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 15, 9, 0, tzinfo=UTC)

    with (
        patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=True),
        patch("app.infrastructure.database.async_session_factory", mock_factory),
        patch("app.worker.datetime", _Wed),
    ):
        await worker.run_daily_scout({"redis": mock_redis})

    assert cand_id not in _collect_enqueued(mock_redis, "process_scout_chunk")


@pytest.mark.asyncio
async def test_mixed_tiers_on_non_monday_only_paid_enqueued():
    """Non-Monday: only paid-tier candidates (freq=1) should be enqueued."""
    from app import worker

    free_id = uuid.uuid4()
    hunter_id = uuid.uuid4()
    explorer_id = uuid.uuid4()
    mock_factory = _make_db_mock(
        [
            (free_id, "free"),
            (hunter_id, "hunter"),
            (explorer_id, "explorer"),
        ]
    )
    mock_redis = AsyncMock()

    class _Wed(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 4, 15, 9, 0, tzinfo=UTC)

    with (
        patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=True),
        patch("app.infrastructure.database.async_session_factory", mock_factory),
        patch("app.worker.datetime", _Wed),
    ):
        await worker.run_daily_scout({"redis": mock_redis})

    enqueued = _collect_enqueued(mock_redis, "process_scout_chunk")
    assert hunter_id in enqueued
    assert explorer_id in enqueued
    assert free_id not in enqueued
