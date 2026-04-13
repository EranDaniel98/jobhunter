"""Tests for the load-test AI budget guard."""
from unittest.mock import AsyncMock

import pytest

from app.loadtest_guard import AI_RUNS_KEY, AIBudgetExceeded, enforce_ai_budget


@pytest.mark.asyncio
async def test_allows_when_disabled():
    redis = AsyncMock()
    await enforce_ai_budget(redis, 0)
    redis.incr.assert_not_called()


@pytest.mark.asyncio
async def test_allows_under_budget():
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=5)
    await enforce_ai_budget(redis, 200)
    redis.incr.assert_called_once_with(AI_RUNS_KEY)


@pytest.mark.asyncio
async def test_raises_over_budget():
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=201)
    with pytest.raises(AIBudgetExceeded):
        await enforce_ai_budget(redis, 200)


@pytest.mark.asyncio
async def test_raises_at_boundary_plus_one():
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=200)
    # 200th run still allowed
    await enforce_ai_budget(redis, 200)
