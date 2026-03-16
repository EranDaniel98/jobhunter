"""Integration tests for contacts API endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company
from app.models.contact import Contact

API = settings.API_V1_PREFIX


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_candidate_id(client: AsyncClient, auth_headers: dict) -> uuid.UUID:
    resp = await client.get(f"{API}/auth/me", headers=auth_headers)
    return uuid.UUID(resp.json()["id"])


async def _seed_company(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    domain: str = "contactco.dev",
    name: str = "ContactCo",
) -> Company:
    company = Company(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        name=name,
        domain=domain,
        industry="Technology",
        status="approved",
        research_status="completed",
    )
    db.add(company)
    await db.flush()
    return company


async def _seed_contact(
    db: AsyncSession,
    company_id: uuid.UUID,
    candidate_id: uuid.UUID,
    full_name: str = "Jane Doe",
    email: str = "jane@contactco.dev",
    email_verified: bool = False,
    priority: int = 5,
) -> Contact:
    contact = Contact(
        id=uuid.uuid4(),
        company_id=company_id,
        candidate_id=candidate_id,
        full_name=full_name,
        email=email,
        email_verified=email_verified,
        email_confidence=80.0,
        title="Engineering Manager",
        role_type="hiring_manager",
        is_decision_maker=True,
        outreach_priority=priority,
    )
    db.add(contact)
    await db.flush()
    return contact


# ── GET /contacts ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_contacts_empty(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    resp = await client.get(f"{API}/contacts", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_contacts_returns_all(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, domain="listall.dev")
    await _seed_contact(db_session, company.id, cid, full_name="Alice", email="alice@listall.dev", priority=10)
    await _seed_contact(db_session, company.id, cid, full_name="Bob", email="bob@listall.dev", priority=5)
    await db_session.commit()

    resp = await client.get(f"{API}/contacts", headers=auth_headers)
    assert resp.status_code == 200
    contacts = resp.json()
    assert len(contacts) >= 2
    names = [c["full_name"] for c in contacts]
    assert "Alice" in names
    assert "Bob" in names


@pytest.mark.asyncio
async def test_list_contacts_company_id_filter(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company_a = await _seed_company(db_session, cid, domain="companya.dev", name="CompanyA")
    company_b = await _seed_company(db_session, cid, domain="companyb.dev", name="CompanyB")
    await _seed_contact(db_session, company_a.id, cid, full_name="AliceA", email="alice@companya.dev")
    await _seed_contact(db_session, company_b.id, cid, full_name="BobB", email="bob@companyb.dev")
    await db_session.commit()

    resp = await client.get(f"{API}/contacts?company_id={company_a.id}", headers=auth_headers)
    assert resp.status_code == 200
    contacts = resp.json()
    names = [c["full_name"] for c in contacts]
    assert "AliceA" in names
    assert "BobB" not in names


@pytest.mark.asyncio
async def test_list_contacts_verified_filter_true(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, domain="verifiedfilter.dev", name="VerifiedFilter")
    await _seed_contact(
        db_session,
        company.id,
        cid,
        full_name="VerifiedPerson",
        email="verified@verifiedfilter.dev",
        email_verified=True,
    )
    await _seed_contact(
        db_session,
        company.id,
        cid,
        full_name="UnverifiedPerson",
        email="unverified@verifiedfilter.dev",
        email_verified=False,
    )
    await db_session.commit()

    resp = await client.get(f"{API}/contacts?verified=true", headers=auth_headers)
    assert resp.status_code == 200
    contacts = resp.json()
    names = [c["full_name"] for c in contacts]
    assert "VerifiedPerson" in names
    assert "UnverifiedPerson" not in names


@pytest.mark.asyncio
async def test_list_contacts_verified_filter_false(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, domain="unverifiedfilter.dev", name="UnverifiedFilter")
    await _seed_contact(
        db_session,
        company.id,
        cid,
        full_name="VerifiedX",
        email="vx@unverifiedfilter.dev",
        email_verified=True,
    )
    await _seed_contact(
        db_session,
        company.id,
        cid,
        full_name="UnverifiedX",
        email="ux@unverifiedfilter.dev",
        email_verified=False,
    )
    await db_session.commit()

    resp = await client.get(f"{API}/contacts?verified=false", headers=auth_headers)
    assert resp.status_code == 200
    contacts = resp.json()
    names = [c["full_name"] for c in contacts]
    assert "UnverifiedX" in names
    assert "VerifiedX" not in names


@pytest.mark.asyncio
async def test_list_contacts_ordered_by_priority(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, domain="priority.dev", name="PriorityCo")
    await _seed_contact(db_session, company.id, cid, full_name="Low", email="low@priority.dev", priority=1)
    await _seed_contact(db_session, company.id, cid, full_name="High", email="high@priority.dev", priority=99)
    await db_session.commit()

    resp = await client.get(f"{API}/contacts", headers=auth_headers)
    assert resp.status_code == 200
    contacts = resp.json()
    relevant = [c for c in contacts if c["full_name"] in ("Low", "High")]
    assert len(relevant) == 2
    assert relevant[0]["full_name"] == "High"
    assert relevant[1]["full_name"] == "Low"


# ── POST /contacts/find ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_contact(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    """POST /contacts/find should call Hunter.io stub and return a contact."""
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, domain="huntertest.io", name="HunterTest")
    await db_session.commit()

    resp = await client.post(
        f"{API}/contacts/find",
        headers=auth_headers,
        json={
            "company_id": str(company.id),
            "first_name": "Jane",
            "last_name": "Smith",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "email" in data
    assert data["company_id"] == str(company.id)


@pytest.mark.asyncio
async def test_find_contact_invalid_company(client: AsyncClient, auth_headers: dict):
    """POST /contacts/find with non-existent company should return 400."""
    resp = await client.post(
        f"{API}/contacts/find",
        headers=auth_headers,
        json={
            "company_id": str(uuid.uuid4()),
            "first_name": "Jane",
            "last_name": "Smith",
        },
    )
    # Company doesn't exist → service raises ValueError → 400
    assert resp.status_code == 400


# ── POST /contacts/{id}/verify ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_contact(client: AsyncClient, auth_headers: dict, db_session: AsyncSession):
    cid = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid, domain="verifyco.dev", name="VerifyCo")
    contact = await _seed_contact(
        db_session,
        company.id,
        cid,
        full_name="ToVerify",
        email="toverify@verifyco.dev",
        email_verified=False,
    )
    await db_session.commit()

    resp = await client.post(f"{API}/contacts/{contact.id}/verify", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(contact.id)


@pytest.mark.asyncio
async def test_verify_contact_not_found(client: AsyncClient, auth_headers: dict):
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"{API}/contacts/{fake_id}/verify", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_verify_contact_cross_tenant(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """Candidate B cannot verify Candidate A's contact."""
    cid_a = await _get_candidate_id(client, auth_headers)
    company = await _seed_company(db_session, cid_a, domain="tenantcontact.dev", name="TenantContact")
    contact = await _seed_contact(
        db_session,
        company.id,
        cid_a,
        full_name="TenantA Contact",
        email="contact@tenantcontact.dev",
    )
    await db_session.commit()

    # Register Candidate B
    from tests.conftest import _create_invite_code

    code_b = await _create_invite_code(db_session)
    email_b = f"contacttenantb-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        f"{API}/auth/register",
        json={"email": email_b, "password": "testpass123", "full_name": "Contact B", "invite_code": code_b},
    )
    login_b = await client.post(f"{API}/auth/login", json={"email": email_b, "password": "testpass123"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    resp = await client.post(f"{API}/contacts/{contact.id}/verify", headers=headers_b)
    assert resp.status_code == 404
