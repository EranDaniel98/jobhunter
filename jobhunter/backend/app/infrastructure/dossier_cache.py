import asyncio
import hashlib
import json

import structlog

from app.config import settings
from app.infrastructure.redis_client import get_redis, redis_safe_get, redis_safe_setex

logger = structlog.get_logger()


def _compute_input_hash(
    name: str,
    domain: str,
    industry: str | None,
    size: str | None,
    description: str | None,
    tech_stack: str | None,
) -> str:
    """Hash company fields that affect generic dossier output."""
    payload = f"{name}|{domain}|{industry}|{size}|{description}|{tech_stack}"
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


async def get_cached_dossier(domain: str, input_hash: str) -> dict | None:
    """Get cached generic dossier from Redis."""
    key = f"dossier:generic:{domain}:{input_hash}"
    raw = await redis_safe_get(key)
    if raw:
        logger.info(
            "dossier_cache.hit",
            extra={
                "feature": "dossier_cache",
                "detail": {"domain": domain, "hash": input_hash},
            },
        )
        return json.loads(raw)
    return None


async def cache_dossier(domain: str, input_hash: str, data: dict, ttl: int | None = None) -> None:
    """Cache generic dossier result in Redis."""
    key = f"dossier:generic:{domain}:{input_hash}"
    ttl = ttl or settings.DOSSIER_CACHE_TTL
    raw = json.dumps(data)
    await redis_safe_setex(key, ttl, raw)
    logger.info(
        "dossier_cache.stored",
        extra={
            "feature": "dossier_cache",
            "detail": {"domain": domain, "hash": input_hash, "size_bytes": len(raw)},
        },
    )


async def invalidate_dossier(domain: str) -> int:
    """Delete all cached dossier entries for a domain."""
    redis = get_redis()
    pattern = f"dossier:generic:{domain}:*"
    keys = []
    async for key in redis.scan_iter(match=pattern):
        keys.append(key)
    if keys:
        deleted = await redis.delete(*keys)
        logger.info(
            "dossier_cache.invalidated",
            extra={
                "feature": "dossier_cache",
                "detail": {"domain": domain, "keys_deleted": deleted},
            },
        )
        return deleted
    return 0


async def acquire_stampede_lock(domain: str, ttl: int = 60) -> bool:
    """Try to acquire a lock for generating a dossier. Returns True if acquired."""
    redis = get_redis()
    lock_key = f"dossier:lock:{domain}"
    return await redis.set(lock_key, "1", nx=True, ex=ttl)


async def release_stampede_lock(domain: str) -> None:
    """Release the stampede lock."""
    redis = get_redis()
    lock_key = f"dossier:lock:{domain}"
    await redis.delete(lock_key)


async def wait_for_cache(domain: str, input_hash: str, max_wait: int = 30, interval: int = 2) -> dict | None:
    """Poll cache waiting for another generator to populate it."""
    logger.info(
        "dossier_cache.stampede_wait",
        extra={
            "feature": "dossier_cache",
            "detail": {"domain": domain},
        },
    )
    elapsed = 0
    while elapsed < max_wait:
        result = await get_cached_dossier(domain, input_hash)
        if result:
            return result
        await asyncio.sleep(interval)
        elapsed += interval
    logger.warning(
        "dossier_cache.stampede_timeout",
        extra={
            "feature": "dossier_cache",
            "detail": {"domain": domain},
        },
    )
    return None
