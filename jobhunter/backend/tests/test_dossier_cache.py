import asyncio

import pytest

from app.infrastructure.dossier_cache import (
    _compute_input_hash,
    acquire_stampede_lock,
    cache_dossier,
    get_cached_dossier,
    invalidate_dossier,
    release_stampede_lock,
)


def test_compute_input_hash_deterministic():
    h1 = _compute_input_hash("Acme", "acme.com", "Tech", "50-100", "A company", "Python")
    h2 = _compute_input_hash("Acme", "acme.com", "Tech", "50-100", "A company", "Python")
    assert h1 == h2
    assert len(h1) == 12


def test_compute_input_hash_changes_on_different_input():
    h1 = _compute_input_hash("Acme", "acme.com", "Tech", "50-100", "A company", "Python")
    h2 = _compute_input_hash("Beta", "beta.com", "Finance", "100-200", "B company", "Java")
    assert h1 != h2


@pytest.mark.asyncio
async def test_cache_roundtrip(redis):
    data = {"culture_summary": "Great culture", "culture_score": 85}
    await cache_dossier("acme.com", "abc123", data, ttl=60)
    result = await get_cached_dossier("acme.com", "abc123")
    assert result == data


@pytest.mark.asyncio
async def test_cache_miss_returns_none(redis):
    result = await get_cached_dossier("nonexistent.com", "xyz")
    assert result is None


@pytest.mark.asyncio
async def test_cache_ttl_expiry(redis):
    data = {"culture_summary": "Expires soon"}
    await cache_dossier("ttl.com", "hash1", data, ttl=1)
    assert await get_cached_dossier("ttl.com", "hash1") is not None
    await asyncio.sleep(1.5)
    assert await get_cached_dossier("ttl.com", "hash1") is None


@pytest.mark.asyncio
async def test_invalidate_dossier(redis):
    await cache_dossier("acme.com", "hash1", {"a": 1}, ttl=60)
    await cache_dossier("acme.com", "hash2", {"b": 2}, ttl=60)
    deleted = await invalidate_dossier("acme.com")
    assert deleted >= 2
    assert await get_cached_dossier("acme.com", "hash1") is None


@pytest.mark.asyncio
async def test_stampede_lock(redis):
    assert await acquire_stampede_lock("test.com") is True
    assert await acquire_stampede_lock("test.com") is False
    await release_stampede_lock("test.com")
    assert await acquire_stampede_lock("test.com") is True
    await release_stampede_lock("test.com")
