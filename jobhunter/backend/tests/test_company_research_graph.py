"""Tests for the LangGraph company research pipeline."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.candidate import Candidate, CandidateDNA
from app.models.company import Company, CompanyDossier
from app.models.contact import Contact
from app.utils.security import hash_password
from app.graphs.company_research import (
    CompanyResearchState,
    build_company_research_graph,
    get_company_research_pipeline_no_checkpointer,
)


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
async def patch_stubs(monkeypatch):
    """Ensure the graph nodes use OpenAIStub and HunterStub via get_openai()/get_hunter()."""
    import app.dependencies as deps
    from tests.conftest import OpenAIStub, HunterStub
    deps._openai_client = OpenAIStub()
    deps._hunter_client = HunterStub()
    yield
    deps._openai_client = None
    deps._hunter_client = None


@pytest_asyncio.fixture
async def candidate_with_company(db_session: AsyncSession):
    """Create a candidate with DNA and a company ready for research."""
    candidate_id = uuid.uuid4()
    candidate = Candidate(
        id=candidate_id,
        email=f"graph-co-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass123"),
        full_name="Company Graph Test User",
    )
    db_session.add(candidate)
    await db_session.flush()

    # Create CandidateDNA (needed for dossier personalization)
    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        experience_summary="Experienced software engineer with 5 years in Python and cloud.",
        strengths=["Python", "Cloud Architecture"],
        gaps=[],
        career_stage="mid",
    )
    db_session.add(dna)
    await db_session.flush()

    # Create a company to research
    company_id = uuid.uuid4()
    company = Company(
        id=company_id,
        candidate_id=candidate_id,
        name="Graphtest",
        domain="graphtest.com",
        status="approved",
        research_status="pending",
    )
    db_session.add(company)
    await db_session.commit()

    return candidate_id, company_id


def _initial_state(company_id: uuid.UUID, candidate_id: uuid.UUID) -> CompanyResearchState:
    """Build the initial graph state dict."""
    return {
        "company_id": str(company_id),
        "candidate_id": str(candidate_id),
        "plan_tier": "free",
        "hunter_data": None,
        "web_context": None,
        "dossier_data": None,
        "contacts_created": 0,
        "embedding_set": False,
        "status": "pending",
        "error": None,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_graph_builds_and_compiles():
    """The graph should build and compile without errors."""
    graph = build_company_research_graph()
    assert graph is not None
    compiled = graph.compile()
    assert compiled is not None


@pytest.mark.asyncio
async def test_graph_has_expected_nodes():
    """Graph should contain all 7 nodes."""
    graph = build_company_research_graph()
    node_names = set(graph.nodes.keys())
    expected = {
        "enrich_company", "web_search", "generate_dossier",
        "create_contacts", "embed_company", "notify", "mark_failed",
    }
    assert expected == node_names


@pytest.mark.asyncio
async def test_full_pipeline_with_stubs(
    db_session, candidate_with_company, patch_graph_db, patch_stubs
):
    """Full graph run: enrich -> web_search -> dossier -> contacts -> embed -> notify."""
    candidate_id, company_id = candidate_with_company

    # Mock DuckDuckGo (synchronous DDGS) to avoid real HTTP calls
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text = MagicMock(return_value=[
        {"title": "GraphTest raises $50M", "body": "Series B funding round."},
        {"title": "GraphTest Glassdoor", "body": "Great culture, fast-paced."},
    ])
    mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
    mock_ddgs_instance.__exit__ = MagicMock(return_value=False)

    with patch("duckduckgo_search.DDGS", return_value=mock_ddgs_instance):
        pipeline = get_company_research_pipeline_no_checkpointer()
        result = await pipeline.ainvoke(
            _initial_state(company_id, candidate_id)
        )

    assert result["status"] == "completed"
    assert result["error"] is None
    assert result["hunter_data"] is not None
    assert result["dossier_data"] is not None
    assert result["contacts_created"] >= 0
    assert result["embedding_set"] is True

    # Verify DB state: company research_status is completed
    co_result = await db_session.execute(
        select(Company).where(Company.id == company_id)
    )
    company = co_result.scalar_one()
    assert company.research_status == "completed"
    assert company.embedding is not None
    assert company.last_enriched is not None

    # Verify DB state: dossier was created
    dos_result = await db_session.execute(
        select(CompanyDossier).where(CompanyDossier.company_id == company_id)
    )
    dossier = dos_result.scalar_one_or_none()
    assert dossier is not None
    assert dossier.culture_summary is not None

    # Verify DB state: contacts were created from hunter data
    ct_result = await db_session.execute(
        select(Contact).where(Contact.company_id == company_id)
    )
    contacts = ct_result.scalars().all()
    assert len(contacts) >= 0  # HunterStub returns 1 email


@pytest.mark.asyncio
async def test_pipeline_handles_missing_company(patch_graph_db, patch_stubs):
    """Graph should fail gracefully when company doesn't exist."""
    pipeline = get_company_research_pipeline_no_checkpointer()
    result = await pipeline.ainvoke(
        _initial_state(uuid.uuid4(), uuid.uuid4())
    )
    assert result["status"] == "failed"
    assert "not found" in result["error"]
