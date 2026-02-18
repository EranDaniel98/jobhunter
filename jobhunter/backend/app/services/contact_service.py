import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_hunter
from app.models.contact import Contact

logger = structlog.get_logger()


async def find_contact(
    db: AsyncSession, company_id: uuid.UUID, candidate_id: uuid.UUID, first_name: str, last_name: str
) -> Contact:
    """Find a specific contact at a company using Hunter.io email finder."""
    from app.models.company import Company

    # Get company domain
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise ValueError("Company not found")

    hunter = get_hunter()
    data = await hunter.email_finder(company.domain, first_name, last_name)

    # Check if contact already exists
    existing = await db.execute(
        select(Contact).where(
            Contact.company_id == company_id,
            Contact.email == data.get("email"),
        )
    )
    contact = existing.scalar_one_or_none()

    if contact:
        # Update with new data
        contact.email_confidence = data.get("confidence")
        contact.title = data.get("position") or contact.title
    else:
        position = (data.get("position") or "").lower()
        role_type = "recruiter"
        is_decision_maker = False
        priority = 0

        if any(t in position for t in ["vp", "director", "head", "cto", "ceo"]):
            role_type = "hiring_manager"
            is_decision_maker = True
            priority = 3
        elif any(t in position for t in ["manager", "lead"]):
            role_type = "team_lead"
            priority = 2
        elif "recruit" in position:
            role_type = "recruiter"
            priority = 1

        contact = Contact(
            id=uuid.uuid4(),
            company_id=company_id,
            candidate_id=candidate_id,
            full_name=f"{first_name} {last_name}",
            email=data.get("email"),
            email_confidence=data.get("confidence"),
            title=data.get("position"),
            role_type=role_type,
            is_decision_maker=is_decision_maker,
            outreach_priority=priority,
            hunter_data=data,
        )
        db.add(contact)

    await db.commit()
    await db.refresh(contact)
    logger.info("contact_found", contact_id=str(contact.id), email=contact.email)
    return contact


async def verify_contact(db: AsyncSession, contact_id: uuid.UUID) -> Contact:
    """Verify a contact's email address."""
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact or not contact.email:
        raise ValueError("Contact not found or has no email")

    hunter = get_hunter()
    data = await hunter.email_verifier(contact.email)

    contact.email_verified = data.get("result") == "deliverable"
    contact.email_confidence = data.get("score")

    await db.commit()
    await db.refresh(contact)
    logger.info("contact_verified", contact_id=str(contact_id), verified=contact.email_verified)
    return contact


async def prioritize_contacts(
    db: AsyncSession, company_id: uuid.UUID
) -> list[Contact]:
    """Return contacts ranked by outreach priority."""
    result = await db.execute(
        select(Contact)
        .where(Contact.company_id == company_id)
        .order_by(Contact.outreach_priority.desc())
    )
    return list(result.scalars().all())
