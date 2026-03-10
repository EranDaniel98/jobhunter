"""Unit tests for quota_service – no real Redis required."""

import uuid
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi import HTTPException

from app.services.quota_service import (
    QUOTA_KEY,
    USER_FACING_QUOTAS,
    check_and_increment,
    get_usage,
)


CANDIDATE_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# check_and_increment
# ---------------------------------------------------------------------------

class TestCheckAndIncrement:
    @pytest.mark.asyncio
    async def test_increment_under_limit(self):
        mock_redis = AsyncMock()
        mock_redis.eval.return_value = 1  # first call today

        with patch("app.services.quota_service.get_redis", return_value=mock_redis), \
             patch("app.config.settings.REDIS_QUOTA_TTL", 86400):
            count = await check_and_increment(CANDIDATE_ID, "email", "free")
            assert count == 1
            mock_redis.eval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_increment_at_limit_succeeds(self):
        """Exactly at the limit (e.g. 3/3 for free email) should succeed."""
        mock_redis = AsyncMock()
        mock_redis.eval.return_value = 3  # free email limit is 3

        with patch("app.services.quota_service.get_redis", return_value=mock_redis), \
             patch("app.config.settings.REDIS_QUOTA_TTL", 86400):
            count = await check_and_increment(CANDIDATE_ID, "email", "free")
            assert count == 3
            # Should NOT call decr
            mock_redis.decr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_increment_over_limit_raises_429(self):
        mock_redis = AsyncMock()
        mock_redis.eval.return_value = 4  # over free email limit (3)

        with patch("app.services.quota_service.get_redis", return_value=mock_redis), \
             patch("app.config.settings.REDIS_QUOTA_TTL", 86400):
            with pytest.raises(HTTPException) as exc_info:
                await check_and_increment(CANDIDATE_ID, "email", "free")
            assert exc_info.value.status_code == 429
            # Should decrement to undo the over-count
            mock_redis.decr.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_increment_429_detail_contains_quota_type(self):
        mock_redis = AsyncMock()
        mock_redis.eval.return_value = 4

        with patch("app.services.quota_service.get_redis", return_value=mock_redis), \
             patch("app.config.settings.REDIS_QUOTA_TTL", 86400):
            with pytest.raises(HTTPException) as exc_info:
                await check_and_increment(CANDIDATE_ID, "email", "free")
            detail = exc_info.value.detail
            assert detail["quota_type"] == "email"
            assert detail["limit"] == 3
            assert detail["plan_tier"] == "free"

    @pytest.mark.asyncio
    async def test_increment_unknown_quota_type_returns_zero(self):
        """If the quota type isn't in the plan limits, return 0 (unlimited)."""
        mock_redis = AsyncMock()

        with patch("app.services.quota_service.get_redis", return_value=mock_redis):
            count = await check_and_increment(CANDIDATE_ID, "nonexistent_type", "free")
            assert count == 0
            mock_redis.eval.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_increment_explorer_plan_higher_limits(self):
        """Explorer plan has email limit of 20 — 15 should succeed."""
        mock_redis = AsyncMock()
        mock_redis.eval.return_value = 15

        with patch("app.services.quota_service.get_redis", return_value=mock_redis), \
             patch("app.config.settings.REDIS_QUOTA_TTL", 86400):
            count = await check_and_increment(CANDIDATE_ID, "email", "explorer")
            assert count == 15
            mock_redis.decr.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_increment_hunter_plan_highest_limits(self):
        """Hunter plan has email limit of 75."""
        mock_redis = AsyncMock()
        mock_redis.eval.return_value = 50

        with patch("app.services.quota_service.get_redis", return_value=mock_redis), \
             patch("app.config.settings.REDIS_QUOTA_TTL", 86400):
            count = await check_and_increment(CANDIDATE_ID, "email", "hunter")
            assert count == 50


# ---------------------------------------------------------------------------
# get_usage
# ---------------------------------------------------------------------------

class TestGetUsage:
    @pytest.mark.asyncio
    async def test_get_usage_returns_all_quota_types(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "5"
        mock_redis.mget.return_value = ["1"] * 7  # 7 days or 30 days

        with patch("app.services.quota_service.get_redis", return_value=mock_redis):
            result = await get_usage(CANDIDATE_ID, "free")

        assert result["plan_tier"] == "free"
        for qt in USER_FACING_QUOTAS:
            assert qt in result["quotas"]
            assert "used" in result["quotas"][qt]
            assert "limit" in result["quotas"][qt]

    @pytest.mark.asyncio
    async def test_get_usage_graceful_redis_failure(self):
        """When Redis is down, usage should return zeros instead of crashing."""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Connection refused")

        with patch("app.services.quota_service.get_redis", return_value=mock_redis):
            result = await get_usage(CANDIDATE_ID, "free")

        assert result["plan_tier"] == "free"
        for qt in USER_FACING_QUOTAS:
            assert result["quotas"][qt]["used"] == 0

    @pytest.mark.asyncio
    async def test_get_usage_weekly_sums_correctly(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "2"
        # 7 days worth for weekly, 30 days for monthly
        mock_redis.mget.side_effect = [
            ["3"] * 7,   # weekly
            ["3"] * 30,  # monthly
        ] * len(USER_FACING_QUOTAS)

        with patch("app.services.quota_service.get_redis", return_value=mock_redis):
            result = await get_usage(CANDIDATE_ID, "free")

        # Weekly sum for first quota type should be 3*7 = 21
        first_qt = USER_FACING_QUOTAS[0]
        assert result["weekly"][first_qt]["used"] == 21
