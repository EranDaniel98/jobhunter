"""Integration tests for /api/v1/companies routes — targeting uncovered lines.

Covers:
  - GET /companies with pagination, status filter
  - GET /companies/{id} found + 404
  - POST /companies/{id}/approve 404
  - POST /companies/{id}/reject 404
  - GET /companies/{id}/dossier (404 + found with data)
  - GET /companies/{id}/contacts
  - GET /companies/{id}/notes (null + with note)
  - PUT /companies/{id}/notes (upsert)
  - POST /companies/discover (with CandidateDNA)
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate import CandidateDNA
from app.models.company import Company, CompanyDossier
from app.models.company_note import CompanyNote
from app.models.contact import Contact

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
    research_status: str = "pending",
    fit_score: float | None = None,
) -> Company:
    domain = domain or f"{name.lower().replace(' ', '')}-{uuid.uuid4().hex[:6]}.example.com"
    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name=name,
        domain=domain,
        industry="Technology",
        status=status,
        research_status=research_status,
        fit_score=fit_score,
    )
    db.add(company)
    await db.flush()
    return company


async def _seed_dna(
    db: AsyncSession,
    candidate_id: uuid.UUID,
) -> CandidateDNA:
    dna = CandidateDNA(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        experience_summary="Python backend engineer with 5 years experience.",
        strengths=["Python", "FastAPI"],
        gaps=[],
        career_stage="mid",
    )
    db.add(dna)
    await db.flush()
    return dna


# ── GET /companies ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_companies_empty(client: AsyncClient, auth_headers: dict):
    """GET /companies returns empty list when no companies exist for the candidate."""
    resp = await client.get(f"{API}/companies", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "companies" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_list_companies_with_data(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """GET /companies returns companies for the authenticated candidate."""
    cid = await _get_candidate_id(client, auth_headers)
    await _seed_company(db_session, cid, name="ListAlpha", domain="listalpha.dev")
    await _seed_company(db_session, cid, name="ListBeta", domain="listbeta.dev")
    await db_session.flush()

    resp = await client.get(f"{API}/companies", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    names = [c["name"] for c in data["companies"]]
    assert "ListAlpha" in names
    assert "ListBeta" in names


@pytest.mark.asyncio
async def test_list_companies_status_filter(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """?status=approved filters correctly."""
    cid = await _get_candidate_id(client, auth_headers)
    await _seed_company(db_session, cid, name="StatusApproved", domain="statusapproved.dev", status="approved")
    await _seed_company(db_session, cid, name="StatusRejected", domain="statusrejected.dev", status="rejected")
    await db_session.flush()

    resp = await client.get(f"{API}/companies?status=approved", headers=auth_headers)
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()["companies"]]
    assert "StatusApproved" in names
    assert "StatusRejected" not in names


@pytest.mark.asyncio
async def test_list_companies_pagination(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """skip/limit work correctly."""
    cid = await _get_candidate_id(client, auth_headers)
    for i in range(4):
        await _seed_company(db_session, cid, name=f"PagComp{i}", domain=f"pagcomp{i}.dev")
    await db_session.flush()

    resp = await client.get(f"{API}/companies?skip=0&limit=2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["companies"]) <= 2
    # Total should still reflect all companies
    assert data["total"] >= 4


# ── GET /companies/{id} ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_company_found(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="GetComp", domain="getcomp.dev")
    await db_session.flush()

    resp = await client.get(f"{API}/companies/{company.id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "GetComp"


@pytest.mark.asyncio
async def test_get_company_not_found(client: AsyncClient, auth_headers: dict):
    """Non-existent company UUID returns 404."""
    resp = await client.get(
        f"{API}/companies/00000000-0000-0000-0000-000000000099",
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert "Company not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_company_wrong_tenant(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    invite_code: str,
):
    """Company owned by another candidate returns 404 (tenant isolation)."""
    from tests.conftest import _create_invite_code

    # Seed a company for the current user
    cid_a = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid_a, name="TenantCo", domain="tenantco.dev")
    await db_session.flush()

    # Register and login as a different user
    code_b = await _create_invite_code(db_session)
    email_b = f"tenantb2-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        f"{API}/auth/register",
        json={
            "email": email_b,
            "password": "Testpass123",
            "full_name": "Tenant B2",
            "invite_code": code_b,
        },
    )
    login_b = await client.post(f"{API}/auth/login", json={"email": email_b, "password": "Testpass123"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    resp = await client.get(f"{API}/companies/{company.id}", headers=headers_b)
    assert resp.status_code == 404


# ── POST /companies/{id}/approve ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_company_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        f"{API}/companies/00000000-0000-0000-0000-000000000088/approve",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_approve_company_success(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="ApproveCo2", domain="approveco2.dev", status="suggested")
    await db_session.flush()

    resp = await client.post(f"{API}/companies/{company.id}/approve", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_approve_company_already_approved(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Approving an already-approved company still returns 200 (idempotent path)."""
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(
        db_session,
        cid,
        name="AlreadyApprovedCo",
        domain="alreadyapproved.dev",
        status="approved",
        research_status="completed",
    )
    await db_session.flush()

    resp = await client.post(f"{API}/companies/{company.id}/approve", headers=auth_headers)
    assert resp.status_code == 200


# ── POST /companies/{id}/reject ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_company_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        f"{API}/companies/00000000-0000-0000-0000-000000000077/reject",
        headers=auth_headers,
        json={"reason": "not a fit"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reject_company_success(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="RejectCo2", domain="rejectco2.dev", status="suggested")
    await db_session.flush()

    resp = await client.post(
        f"{API}/companies/{company.id}/reject",
        headers=auth_headers,
        json={"reason": "Culture mismatch"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


# ── GET /companies/{id}/dossier ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_dossier_company_not_found(client: AsyncClient, auth_headers: dict):
    """Requesting dossier for non-existent company returns 404."""
    resp = await client.get(
        f"{API}/companies/00000000-0000-0000-0000-000000000066/dossier",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_dossier_no_dossier_yet(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Company exists but no dossier returns 404 with explanatory message."""
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="NoDossierComp", domain="nodossiercomp.dev")
    await db_session.flush()

    resp = await client.get(f"{API}/companies/{company.id}/dossier", headers=auth_headers)
    assert resp.status_code == 404
    assert "Dossier not yet generated" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_dossier_found(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="DossierComp2", domain="dossiercomp2.dev", status="approved")
    dossier = CompanyDossier(
        id=uuid.uuid4(),
        company_id=company.id,
        culture_summary="Exciting culture",
        culture_score=7.5,
        red_flags=[],
        interview_format="Phone + Onsite",
        interview_questions=["Why us?"],
        compensation_data={"range": "120k-160k"},
        key_people=[{"name": "John", "title": "CEO"}],
        why_hire_me="Great Python experience",
        recent_news=[{"title": "Series A", "date": "2025-06-01"}],
    )
    db_session.add(dossier)
    await db_session.flush()

    resp = await client.get(f"{API}/companies/{company.id}/dossier", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["culture_summary"] == "Exciting culture"
    assert data["culture_score"] == 7.5
    assert data["why_hire_me"] == "Great Python experience"


# ── GET /companies/{id}/contacts ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_contacts_empty(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="ContactsCo", domain="contactsco.dev")
    await db_session.flush()

    resp = await client.get(f"{API}/companies/{company.id}/contacts", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_contacts_with_data(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="ContactsCoData", domain="contactscodata.dev")
    contact = Contact(
        id=uuid.uuid4(),
        company_id=company.id,
        candidate_id=cid,
        full_name="Alice Contact",
        email="alice@contactscodata.dev",
        title="Engineering Manager",
        outreach_priority=90,
    )
    db_session.add(contact)
    await db_session.flush()

    resp = await client.get(f"{API}/companies/{company.id}/contacts", headers=auth_headers)
    assert resp.status_code == 200
    contacts = resp.json()
    assert len(contacts) == 1
    assert contacts[0]["full_name"] == "Alice Contact"
    assert contacts[0]["email"] == "alice@contactscodata.dev"


# ── GET /companies/{id}/notes ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_notes_no_note(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="NoteNoCo", domain="notenocomp.dev")
    await db_session.flush()

    resp = await client.get(f"{API}/companies/{company.id}/notes", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_get_notes_with_existing_note(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="NoteExistCo", domain="noteexistco.dev")
    note = CompanyNote(
        id=uuid.uuid4(),
        candidate_id=cid,
        company_id=company.id,
        content="Very promising company.",
    )
    db_session.add(note)
    await db_session.flush()

    resp = await client.get(f"{API}/companies/{company.id}/notes", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data is not None
    assert data["content"] == "Very promising company."


# ── PUT /companies/{id}/notes ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_notes_create(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="UpsertNoteCo", domain="upsertnote.dev")
    await db_session.flush()

    resp = await client.put(
        f"{API}/companies/{company.id}/notes",
        headers=auth_headers,
        json={"content": "Initial note content."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "Initial note content."
    assert data["company_id"] == str(company.id)


@pytest.mark.asyncio
async def test_upsert_notes_update(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, name="UpdateNoteCo2", domain="updatenote2.dev")
    await db_session.flush()

    # First upsert
    await client.put(
        f"{API}/companies/{company.id}/notes",
        headers=auth_headers,
        json={"content": "First version."},
    )

    # Second upsert — should update
    resp = await client.put(
        f"{API}/companies/{company.id}/notes",
        headers=auth_headers,
        json={"content": "Updated version."},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "Updated version."


# ── POST /companies/discover ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discover_requires_auth(client: AsyncClient):
    resp = await client.post(f"{API}/companies/discover")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_discover_with_dna(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """POST /companies/discover succeeds when CandidateDNA exists."""
    cid = await _get_candidate_id(client, auth_headers)
    await _seed_dna(db_session, cid)
    await db_session.flush()

    resp = await client.post(f"{API}/companies/discover", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "companies" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_discover_with_filters(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """POST /companies/discover with request body works."""
    cid = await _get_candidate_id(client, auth_headers)
    await _seed_dna(db_session, cid)
    await db_session.flush()

    resp = await client.post(
        f"{API}/companies/discover",
        headers=auth_headers,
        json={
            "industries": ["SaaS"],
            "locations": ["Remote"],
            "company_size": "51-200",
            "keywords": "Python backend",
        },
    )
    assert resp.status_code == 200
    assert "companies" in resp.json()


# ── POST /companies/add ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_company_success(client: AsyncClient, auth_headers: dict):
    """POST /companies/add with valid domain creates a company."""
    resp = await client.post(
        f"{API}/companies/add",
        headers=auth_headers,
        json={"domain": "newaddedco.io"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["domain"] == "newaddedco.io"


@pytest.mark.asyncio
async def test_add_company_duplicate_domain(client: AsyncClient, auth_headers: dict):
    """Adding the same domain twice returns 400."""
    await client.post(
        f"{API}/companies/add",
        headers=auth_headers,
        json={"domain": "dupaddco.io"},
    )
    resp = await client.post(
        f"{API}/companies/add",
        headers=auth_headers,
        json={"domain": "dupaddco.io"},
    )
    assert resp.status_code == 400
