"""Daily OpenAI cost tracking and circuit breaker.

Tracks total daily spend in Redis using atomic INCR.
Cost is stored in hundredths of a cent (1/100 cent) for integer math precision.
GPT-4o pricing: $2.50/1M input tokens, $10.00/1M output tokens.
"""

from datetime import UTC, datetime

import structlog
from fastapi import HTTPException

from app.config import settings

logger = structlog.get_logger()

# GPT-4o pricing in hundredths-of-a-cent per token
# $2.50 / 1M input = 0.00025 cents/token = 0.025 hundredths/token
# $10.00 / 1M output = 0.001 cents/token = 0.1 hundredths/token
INPUT_COST_PER_TOKEN = 0.025  # hundredths of a cent
OUTPUT_COST_PER_TOKEN = 0.1  # hundredths of a cent

DAILY_COST_KEY_PREFIX = "openai:daily_cost"


def _today_key() -> str:
    return f"{DAILY_COST_KEY_PREFIX}:{datetime.now(UTC).strftime('%Y-%m-%d')}"


async def check_budget() -> None:
    """Raise HTTP 503 if daily OpenAI budget has been exceeded."""
    try:
        from app.infrastructure.redis_client import get_redis

        redis = get_redis()
        current = await redis.get(_today_key())
        if current is not None:
            # Convert from hundredths-of-a-cent to cents
            current_cents = int(current) / 100
            if current_cents >= settings.DAILY_OPENAI_COST_LIMIT_CENTS:
                logger.warning(
                    "daily_cost_limit_reached",
                    current_cents=current_cents,
                    limit_cents=settings.DAILY_OPENAI_COST_LIMIT_CENTS,
                )
                raise HTTPException(
                    status_code=503,
                    detail="AI service temporarily unavailable - daily cost limit reached. Try again tomorrow.",
                )
    except HTTPException:
        raise
    except Exception as e:
        # Graceful degradation: if Redis is down, allow the request
        logger.warning("cost_budget_check_failed", error=str(e))


async def record_usage(
    tokens_in: int,
    tokens_out: int,
    *,
    candidate_id: str | None = None,
    endpoint: str | None = None,
    model: str = "gpt-4o",
) -> int:
    """Record token usage and return estimated cost in hundredths of a cent.

    Also records per-user usage to the api_usage table if candidate_id is provided.
    """
    cost_hundredths = int(tokens_in * INPUT_COST_PER_TOKEN + tokens_out * OUTPUT_COST_PER_TOKEN)
    if cost_hundredths <= 0:
        return 0

    try:
        from app.infrastructure.redis_client import get_redis

        redis = get_redis()
        key = _today_key()
        await redis.incrby(key, cost_hundredths)
        await redis.expire(key, 48 * 3600)  # 48h TTL

        logger.debug(
            "openai_cost_recorded",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_hundredths=cost_hundredths,
            candidate_id=candidate_id,
        )
    except Exception as e:
        logger.warning("cost_recording_failed", error=str(e))

    # Per-user tracking (Wave 4A)
    if candidate_id:
        try:
            await _record_per_user(
                candidate_id=candidate_id,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_hundredths=cost_hundredths,
                endpoint=endpoint,
            )
        except Exception as e:
            logger.warning("per_user_cost_recording_failed", error=str(e))

    return cost_hundredths


async def _record_per_user(
    *,
    candidate_id: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    cost_hundredths: int,
    endpoint: str | None,
) -> None:
    """Insert a row into the api_usage table for per-user cost tracking."""
    import uuid as _uuid

    from app.infrastructure.database import async_session_factory

    async with async_session_factory() as db:
        try:
            from app.models.billing import ApiUsageRecord

            record = ApiUsageRecord(
                id=_uuid.uuid4(),
                candidate_id=_uuid.UUID(candidate_id),
                service="openai",
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                estimated_cost_cents=cost_hundredths // 100,  # convert hundredths to cents
                endpoint=endpoint,
            )
            db.add(record)
            await db.commit()
        except Exception as e:
            logger.debug("api_usage_insert_skipped", error=str(e))
