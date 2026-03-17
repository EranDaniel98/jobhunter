import uuid
import pytest
from app.services.outreach_service import _get_contact, _get_contact_with_company


def _make_candidate(tenant_id):
    from app.models.candidate import Candidate
    return Candidate(
        id=tenant_id,
        email=f"{tenant_id}@test.com",
        password_hash="fakehash",
        full_name="Test User",
    )


@pytest.mark.asyncio
async def test_get_contact_rejects_foreign_tenant(db_session):
    """_get_contact must reject contact_id that belongs to a different candidate."""
    from app.models.company import Company
    from app.models.contact import Contact

    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    # Create candidate records to satisfy FK constraints
    db_session.add(_make_candidate(tenant_a))
    db_session.add(_make_candidate(tenant_b))
    await db_session.flush()

    company = Company(id=uuid.uuid4(), candidate_id=tenant_b, name="B Corp", domain="bcorp.com", status="approved")
    db_session.add(company)
    await db_session.flush()

    contact = Contact(
        id=uuid.uuid4(), company_id=company.id, candidate_id=tenant_b,
        full_name="Bob", email="bob@bcorp.com",
    )
    db_session.add(contact)
    await db_session.flush()

    with pytest.raises(ValueError, match="Contact not found"):
        await _get_contact(db_session, contact.id, tenant_a)


@pytest.mark.asyncio
async def test_get_contact_allows_own_tenant(db_session):
    """_get_contact returns contact when candidate_id matches."""
    from app.models.company import Company
    from app.models.contact import Contact

    tenant_a = uuid.uuid4()

    # Create candidate record to satisfy FK constraint
    db_session.add(_make_candidate(tenant_a))
    await db_session.flush()

    company = Company(id=uuid.uuid4(), candidate_id=tenant_a, name="A Corp", domain="acorp.com", status="approved")
    db_session.add(company)
    await db_session.flush()

    contact = Contact(
        id=uuid.uuid4(), company_id=company.id, candidate_id=tenant_a,
        full_name="Alice", email="alice@acorp.com",
    )
    db_session.add(contact)
    await db_session.flush()

    result = await _get_contact(db_session, contact.id, tenant_a)
    assert result.id == contact.id
