"""Integration tests for app/api/scout.py — covers uncovered route lines."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate import CandidateDNA
from app.models.company import Company
from app.models.signal import CompanySignal

API = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_candidate_id(client: AsyncClient, auth_headers: dict) -> uuid.UUID:
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    return uuid.UUID(resp.json()["id"])


async def _seed_dna(db_session: AsyncSession, candidate_id: uuid.UUID) -> CandidateDNA:
    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        experience_summary="Software engineer with 5 years Python experience.",
        strengths=["Python", "APIs"],
        gaps=[],
        career_stage="mid",
    )
    db_session.add(dna)
    await db_session.flush()
    return dna


async def _seed_signal(
    db_session: AsyncSession,
    candidate_id: uuid.UUID,
    company_id: uuid.UUID,
) -> CompanySignal:
    signal = CompanySignal(
        id=uuid.uuid4(),
        company_id=company_id,
        candidate_id=candidate_id,
        signal_type="funding_round",
        title="Series B Funding",
        description="Raised $50M Series B",
        source_url="https://techcrunch.com/example",
        signal_strength=0.9,
        detected_at=datetime.now(UTC),
        metadata_={"funding_round": "Series B", "amount": "$50M"},
    )
    db_session.add(signal)
    await db_session.flush()
    return signal


# ---------------------------------------------------------------------------
# POST /scout/run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_scout(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Trigger the scout pipeline — should return 200 with scouting status."""
    candidate_id = await _get_candidate_id(client, auth_headers)
    await _seed_dna(db_session, candidate_id)

    resp = await client.post(f"{API}/scout/run", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "scouting"
    assert "thread_id" in data


# ---------------------------------------------------------------------------
# GET /scout/signals
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_signals_empty(client: AsyncClient, auth_headers: dict):
    """Returns empty list when no signals exist."""
    resp = await client.get(f"{API}/scout/signals", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["signals"] == []


@pytest.mark.asyncio
async def test_list_signals_with_data(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Returns signals with company name when signals exist."""
    candidate_id = await _get_candidate_id(client, auth_headers)

    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name="FundedCo",
        domain="fundedco.com",
    )
    db_session.add(company)
    await db_session.flush()

    await _seed_signal(db_session, candidate_id, company.id)

    resp = await client.get(f"{API}/scout/signals", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["signals"]) == 1

    signal = data["signals"][0]
    assert signal["company_name"] == "FundedCo"
    assert signal["signal_type"] == "funding_round"
    assert signal["funding_round"] == "Series B"
    assert signal["amount"] == "$50M"


@pytest.mark.asyncio
async def test_list_signals_pagination(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Pagination parameters are respected."""
    candidate_id = await _get_candidate_id(client, auth_headers)

    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name="PaginateCo",
        domain="paginateco.com",
    )
    db_session.add(company)
    await db_session.flush()

    for _ in range(3):
        await _seed_signal(db_session, candidate_id, company.id)

    resp = await client.get(f"{API}/scout/signals?skip=0&limit=2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    assert len(data["signals"]) <= 2
