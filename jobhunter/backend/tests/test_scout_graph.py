"""Tests for the Scout Agent (funding news discovery) pipeline."""

import uuid

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models.candidate import Candidate, CandidateDNA
from app.models.company import Company
from app.models.signal import CompanySignal
from app.utils.security import hash_password

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def graph_session_factory(test_engine):
    """Create a session factory bound to the test engine for graph nodes."""
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def patch_graph_db(graph_session_factory, monkeypatch):
    """Monkeypatch the graph module to use test DB session factory."""
    import app.infrastructure.database as db_mod

    monkeypatch.setattr(db_mod, "async_session_factory", graph_session_factory)


@pytest_asyncio.fixture
async def patch_stubs(monkeypatch):
    """Ensure the graph nodes use test stubs."""
    import app.dependencies as deps
    from tests.conftest import NewsAPIStub, OpenAIStub

    deps._openai_client = OpenAIStub()
    deps._newsapi_client = NewsAPIStub()
    yield
    deps._openai_client = None
    deps._newsapi_client = None


@pytest_asyncio.fixture
async def candidate_with_dna(db_session: AsyncSession):
    """Create a candidate with CandidateDNA (needed by scout pipeline)."""
    candidate_id = uuid.uuid4()
    candidate = Candidate(
        id=candidate_id,
        email=f"scout-test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass123"),
        full_name="Scout Test User",
        target_industries=["technology", "fintech"],
    )
    db_session.add(candidate)
    await db_session.flush()

    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        embedding=[0.1] * 1536,
        skills_vector=[0.1] * 1536,
        experience_summary="Experienced backend engineer with 5 years in Python and cloud.",
        strengths=["Python", "Cloud Architecture", "APIs"],
        gaps=["Frontend"],
        career_stage="mid",
    )
    db_session.add(dna)
    await db_session.commit()

    return candidate_id


@pytest_asyncio.fixture
async def candidate_no_dna(db_session: AsyncSession):
    """Create a candidate without CandidateDNA."""
    candidate_id = uuid.uuid4()
    candidate = Candidate(
        id=candidate_id,
        email=f"scout-nodna-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass123"),
        full_name="No DNA User",
    )
    db_session.add(candidate)
    await db_session.commit()

    return candidate_id


def _initial_state(candidate_id: uuid.UUID) -> dict:
    """Build the initial scout graph state dict."""
    return {
        "candidate_id": str(candidate_id),
        "plan_tier": "free",
        "parsed_companies": None,
        "scored_companies": None,
        "companies_created": 0,
        "status": "pending",
        "error": None,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_graph_builds_and_compiles():
    """Scout graph builds and compiles without errors."""
    from app.graphs.scout_pipeline import get_scout_pipeline_no_checkpointer

    graph = get_scout_pipeline_no_checkpointer()
    assert graph is not None


def test_graph_has_expected_nodes():
    """Verify post-refactor node set: load_shared_signals replaces the old 3."""
    from app.graphs.scout_pipeline import build_scout_pipeline

    builder = build_scout_pipeline()
    node_names = set(builder.nodes.keys())
    expected = {
        "load_shared_signals",
        "score_and_filter",
        "create_companies",
        "notify",
        "mark_failed",
    }
    assert expected == node_names


async def test_full_pipeline(db_session, candidate_with_dna, patch_graph_db, patch_stubs):
    """Full pipeline: load shared signals → score → create → notify."""
    from datetime import UTC, datetime

    from app.graphs.scout_pipeline import get_scout_pipeline_no_checkpointer
    from app.models.funding_signal import FundingSignal

    # Seed a funding_signal whose embedding matches the DNA for scoring
    db_session.add(
        FundingSignal(
            id=uuid.uuid4(),
            source_url=f"https://news.example/full-{uuid.uuid4()}",
            title="Acme raised $5M Series A",
            description="Acme builds fintech APIs.",
            published_at=datetime.now(UTC),
            company_name="Acme",
            estimated_domain=f"acme-{uuid.uuid4().hex[:6]}.co",
            funding_round="Series A",
            amount="$5M",
            industry="fintech",
            signal_types=["funding_round"],
            embedding=[0.1] * 1536,
        )
    )
    await db_session.commit()

    candidate_id = candidate_with_dna
    graph = get_scout_pipeline_no_checkpointer()

    result = await graph.ainvoke(_initial_state(candidate_id))

    assert result["status"] == "completed"
    assert result["error"] is None
    assert result["companies_created"] >= 1

    # Verify Company records created with correct source
    companies_result = await db_session.execute(
        select(Company).where(
            Company.candidate_id == candidate_id,
            Company.source == "scout_funding",
        )
    )
    companies = companies_result.scalars().all()
    assert len(companies) >= 1

    for company in companies:
        assert company.status == "suggested"
        assert company.research_status == "pending"
        assert company.source == "scout_funding"
        assert company.fit_score is not None

    # Verify CompanySignal records created
    signals_result = await db_session.execute(select(CompanySignal).where(CompanySignal.candidate_id == candidate_id))
    signals = signals_result.scalars().all()
    assert len(signals) >= 1

    for signal in signals:
        assert signal.signal_type == "funding_round"
        assert signal.metadata_ is not None
        assert "funding_round" in signal.metadata_


async def test_pipeline_no_dna_fails(db_session, candidate_no_dna, patch_graph_db, patch_stubs):
    """Candidate without CandidateDNA should result in status='failed' once scoring starts."""
    from datetime import UTC, datetime

    from app.graphs.scout_pipeline import get_scout_pipeline_no_checkpointer
    from app.models.funding_signal import FundingSignal

    # Need at least one signal so scoring is reached (empty pool = completed no-op)
    db_session.add(
        FundingSignal(
            id=uuid.uuid4(),
            source_url=f"https://news.example/nodna-{uuid.uuid4()}",
            title="x",
            description="d",
            published_at=datetime.now(UTC),
            company_name="X",
            estimated_domain=f"x-{uuid.uuid4().hex[:6]}.co",
            embedding=[0.1] * 1536,
        )
    )
    await db_session.commit()

    candidate_id = candidate_no_dna
    graph = get_scout_pipeline_no_checkpointer()

    result = await graph.ainvoke(_initial_state(candidate_id))

    assert result["status"] == "failed"
    assert "embedding" in result["error"].lower() or "dna" in result["error"].lower()


async def test_scout_run_endpoint(client, auth_headers, db_session):
    """POST /scout/run returns 200 with status='scouting'."""
    # Seed DNA for the authenticated user
    from tests.conftest import seed_candidate_dna

    await seed_candidate_dna(db_session, client, auth_headers)

    resp = await client.post(
        f"{settings.API_V1_PREFIX}/scout/run",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "scouting"
    assert "thread_id" in data


async def test_scout_signals_empty(client, auth_headers):
    """GET /scout/signals returns empty list for candidate with no signals."""
    resp = await client.get(
        f"{settings.API_V1_PREFIX}/scout/signals",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["signals"] == []
    assert data["total"] == 0
