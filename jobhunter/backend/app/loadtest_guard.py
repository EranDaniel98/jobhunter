"""Load-test safety guard: hard cap on expensive AI pipeline runs.

Used only when LOADTEST_MODE=1 and LOADTEST_AI_BUDGET>0. In production these
settings are 0/False and this module is a no-op.
"""
from redis.asyncio import Redis


class AIBudgetExceeded(Exception):
    """Raised when the load-test AI run budget has been exhausted."""


AI_RUNS_KEY = "loadtest:ai_runs"


async def enforce_ai_budget(redis: Redis, budget: int) -> None:
    """Atomically increment the AI run counter and raise if over budget.

    budget=0 disables the check entirely (production default).
    """
    if budget <= 0:
        return
    count = await redis.incr(AI_RUNS_KEY)
    if count > budget:
        raise AIBudgetExceeded(
            f"Load-test AI budget exhausted: {count} > {budget}"
        )
