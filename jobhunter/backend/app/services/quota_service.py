"""Per-user daily API quota tracking via Redis, tier-aware."""
import structlog
from datetime import datetime, timezone
from fastapi import HTTPException, status
from app.plans import PlanTier, get_limits_for_tier
from app.infrastructure.redis_client import get_redis

logger = structlog.get_logger()

QUOTA_KEY = "quota:{candidate_id}:{quota_type}:{date}"

# Quotas shown to users (openai is internal-only)
USER_FACING_QUOTAS = ["discovery", "research", "hunter", "email"]


async def check_and_increment(candidate_id: str, quota_type: str, plan_tier: str = "free") -> int:
    """Atomically increment quota counter. Raises HTTP 429 if limit exceeded."""
    limits = get_limits_for_tier(PlanTier(plan_tier))
    limit = limits.get(quota_type)
    if limit is None:
        return 0

    redis = get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = QUOTA_KEY.format(candidate_id=candidate_id, quota_type=quota_type, date=today)

    count = await redis.incr(key)
    if count == 1:
        from app.config import settings
        await redis.expire(key, settings.REDIS_QUOTA_TTL)

    if count > limit:
        await redis.decr(key)
        logger.warning("quota_exceeded", candidate_id=candidate_id,
                       quota_type=quota_type, limit=limit, current=count,
                       plan_tier=plan_tier)
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


async def get_usage(candidate_id: str, plan_tier: str = "free") -> dict:
    """Return current usage across user-facing quota types."""
    limits = get_limits_for_tier(PlanTier(plan_tier))
    redis = get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    quotas = {}
    for qt in USER_FACING_QUOTAS:
        key = QUOTA_KEY.format(candidate_id=candidate_id, quota_type=qt, date=today)
        val = await redis.get(key)
        quotas[qt] = {"used": int(val or 0), "limit": limits.get(qt, 0)}
    return {"plan_tier": plan_tier, "quotas": quotas}
