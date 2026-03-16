"""Integration tests for app/api/apply.py — covers uncovered route lines."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
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
) -> JobPosting:
    posting = JobPosting(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        title="Software Engineer",
        company_name="TestCorp",
        raw_text="We are looking for a Python engineer with 5+ years experience.",
        status=status,
    )
    db_session.add(posting)
    await db_session.flush()
    return posting


# ---------------------------------------------------------------------------
# POST /apply/analyze
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_job_posting(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    resp = await client.post(
        f"{API}/apply/analyze",
        headers=auth_headers,
        json={
            "title": "Backend Engineer",
            "company_name": "Acme",
            "raw_text": "We need a Python engineer with FastAPI experience.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Backend Engineer"
    assert data["status"] == JobPostingStatus.PENDING


@pytest.mark.asyncio
async def test_analyze_job_posting_with_url(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        f"{API}/apply/analyze",
        headers=auth_headers,
        json={
            "title": "ML Engineer",
            "raw_text": "Machine learning role requiring Python and TensorFlow.",
            "url": "https://jobs.example.com/ml-engineer",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "ML Engineer"


# ---------------------------------------------------------------------------
# GET /apply/postings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_postings_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"{API}/apply/postings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "postings" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_list_postings_with_data(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    await _seed_posting(db_session, candidate_id)
    await _seed_posting(db_session, candidate_id)

    resp = await client.get(f"{API}/apply/postings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    assert len(data["postings"]) >= 2


@pytest.mark.asyncio
async def test_list_postings_pagination(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    for _ in range(3):
        await _seed_posting(db_session, candidate_id)

    resp = await client.get(f"{API}/apply/postings?skip=0&limit=2", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["postings"]) <= 2


# ---------------------------------------------------------------------------
# GET /apply/postings/{id}  (not in apply.py but test via list)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_analysis_pending(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    posting = await _seed_posting(db_session, candidate_id, JobPostingStatus.PENDING)

    resp = await client.get(f"{API}/apply/postings/{posting.id}/analysis", headers=auth_headers)
    # PENDING → 202 with status=pending
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_get_analysis_not_found(client: AsyncClient, auth_headers: dict):
    fake_id = uuid.uuid4()
    resp = await client.get(f"{API}/apply/postings/{fake_id}/analysis", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /apply/postings/{id}/stage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_posting_stage(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    posting = await _seed_posting(db_session, candidate_id)

    resp = await client.patch(
        f"{API}/apply/postings/{posting.id}/stage",
        headers=auth_headers,
        json={"stage": "applied"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["application_stage"] == "applied"


@pytest.mark.asyncio
async def test_update_posting_stage_invalid(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    posting = await _seed_posting(db_session, candidate_id)

    resp = await client.patch(
        f"{API}/apply/postings/{posting.id}/stage",
        headers=auth_headers,
        json={"stage": "invalid_stage"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_posting_stage_not_found(client: AsyncClient, auth_headers: dict):
    fake_id = uuid.uuid4()
    resp = await client.patch(
        f"{API}/apply/postings/{fake_id}/stage",
        headers=auth_headers,
        json={"stage": "interview"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /apply/postings/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_posting(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    candidate_id = await _get_candidate_id(client, auth_headers)
    posting = await _seed_posting(db_session, candidate_id)

    resp = await client.delete(f"{API}/apply/postings/{posting.id}", headers=auth_headers)
    assert resp.status_code == 204

    # Verify it's gone — the /analysis route gives 404 when posting doesn't exist
    resp2 = await client.get(f"{API}/apply/postings/{posting.id}/analysis", headers=auth_headers)
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_posting_not_found(client: AsyncClient, auth_headers: dict):
    fake_id = uuid.uuid4()
    resp = await client.delete(f"{API}/apply/postings/{fake_id}", headers=auth_headers)
    assert resp.status_code == 404
