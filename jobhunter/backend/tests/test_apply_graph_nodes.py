"""Tests for the LangGraph apply pipeline node functions."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.candidate import Candidate, CandidateDNA, Skill
from app.models.company import Company, CompanyDossier
from app.models.job_posting import JobPosting
from app.utils.security import hash_password

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def graph_session_factory(test_engine):
    return async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture
async def patch_graph_db(graph_session_factory, monkeypatch):
    import app.infrastructure.database as db_mod
    monkeypatch.setattr(db_mod, "async_session_factory", graph_session_factory)


@pytest_asyncio.fixture
async def patch_openai_stub(monkeypatch):
    import app.dependencies as deps
    from tests.conftest import OpenAIStub
    deps._openai_client = OpenAIStub()
    yield
    deps._openai_client = None


@pytest_asyncio.fixture
async def candidate_with_job(db_session: AsyncSession):
    """Create a candidate with DNA, skills, a company, and a job posting."""
    candidate_id = uuid.uuid4()
    candidate = Candidate(
        id=candidate_id,
        email=f"apply-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("Testpass123"),
        full_name="Apply Test User",
    )
    db_session.add(candidate)
    await db_session.flush()

    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        experience_summary="5 years Python backend development",
        strengths=["Python", "FastAPI", "PostgreSQL"],
        gaps=["Frontend", "Mobile"],
        career_stage="mid",
    )
    db_session.add(dna)

    for name in ["python", "fastapi", "postgresql"]:
        skill = Skill(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            name=name,
            category="explicit",
            proficiency="advanced",
        )
        db_session.add(skill)

    company_id = uuid.uuid4()
    company = Company(
        id=company_id,
        candidate_id=candidate_id,
        name="TestCorp",
        domain="testcorp.com",
        industry="Technology",
        status="researching",
    )
    db_session.add(company)
    await db_session.flush()

    dossier = CompanyDossier(
        id=uuid.uuid4(),
        company_id=company_id,
        culture_summary="Innovative engineering culture",
        culture_score=8,
        why_hire_me="Strong backend experience",
    )
    db_session.add(dossier)

    job_posting_id = uuid.uuid4()
    posting = JobPosting(
        id=job_posting_id,
        candidate_id=candidate_id,
        company_id=company_id,
        company_name="TestCorp",
        title="Senior Backend Engineer",
        url="https://testcorp.com/careers/sbe",
        raw_text="We are looking for a Senior Backend Engineer with 3+ years Python, FastAPI, PostgreSQL experience. Docker and Kubernetes preferred.",
        status="pending",
    )
    db_session.add(posting)
    await db_session.commit()

    return candidate_id, job_posting_id


def _apply_state(candidate_id: uuid.UUID, job_posting_id: uuid.UUID) -> dict:
    return {
        "candidate_id": str(candidate_id),
        "job_posting_id": str(job_posting_id),
        "parsed_requirements": None,
        "candidate_skills": None,
        "matching_skills": None,
        "missing_skills": None,
        "resume_tips": None,
        "readiness_score": None,
        "cover_letter": None,
        "ats_keywords": None,
        "context": None,
        "status": "pending",
        "error": None,
    }


# ---------------------------------------------------------------------------
# Tests - match_skills_node (pure logic, no DB or OpenAI)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_match_skills_finds_matches():
    """match_skills_node should find intersection of candidate and job skills."""
    from app.graphs.apply_pipeline import match_skills_node

    state = {
        "parsed_requirements": {
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "preferred_skills": ["Docker", "Kubernetes"],
        },
        "candidate_skills": ["python", "fastapi", "docker"],
    }

    result = await match_skills_node(state)

    assert "python" in result["matching_skills"]
    assert "fastapi" in result["matching_skills"]
    assert "docker" in result["matching_skills"]
    assert "postgresql" in result["missing_skills"]


@pytest.mark.asyncio
async def test_match_skills_no_overlap():
    """match_skills_node with no overlapping skills."""
    from app.graphs.apply_pipeline import match_skills_node

    state = {
        "parsed_requirements": {
            "required_skills": ["Java", "Spring"],
            "preferred_skills": ["AWS"],
        },
        "candidate_skills": ["python", "fastapi"],
    }

    result = await match_skills_node(state)

    assert result["matching_skills"] == []
    assert "java" in result["missing_skills"]
    assert "spring" in result["missing_skills"]


@pytest.mark.asyncio
async def test_match_skills_case_insensitive():
    """match_skills_node should be case-insensitive."""
    from app.graphs.apply_pipeline import match_skills_node

    state = {
        "parsed_requirements": {
            "required_skills": ["PYTHON", "FastAPI"],
            "preferred_skills": [],
        },
        "candidate_skills": ["python", "fastapi"],
    }

    result = await match_skills_node(state)

    assert "python" in result["matching_skills"]
    assert "fastapi" in result["matching_skills"]
    assert result["missing_skills"] == []


@pytest.mark.asyncio
async def test_match_skills_empty_candidate_skills():
    """match_skills_node handles empty candidate skills."""
    from app.graphs.apply_pipeline import match_skills_node

    state = {
        "parsed_requirements": {
            "required_skills": ["Python"],
            "preferred_skills": ["Docker"],
        },
        "candidate_skills": [],
    }

    result = await match_skills_node(state)

    assert result["matching_skills"] == []
    assert "python" in result["missing_skills"]


# ---------------------------------------------------------------------------
# Tests - generate_tips_node (OpenAI call)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_tips_node_returns_tips(patch_openai_stub):
    """generate_tips_node should return resume tips and readiness score."""
    from app.graphs.apply_pipeline import generate_tips_node

    state = {
        "parsed_requirements": {
            "required_skills": ["Python", "FastAPI"],
            "preferred_skills": ["Docker"],
        },
        "candidate_skills": ["python", "fastapi"],
        "context": {
            "title": "Senior Backend Engineer",
            "company_name": "TestCorp",
            "candidate_summary": "5 years Python backend dev",
            "gaps": "Frontend",
        },
        "status": "pending",
        "error": None,
    }

    result = await generate_tips_node(state)

    assert "resume_tips" in result
    assert isinstance(result["resume_tips"], list)
    assert len(result["resume_tips"]) > 0
    assert "readiness_score" in result
    assert isinstance(result["readiness_score"], (int, float))

    for tip in result["resume_tips"]:
        assert "section" in tip
        assert "tip" in tip
        assert "priority" in tip


# ---------------------------------------------------------------------------
# Tests - generate_cover_letter_node (OpenAI call)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_cover_letter_node(patch_openai_stub):
    """generate_cover_letter_node should return a cover letter string."""
    from app.graphs.apply_pipeline import generate_cover_letter_node

    state = {
        "parsed_requirements": {
            "required_skills": ["Python", "FastAPI"],
        },
        "matching_skills": ["python", "fastapi"],
        "context": {
            "title": "Senior Backend Engineer",
            "company_name": "TestCorp",
            "candidate_summary": "5 years Python backend dev",
            "why_hire_me": "Strong backend experience",
        },
        "status": "pending",
        "error": None,
    }

    result = await generate_cover_letter_node(state)

    assert "cover_letter" in result
    assert isinstance(result["cover_letter"], str)
    assert len(result["cover_letter"]) > 0


# ---------------------------------------------------------------------------
# Tests - _check_error routing
# ---------------------------------------------------------------------------

def test_check_error_continue():
    from app.graphs.apply_pipeline import _check_error
    assert _check_error({"status": "pending"}) == "continue"


def test_check_error_failed():
    from app.graphs.apply_pipeline import _check_error
    assert _check_error({"status": "failed"}) == "mark_failed"


# ---------------------------------------------------------------------------
# Tests - parse_job_node (needs DB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_job_node_not_found(patch_graph_db, patch_openai_stub):
    """parse_job_node should fail gracefully for non-existent job posting."""
    from app.graphs.apply_pipeline import parse_job_node

    state = _apply_state(uuid.uuid4(), uuid.uuid4())

    result = await parse_job_node(state)

    assert result["status"] == "failed"
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_parse_job_node_extracts_requirements(
    db_session, candidate_with_job, patch_graph_db, patch_openai_stub,
):
    """parse_job_node should parse job posting and return structured requirements."""
    from app.graphs.apply_pipeline import parse_job_node

    candidate_id, job_posting_id = candidate_with_job
    state = _apply_state(candidate_id, job_posting_id)

    result = await parse_job_node(state)

    assert "parsed_requirements" in result
    assert "required_skills" in result["parsed_requirements"]
    assert "ats_keywords" in result
    assert "candidate_skills" in result
    assert "context" in result
    assert result["context"]["company_name"] == "TestCorp"
