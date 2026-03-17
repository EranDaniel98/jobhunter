"""Tests for the LangGraph interview prep pipeline node functions."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.candidate import Candidate, CandidateDNA
from app.models.company import Company, CompanyDossier
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
async def candidate_with_company(db_session: AsyncSession):
    """Create a candidate with DNA and a company with dossier."""
    candidate_id = uuid.uuid4()
    candidate = Candidate(
        id=candidate_id,
        email=f"interview-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass123"),
        full_name="Interview Test User",
    )
    db_session.add(candidate)
    await db_session.flush()

    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        experience_summary="5 years Python backend development",
        strengths=["Python", "FastAPI", "System Design"],
        gaps=["Frontend", "Mobile"],
        career_stage="mid",
    )
    db_session.add(dna)

    company_id = uuid.uuid4()
    company = Company(
        id=company_id,
        candidate_id=candidate_id,
        name="InterviewCo",
        domain="interviewco.com",
        industry="Technology",
        tech_stack=["Python", "Go", "React"],
        size_range="201-500",
        status="researching",
    )
    db_session.add(company)
    await db_session.flush()

    dossier = CompanyDossier(
        id=uuid.uuid4(),
        company_id=company_id,
        culture_summary="Fast-paced startup culture focused on innovation",
        culture_score=8,
        red_flags=[],
        interview_format="Phone screen, technical, system design, onsite",
        compensation_data={"range": "150k-200k", "equity": "0.1%"},
        why_hire_me="Strong backend and system design experience",
    )
    db_session.add(dossier)
    await db_session.commit()

    return candidate_id, company_id


def _interview_state(
    candidate_id: uuid.UUID,
    company_id: uuid.UUID,
    prep_type: str = "company_qa",
) -> dict:
    return {
        "candidate_id": str(candidate_id),
        "company_id": str(company_id),
        "prep_type": prep_type,
        "session_id": None,
        "context": None,
        "content": None,
        "status": "pending",
        "error": None,
    }


# ---------------------------------------------------------------------------
# Tests - generate_prep_node for each prep_type (OpenAI call, no DB)
# ---------------------------------------------------------------------------

def _make_context():
    """Build a context dict like load_context_node would produce."""
    return {
        "company_name": "InterviewCo",
        "industry": "Technology",
        "tech_stack": "Python, Go, React",
        "size_range": "201-500",
        "culture_summary": "Fast-paced startup culture",
        "red_flags": "None",
        "interview_format": "Phone screen, technical, system design",
        "compensation_data": '{"range": "150k-200k"}',
        "why_hire_me": "Strong backend experience",
        "candidate_summary": "5 years Python backend dev",
        "strengths": "Python, FastAPI, System Design",
        "gaps": "Frontend, Mobile",
        "career_stage": "mid",
    }


@pytest.mark.asyncio
async def test_generate_prep_company_qa(patch_openai_stub):
    """generate_prep_node with prep_type=company_qa returns questions and tips."""
    from app.graphs.interview_prep import generate_prep_node

    state = {
        "candidate_id": str(uuid.uuid4()),
        "company_id": str(uuid.uuid4()),
        "prep_type": "company_qa",
        "session_id": str(uuid.uuid4()),
        "context": _make_context(),
        "content": None,
        "status": "generating",
        "error": None,
    }

    result = await generate_prep_node(state)

    assert "content" in result
    content = result["content"]
    assert "questions" in content
    assert "tips" in content
    assert isinstance(content["questions"], list)
    assert len(content["questions"]) > 0


@pytest.mark.asyncio
async def test_generate_prep_behavioral(patch_openai_stub):
    """generate_prep_node with prep_type=behavioral returns STAR stories."""
    from app.graphs.interview_prep import generate_prep_node

    state = {
        "candidate_id": str(uuid.uuid4()),
        "company_id": str(uuid.uuid4()),
        "prep_type": "behavioral",
        "session_id": str(uuid.uuid4()),
        "context": _make_context(),
        "content": None,
        "status": "generating",
        "error": None,
    }

    result = await generate_prep_node(state)

    assert "content" in result
    stories = result["content"]["stories"]
    assert isinstance(stories, list)
    assert len(stories) > 0
    for story in stories:
        assert "situation" in story
        assert "task" in story
        assert "action" in story
        assert "result" in story


@pytest.mark.asyncio
async def test_generate_prep_technical(patch_openai_stub):
    """generate_prep_node with prep_type=technical returns topics with questions."""
    from app.graphs.interview_prep import generate_prep_node

    state = {
        "candidate_id": str(uuid.uuid4()),
        "company_id": str(uuid.uuid4()),
        "prep_type": "technical",
        "session_id": str(uuid.uuid4()),
        "context": _make_context(),
        "content": None,
        "status": "generating",
        "error": None,
    }

    result = await generate_prep_node(state)

    assert "content" in result
    topics = result["content"]["topics"]
    assert isinstance(topics, list)
    assert len(topics) > 0
    for topic in topics:
        assert "questions" in topic
        for q in topic["questions"]:
            assert "question" in q
            assert "answer" in q
            assert "difficulty" in q


@pytest.mark.asyncio
async def test_generate_prep_unknown_type(patch_openai_stub):
    """generate_prep_node with unknown prep_type should return failed status."""
    from app.graphs.interview_prep import generate_prep_node

    state = {
        "candidate_id": str(uuid.uuid4()),
        "company_id": str(uuid.uuid4()),
        "prep_type": "nonexistent_type",
        "session_id": str(uuid.uuid4()),
        "context": _make_context(),
        "content": None,
        "status": "generating",
        "error": None,
    }

    result = await generate_prep_node(state)

    assert result["status"] == "failed"
    assert "Unknown prep_type" in result["error"]


# ---------------------------------------------------------------------------
# Tests - _check_error routing
# ---------------------------------------------------------------------------

def test_check_error_continue():
    from app.graphs.interview_prep import _check_error
    assert _check_error({"status": "generating"}) == "continue"


def test_check_error_failed():
    from app.graphs.interview_prep import _check_error
    assert _check_error({"status": "failed"}) == "mark_failed"


# ---------------------------------------------------------------------------
# Tests - mark_failed_node
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_failed_node_no_session():
    """mark_failed_node with no session_id should not crash."""
    from app.graphs.interview_prep import mark_failed_node

    state = {
        "candidate_id": str(uuid.uuid4()),
        "company_id": str(uuid.uuid4()),
        "prep_type": "company_qa",
        "session_id": None,
        "context": None,
        "content": None,
        "status": "failed",
        "error": "Test failure",
    }

    result = await mark_failed_node(state)
    assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# Tests - load_context_node (needs DB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_context_company_not_found(patch_graph_db, patch_openai_stub):
    """load_context_node should fail for non-existent company."""
    from app.graphs.interview_prep import load_context_node

    state = _interview_state(uuid.uuid4(), uuid.uuid4())

    result = await load_context_node(state)

    assert result["status"] == "failed"
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_load_context_builds_context(
    db_session, candidate_with_company, patch_graph_db, patch_openai_stub,
):
    """load_context_node should build context dict from DB records."""
    from app.graphs.interview_prep import load_context_node

    candidate_id, company_id = candidate_with_company
    state = _interview_state(candidate_id, company_id)

    result = await load_context_node(state)

    assert result["status"] == "generating"
    assert result["session_id"] is not None
    ctx = result["context"]
    assert ctx["company_name"] == "InterviewCo"
    assert ctx["industry"] == "Technology"
    assert "Python" in ctx["strengths"]


# ---------------------------------------------------------------------------
# Tests - graph structure
# ---------------------------------------------------------------------------

def test_interview_graph_has_expected_nodes():
    """Interview prep graph has all expected nodes."""
    from app.graphs.interview_prep import build_interview_prep_pipeline

    builder = build_interview_prep_pipeline()
    graph = builder.compile()
    node_names = set(graph.get_graph().nodes.keys())
    expected = {"load_context", "generate_prep", "save_and_notify", "mark_failed"}
    assert expected.issubset(node_names)
