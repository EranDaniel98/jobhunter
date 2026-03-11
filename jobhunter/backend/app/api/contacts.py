import uuid as _uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_candidate, get_db
from app.models.candidate import Candidate
from app.models.contact import Contact
from app.rate_limit import limiter
from app.schemas.contact import ContactFindRequest, ContactResponse
from app.services import contact_service

router = APIRouter(prefix="/contacts", tags=["contacts"])
logger = structlog.get_logger()


def _contact_to_response(c: Contact) -> ContactResponse:
    return ContactResponse(
        id=str(c.id),
        company_id=str(c.company_id),
        full_name=c.full_name,
        email=c.email,
        email_verified=c.email_verified,
        email_confidence=c.email_confidence,
        title=c.title,
        role_type=c.role_type,
        is_decision_maker=c.is_decision_maker,
        outreach_priority=c.outreach_priority,
    )


@router.post("/find", response_model=ContactResponse, status_code=201)
@limiter.limit("20/hour")
async def find_contact(
    request: Request,
    data: ContactFindRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    try:
        contact = await contact_service.find_contact(
            db, _uuid.UUID(data.company_id), candidate.id, data.first_name, data.last_name
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _contact_to_response(contact)


@router.post("/{contact_id}/verify", response_model=ContactResponse)
@limiter.limit("30/hour")
async def verify_contact(
    request: Request,
    contact_id: _uuid.UUID,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    # Verify contact belongs to candidate
    result = await db.execute(
        select(Contact).where(
            Contact.id == contact_id,
            Contact.candidate_id == candidate.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contact not found")

    try:
        contact = await contact_service.verify_contact(db, contact_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _contact_to_response(contact)


@router.get("", response_model=list[ContactResponse])
async def list_contacts(
    company_id: str | None = None,
    verified: bool | None = None,
    skip: int = 0,
    limit: int = Query(default=50, le=100),
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    query = select(Contact).where(Contact.candidate_id == candidate.id)
    if company_id:
        query = query.where(Contact.company_id == _uuid.UUID(company_id))
    if verified is not None:
        query = query.where(Contact.email_verified == verified)
    query = query.order_by(Contact.outreach_priority.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    contacts = result.scalars().all()
    return [_contact_to_response(c) for c in contacts]
