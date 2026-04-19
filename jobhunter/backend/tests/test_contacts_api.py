"""Tests for company contacts and notes endpoints."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company
from app.models.contact import Contact

API = settings.API_V1_PREFIX


async def _create_company(db: AsyncSession, candidate_id: uuid.UUID, domain: str = "testco.io") -> Company:
    """Helper: insert a company directly into the DB."""
    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name=domain.split(".")[0].capitalize(),
        domain=domain,
        status="approved",
        research_status="completed",
        source="manual",
    )
    db.add(company)
    await db.flush()
    return company


async def _create_contact(
    db: AsyncSession,
    company_id: uuid.UUID,
    candidate_id: uuid.UUID,
    full_name: str = "Jane Doe",
    email: str = "jane@testco.io",
    title: str = "Engineering Manager",
    priority: int = 5,
) -> Contact:
    """Helper: insert a contact directly into the DB."""
    contact = Contact(
        id=uuid.uuid4(),
        company_id=company_id,
        candidate_id=candidate_id,
        full_name=full_name,
        email=email,
        email_verified=True,
        email_confidence=90.0,
        title=title,
        role_type="hiring_manager",
        is_decision_maker=True,
        outreach_priority=priority,
    )
    db.add(contact)
    await db.flush()
    return contact


async def _get_candidate_id(client: AsyncClient, auth_headers: dict) -> uuid.UUID:
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    return uuid.UUID(resp.json()["id"])


# ── Contacts ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_contacts_empty(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """GET /companies/{id}/contacts for company with no contacts returns []."""
    cid = await _get_candidate_id(client, auth_headers)
    company = await _create_company(db_session, cid)
    await db_session.commit()

    resp = await client.get(f"{API}/companies/{company.id}/contacts", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_contacts_returns_seeded(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """GET /companies/{id}/contacts returns contacts seeded in DB."""
    cid = await _get_candidate_id(client, auth_headers)
    company = await _create_company(db_session, cid, domain="withcontacts.io")
    await _create_contact(db_session, company.id, cid, full_name="Alice Smith", email="alice@withcontacts.io", priority=10)
    await _create_contact(db_session, company.id, cid, full_name="Bob Jones", email="bob@withcontacts.io", priority=5)
    await db_session.commit()

    resp = await client.get(f"{API}/companies/{company.id}/contacts", headers=auth_headers)
    assert resp.status_code == 200
    contacts = resp.json()
    assert len(contacts) == 2
    # Ordered by outreach_priority desc
    assert contacts[0]["full_name"] == "Alice Smith"
    assert contacts[1]["full_name"] == "Bob Jones"


@pytest.mark.asyncio
async def test_list_contacts_wrong_company(client: AsyncClient, auth_headers: dict):
    """GET /companies/{bad-id}/contacts returns 404 for non-existent company."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"{API}/companies/{fake_id}/contacts", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_contact_response_shape(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """Contact response contains all expected fields."""
    cid = await _get_candidate_id(client, auth_headers)
    company = await _create_company(db_session, cid, domain="shape.io")
    await _create_contact(db_session, company.id, cid)
    await db_session.commit()

    resp = await client.get(f"{API}/companies/{company.id}/contacts", headers=auth_headers)
    contact = resp.json()[0]
    for key in ("id", "company_id", "full_name", "email", "email_verified",
                "email_confidence", "title", "role_type", "is_decision_maker", "outreach_priority"):
        assert key in contact, f"Missing field: {key}"


# ── Notes ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_notes_empty(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """GET /companies/{id}/notes returns null when no note exists."""
    cid = await _get_candidate_id(client, auth_headers)
    company = await _create_company(db_session, cid, domain="nonotes.io")
    await db_session.commit()

    resp = await client.get(f"{API}/companies/{company.id}/notes", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() is None


@pytest.mark.asyncio
async def test_upsert_note_create(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """PUT /companies/{id}/notes creates a note on first call."""
    cid = await _get_candidate_id(client, auth_headers)
    company = await _create_company(db_session, cid, domain="newnote.io")
    await db_session.commit()

    resp = await client.put(
        f"{API}/companies/{company.id}/notes",
        headers=auth_headers,
        json={"content": "Great engineering culture, follow up next week."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "Great engineering culture, follow up next week."
    assert data["company_id"] == str(company.id)


@pytest.mark.asyncio
async def test_upsert_note_update(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """PUT /companies/{id}/notes updates existing note on second call."""
    cid = await _get_candidate_id(client, auth_headers)
    company = await _create_company(db_session, cid, domain="updatenote.io")
    await db_session.commit()

    # Create
    await client.put(
        f"{API}/companies/{company.id}/notes",
        headers=auth_headers,
        json={"content": "Initial note"},
    )
    # Update
    resp = await client.put(
        f"{API}/companies/{company.id}/notes",
        headers=auth_headers,
        json={"content": "Updated note with more details"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "Updated note with more details"

    # Verify GET returns updated content
    get_resp = await client.get(f"{API}/companies/{company.id}/notes", headers=auth_headers)
    assert get_resp.json()["content"] == "Updated note with more details"


@pytest.mark.asyncio
async def test_notes_scoped_to_candidate(client: AsyncClient, auth_headers: dict, db_session: AsyncSession, invite_code: str):
    """Notes are tenant-scoped: candidate A cannot see candidate B's notes."""
    cid_a = await _get_candidate_id(client, auth_headers)
    company = await _create_company(db_session, cid_a, domain="scoped.io")
    await db_session.commit()

    # Candidate A creates a note
    await client.put(
        f"{API}/companies/{company.id}/notes",
        headers=auth_headers,
        json={"content": "Candidate A's note"},
    )

    # Register candidate B
    from tests.conftest import _create_invite_code
    code_b = await _create_invite_code(db_session)
    email_b = f"candidateb-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        f"{API}/auth/register",
        json={"email": email_b, "password": "Testpass123", "full_name": "Candidate B", "invite_code": code_b},
    )
    login_b = await client.post(f"{API}/auth/login", json={"email": email_b, "password": "Testpass123"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # Candidate B cannot see Candidate A's company (tenant isolation at company level)
    resp = await client.get(f"{API}/companies/{company.id}/notes", headers=headers_b)
    assert resp.status_code == 404
