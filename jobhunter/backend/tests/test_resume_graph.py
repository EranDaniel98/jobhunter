"""Tests for the LangGraph resume processing pipeline."""

import uuid

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.candidate import Candidate, CandidateDNA, Resume, Skill
from app.utils.security import hash_password

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def graph_session_factory(test_engine):
    """Create a session factory bound to the test engine for graph nodes."""
    return async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture
async def patch_graph_db(graph_session_factory, monkeypatch):
    """Monkeypatch the graph module to use test DB session factory."""
    import app.infrastructure.database as db_mod
    monkeypatch.setattr(db_mod, "async_session_factory", graph_session_factory)


@pytest_asyncio.fixture
async def patch_openai_stub(monkeypatch):
    """Ensure the graph nodes use OpenAIStub via get_openai()."""
    import app.dependencies as deps
    from tests.conftest import OpenAIStub
    deps._openai_client = OpenAIStub()
    yield
    deps._openai_client = None


@pytest_asyncio.fixture
async def candidate_with_resume(db_session: AsyncSession):
    """Create a candidate with a resume that has raw_text."""
    candidate_id = uuid.uuid4()
    candidate = Candidate(
        id=candidate_id,
        email=f"graph-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass123"),
        full_name="Graph Test User",
    )
    db_session.add(candidate)
    await db_session.flush()

    resume_id = uuid.uuid4()
    resume = Resume(
        id=resume_id,
        candidate_id=candidate_id,
        file_path=f"resumes/{candidate_id}/test.pdf",
        file_hash="abc123",
        raw_text="John Doe\nSenior Software Engineer\n5 years Python development\nBuilt REST APIs with FastAPI\nLed team of 5 engineers\nMIT BS Computer Science 2018",
        is_primary=True,
    )
    db_session.add(resume)
    await db_session.commit()

    return candidate_id, resume_id


@pytest_asyncio.fixture
async def candidate_no_text(db_session: AsyncSession):
    """Create a candidate with a resume that has no raw_text."""
    candidate_id = uuid.uuid4()
    candidate = Candidate(
        id=candidate_id,
        email=f"graph-notext-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass123"),
        full_name="No Text User",
    )
    db_session.add(candidate)
    await db_session.flush()

    resume_id = uuid.uuid4()
    resume = Resume(
        id=resume_id,
        candidate_id=candidate_id,
        file_path=f"resumes/{candidate_id}/empty.pdf",
        file_hash="empty123",
        raw_text=None,
        is_primary=True,
    )
    db_session.add(resume)
    await db_session.commit()

    return candidate_id, resume_id


def _initial_state(resume_id: uuid.UUID, candidate_id: uuid.UUID) -> dict:
    """Build the initial graph state dict."""
    return {
        "resume_id": str(resume_id),
        "candidate_id": str(candidate_id),
        "parsed_data": None,
        "raw_text": None,
        "skills_data": None,
        "dna_data": None,
        "embedding": None,
        "skills_vector": None,
        "fit_scores_updated": 0,
        "status": "pending",
        "error": None,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_graph_full_pipeline(
    db_session, candidate_with_resume, patch_graph_db, patch_openai_stub
):
    """Full pipeline: parse → extract_skills → generate_dna → recalculate_fits → notify."""
    from app.graphs.resume_pipeline import get_resume_pipeline_no_checkpointer

    candidate_id, resume_id = candidate_with_resume
    graph = get_resume_pipeline_no_checkpointer()

    result = await graph.ainvoke(_initial_state(resume_id, candidate_id))

    # Pipeline completed successfully
    assert result["status"] == "completed"
    assert result["error"] is None

    # parsed_data was populated
    assert result["parsed_data"] is not None
    assert "name" in result["parsed_data"]

    # skills_data has categorized skills
    assert result["skills_data"] is not None
    skills = result["skills_data"]["skills"]
    assert len(skills) > 0
    assert all("category" in s for s in skills)

    # DNA and embedding vectors generated
    assert result["dna_data"] is not None
    assert result["embedding"] is not None
    assert result["skills_vector"] is not None

    # Verify DB state: CandidateDNA created
    dna_result = await db_session.execute(
        select(CandidateDNA).where(CandidateDNA.candidate_id == candidate_id)
    )
    dna = dna_result.scalar_one_or_none()
    assert dna is not None
    assert dna.experience_summary is not None
    assert dna.career_stage is not None

    # Verify DB state: Skill records created
    skills_result = await db_session.execute(
        select(Skill).where(Skill.candidate_id == candidate_id)
    )
    db_skills = skills_result.scalars().all()
    assert len(db_skills) > 0

    # Verify DB state: Resume marked completed
    resume_result = await db_session.execute(
        select(Resume).where(Resume.id == resume_id)
    )
    resume = resume_result.scalar_one()
    assert resume.parse_status == "completed"
    assert resume.parsed_data is not None


async def test_graph_missing_resume(
    db_session, patch_graph_db, patch_openai_stub
):
    """Non-existent resume_id should fail gracefully."""
    from app.graphs.resume_pipeline import get_resume_pipeline_no_checkpointer

    fake_resume_id = uuid.uuid4()
    fake_candidate_id = uuid.uuid4()
    graph = get_resume_pipeline_no_checkpointer()

    result = await graph.ainvoke(_initial_state(fake_resume_id, fake_candidate_id))

    assert result["status"] == "failed"
    assert "not found" in result["error"]


async def test_graph_no_raw_text(
    db_session, candidate_no_text, patch_graph_db, patch_openai_stub
):
    """Resume with no raw_text should fail and mark DB as failed."""
    from app.graphs.resume_pipeline import get_resume_pipeline_no_checkpointer

    candidate_id, resume_id = candidate_no_text
    graph = get_resume_pipeline_no_checkpointer()

    result = await graph.ainvoke(_initial_state(resume_id, candidate_id))

    assert result["status"] == "failed"
    assert "no extracted text" in result["error"]

    # Verify DB: resume marked as failed
    resume_result = await db_session.execute(
        select(Resume).where(Resume.id == resume_id)
    )
    resume = resume_result.scalar_one()
    assert resume.parse_status == "failed"


async def test_graph_state_has_skills(
    db_session, candidate_with_resume, patch_graph_db, patch_openai_stub
):
    """Verify skills_data contains properly categorized skills from the stub."""
    from app.graphs.resume_pipeline import get_resume_pipeline_no_checkpointer

    candidate_id, resume_id = candidate_with_resume
    graph = get_resume_pipeline_no_checkpointer()

    result = await graph.ainvoke(_initial_state(resume_id, candidate_id))

    assert result["status"] == "completed"
    skills = result["skills_data"]["skills"]

    # Verify stub returns expected categorized skills
    skill_names = {s["name"] for s in skills}
    assert "Python" in skill_names
    assert "FastAPI" in skill_names
    assert "Leadership" in skill_names

    categories = {s["category"] for s in skills}
    assert "explicit" in categories
    assert "transferable" in categories
