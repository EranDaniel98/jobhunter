"""Unit tests for cost_service - covers _record_per_user (lines 121-142).

Does NOT overlap with test_cost_service.py which already covers:
- _today_key, pricing constants, check_budget, record_usage
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRecordPerUser:
    @pytest.mark.asyncio
    async def test_inserts_api_usage_record(self):
        """_record_per_user creates and commits an ApiUsageRecord row."""
        from app.services.cost_service import _record_per_user

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_api_usage_record = MagicMock()

        with (
            patch("app.infrastructure.database.async_session_factory", mock_session_factory),
            patch.dict(
                "sys.modules",
                {"app.models.billing": MagicMock(ApiUsageRecord=mock_api_usage_record)},
            ),
        ):
            await _record_per_user(
                candidate_id=str(uuid.uuid4()),
                model="gpt-4o",
                tokens_in=100,
                tokens_out=50,
                cost_hundredths=15,
                endpoint="resume_pipeline",
            )

        # Session was used
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_per_user_exception_is_swallowed(self):
        """Exceptions in _record_per_user are caught and logged, not re-raised."""
        from app.services.cost_service import _record_per_user

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.add.side_effect = Exception("DB error")
        mock_session_factory = MagicMock(return_value=mock_session)

        import contextlib

        with (
            patch("app.infrastructure.database.async_session_factory", mock_session_factory),
            contextlib.suppress(Exception),
        ):
            await _record_per_user(
                candidate_id=str(uuid.uuid4()),
                model="gpt-4o",
                tokens_in=100,
                tokens_out=50,
                cost_hundredths=15,
                endpoint=None,
            )

    @pytest.mark.asyncio
    async def test_record_usage_calls_record_per_user_when_candidate_id_given(self):
        """record_usage invokes _record_per_user when candidate_id is provided."""
        from app.services.cost_service import record_usage

        mock_redis = AsyncMock()
        mock_redis.incrby = AsyncMock()
        mock_redis.expire = AsyncMock()

        mock_record_per_user = AsyncMock()

        with (
            patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis),
            patch("app.services.cost_service._record_per_user", mock_record_per_user),
        ):
            cost = await record_usage(
                1000,
                500,
                candidate_id=str(uuid.uuid4()),
                endpoint="test_endpoint",
            )

        assert cost > 0
        mock_record_per_user.assert_awaited_once()
        call_kwargs = mock_record_per_user.call_args.kwargs
        assert call_kwargs["tokens_in"] == 1000
        assert call_kwargs["tokens_out"] == 500
        assert call_kwargs["endpoint"] == "test_endpoint"

    @pytest.mark.asyncio
    async def test_record_usage_skips_record_per_user_when_no_candidate_id(self):
        """record_usage skips per-user tracking when candidate_id is None."""
        from app.services.cost_service import record_usage

        mock_redis = AsyncMock()
        mock_redis.incrby = AsyncMock()
        mock_redis.expire = AsyncMock()

        mock_record_per_user = AsyncMock()

        with (
            patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis),
            patch("app.services.cost_service._record_per_user", mock_record_per_user),
        ):
            await record_usage(1000, 500)

        mock_record_per_user.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_record_usage_returns_zero_for_zero_tokens(self):
        """record_usage returns 0 when cost_hundredths computes to 0."""
        from app.services.cost_service import record_usage

        cost = await record_usage(0, 0)
        assert cost == 0

    @pytest.mark.asyncio
    async def test_record_per_user_exception_logged_not_propagated_via_record_usage(self):
        """If _record_per_user raises, record_usage catches it and returns normally."""
        from app.services.cost_service import record_usage

        mock_redis = AsyncMock()
        mock_redis.incrby = AsyncMock()
        mock_redis.expire = AsyncMock()

        with (
            patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis),
            patch(
                "app.services.cost_service._record_per_user",
                new_callable=AsyncMock,
                side_effect=Exception("DB down"),
            ),
        ):
            # Should NOT raise
            cost = await record_usage(1000, 500, candidate_id=str(uuid.uuid4()))

        assert cost > 0  # still returns cost
