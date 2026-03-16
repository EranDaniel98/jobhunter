"""Per-user daily API quota tracking via Redis, tier-aware."""

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import HTTPException, status

from app.infrastructure.redis_client import get_redis
from app.plans import PlanTier, get_limits_for_tier

logger = structlog.get_logger()

QUOTA_KEY = "quota:{candidate_id}:{quota_type}:{date}"

_LUA_INCR_EXPIRE = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""

# Quotas shown to users (openai is internal-only)
USER_FACING_QUOTAS = ["discovery", "research", "hunter", "email"]


async def check_and_increment(
    candidate_id: str, quota_type: str, plan_tier: str = "free", is_admin: bool = False
) -> int:
    """Atomically increment quota counter. Raises HTTP 429 if limit exceeded."""
    if is_admin:
        return 0

    limits = get_limits_for_tier(PlanTier(plan_tier))
    limit = limits.get(quota_type)
    if limit is None:
        return 0

    redis = get_redis()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    key = QUOTA_KEY.format(candidate_id=candidate_id, quota_type=quota_type, date=today)

    from app.config import settings

    count = await redis.eval(_LUA_INCR_EXPIRE, 1, key, settings.REDIS_QUOTA_TTL)

    if count > limit:
        await redis.decr(key)
        logger.warning(
            "quota_exceeded",
            candidate_id=candidate_id,
            quota_type=quota_type,
            limit=limit,
            current=count,
            plan_tier=plan_tier,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": f"Daily {quota_type} limit ({limit}) reached. Resets at midnight UTC.",
                "quota_type": quota_type,
                "limit": limit,
                "plan_tier": plan_tier,
                "resets_at": "midnight UTC",
            },
        )
    return count


async def decrement_usage(candidate_id: str, quota_type: str) -> None:
    """Decrement quota counter (e.g. when a send fails after increment)."""
    try:
        redis = get_redis()
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        key = QUOTA_KEY.format(candidate_id=candidate_id, quota_type=quota_type, date=today)
        await redis.decr(key)
    except Exception as e:
        logger.warning("quota_decrement_failed", candidate_id=candidate_id, quota_type=quota_type, error=str(e))


async def get_usage(candidate_id: str, plan_tier: str = "free", is_admin: bool = False) -> dict:
    """Return current usage across user-facing quota types (daily, weekly, monthly)."""
    # Admin sees hunter-tier limits so usage cards show generous caps
    limits = get_limits_for_tier(PlanTier("hunter")) if is_admin else get_limits_for_tier(PlanTier(plan_tier))
    now = datetime.now(UTC)
    week_dates = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    month_dates = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]

    quotas: dict = {}
    weekly: dict = {}
    monthly: dict = {}

    try:
        redis = get_redis()

        for qt in USER_FACING_QUOTAS:
            daily_key = QUOTA_KEY.format(candidate_id=candidate_id, quota_type=qt, date=week_dates[0])
            daily_val = await redis.get(daily_key)
            quotas[qt] = {"used": int(daily_val or 0), "limit": limits.get(qt, 0)}

            week_keys = [QUOTA_KEY.format(candidate_id=candidate_id, quota_type=qt, date=d) for d in week_dates]
            month_keys = [QUOTA_KEY.format(candidate_id=candidate_id, quota_type=qt, date=d) for d in month_dates]

            week_vals = await redis.mget(*week_keys)
            month_vals = await redis.mget(*month_keys)

            weekly[qt] = {"used": sum(int(v or 0) for v in week_vals), "limit": limits.get(qt, 0) * 7}
            monthly[qt] = {"used": sum(int(v or 0) for v in month_vals), "limit": limits.get(qt, 0) * 30}
    except Exception as e:
        logger.warning("get_usage_redis_failure", candidate_id=candidate_id, error=str(e))
        for qt in USER_FACING_QUOTAS:
            quotas.setdefault(qt, {"used": 0, "limit": limits.get(qt, 0)})
            weekly.setdefault(qt, {"used": 0, "limit": limits.get(qt, 0) * 7})
            monthly.setdefault(qt, {"used": 0, "limit": limits.get(qt, 0) * 30})

    return {"plan_tier": plan_tier, "quotas": quotas, "weekly": weekly, "monthly": monthly}
