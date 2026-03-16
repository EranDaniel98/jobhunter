"""Extended tests for candidates API endpoints (upload, DNA, skills, resumes, usage)."""

import io
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

API = settings.API_V1_PREFIX


async def _get_candidate_id(client: AsyncClient, auth_headers: dict) -> uuid.UUID:
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    return uuid.UUID(resp.json()["id"])


# ── Auth guard ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_resume_unauthenticated(client: AsyncClient):
    """POST /candidates/resume without auth returns 401."""
    data = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    resp = await client.post(f"{API}/candidates/resume", files=data)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_dna_unauthenticated(client: AsyncClient):
    """GET /candidates/me/dna without auth returns 401."""
    resp = await client.get(f"{API}/candidates/me/dna")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_skills_unauthenticated(client: AsyncClient):
    """GET /candidates/me/skills without auth returns 401."""
    resp = await client.get(f"{API}/candidates/me/skills")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_resumes_unauthenticated(client: AsyncClient):
    """GET /candidates/me/resumes without auth returns 401."""
    resp = await client.get(f"{API}/candidates/me/resumes")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_usage_unauthenticated(client: AsyncClient):
    """GET /candidates/me/usage without auth returns 401."""
    resp = await client.get(f"{API}/candidates/me/usage")
    assert resp.status_code == 401


# ── Resume upload validation ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_resume_no_file_returns_error(client: AsyncClient, auth_headers: dict):
    """POST /candidates/resume with empty filename returns 400 or 422."""
    # An empty filename either triggers a FastAPI 422 (validation) or our 400 (app logic).
    # Both are acceptable rejection codes — the request must not succeed.
    data = {"file": ("", io.BytesIO(b""), "application/pdf")}
    resp = await client.post(f"{API}/candidates/resume", files=data, headers=auth_headers)
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_upload_resume_invalid_extension(client: AsyncClient, auth_headers: dict):
    """POST /candidates/resume with .txt file returns 400."""
    data = {"file": ("resume.txt", io.BytesIO(b"plain text"), "text/plain")}
    resp = await client.post(f"{API}/candidates/resume", files=data, headers=auth_headers)
    assert resp.status_code == 400
    assert "PDF and DOCX" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_resume_invalid_mime_type(client: AsyncClient, auth_headers: dict):
    """POST /candidates/resume with PDF extension but wrong MIME returns 400."""
    data = {"file": ("resume.pdf", io.BytesIO(b"%PDF-1.4 real"), "text/plain")}
    resp = await client.post(f"{API}/candidates/resume", files=data, headers=auth_headers)
    assert resp.status_code == 400
    assert "Invalid file type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_resume_pdf_bad_magic_bytes(client: AsyncClient, auth_headers: dict):
    """POST /candidates/resume with PDF MIME but bad magic bytes returns 400."""
    # Valid MIME type but content doesn't start with %PDF
    data = {"file": ("resume.pdf", io.BytesIO(b"not-a-pdf-content"), "application/pdf")}
    resp = await client.post(f"{API}/candidates/resume", files=data, headers=auth_headers)
    assert resp.status_code == 400
    assert "PDF format" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_resume_docx_bad_magic_bytes(client: AsyncClient, auth_headers: dict):
    """POST /candidates/resume with DOCX MIME but bad magic bytes returns 400."""
    bad_docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    data = {"file": ("resume.docx", io.BytesIO(b"not-a-zip"), bad_docx_mime)}
    resp = await client.post(f"{API}/candidates/resume", files=data, headers=auth_headers)
    assert resp.status_code == 400
    assert "DOCX format" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_resume_too_large(client: AsyncClient, auth_headers: dict):
    """POST /candidates/resume with file > 10MB returns 400."""
    large_content = b"%PDF" + b"x" * (10 * 1024 * 1024 + 1)
    data = {"file": ("big.pdf", io.BytesIO(large_content), "application/pdf")}
    resp = await client.post(f"{API}/candidates/resume", files=data, headers=auth_headers)
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"]


# ── GET /candidates/me/dna ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_dna_not_found(client: AsyncClient, auth_headers: dict):
    """GET /candidates/me/dna returns 404 when no DNA exists yet."""
    resp = await client.get(f"{API}/candidates/me/dna", headers=auth_headers)
    assert resp.status_code == 404
    assert "DNA not generated yet" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_dna_with_data(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """GET /candidates/me/dna returns DNA when seeded."""
    from app.models.candidate import CandidateDNA, Skill

    cid = await _get_candidate_id(client, auth_headers)

    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=cid,
        experience_summary="Senior backend engineer.",
        strengths=["Python", "APIs"],
        gaps=["Frontend"],
        career_stage="senior",
        transferable_skills={"leadership": "Led team of 5"},
    )
    db_session.add(dna)

    skill = Skill(
        id=uuid.uuid4(),
        candidate_id=cid,
        name="Python",
        category="explicit",
        proficiency="expert",
        years_experience=5.0,
        evidence="5 years",
    )
    db_session.add(skill)
    await db_session.commit()

    resp = await client.get(f"{API}/candidates/me/dna", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["experience_summary"] == "Senior backend engineer."
    assert data["career_stage"] == "senior"
    assert len(data["skills"]) == 1
    assert data["skills"][0]["name"] == "Python"


# ── GET /candidates/me/skills ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_skills_empty(client: AsyncClient, auth_headers: dict):
    """GET /candidates/me/skills returns empty list when no skills."""
    resp = await client.get(f"{API}/candidates/me/skills", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_skills_with_data(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """GET /candidates/me/skills returns seeded skills."""
    from app.models.candidate import Skill

    cid = await _get_candidate_id(client, auth_headers)

    for name, cat in [("Python", "explicit"), ("Docker", "explicit"), ("Communication", "transferable")]:
        skill = Skill(
            id=uuid.uuid4(),
            candidate_id=cid,
            name=name,
            category=cat,
            proficiency="advanced",
            years_experience=2.0,
            evidence=f"Used {name} at work",
        )
        db_session.add(skill)
    await db_session.commit()

    resp = await client.get(f"{API}/candidates/me/skills", headers=auth_headers)
    assert resp.status_code == 200
    skills = resp.json()
    assert len(skills) == 3
    names = {s["name"] for s in skills}
    assert names == {"Python", "Docker", "Communication"}
    # Verify response shape
    for s in skills:
        for key in ("id", "name", "category", "proficiency", "years_experience", "evidence"):
            assert key in s, f"Missing field: {key}"


# ── GET /candidates/me/resumes ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_resumes_empty(client: AsyncClient, auth_headers: dict):
    """GET /candidates/me/resumes returns empty list when no resumes."""
    resp = await client.get(f"{API}/candidates/me/resumes", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_resumes_with_data(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """GET /candidates/me/resumes returns seeded resumes in desc order."""
    from app.models.candidate import Resume

    cid = await _get_candidate_id(client, auth_headers)

    r1 = Resume(
        id=uuid.uuid4(),
        candidate_id=cid,
        file_path="resumes/first.pdf",
        file_hash="aabbcc001aabbcc001aabbcc001aabbcc001aabbcc001aabbcc001aabbcc001a",
        is_primary=True,
        parse_status="completed",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    r2 = Resume(
        id=uuid.uuid4(),
        candidate_id=cid,
        file_path="resumes/second.pdf",
        file_hash="bbccdd002bbccdd002bbccdd002bbccdd002bbccdd002bbccdd002bbccdd002b",
        is_primary=False,
        parse_status="pending",
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    db_session.add(r1)
    db_session.add(r2)
    await db_session.commit()

    resp = await client.get(f"{API}/candidates/me/resumes", headers=auth_headers)
    assert resp.status_code == 200
    resumes = resp.json()
    assert len(resumes) == 2
    # Should be ordered by created_at desc - r2 first
    assert resumes[0]["file_path"] == "resumes/second.pdf"
    assert resumes[1]["file_path"] == "resumes/first.pdf"
    # Verify shape
    for r in resumes:
        for key in ("id", "file_path", "is_primary", "parse_status", "created_at"):
            assert key in r


# ── DELETE /candidates/me/resumes/{id} ────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_resume_not_found(client: AsyncClient, auth_headers: dict):
    """DELETE /candidates/me/resumes/{id} with unknown id returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"{API}/candidates/me/resumes/{fake_id}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_primary_resume_rejected(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """DELETE /candidates/me/resumes/{id} on primary resume returns 400."""
    from app.models.candidate import Resume

    cid = await _get_candidate_id(client, auth_headers)
    r = Resume(
        id=uuid.uuid4(),
        candidate_id=cid,
        file_path="resumes/primary.pdf",
        file_hash="ccddee003ccddee003ccddee003ccddee003ccddee003ccddee003ccddee003c",
        is_primary=True,
        parse_status="completed",
    )
    db_session.add(r)
    await db_session.commit()

    resp = await client.delete(f"{API}/candidates/me/resumes/{r.id}", headers=auth_headers)
    assert resp.status_code == 400
    assert "primary" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_non_primary_resume_success(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """DELETE /candidates/me/resumes/{id} on non-primary returns 204."""
    from app.models.candidate import Resume

    cid = await _get_candidate_id(client, auth_headers)
    r = Resume(
        id=uuid.uuid4(),
        candidate_id=cid,
        file_path="resumes/secondary.pdf",
        file_hash="ddeeff004ddeeff004ddeeff004ddeeff004ddeeff004ddeeff004ddeeff004d",
        is_primary=False,
        parse_status="pending",
    )
    db_session.add(r)
    await db_session.commit()

    resp = await client.delete(f"{API}/candidates/me/resumes/{r.id}", headers=auth_headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_resume_other_candidate(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """DELETE /candidates/me/resumes/{id} cannot delete another candidate's resume."""
    from app.models.candidate import Candidate, Resume
    from app.utils.security import hash_password

    # Create a second candidate
    other = Candidate(
        id=uuid.uuid4(),
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("pass123"),
        full_name="Other User",
    )
    db_session.add(other)
    await db_session.flush()

    r = Resume(
        id=uuid.uuid4(),
        candidate_id=other.id,
        file_path="resumes/other.pdf",
        file_hash="eeff0005eeff0005eeff0005eeff0005eeff0005eeff0005eeff0005eeff0005",
        is_primary=False,
        parse_status="pending",
    )
    db_session.add(r)
    await db_session.commit()

    resp = await client.delete(f"{API}/candidates/me/resumes/{r.id}", headers=auth_headers)
    assert resp.status_code == 404


# ── GET /candidates/me/usage ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_usage_authenticated(client: AsyncClient, auth_headers: dict):
    """GET /candidates/me/usage returns quota data for authenticated user."""
    resp = await client.get(f"{API}/candidates/me/usage", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "plan_tier" in data
    assert "quotas" in data
