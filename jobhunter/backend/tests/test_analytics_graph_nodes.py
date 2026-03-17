"""Tests for the LangGraph analytics pipeline node functions."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.candidate import Candidate, CandidateDNA, Skill
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
async def patch_email_stub(monkeypatch):
    import app.dependencies as deps
    from tests.conftest import ResendStub
    deps._email_client = ResendStub()
    yield
    deps._email_client = None


@pytest_asyncio.fixture
async def candidate_with_data(db_session: AsyncSession):
    """Create a candidate with DNA and skills for analytics tests."""
    candidate_id = uuid.uuid4()
    candidate = Candidate(
        id=candidate_id,
        email=f"analytics-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass123"),
        full_name="Analytics Test User",
    )
    db_session.add(candidate)
    await db_session.flush()

    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        experience_summary="5 years Python backend development",
        strengths=["Python", "FastAPI", "PostgreSQL"],
        gaps=["Frontend"],
        career_stage="mid",
    )
    db_session.add(dna)

    for name in ["Python", "FastAPI", "PostgreSQL"]:
        skill = Skill(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            name=name,
            category="explicit",
            proficiency="advanced",
        )
        db_session.add(skill)

    await db_session.commit()
    return candidate_id


def _analytics_state(candidate_id: uuid.UUID, include_email: bool = False) -> dict:
    return {
        "candidate_id": str(candidate_id),
        "include_email": include_email,
        "raw_data": None,
        "insights": None,
        "insights_saved": 0,
        "status": "pending",
        "error": None,
    }


# ---------------------------------------------------------------------------
# Tests - generate_insights_node (pure OpenAI call, no DB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_insights_node_produces_insights(patch_openai_stub):
    """generate_insights_node should call OpenAI and return insights list."""
    from app.graphs.analytics_pipeline import generate_insights_node

    state = {
        "candidate_id": str(uuid.uuid4()),
        "include_email": False,
        "raw_data": {
            "funnel": {"researching": 3, "contacted": 1},
            "outreach": {"sent": 5, "replied": 1},
            "pipeline": {"total": 4},
            "skill_count": 3,
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "career_stage": "mid",
            "experience_summary": "5 years backend dev",
        },
        "insights": None,
        "insights_saved": 0,
        "status": "pending",
        "error": None,
    }

    result = await generate_insights_node(state)

    assert "insights" in result
    assert isinstance(result["insights"], list)
    assert len(result["insights"]) > 0
    # Each insight has required fields
    for insight in result["insights"]:
        assert "insight_type" in insight
        assert "title" in insight
        assert "body" in insight
        assert "severity" in insight


@pytest.mark.asyncio
async def test_generate_insights_node_handles_empty_data(patch_openai_stub):
    """generate_insights_node should handle empty raw_data gracefully."""
    from app.graphs.analytics_pipeline import generate_insights_node

    state = {
        "candidate_id": str(uuid.uuid4()),
        "include_email": False,
        "raw_data": {},
        "insights": None,
        "insights_saved": 0,
        "status": "pending",
        "error": None,
    }

    result = await generate_insights_node(state)
    assert "insights" in result
    assert isinstance(result["insights"], list)


@pytest.mark.asyncio
async def test_generate_insights_node_handles_none_raw_data(patch_openai_stub):
    """generate_insights_node should handle None raw_data."""
    from app.graphs.analytics_pipeline import generate_insights_node

    state = {
        "candidate_id": str(uuid.uuid4()),
        "include_email": False,
        "raw_data": None,
        "insights": None,
        "insights_saved": 0,
        "status": "pending",
        "error": None,
    }

    result = await generate_insights_node(state)
    assert "insights" in result


# ---------------------------------------------------------------------------
# Tests - _check_error routing
# ---------------------------------------------------------------------------

def test_check_error_routes_to_continue_on_success():
    """_check_error returns 'continue' when status is not 'failed'."""
    from app.graphs.analytics_pipeline import _check_error

    state = {"status": "pending", "error": None}
    assert _check_error(state) == "continue"


def test_check_error_routes_to_mark_failed_on_failure():
    """_check_error returns 'mark_failed' when status is 'failed'."""
    from app.graphs.analytics_pipeline import _check_error

    state = {"status": "failed", "error": "Something went wrong"}
    assert _check_error(state) == "mark_failed"


# ---------------------------------------------------------------------------
# Tests - mark_failed_node
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_failed_node_sets_status():
    """mark_failed_node should return status='failed'."""
    from app.graphs.analytics_pipeline import mark_failed_node

    state = {
        "candidate_id": str(uuid.uuid4()),
        "include_email": False,
        "raw_data": None,
        "insights": None,
        "insights_saved": 0,
        "status": "failed",
        "error": "Test error",
    }

    result = await mark_failed_node(state)
    assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# Tests - full pipeline (with DB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_analytics_pipeline(
    db_session, candidate_with_data, patch_graph_db, patch_openai_stub, patch_email_stub,
):
    """Full pipeline: gather_data -> generate_insights -> save_insights -> notify."""
    from app.graphs.analytics_pipeline import get_analytics_pipeline_no_checkpointer

    candidate_id = candidate_with_data
    graph = get_analytics_pipeline_no_checkpointer()
    state = _analytics_state(candidate_id)

    result = await graph.ainvoke(state)

    assert result["status"] == "completed"
    assert result["error"] is None
    assert result["insights"] is not None
    assert result["insights_saved"] > 0


@pytest.mark.asyncio
async def test_graph_structure():
    """Analytics graph has all expected nodes."""
    from app.graphs.analytics_pipeline import build_analytics_pipeline

    builder = build_analytics_pipeline()
    graph = builder.compile()
    node_names = set(graph.get_graph().nodes.keys())
    expected = {"gather_data", "generate_insights", "save_insights", "notify", "mark_failed"}
    assert expected.issubset(node_names)
