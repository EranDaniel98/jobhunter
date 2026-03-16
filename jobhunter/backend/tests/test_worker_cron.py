"""Unit tests for worker.py — cron coordinator and chunk worker functions."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# process_followup_chunk
# ---------------------------------------------------------------------------


class TestProcessFollowupChunk:
    @pytest.mark.asyncio
    async def test_skips_missing_message(self):
        """process_one_message returns early when message not found in DB."""
        from app.worker import process_followup_chunk

        msg_id = uuid.uuid4()
        ctx = {}

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        # First execute: scalar_one_or_none returns None → early return
        not_found = MagicMock()
        not_found.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = not_found

        mock_factory = MagicMock(return_value=mock_db)

        with patch("app.infrastructure.database.async_session_factory", mock_factory):
            # Should not raise even though message is missing
            await process_followup_chunk(ctx, [msg_id])

    @pytest.mark.asyncio
    async def test_skips_when_newer_message_exists(self):
        """process_one_message skips when a newer message exists for that contact."""
        from app.worker import process_followup_chunk

        msg_id = uuid.uuid4()
        ctx = {}

        mock_msg = MagicMock()
        mock_msg.id = msg_id
        mock_msg.contact_id = uuid.uuid4()
        mock_msg.candidate_id = uuid.uuid4()
        mock_msg.message_type = "initial"
        mock_msg.created_at = MagicMock()

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        msg_result = MagicMock()
        msg_result.scalar_one_or_none.return_value = mock_msg

        newer_result = MagicMock()
        newer_result.scalar_one_or_none.return_value = uuid.uuid4()  # newer exists

        mock_db.execute.side_effect = [msg_result, newer_result]

        mock_factory = MagicMock(return_value=mock_db)

        with patch("app.infrastructure.database.async_session_factory", mock_factory):
            await process_followup_chunk(ctx, [msg_id])

        # Only 2 execute calls: fetch message + newer check (stops there)
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_when_pending_action_exists(self):
        """process_one_message skips when a pending action already exists."""
        from app.worker import process_followup_chunk

        msg_id = uuid.uuid4()
        ctx = {}

        mock_msg = MagicMock()
        mock_msg.id = msg_id
        mock_msg.contact_id = uuid.uuid4()
        mock_msg.candidate_id = uuid.uuid4()
        mock_msg.message_type = "initial"
        mock_msg.created_at = MagicMock()

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        msg_result = MagicMock()
        msg_result.scalar_one_or_none.return_value = mock_msg

        newer_result = MagicMock()
        newer_result.scalar_one_or_none.return_value = None  # no newer message

        pending_result = MagicMock()
        pending_result.scalar_one_or_none.return_value = uuid.uuid4()  # pending exists

        mock_db.execute.side_effect = [msg_result, newer_result, pending_result]

        mock_factory = MagicMock(return_value=mock_db)

        with patch("app.infrastructure.database.async_session_factory", mock_factory):
            await process_followup_chunk(ctx, [msg_id])

        # 3 execute calls: fetch message + newer check + pending check (stops)
        assert mock_db.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_invokes_graph_when_conditions_met(self):
        """process_one_message invokes the outreach graph when all checks pass."""
        from app.worker import process_followup_chunk

        msg_id = uuid.uuid4()
        ctx = {}

        mock_msg = MagicMock()
        mock_msg.id = msg_id
        mock_msg.contact_id = uuid.uuid4()
        mock_msg.candidate_id = uuid.uuid4()
        mock_msg.message_type = "initial"
        mock_msg.created_at = MagicMock()

        mock_cand = MagicMock()
        mock_cand.plan_tier = "pro"

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        msg_result = MagicMock()
        msg_result.scalar_one_or_none.return_value = mock_msg

        newer_result = MagicMock()
        newer_result.scalar_one_or_none.return_value = None

        pending_result = MagicMock()
        pending_result.scalar_one_or_none.return_value = None

        cand_result = MagicMock()
        cand_result.scalar_one_or_none.return_value = mock_cand

        mock_db.execute.side_effect = [msg_result, newer_result, pending_result, cand_result]

        mock_factory = MagicMock(return_value=mock_db)
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock()
        mock_get_pipeline = MagicMock(return_value=mock_graph)

        with (
            patch("app.infrastructure.database.async_session_factory", mock_factory),
            patch("app.graphs.outreach.get_outreach_pipeline", mock_get_pipeline),
        ):
            await process_followup_chunk(ctx, [msg_id])

        mock_graph.ainvoke.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_uses_free_tier_when_candidate_missing(self):
        """process_one_message defaults to 'free' plan when candidate not found."""
        from app.worker import process_followup_chunk

        msg_id = uuid.uuid4()
        ctx = {}

        mock_msg = MagicMock()
        mock_msg.id = msg_id
        mock_msg.contact_id = uuid.uuid4()
        mock_msg.candidate_id = uuid.uuid4()
        mock_msg.message_type = "followup_1"
        mock_msg.created_at = MagicMock()

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        msg_result = MagicMock()
        msg_result.scalar_one_or_none.return_value = mock_msg

        newer_result = MagicMock()
        newer_result.scalar_one_or_none.return_value = None

        pending_result = MagicMock()
        pending_result.scalar_one_or_none.return_value = None

        cand_result = MagicMock()
        cand_result.scalar_one_or_none.return_value = None  # missing candidate

        mock_db.execute.side_effect = [msg_result, newer_result, pending_result, cand_result]

        mock_factory = MagicMock(return_value=mock_db)
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock()
        mock_get_pipeline = MagicMock(return_value=mock_graph)

        with (
            patch("app.infrastructure.database.async_session_factory", mock_factory),
            patch("app.graphs.outreach.get_outreach_pipeline", mock_get_pipeline),
        ):
            await process_followup_chunk(ctx, [msg_id])

        # Verify graph was still invoked (with free tier)
        mock_graph.ainvoke.assert_awaited_once()
        call_state = mock_graph.ainvoke.call_args[0][0]
        assert call_state["plan_tier"] == "free"

    @pytest.mark.asyncio
    async def test_empty_chunk_succeeds(self):
        """Passing an empty list should complete without error."""
        from app.worker import process_followup_chunk

        ctx = {}
        await process_followup_chunk(ctx, [])


# ---------------------------------------------------------------------------
# run_daily_scout
# ---------------------------------------------------------------------------


class TestRunDailyScout:
    @pytest.mark.asyncio
    async def test_skips_when_lock_not_acquired(self):
        from app.worker import run_daily_scout

        mock_redis = AsyncMock()
        ctx = {"redis": mock_redis}

        with patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=False):
            await run_daily_scout(ctx)

        mock_redis.enqueue_job.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_enqueues_scout_chunks(self):
        from app.worker import run_daily_scout

        cand_id_1 = uuid.uuid4()
        cand_id_2 = uuid.uuid4()

        mock_arq_redis = AsyncMock()
        mock_arq_redis.enqueue_job = AsyncMock()
        ctx = {"redis": mock_arq_redis}

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        scalars_result = MagicMock()
        scalars_result.scalars.return_value.all.return_value = [cand_id_1, cand_id_2]
        mock_db.execute.return_value = scalars_result

        mock_factory = MagicMock(return_value=mock_db)

        with (
            patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=True),
            patch("app.worker.settings") as ms,
            patch("app.infrastructure.database.async_session_factory", mock_factory),
        ):
            ms.ARQ_MAX_CHUNKS_PER_RUN = 10
            ms.ARQ_CHUNK_SIZE = 10
            await run_daily_scout(ctx)

        assert mock_arq_redis.enqueue_job.await_count >= 1
        # Confirm it enqueued the right job name
        call_args = mock_arq_redis.enqueue_job.call_args_list[0]
        assert call_args[0][0] == "process_scout_chunk"

    @pytest.mark.asyncio
    async def test_logs_overflow_when_too_many_candidates(self):
        """When candidates exceed capacity, logs a warning (deferred > 0 branch)."""
        from app.worker import run_daily_scout

        cand_ids = [uuid.uuid4() for _ in range(5)]
        mock_arq_redis = AsyncMock()
        ctx = {"redis": mock_arq_redis}

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        scalars_result = MagicMock()
        scalars_result.scalars.return_value.all.return_value = cand_ids
        mock_db.execute.return_value = scalars_result

        mock_factory = MagicMock(return_value=mock_db)

        with (
            patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=True),
            patch("app.worker.settings") as ms,
            patch("app.infrastructure.database.async_session_factory", mock_factory),
        ):
            ms.ARQ_MAX_CHUNKS_PER_RUN = 1
            ms.ARQ_CHUNK_SIZE = 2  # max 2 items total, 5 → deferred=3
            await run_daily_scout(ctx)

        # Only 1 chunk of 2 items should be enqueued
        assert mock_arq_redis.enqueue_job.await_count == 1

    @pytest.mark.asyncio
    async def test_no_candidates_no_chunks_enqueued(self):
        """When no active candidates exist, nothing is enqueued."""
        from app.worker import run_daily_scout

        mock_arq_redis = AsyncMock()
        ctx = {"redis": mock_arq_redis}

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        scalars_result = MagicMock()
        scalars_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = scalars_result

        mock_factory = MagicMock(return_value=mock_db)

        with (
            patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=True),
            patch("app.worker.settings") as ms,
            patch("app.infrastructure.database.async_session_factory", mock_factory),
        ):
            ms.ARQ_MAX_CHUNKS_PER_RUN = 10
            ms.ARQ_CHUNK_SIZE = 10
            await run_daily_scout(ctx)

        mock_arq_redis.enqueue_job.assert_not_awaited()


# ---------------------------------------------------------------------------
# process_scout_chunk
# ---------------------------------------------------------------------------


class TestProcessScoutChunk:
    @pytest.mark.asyncio
    async def test_invokes_scout_pipeline(self):
        """process_one_candidate fetches plan_tier and invokes the scout graph."""
        from app.worker import process_scout_chunk

        cand_id = uuid.uuid4()
        ctx = {}

        mock_cand = MagicMock()
        mock_cand.plan_tier = "pro"

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        cand_result = MagicMock()
        cand_result.scalar_one_or_none.return_value = mock_cand
        mock_db.execute.return_value = cand_result

        mock_factory = MagicMock(return_value=mock_db)
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock()
        mock_get_pipeline = MagicMock(return_value=mock_graph)

        with (
            patch("app.infrastructure.database.async_session_factory", mock_factory),
            patch("app.graphs.scout_pipeline.get_scout_pipeline", mock_get_pipeline),
        ):
            await process_scout_chunk(ctx, [cand_id])

        mock_graph.ainvoke.assert_awaited_once()
        call_state = mock_graph.ainvoke.call_args[0][0]
        assert call_state["candidate_id"] == str(cand_id)
        assert call_state["plan_tier"] == "pro"

    @pytest.mark.asyncio
    async def test_uses_free_tier_when_candidate_missing(self):
        """Defaults to free when candidate not found."""
        from app.worker import process_scout_chunk

        cand_id = uuid.uuid4()
        ctx = {}

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        cand_result = MagicMock()
        cand_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = cand_result

        mock_factory = MagicMock(return_value=mock_db)
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock()
        mock_get_pipeline = MagicMock(return_value=mock_graph)

        with (
            patch("app.infrastructure.database.async_session_factory", mock_factory),
            patch("app.graphs.scout_pipeline.get_scout_pipeline", mock_get_pipeline),
        ):
            await process_scout_chunk(ctx, [cand_id])

        call_state = mock_graph.ainvoke.call_args[0][0]
        assert call_state["plan_tier"] == "free"

    @pytest.mark.asyncio
    async def test_isolates_per_candidate_errors(self):
        """If graph raises for one candidate, others still run."""
        from app.worker import process_scout_chunk

        cand_id_1 = uuid.uuid4()
        cand_id_2 = uuid.uuid4()
        ctx = {}

        call_count = 0

        mock_cand = MagicMock()
        mock_cand.plan_tier = "free"

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        cand_result = MagicMock()
        cand_result.scalar_one_or_none.return_value = mock_cand
        mock_db.execute.return_value = cand_result

        mock_factory = MagicMock(return_value=mock_db)

        async def failing_then_passing(state, config=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("graph error")

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(side_effect=failing_then_passing)
        mock_get_pipeline = MagicMock(return_value=mock_graph)

        with (
            patch("app.infrastructure.database.async_session_factory", mock_factory),
            patch("app.graphs.scout_pipeline.get_scout_pipeline", mock_get_pipeline),
        ):
            # Should not raise
            await process_scout_chunk(ctx, [cand_id_1, cand_id_2])

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_empty_chunk(self):
        """Empty list should succeed without calling the pipeline."""
        from app.worker import process_scout_chunk

        ctx = {}
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock()
        mock_get_pipeline = MagicMock(return_value=mock_graph)

        with patch("app.graphs.scout_pipeline.get_scout_pipeline", mock_get_pipeline):
            await process_scout_chunk(ctx, [])

        mock_graph.ainvoke.assert_not_awaited()


# ---------------------------------------------------------------------------
# run_weekly_analytics
# ---------------------------------------------------------------------------


class TestRunWeeklyAnalytics:
    @pytest.mark.asyncio
    async def test_skips_when_lock_not_acquired(self):
        from app.worker import run_weekly_analytics

        mock_redis = AsyncMock()
        ctx = {"redis": mock_redis}

        with patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=False):
            await run_weekly_analytics(ctx)

        mock_redis.enqueue_job.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_enqueues_analytics_chunks(self):
        from app.worker import run_weekly_analytics

        cand_id_1 = uuid.uuid4()
        cand_id_2 = uuid.uuid4()

        mock_arq_redis = AsyncMock()
        mock_arq_redis.enqueue_job = AsyncMock()
        ctx = {"redis": mock_arq_redis}

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        scalars_result = MagicMock()
        scalars_result.scalars.return_value.all.return_value = [cand_id_1, cand_id_2]
        mock_db.execute.return_value = scalars_result

        mock_factory = MagicMock(return_value=mock_db)

        with (
            patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=True),
            patch("app.worker.settings") as ms,
            patch("app.infrastructure.database.async_session_factory", mock_factory),
        ):
            ms.ARQ_MAX_CHUNKS_PER_RUN = 10
            ms.ARQ_CHUNK_SIZE = 10
            await run_weekly_analytics(ctx)

        assert mock_arq_redis.enqueue_job.await_count >= 1
        call_args = mock_arq_redis.enqueue_job.call_args_list[0]
        assert call_args[0][0] == "process_analytics_chunk"

    @pytest.mark.asyncio
    async def test_overflow_branch(self):
        """Deferred > 0 branch: only processes first max_items candidates."""
        from app.worker import run_weekly_analytics

        cand_ids = [uuid.uuid4() for _ in range(10)]
        mock_arq_redis = AsyncMock()
        ctx = {"redis": mock_arq_redis}

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        scalars_result = MagicMock()
        scalars_result.scalars.return_value.all.return_value = cand_ids
        mock_db.execute.return_value = scalars_result

        mock_factory = MagicMock(return_value=mock_db)

        with (
            patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=True),
            patch("app.worker.settings") as ms,
            patch("app.infrastructure.database.async_session_factory", mock_factory),
        ):
            ms.ARQ_MAX_CHUNKS_PER_RUN = 1
            ms.ARQ_CHUNK_SIZE = 3  # max 3 items, 10 → deferred=7
            await run_weekly_analytics(ctx)

        # 1 chunk of 3 items
        assert mock_arq_redis.enqueue_job.await_count == 1

    @pytest.mark.asyncio
    async def test_no_candidates_no_enqueue(self):
        from app.worker import run_weekly_analytics

        mock_arq_redis = AsyncMock()
        ctx = {"redis": mock_arq_redis}

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        scalars_result = MagicMock()
        scalars_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = scalars_result

        mock_factory = MagicMock(return_value=mock_db)

        with (
            patch("app.worker._acquire_run_lock", new_callable=AsyncMock, return_value=True),
            patch("app.worker.settings") as ms,
            patch("app.infrastructure.database.async_session_factory", mock_factory),
        ):
            ms.ARQ_MAX_CHUNKS_PER_RUN = 10
            ms.ARQ_CHUNK_SIZE = 10
            await run_weekly_analytics(ctx)

        mock_arq_redis.enqueue_job.assert_not_awaited()


# ---------------------------------------------------------------------------
# process_analytics_chunk
# ---------------------------------------------------------------------------


class TestProcessAnalyticsChunk:
    @pytest.mark.asyncio
    async def test_invokes_analytics_pipeline(self):
        """process_one_candidate invokes the analytics graph for each candidate."""
        from app.worker import process_analytics_chunk

        cand_id = uuid.uuid4()
        ctx = {}

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock()
        mock_get_pipeline = MagicMock(return_value=mock_graph)

        with patch("app.graphs.analytics_pipeline.get_analytics_pipeline", mock_get_pipeline):
            await process_analytics_chunk(ctx, [cand_id])

        mock_graph.ainvoke.assert_awaited_once()
        call_state = mock_graph.ainvoke.call_args[0][0]
        assert call_state["candidate_id"] == str(cand_id)
        assert call_state["include_email"] is True
        assert call_state["status"] == "pending"

    @pytest.mark.asyncio
    async def test_isolates_per_candidate_errors(self):
        """Errors in one candidate do not abort others."""
        from app.worker import process_analytics_chunk

        cand_id_1 = uuid.uuid4()
        cand_id_2 = uuid.uuid4()
        ctx = {}

        call_count = 0

        async def failing_then_passing(state, config=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("analytics error")

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(side_effect=failing_then_passing)
        mock_get_pipeline = MagicMock(return_value=mock_graph)

        with patch("app.graphs.analytics_pipeline.get_analytics_pipeline", mock_get_pipeline):
            await process_analytics_chunk(ctx, [cand_id_1, cand_id_2])

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_empty_chunk(self):
        """Empty candidate list is handled without error."""
        from app.worker import process_analytics_chunk

        ctx = {}
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock()
        mock_get_pipeline = MagicMock(return_value=mock_graph)

        with patch("app.graphs.analytics_pipeline.get_analytics_pipeline", mock_get_pipeline):
            await process_analytics_chunk(ctx, [])

        mock_graph.ainvoke.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_uses_correct_state_shape(self):
        """The state dict passed to the analytics graph has all required keys."""
        from app.worker import process_analytics_chunk

        cand_id = uuid.uuid4()
        ctx = {}

        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock()
        mock_get_pipeline = MagicMock(return_value=mock_graph)

        with patch("app.graphs.analytics_pipeline.get_analytics_pipeline", mock_get_pipeline):
            await process_analytics_chunk(ctx, [cand_id])

        state = mock_graph.ainvoke.call_args[0][0]
        required_keys = {"candidate_id", "include_email", "raw_data", "insights", "insights_saved", "status", "error"}
        assert required_keys.issubset(state.keys())
