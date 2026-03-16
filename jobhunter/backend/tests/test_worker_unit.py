"""Unit tests for worker.py - ARQ background task functions."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestChunkList:
    def test_splits_into_chunks(self):
        from app.worker import _chunk_list

        result = _chunk_list([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]

    def test_empty_list_returns_empty(self):
        from app.worker import _chunk_list

        assert _chunk_list([], 3) == []

    def test_single_chunk_when_size_larger_than_list(self):
        from app.worker import _chunk_list

        assert _chunk_list([1, 2], 10) == [[1, 2]]


# ---------------------------------------------------------------------------
# _process_chunk
# ---------------------------------------------------------------------------


class TestProcessChunk:
    @pytest.mark.asyncio
    async def test_counts_successes(self):
        from app.worker import _process_chunk

        processor = AsyncMock(return_value=None)
        result = await _process_chunk([1, 2, 3], processor, 3, "test_job")
        assert result["succeeded"] == 3
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_counts_failures_and_isolates_errors(self):
        from app.worker import _process_chunk

        async def flaky(item):
            if item == 2:
                raise RuntimeError("boom")

        result = await _process_chunk([1, 2, 3], flaky, 3, "test_job")
        assert result["succeeded"] == 2
        assert result["failed"] == 1

    @pytest.mark.asyncio
    async def test_empty_list_returns_zero_counts(self):
        from app.worker import _process_chunk

        processor = AsyncMock()
        result = await _process_chunk([], processor, 3, "test_job")
        assert result == {"succeeded": 0, "failed": 0}


# ---------------------------------------------------------------------------
# _acquire_run_lock
# ---------------------------------------------------------------------------


class TestAcquireRunLock:
    @pytest.mark.asyncio
    async def test_returns_true_when_lock_acquired(self):
        from app.worker import _acquire_run_lock

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        with patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis):
            result = await _acquire_run_lock("test_job", 60)

        assert result is True
        mock_redis.set.assert_awaited_once_with("lock:cron:test_job", "1", nx=True, ex=60)

    @pytest.mark.asyncio
    async def test_returns_false_when_lock_already_held(self):
        from app.worker import _acquire_run_lock

        mock_redis = AsyncMock()
        mock_redis.set.return_value = None  # Redis SET NX returns None when key exists

        with patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis):
            result = await _acquire_run_lock("test_job", 60)

        # None is falsy
        assert not result


# ---------------------------------------------------------------------------
# check_followup_due
# ---------------------------------------------------------------------------


class TestCheckFollowupDue:
    @pytest.mark.asyncio
    async def test_skips_when_lock_not_acquired(self):
        from app.worker import check_followup_due

        ctx = {"redis": AsyncMock()}

        with patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=False):
            await check_followup_due(ctx)

        ctx["redis"].enqueue_job.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_enqueues_chunks_for_due_messages(self):
        from app.worker import check_followup_due

        msg_id_1 = uuid.uuid4()
        msg_id_2 = uuid.uuid4()

        mock_arq_redis = AsyncMock()
        mock_arq_redis.enqueue_job = AsyncMock()

        ctx = {"redis": mock_arq_redis}

        mock_db = AsyncMock()
        scalars_result = MagicMock()
        scalars_result.scalars.return_value.all.return_value = [msg_id_1, msg_id_2]
        mock_db.execute.return_value = scalars_result
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_db)

        with (
            patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=True),
            patch("app.worker.settings") as ms,
            patch("app.infrastructure.database.async_session_factory", mock_factory),
        ):
            ms.ARQ_MAX_CHUNKS_PER_RUN = 10
            ms.ARQ_CHUNK_SIZE = 10
            await check_followup_due(ctx)

        # Should have enqueued chunks for the 2 message IDs
        assert mock_arq_redis.enqueue_job.await_count >= 1


# ---------------------------------------------------------------------------
# expire_stale_actions
# ---------------------------------------------------------------------------


class TestExpireStaleActions:
    @pytest.mark.asyncio
    async def test_calls_expire_service(self):
        from app.worker import expire_stale_actions

        ctx = {}

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_db)

        mock_expire_fn = AsyncMock(return_value=3)

        with (
            patch("app.infrastructure.database.async_session_factory", mock_factory),
            patch("app.services.approval_service.expire_stale_actions", mock_expire_fn),
        ):
            # Just verify it doesn't raise
            await expire_stale_actions(ctx)


# ---------------------------------------------------------------------------
# send_approved_message
# ---------------------------------------------------------------------------


class TestSendApprovedMessage:
    @pytest.mark.asyncio
    async def test_sends_message_successfully(self):
        from app.worker import send_approved_message

        outreach_id = str(uuid.uuid4())
        ctx = {}

        mock_outreach = MagicMock()
        mock_outreach.candidate_id = uuid.uuid4()

        mock_candidate = MagicMock()
        mock_candidate.plan_tier = "pro"

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        outreach_result = MagicMock()
        outreach_result.scalar_one_or_none.return_value = mock_outreach
        cand_result = MagicMock()
        cand_result.scalar_one_or_none.return_value = mock_candidate
        mock_db.execute.side_effect = [outreach_result, cand_result]

        mock_factory = MagicMock(return_value=mock_db)
        mock_send = AsyncMock(return_value=mock_outreach)

        with (
            patch("app.infrastructure.database.async_session_factory", mock_factory),
            patch("app.services.email_service.send_outreach", mock_send),
        ):
            await send_approved_message(ctx, outreach_id)

    @pytest.mark.asyncio
    async def test_handles_send_error_gracefully(self):
        from app.worker import send_approved_message

        outreach_id = str(uuid.uuid4())
        ctx = {}

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        mock_outreach = MagicMock()
        mock_outreach.candidate_id = uuid.uuid4()

        mock_candidate = MagicMock()
        mock_candidate.plan_tier = "free"

        outreach_result = MagicMock()
        outreach_result.scalar_one_or_none.return_value = mock_outreach
        cand_result = MagicMock()
        cand_result.scalar_one_or_none.return_value = mock_candidate
        mock_db.execute.side_effect = [outreach_result, cand_result]

        mock_factory = MagicMock(return_value=mock_db)
        mock_send = AsyncMock(side_effect=ValueError("send failed"))

        with (
            patch("app.infrastructure.database.async_session_factory", mock_factory),
            patch("app.services.email_service.send_outreach", mock_send),
        ):
            # Should not raise - errors are caught and logged
            await send_approved_message(ctx, outreach_id)


# ---------------------------------------------------------------------------
# startup / shutdown
# ---------------------------------------------------------------------------


class TestStartupShutdown:
    @pytest.mark.asyncio
    async def test_startup_sets_db_factory(self):
        from app.worker import startup

        ctx = {}
        with (
            patch("app.infrastructure.redis_client.init_redis", new_callable=AsyncMock),
            patch("app.infrastructure.database.async_session_factory"),
        ):
            await startup(ctx)
        assert "db_factory" in ctx

    @pytest.mark.asyncio
    async def test_shutdown_runs_without_error(self):
        from app.worker import shutdown

        ctx = {}
        with patch("app.infrastructure.redis_client.close_redis", new_callable=AsyncMock):
            await shutdown(ctx)  # should not raise
