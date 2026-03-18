"""Per-user concurrency limiter for AI operations."""

import asyncio
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import HTTPException


@lru_cache(maxsize=10_000)
def _get_semaphore(candidate_id: str) -> asyncio.Semaphore:
    return asyncio.Semaphore(3)


@asynccontextmanager
async def acquire_ai_slot(candidate_id: str):
    """Acquire a concurrency slot for an AI operation.

    Raises HTTP 429 if the user already has 3 concurrent AI jobs running
    and no slot becomes available within 5 seconds.
    """
    sem = _get_semaphore(candidate_id)
    try:
        await asyncio.wait_for(sem.acquire(), timeout=5.0)
    except TimeoutError:
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent AI requests. Please wait for a current operation to finish.",
        ) from None
    try:
        yield
    finally:
        sem.release()
