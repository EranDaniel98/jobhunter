"""Per-user daily API quota tracking via Redis."""
import structlog
from datetime import datetime, timezone
from fastapi import HTTPException, status
from app.config import settings
from app.infrastructure.redis_client import get_redis

logger = structlog.get_logger()

QUOTA_KEY = "quota:{candidate_id}:{quota_type}:{date}"

QUOTA_LIMITS = {
    "openai": settings.DAILY_OPENAI_CALL_LIMIT,
    "hunter": settings.DAILY_HUNTER_CALL_LIMIT,
    "discovery": settings.DAILY_DISCOVERY_LIMIT,
    "research": settings.DAILY_RESEARCH_LIMIT,
}


async def check_and_increment(candidate_id: str, quota_type: str) -> int:
    """Atomically increment quota counter. Raises HTTP 429 if limit exceeded."""
    limit = QUOTA_LIMITS.get(quota_type)
    if limit is None:
        return 0

    redis = get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = QUOTA_KEY.format(candidate_id=candidate_id, quota_type=quota_type, date=today)

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 86400)

    if count > limit:
        await redis.decr(key)
        logger.warning("quota_exceeded", candidate_id=candidate_id,
                       quota_type=quota_type, limit=limit, current=count)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily {quota_type} limit ({limit}) reached. Resets at midnight UTC.",
        )
    return count


async def get_usage(candidate_id: str) -> dict:
    """Return current usage across all quota types."""
    redis = get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = {}
    for qt, limit in QUOTA_LIMITS.items():
        key = QUOTA_KEY.format(candidate_id=candidate_id, quota_type=qt, date=today)
        val = await redis.get(key)
        usage[qt] = {"used": int(val or 0), "limit": limit}
    return usage
