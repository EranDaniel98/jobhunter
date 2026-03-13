"""Integration tests for per-user concurrency semaphore.

Tests the acquire_ai_slot context manager and verifies that the concurrency
limiter correctly blocks when a user exceeds 3 concurrent AI operations.
"""

import asyncio

import pytest
from fastapi import HTTPException

from app.services.concurrency import _semaphores, acquire_ai_slot

# ---------------------------------------------------------------------------
# Basic acquire / release
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_and_release():
    """Single acquire should succeed and properly release."""
    user = "test-concurrency-basic"
    _semaphores.pop(user, None)

    async with acquire_ai_slot(user):
        # Inside the slot — semaphore should be acquired
        sem = _semaphores[user]
        # We acquired 1 of 3 slots, so 2 more should be available
        # Try acquiring another to verify
        await asyncio.wait_for(sem.acquire(), timeout=0.1)
        sem.release()

    # After exit, slot should be released


@pytest.mark.asyncio
async def test_three_concurrent_slots_allowed():
    """Up to 3 concurrent acquisitions should succeed."""
    user = "test-concurrency-three"
    _semaphores.pop(user, None)

    acquired = []

    async def acquire_slot():
        async with acquire_ai_slot(user):
            acquired.append(True)
            await asyncio.sleep(0.1)

    # Run 3 concurrent tasks — all should succeed
    await asyncio.gather(
        acquire_slot(),
        acquire_slot(),
        acquire_slot(),
    )
    assert len(acquired) == 3


@pytest.mark.asyncio
async def test_fourth_concurrent_raises_429():
    """4th concurrent request should get HTTP 429."""
    user = "test-concurrency-overflow"
    _semaphores.pop(user, None)

    sem = _semaphores[user]

    # Manually acquire all 3 slots
    await sem.acquire()
    await sem.acquire()
    await sem.acquire()

    try:
        with pytest.raises(HTTPException) as exc_info:
            async with acquire_ai_slot(user):
                pass
        assert exc_info.value.status_code == 429
        assert "concurrent" in exc_info.value.detail.lower()
    finally:
        sem.release()
        sem.release()
        sem.release()


@pytest.mark.asyncio
async def test_slot_released_after_exception():
    """Slot should be released even if the operation raises an exception."""
    user = "test-concurrency-exception"
    _semaphores.pop(user, None)

    with pytest.raises(ValueError, match="test error"):
        async with acquire_ai_slot(user):
            raise ValueError("test error")

    # Should be able to acquire again (slot was released)
    async with acquire_ai_slot(user):
        pass


@pytest.mark.asyncio
async def test_different_users_independent():
    """Slots for different users should be independent."""
    user_x = "test-concurrency-x"
    user_y = "test-concurrency-y"
    _semaphores.pop(user_x, None)
    _semaphores.pop(user_y, None)

    # Exhaust user_x's slots
    sem_x = _semaphores[user_x]
    await sem_x.acquire()
    await sem_x.acquire()
    await sem_x.acquire()

    try:
        # user_y should still be able to acquire
        async with acquire_ai_slot(user_y):
            pass  # Should succeed
    finally:
        sem_x.release()
        sem_x.release()
        sem_x.release()


@pytest.mark.asyncio
async def test_slot_becomes_available_after_release():
    """Once a slot is released, a waiting request should proceed."""
    user = "test-concurrency-wait"
    _semaphores.pop(user, None)

    results = []

    async def hold_slot(delay: float, label: str):
        async with acquire_ai_slot(user):
            results.append(f"{label}-acquired")
            await asyncio.sleep(delay)
            results.append(f"{label}-released")

    # Start 4 tasks — 3 will acquire immediately, 4th will wait
    # The first tasks release quickly so the 4th should succeed within timeout
    tasks = [
        hold_slot(0.05, "a"),
        hold_slot(0.05, "b"),
        hold_slot(0.05, "c"),
        hold_slot(0.05, "d"),
    ]

    await asyncio.gather(*tasks)
    # All 4 should have completed (d waited for a/b/c to release)
    assert len(results) == 8  # 4 acquired + 4 released


@pytest.mark.asyncio
async def test_semaphore_per_user_isolation():
    """Each user gets their own semaphore instance."""
    user1 = "test-isolation-1"
    user2 = "test-isolation-2"
    _semaphores.pop(user1, None)
    _semaphores.pop(user2, None)

    # Access semaphores
    _ = _semaphores[user1]
    _ = _semaphores[user2]

    assert _semaphores[user1] is not _semaphores[user2]
