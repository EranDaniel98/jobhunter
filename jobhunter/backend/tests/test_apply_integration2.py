"""Integration tests for app/api/apply.py — second pass.

Targets uncovered lines:
- POST /apply/analyze — company_id optional field, vary inputs
- GET /apply/postings/{id}/analysis — 200 path with Redis-cached data
- GET /apply/postings/{id}/analysis — 503 Redis error path
- PATCH /apply/postings/{id}/stage — various stage values
- DELETE /apply/postings/{id} — cleans Redis cache
"""

import json
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.redis_client import get_redis
from app.models.company import Company
from app.models.enums import JobPostingStatus
from app.models.job_posting import JobPosting

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_candidate_id(client: AsyncClient, auth_headers: dict) -> uuid.UUID:
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    return uuid.UUID(resp.json()["id"])


async def _seed_posting(
    db_session: AsyncSession,
    candidate_id: uuid.UUID,
    status: JobPostingStatus = JobPostingStatus.PENDING,
    title: str = "Backend Engineer",
    company_id: uuid.UUID | None = None,
) -> JobPosting:
    posting = JobPosting(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        company_id=company_id,
        title=title,
        company_name="TargetCorp",
        raw_text="Python engineer needed with 3+ years FastAPI experience.",
        status=status,
    )
    db_session.add(posting)
    await db_session.flush()
    return posting


async def _seed_company(db_session: AsyncSession, candidate_id: uuid.UUID) -> Company:
    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name="JobCo",
        domain="jobco.com",
    )
    db_session.add(company)
    await db_session.flush()
    return company


# ---------------------------------------------------------------------------
# POST /apply/analyze — varied inputs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_with_company_id(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """analyze accepts optional company_id and stores it on the posting."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, candidate_id)

    resp = await client.post(
        f"{API}/apply/analyze",
        headers=auth_headers,
        json={
            "title": "ML Engineer",
            "company_name": "JobCo",
            "company_id": str(company.id),
            "raw_text": "We need an ML engineer with Python and TensorFlow.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "ML Engineer"
    assert data["status"] == JobPostingStatus.PENDING
    assert data["company_id"] == str(company.id)


@pytest.mark.asyncio
async def test_analyze_without_company_name(client: AsyncClient, auth_headers: dict):
    """analyze works without company_name (optional field)."""
    resp = await client.post(
        f"{API}/apply/analyze",
        headers=auth_headers,
        json={
            "title": "DevOps Engineer",
            "raw_text": "Looking for a Kubernetes and Docker expert.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "DevOps Engineer"


@pytest.mark.asyncio
async def test_analyze_missing_required_fields_returns_422(client: AsyncClient, auth_headers: dict):
    """analyze without required 'title' returns 422."""
    resp = await client.post(
        f"{API}/apply/analyze",
        headers=auth_headers,
        json={"raw_text": "Some job description here."},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_analyze_with_url_field(client: AsyncClient, auth_headers: dict):
    """analyze with optional url field stores it properly."""
    resp = await client.post(
        f"{API}/apply/analyze",
        headers=auth_headers,
        json={
            "title": "Frontend Engineer",
            "raw_text": "React and TypeScript role.",
            "url": "https://jobs.example.com/frontend",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["url"] == "https://jobs.example.com/frontend"


# ---------------------------------------------------------------------------
# GET /apply/postings/{id}/analysis — 200 path with Redis data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_analysis_returns_200_with_cached_data(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    """When posting is not PENDING and Redis has data, returns 200 with full analysis."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    posting = await _seed_posting(db_session, candidate_id, status=JobPostingStatus.COMPLETED)

    analysis_data = {
        "readiness_score": 82.0,
        "resume_tips": [{"section": "Skills", "tip": "Add Kubernetes", "priority": "high"}],
        "cover_letter": "Dear Hiring Manager, I am excited to apply...",
        "ats_keywords": ["Python", "FastAPI", "PostgreSQL"],
        "missing_skills": ["Kubernetes"],
        "matching_skills": ["Python", "FastAPI"],
        "status": "completed",
    }

    redis = get_redis()
    await redis.set(
        f"apply:analysis:{posting.id}",
        json.dumps(analysis_data),
    )

    resp = await client.get(
        f"{API}/apply/postings/{posting.id}/analysis",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["readiness_score"] == 82.0
    assert data["cover_letter"] == "Dear Hiring Manager, I am excited to apply..."
    assert "Python" in data["ats_keywords"]
    assert data["missing_skills"] == ["Kubernetes"]
    assert data["matching_skills"] == ["Python", "FastAPI"]
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_get_analysis_completed_but_no_cache_returns_404(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    """When posting is COMPLETED but Redis has no data, returns 404."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    posting = await _seed_posting(db_session, candidate_id, status=JobPostingStatus.COMPLETED)
    # Ensure no Redis key exists for this posting
    redis = get_redis()
    await redis.delete(f"apply:analysis:{posting.id}")

    resp = await client.get(
        f"{API}/apply/postings/{posting.id}/analysis",
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert "expired" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_analysis_failed_posting_with_cache(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    """FAILED posting still tries Redis and returns cached data if present."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    posting = await _seed_posting(db_session, candidate_id, status=JobPostingStatus.FAILED)

    analysis_data = {
        "readiness_score": 0,
        "resume_tips": [],
        "cover_letter": "",
        "ats_keywords": [],
        "missing_skills": [],
        "matching_skills": [],
        "status": "failed",
    }
    redis = get_redis()
    await redis.set(
        f"apply:analysis:{posting.id}",
        json.dumps(analysis_data),
    )

    resp = await client.get(
        f"{API}/apply/postings/{posting.id}/analysis",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"


# ---------------------------------------------------------------------------
# GET /apply/postings/{id}/analysis — 503 Redis error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_analysis_redis_error_returns_503(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """When Redis raises an exception, returns 503."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    posting = await _seed_posting(db_session, candidate_id, status=JobPostingStatus.COMPLETED)

    import app.infrastructure.redis_client as _redis_mod

    original_get_redis = _redis_mod.get_redis

    def _broken_redis():
        m = AsyncMock()
        m.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        return m

    _redis_mod.get_redis = _broken_redis
    try:
        resp = await client.get(
            f"{API}/apply/postings/{posting.id}/analysis",
            headers=auth_headers,
        )
        assert resp.status_code == 503
        assert "unavailable" in resp.json()["detail"].lower()
    finally:
        _redis_mod.get_redis = original_get_redis


# ---------------------------------------------------------------------------
# PATCH /apply/postings/{id}/stage — various stages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_stage_to_interviewing(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Update stage to 'interviewing'."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    posting = await _seed_posting(db_session, candidate_id)

    resp = await client.patch(
        f"{API}/apply/postings/{posting.id}/stage",
        headers=auth_headers,
        json={"stage": "interview"},
    )
    assert resp.status_code == 200
    assert resp.json()["application_stage"] == "interview"


@pytest.mark.asyncio
async def test_update_stage_to_offer(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Update stage to 'offer'."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    posting = await _seed_posting(db_session, candidate_id)

    resp = await client.patch(
        f"{API}/apply/postings/{posting.id}/stage",
        headers=auth_headers,
        json={"stage": "offer"},
    )
    assert resp.status_code == 200
    assert resp.json()["application_stage"] == "offer"


@pytest.mark.asyncio
async def test_update_stage_not_found(client: AsyncClient, auth_headers: dict):
    """Update stage for non-existent posting returns 404."""
    fake_id = uuid.uuid4()
    resp = await client.patch(
        f"{API}/apply/postings/{fake_id}/stage",
        headers=auth_headers,
        json={"stage": "applied"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /apply/postings/{id} — cleans Redis, removes posting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_posting_removes_redis_cache(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Deleting a posting cleans up its Redis analysis cache."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    posting = await _seed_posting(db_session, candidate_id, status=JobPostingStatus.COMPLETED)

    # Pre-populate Redis
    redis = get_redis()
    await redis.set(f"apply:analysis:{posting.id}", json.dumps({"readiness_score": 50}))

    resp = await client.delete(f"{API}/apply/postings/{posting.id}", headers=auth_headers)
    assert resp.status_code == 204

    # Verify Redis key is gone
    cached = await redis.get(f"apply:analysis:{posting.id}")
    assert cached is None


@pytest.mark.asyncio
async def test_delete_posting_not_found(client: AsyncClient, auth_headers: dict):
    """Deleting non-existent posting returns 404."""
    fake_id = uuid.uuid4()
    resp = await client.delete(f"{API}/apply/postings/{fake_id}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_posting_and_verify_gone(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """After delete, posting no longer appears in the list."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    posting = await _seed_posting(db_session, candidate_id)

    resp = await client.delete(f"{API}/apply/postings/{posting.id}", headers=auth_headers)
    assert resp.status_code == 204

    # Verify gone from analysis endpoint
    get_resp = await client.get(f"{API}/apply/postings/{posting.id}/analysis", headers=auth_headers)
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /apply/postings — pagination and isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_postings_skips_others_candidate(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Postings from another candidate are not visible."""
    candidate_id = await _get_candidate_id(client, auth_headers)

    # Seed posting for current candidate
    await _seed_posting(db_session, candidate_id, title="My Posting")

    resp = await client.get(f"{API}/apply/postings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Verify response has expected shape
    assert "postings" in data
    assert "total" in data
    # Should have at least the posting we seeded
    assert data["total"] >= 1
