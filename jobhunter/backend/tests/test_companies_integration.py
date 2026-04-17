"""Integration tests for company API endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company, CompanyDossier

API = settings.API_V1_PREFIX


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_candidate_id(client: AsyncClient, auth_headers: dict) -> uuid.UUID:
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    return uuid.UUID(resp.json()["id"])


async def _seed_company(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    *,
    name: str = "TestCo",
    domain: str | None = None,
    status: str = "suggested",
    fit_score: float | None = None,
) -> Company:
    domain = domain or f"{name.lower().replace(' ', '')}.example.com"
    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name=name,
        domain=domain,
        industry="Technology",
        status=status,
        research_status="pending",
        fit_score=fit_score,
    )
    db.add(company)
    await db.flush()
    return company


# ── GET /companies ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_companies_with_data(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    await _seed_company(db_session, cid, name="AlphaCo", domain="alphaco.dev")
    await _seed_company(db_session, cid, name="BetaCo", domain="betaco.dev")
    await db_session.commit()

    resp = await client.get(f"{API}/companies", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    names = [c["name"] for c in data["companies"]]
    assert "AlphaCo" in names
    assert "BetaCo" in names


@pytest.mark.asyncio
async def test_list_companies_status_filter(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    await _seed_company(db_session, cid, name="ApprovedCo", domain="approved.dev", status="approved")
    await _seed_company(db_session, cid, name="RejectedCo", domain="rejected.dev", status="rejected")
    await db_session.commit()

    resp = await client.get(f"{API}/companies?status=approved", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    names = [c["name"] for c in data["companies"]]
    assert "ApprovedCo" in names
    assert "RejectedCo" not in names


@pytest.mark.asyncio
async def test_list_companies_pagination(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    for i in range(5):
        await _seed_company(db_session, cid, name=f"PagCo{i}", domain=f"pagco{i}.dev")
    await db_session.commit()

    resp = await client.get(f"{API}/companies?skip=0&limit=2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["companies"]) <= 2


@pytest.mark.asyncio
async def test_list_companies_fit_score_ordering(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Companies should be ordered by fit_score desc (nulls last)."""
    cid = await _get_candidate_id(client, auth_headers)
    await _seed_company(db_session, cid, name="HighScore", domain="highscore.dev", fit_score=90.0)
    await _seed_company(db_session, cid, name="LowScore", domain="lowscore.dev", fit_score=10.0)
    await db_session.commit()

    resp = await client.get(f"{API}/companies", headers=auth_headers)
    assert resp.status_code == 200
    companies = resp.json()["companies"]
    # find our two companies
    scores = {c["name"]: c.get("fit_score") for c in companies if c["name"] in ("HighScore", "LowScore")}
    if scores.get("HighScore") and scores.get("LowScore"):
        high_idx = next(i for i, c in enumerate(companies) if c["name"] == "HighScore")
        low_idx = next(i for i, c in enumerate(companies) if c["name"] == "LowScore")
        assert high_idx < low_idx


# ── GET /companies/{id} ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_company_found(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="GetMeCo", domain="getmeco.dev")
    await db_session.commit()

    resp = await client.get(f"{API}/companies/{company.id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "GetMeCo"
    assert data["domain"] == "getmeco.dev"


@pytest.mark.asyncio
async def test_get_company_not_found_404(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"{API}/companies/00000000-0000-0000-0000-000000000001", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_company_cross_tenant_404(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    invite_code: str,
):
    """Candidate B cannot fetch Candidate A's company."""
    cid_a = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid_a, name="PrivateCo", domain="privateco.dev")
    await db_session.commit()

    # Register and login as Candidate B
    from tests.conftest import _create_invite_code

    code_b = await _create_invite_code(db_session)
    email_b = f"tenantb-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        f"{API}/auth/register",
        json={"email": email_b, "password": "Testpass123", "full_name": "Tenant B", "invite_code": code_b},
    )
    login_b = await client.post(f"{API}/auth/login", json={"email": email_b, "password": "Testpass123"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    resp = await client.get(f"{API}/companies/{company.id}", headers=headers_b)
    assert resp.status_code == 404


# ── GET /companies/suggested ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_suggested_companies(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    await _seed_company(db_session, cid, name="SuggestedCo", domain="suggestedco.dev", status="suggested")
    await _seed_company(db_session, cid, name="ApprovedCo2", domain="approved2.dev", status="approved")
    await db_session.commit()

    resp = await client.get(f"{API}/companies/suggested", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # Only suggested companies should appear
    statuses = {c["status"] for c in data["companies"]}
    assert statuses <= {"suggested"}


# ── POST /companies/{id}/approve and reject ────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_company(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="ToApproveCo", domain="toapprove.dev", status="suggested")
    await db_session.commit()

    resp = await client.post(f"{API}/companies/{company.id}/approve", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_company(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="ToRejectCo", domain="toreject.dev", status="suggested")
    await db_session.commit()

    resp = await client.post(
        f"{API}/companies/{company.id}/reject",
        headers=auth_headers,
        json={"reason": "Not a good culture fit"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


# ── GET /companies/{id}/dossier ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_dossier_not_found(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="NoDossierCo", domain="nodossier.dev")
    await db_session.commit()

    resp = await client.get(f"{API}/companies/{company.id}/dossier", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_dossier_found(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="DossierCo", domain="dossier.dev", status="approved")
    dossier = CompanyDossier(
        id=uuid.uuid4(),
        company_id=company.id,
        culture_summary="Innovative culture",
        culture_score=8.5,
        red_flags=[],
        interview_format="Phone + Onsite",
        interview_questions=["Tell me about yourself"],
        compensation_data={"range": "150k-200k"},
        key_people=[{"name": "Jane", "title": "CTO"}],
        why_hire_me="Great match",
        recent_news=[{"title": "Series B", "date": "2025-01-01"}],
    )
    db_session.add(dossier)
    await db_session.commit()

    resp = await client.get(f"{API}/companies/{company.id}/dossier", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["culture_summary"] == "Innovative culture"
    assert data["culture_score"] == 8.5
    assert data["why_hire_me"] == "Great match"


# ── GET /companies/{id}/notes and PUT /companies/{id}/notes ───────────────────


@pytest.mark.asyncio
async def test_get_notes_no_note(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="NoNoteCo", domain="nonote.dev")
    await db_session.commit()

    resp = await client.get(f"{API}/companies/{company.id}/notes", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_upsert_and_get_notes(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="NotesCo", domain="notesco.dev")
    await db_session.commit()

    # Create note
    resp = await client.put(
        f"{API}/companies/{company.id}/notes",
        headers=auth_headers,
        json={"content": "Follow up in two weeks."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "Follow up in two weeks."
    assert data["company_id"] == str(company.id)

    # Verify GET returns it
    get_resp = await client.get(f"{API}/companies/{company.id}/notes", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["content"] == "Follow up in two weeks."


@pytest.mark.asyncio
async def test_update_notes(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="UpdateNotesCo", domain="updatenotes.dev")
    await db_session.commit()

    await client.put(
        f"{API}/companies/{company.id}/notes",
        headers=auth_headers,
        json={"content": "Initial"},
    )
    resp = await client.put(
        f"{API}/companies/{company.id}/notes",
        headers=auth_headers,
        json={"content": "Updated content"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "Updated content"


# ── POST /companies/discover ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discover_companies(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    from tests.conftest import seed_candidate_dna

    await seed_candidate_dna(db_session, client, auth_headers)

    resp = await client.post(f"{API}/companies/discover", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "companies" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_discover_companies_with_filters(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    from tests.conftest import seed_candidate_dna

    await seed_candidate_dna(db_session, client, auth_headers)

    resp = await client.post(
        f"{API}/companies/discover",
        headers=auth_headers,
        json={
            "industries": ["Technology"],
            "locations": ["Remote"],
            "company_size": "51-200",
            "keywords": "Python API",
        },
    )
    assert resp.status_code == 200
    assert "companies" in resp.json()
