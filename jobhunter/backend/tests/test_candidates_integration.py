"""Integration tests for /api/v1/candidates routes.

Covers: successful PDF upload (201), usage stats, DNA (found/404),
skills list, resumes list, delete non-primary resume.

NOTE: most negative / validation paths are already covered in
test_candidates_api_extended.py.  This file adds the happy-path flows
that were still uncovered.
"""

import io
import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

API = settings.API_V1_PREFIX


# ── helpers ───────────────────────────────────────────────────────────────────


async def _get_candidate_id(client: AsyncClient, auth_headers: dict) -> uuid.UUID:
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    return uuid.UUID(resp.json()["id"])


# ── POST /candidates/resume (happy path) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_resume_success(client: AsyncClient, auth_headers: dict):
    """POST /candidates/resume with valid PDF returns 201 and ResumeUploadResponse."""
    # Minimal valid PDF content (magic bytes + enough content for pypdf not to fail badly).
    # StorageStub accepts any bytes, so we just need the magic-byte check to pass.
    pdf_content = b"%PDF-1.4 fake content"
    files = {"file": ("resume.pdf", io.BytesIO(pdf_content), "application/pdf")}
    with patch("app.services.resume_service._extract_text_from_pdf", return_value="Extracted text"):
        resp = await client.post(f"{API}/candidates/resume", files=files, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "file_path" in data
    assert "is_primary" in data
    assert data["is_primary"] is True


@pytest.mark.asyncio
async def test_upload_resume_sets_as_primary(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Second resume upload makes the new one primary and demotes the previous one."""

    from app.models.candidate import Resume

    cid = await _get_candidate_id(client, auth_headers)

    # Seed an existing primary resume directly
    first = Resume(
        id=uuid.uuid4(),
        candidate_id=cid,
        file_path="resumes/old.pdf",
        file_hash="aabbcc" * 10 + "aabb",
        is_primary=True,
        parse_status="completed",
    )
    db_session.add(first)
    await db_session.commit()

    # Upload a second one
    pdf_content = b"%PDF-1.4 fake content"
    files = {"file": ("new_resume.pdf", io.BytesIO(pdf_content), "application/pdf")}
    with patch("app.services.resume_service._extract_text_from_pdf", return_value="Extracted text"):
        resp = await client.post(f"{API}/candidates/resume", files=files, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["is_primary"] is True

    # Verify via list endpoint that old resume is no longer primary
    list_resp = await client.get(f"{API}/candidates/me/resumes", headers=auth_headers)
    resumes = list_resp.json()
    primary_count = sum(1 for r in resumes if r["is_primary"])
    assert primary_count == 1  # Only the new one should be primary


# ── GET /candidates/me/usage ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_usage_returns_plan_tier(client: AsyncClient, auth_headers: dict):
    """GET /candidates/me/usage includes plan_tier and quotas keys."""
    resp = await client.get(f"{API}/candidates/me/usage", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "plan_tier" in data
    assert "quotas" in data
    # Free-tier user
    assert data["plan_tier"] == "free"


# ── GET /candidates/me/dna ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_dna_not_found_returns_404(client: AsyncClient, auth_headers: dict):
    """GET /candidates/me/dna before any upload returns 404."""
    resp = await client.get(f"{API}/candidates/me/dna", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_dna_with_seeded_data(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """GET /candidates/me/dna returns DNA + skills when seeded."""
    from app.models.candidate import CandidateDNA, Skill

    cid = await _get_candidate_id(client, auth_headers)

    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=cid,
        experience_summary="5 years building backend systems.",
        strengths=["Python", "FastAPI", "PostgreSQL"],
        gaps=["Frontend"],
        career_stage="mid",
        transferable_skills={"mentoring": "Mentored two junior devs"},
    )
    db_session.add(dna)

    skill = Skill(
        id=uuid.uuid4(),
        candidate_id=cid,
        name="Python",
        category="explicit",
        proficiency="expert",
        years_experience=5.0,
        evidence="5 years professional use",
    )
    db_session.add(skill)
    await db_session.commit()

    resp = await client.get(f"{API}/candidates/me/dna", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["experience_summary"] == "5 years building backend systems."
    assert data["career_stage"] == "mid"
    assert len(data["skills"]) == 1
    assert data["skills"][0]["name"] == "Python"


# ── GET /candidates/me/skills ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_skills_empty_list(client: AsyncClient, auth_headers: dict):
    """GET /candidates/me/skills returns [] when no skills exist."""
    resp = await client.get(f"{API}/candidates/me/skills", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_skills_with_seeded_data(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """GET /candidates/me/skills returns all seeded skills with correct shape."""
    from app.models.candidate import Skill

    cid = await _get_candidate_id(client, auth_headers)

    skills_data = [
        ("Python", "explicit", "expert"),
        ("Communication", "transferable", "advanced"),
    ]
    for name, cat, prof in skills_data:
        db_session.add(
            Skill(
                id=uuid.uuid4(),
                candidate_id=cid,
                name=name,
                category=cat,
                proficiency=prof,
                years_experience=3.0,
                evidence=f"Evidence for {name}",
            )
        )
    await db_session.commit()

    resp = await client.get(f"{API}/candidates/me/skills", headers=auth_headers)
    assert resp.status_code == 200
    skills = resp.json()
    assert len(skills) == 2
    names = {s["name"] for s in skills}
    assert names == {"Python", "Communication"}
    for s in skills:
        for key in ("id", "name", "category", "proficiency", "years_experience", "evidence"):
            assert key in s, f"Missing field: {key}"


# ── GET /candidates/me/resumes ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_resumes_empty_list(client: AsyncClient, auth_headers: dict):
    """GET /candidates/me/resumes returns [] when candidate has no resumes."""
    resp = await client.get(f"{API}/candidates/me/resumes", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_resumes_ordered_desc(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """GET /candidates/me/resumes returns resumes in descending created_at order."""
    from datetime import UTC, datetime

    from app.models.candidate import Resume

    cid = await _get_candidate_id(client, auth_headers)

    r1 = Resume(
        id=uuid.uuid4(),
        candidate_id=cid,
        file_path="resumes/first.pdf",
        file_hash="aa" * 32,
        is_primary=True,
        parse_status="completed",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    r2 = Resume(
        id=uuid.uuid4(),
        candidate_id=cid,
        file_path="resumes/second.pdf",
        file_hash="bb" * 32,
        is_primary=False,
        parse_status="pending",
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    db_session.add(r1)
    db_session.add(r2)
    await db_session.commit()

    resp = await client.get(f"{API}/candidates/me/resumes", headers=auth_headers)
    assert resp.status_code == 200
    resumes = resp.json()
    assert len(resumes) == 2
    # Most recent first
    assert resumes[0]["file_path"] == "resumes/second.pdf"
    assert resumes[1]["file_path"] == "resumes/first.pdf"
    for r in resumes:
        for key in ("id", "file_path", "is_primary", "parse_status", "created_at"):
            assert key in r


# ── DELETE /candidates/me/resumes/{id} ────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_non_primary_resume(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """DELETE /candidates/me/resumes/{id} on non-primary resume returns 204."""
    from app.models.candidate import Resume

    cid = await _get_candidate_id(client, auth_headers)
    r = Resume(
        id=uuid.uuid4(),
        candidate_id=cid,
        file_path="resumes/to_delete.pdf",
        file_hash="cc" * 32,
        is_primary=False,
        parse_status="pending",
    )
    db_session.add(r)
    await db_session.commit()

    resp = await client.delete(f"{API}/candidates/me/resumes/{r.id}", headers=auth_headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_primary_resume_blocked(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """DELETE /candidates/me/resumes/{id} on primary resume returns 400."""
    from app.models.candidate import Resume

    cid = await _get_candidate_id(client, auth_headers)
    r = Resume(
        id=uuid.uuid4(),
        candidate_id=cid,
        file_path="resumes/primary.pdf",
        file_hash="dd" * 32,
        is_primary=True,
        parse_status="completed",
    )
    db_session.add(r)
    await db_session.commit()

    resp = await client.delete(f"{API}/candidates/me/resumes/{r.id}", headers=auth_headers)
    assert resp.status_code == 400
    assert "primary" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_resume_not_found(client: AsyncClient, auth_headers: dict):
    """DELETE /candidates/me/resumes/{id} with unknown id returns 404."""
    resp = await client.delete(f"{API}/candidates/me/resumes/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404
