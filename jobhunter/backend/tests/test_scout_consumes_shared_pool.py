"""Verify the refactored scout pipeline reads from funding_signals and
scores per-candidate via the existing CandidateDNA cosine similarity path."""

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.candidate import Candidate, CandidateDNA
from app.models.company import Company
from app.models.funding_signal import FundingSignal
from app.utils.security import hash_password


@pytest_asyncio.fixture
async def patched_graph_db(test_engine, monkeypatch):
    import app.infrastructure.database as db_mod

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(db_mod, "async_session_factory", factory)


def _state(candidate_id: uuid.UUID) -> dict:
    return {
        "candidate_id": str(candidate_id),
        "plan_tier": "hunter",
        "parsed_companies": None,
        "scored_companies": None,
        "companies_created": 0,
        "status": "pending",
        "error": None,
    }


async def _seed_candidate_with_dna(db_session):
    cand_id = uuid.uuid4()
    db_session.add(
        Candidate(
            id=cand_id,
            email=f"scout-{uuid.uuid4().hex[:6]}@t.co",
            password_hash=hash_password("x"),
            full_name="T",
            target_industries=["fintech"],
        )
    )
    db_session.add(
        CandidateDNA(
            id=uuid.uuid4(),
            candidate_id=cand_id,
            embedding=[0.1] * 1536,
            skills_vector=[0.1] * 1536,
            experience_summary="Senior backend eng",
        )
    )
    await db_session.commit()
    return cand_id


@pytest.mark.asyncio
async def test_scout_scores_candidates_against_shared_pool(db_session, patched_graph_db):
    from sqlalchemy import delete

    from app.graphs.scout_pipeline import get_scout_pipeline_no_checkpointer

    # Reset pool for test isolation
    await db_session.execute(delete(FundingSignal))
    await db_session.commit()

    cand_id = await _seed_candidate_with_dna(db_session)

    # Seed a funding_signal whose embedding matches the DNA exactly (cosine=1.0)
    db_session.add(
        FundingSignal(
            id=uuid.uuid4(),
            source_url=f"https://news.example/shared-{uuid.uuid4()}",
            title="Acme raised $5M Series A",
            description="Acme builds backend infra.",
            published_at=datetime.now(UTC),
            company_name="Acme",
            estimated_domain=f"acme-{uuid.uuid4().hex[:6]}.co",
            funding_round="Series A",
            amount="$5M",
            industry="dev tools",
            signal_types=["funding_round"],
            extra_data={"funding_round": "Series A", "amount": "$5M"},
            embedding=[0.1] * 1536,
        )
    )
    await db_session.commit()

    graph = get_scout_pipeline_no_checkpointer()
    result = await graph.ainvoke(_state(cand_id))

    assert result["status"] == "completed"
    assert result["companies_created"] == 1

    created = (await db_session.execute(select(Company).where(Company.candidate_id == cand_id))).scalars().all()
    assert len(created) == 1
    assert created[0].name == "Acme"
    assert created[0].source == "scout_funding"


@pytest.mark.asyncio
async def test_scout_noop_when_pool_empty(db_session, patched_graph_db):
    from sqlalchemy import delete

    from app.graphs.scout_pipeline import get_scout_pipeline_no_checkpointer

    # Ensure pool is empty (test order isolation)
    await db_session.execute(delete(FundingSignal))
    await db_session.commit()

    cand_id = await _seed_candidate_with_dna(db_session)

    graph = get_scout_pipeline_no_checkpointer()
    result = await graph.ainvoke(_state(cand_id))

    assert result["status"] == "completed"
    assert result["companies_created"] == 0
