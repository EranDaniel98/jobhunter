"""Tests for the daily spending circuit breaker and cost service edge cases.

Complements test_cost_service.py with additional integration-level scenarios.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.services.cost_service import (
    DAILY_COST_KEY_PREFIX,
    INPUT_COST_PER_TOKEN,
    OUTPUT_COST_PER_TOKEN,
    _today_key,
    check_budget,
    record_usage,
)

# ---------------------------------------------------------------------------
# _today_key
# ---------------------------------------------------------------------------


class TestTodayKey:
    def test_prefix_format(self):
        key = _today_key()
        assert key.startswith(f"{DAILY_COST_KEY_PREFIX}:")

    def test_date_part_length(self):
        key = _today_key()
        date_part = key.split(":")[-1]
        assert len(date_part) == 10  # YYYY-MM-DD

    def test_contains_hyphens(self):
        key = _today_key()
        date_part = key.split(":")[-1]
        parts = date_part.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # year
        assert len(parts[1]) == 2  # month
        assert len(parts[2]) == 2  # day


# ---------------------------------------------------------------------------
# check_budget edge cases
# ---------------------------------------------------------------------------


class TestCheckBudget:
    @pytest.mark.asyncio
    async def test_exactly_at_limit_triggers(self):
        """Cost exactly equal to limit should trigger circuit breaker."""
        mock_redis = AsyncMock()
        # 5000 cents * 100 hundredths = 500000 hundredths
        mock_redis.get.return_value = "500000"

        with (
            patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis),
            patch("app.services.cost_service.settings") as s,
        ):
            s.DAILY_OPENAI_COST_LIMIT_CENTS = 5000
            with pytest.raises(HTTPException) as exc_info:
                await check_budget()
            assert exc_info.value.status_code == 503
            assert "daily cost limit" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_one_under_limit_passes(self):
        """Cost 1 hundredth under limit should pass."""
        mock_redis = AsyncMock()
        # (5000 * 100) - 1 = 499999 hundredths = 4999.99 cents
        mock_redis.get.return_value = "499999"

        with (
            patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis),
            patch("app.services.cost_service.settings") as s,
        ):
            s.DAILY_OPENAI_COST_LIMIT_CENTS = 5000
            await check_budget()  # Should not raise

    @pytest.mark.asyncio
    async def test_zero_cost_passes(self):
        """Zero recorded cost should pass."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "0"

        with patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis):
            await check_budget()

    @pytest.mark.asyncio
    async def test_redis_connection_error_allows_request(self):
        """ConnectionError from Redis should be gracefully handled."""
        with patch(
            "app.infrastructure.redis_client.get_redis",
            side_effect=ConnectionError("Connection refused"),
        ):
            await check_budget()  # Graceful degradation


# ---------------------------------------------------------------------------
# record_usage edge cases
# ---------------------------------------------------------------------------


class TestRecordUsage:
    @pytest.mark.asyncio
    async def test_cost_calculation_accuracy(self):
        """Verify cost calculation matches expected formula."""
        mock_redis = AsyncMock()
        with patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis):
            cost = await record_usage(10000, 5000)

        expected = int(10000 * INPUT_COST_PER_TOKEN + 5000 * OUTPUT_COST_PER_TOKEN)
        assert cost == expected

    @pytest.mark.asyncio
    async def test_zero_tokens_returns_zero(self):
        """Zero tokens should return 0 without hitting Redis."""
        cost = await record_usage(0, 0)
        assert cost == 0

    @pytest.mark.asyncio
    async def test_redis_expire_called_with_48h(self):
        """Redis key should be set to expire after 48 hours."""
        mock_redis = AsyncMock()
        with patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis):
            await record_usage(1000, 500)

        mock_redis.expire.assert_called_once()
        # Second positional arg is the TTL
        ttl_arg = mock_redis.expire.call_args[0][1]
        assert ttl_arg == 48 * 3600

    @pytest.mark.asyncio
    async def test_large_token_counts(self):
        """Large token counts should produce correct integer costs."""
        mock_redis = AsyncMock()
        with patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis):
            cost = await record_usage(1_000_000, 500_000)

        expected = int(1_000_000 * INPUT_COST_PER_TOKEN + 500_000 * OUTPUT_COST_PER_TOKEN)
        assert cost == expected
        assert cost > 0

    @pytest.mark.asyncio
    async def test_per_user_tracking_called_with_correct_args(self):
        """When candidate_id is provided, per-user tracking should be invoked."""
        mock_redis = AsyncMock()

        with (
            patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis),
            patch("app.services.cost_service._record_per_user", new_callable=AsyncMock) as mock_record,
        ):
            await record_usage(
                1000, 500,
                candidate_id="user-123",
                endpoint="/test",
                model="gpt-4o-mini",
            )

        mock_record.assert_called_once()
        kwargs = mock_record.call_args.kwargs
        assert kwargs["candidate_id"] == "user-123"
        assert kwargs["endpoint"] == "/test"
        assert kwargs["model"] == "gpt-4o-mini"
        assert kwargs["tokens_in"] == 1000
        assert kwargs["tokens_out"] == 500

    @pytest.mark.asyncio
    async def test_no_per_user_tracking_without_candidate_id(self):
        """Without candidate_id, per-user tracking should not be called."""
        mock_redis = AsyncMock()

        with (
            patch("app.infrastructure.redis_client.get_redis", return_value=mock_redis),
            patch("app.services.cost_service._record_per_user", new_callable=AsyncMock) as mock_record,
        ):
            await record_usage(1000, 500)

        mock_record.assert_not_called()


# ---------------------------------------------------------------------------
# Pricing constants
# ---------------------------------------------------------------------------


class TestPricingConstants:
    def test_input_cheaper_than_output(self):
        assert INPUT_COST_PER_TOKEN < OUTPUT_COST_PER_TOKEN

    def test_input_cost_value(self):
        # $2.50/1M tokens = 0.025 hundredths of a cent per token
        assert INPUT_COST_PER_TOKEN == 0.025

    def test_output_cost_value(self):
        # $10.00/1M tokens = 0.1 hundredths of a cent per token
        assert OUTPUT_COST_PER_TOKEN == 0.1
