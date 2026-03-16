import redis.asyncio as aioredis
import structlog

from app.config import settings

logger = structlog.get_logger()

redis_client: aioredis.Redis | None = None


async def init_redis() -> aioredis.Redis:
    global redis_client
    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )
    await redis_client.ping()
    logger.info("redis_connected")
    return redis_client


async def close_redis() -> None:
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


def get_redis() -> aioredis.Redis:
    if redis_client is None:
        raise RuntimeError("Redis not initialized")
    return redis_client


async def redis_safe_get(key: str) -> str | None:
    """Get a value from Redis, returning None if Redis is unreachable."""
    try:
        return await get_redis().get(key)
    except Exception as e:
        logger.warning("redis_unavailable_get", key=key, error=str(e))
        return None


async def redis_safe_setex(key: str, ttl: int, value: str) -> bool:
    """Set a value in Redis with TTL, returning False if Redis is unreachable."""
    try:
        await get_redis().setex(key, ttl, value)
        return True
    except Exception as e:
        logger.warning("redis_unavailable_setex", key=key, error=str(e))
        return False
