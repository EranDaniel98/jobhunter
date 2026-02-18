import uuid as _uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_candidate, get_db
from app.rate_limit import limiter
from app.models.candidate import Candidate
from app.models.outreach import OutreachMessage
from app.schemas.outreach import (
    OutreachDraftRequest,
    OutreachEditRequest,
    OutreachLinkedInRequest,
    OutreachMessageResponse,
)
from app.services import outreach_service

router = APIRouter(prefix="/outreach", tags=["outreach"])
logger = structlog.get_logger()


def _message_to_response(m: OutreachMessage) -> OutreachMessageResponse:
    return OutreachMessageResponse(
        id=str(m.id),
        contact_id=str(m.contact_id),
        candidate_id=str(m.candidate_id),
        channel=m.channel,
        message_type=m.message_type,
        subject=m.subject,
        body=m.body,
        personalization_data=m.personalization_data,
        status=m.status,
        sent_at=m.sent_at,
        opened_at=m.opened_at,
        replied_at=m.replied_at,
    )


@router.post("/draft", response_model=OutreachMessageResponse, status_code=201)
@limiter.limit("20/hour")
async def draft_message(
    request: Request,
    data: OutreachDraftRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    try:
        message = await outreach_service.draft_message(
            db, candidate.id, _uuid.UUID(data.contact_id)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _message_to_response(message)


@router.post("/{message_id}/draft-followup", response_model=OutreachMessageResponse, status_code=201)
async def draft_followup(
    message_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    msg = await _get_candidate_message(db, message_id, candidate.id)
    try:
        followup = await outreach_service.draft_followup(db, msg.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _message_to_response(followup)


@router.post("/draft-linkedin", response_model=OutreachMessageResponse, status_code=201)
async def draft_linkedin(
    data: OutreachLinkedInRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    try:
        message = await outreach_service.draft_linkedin_message(
            db, candidate.id, _uuid.UUID(data.contact_id)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _message_to_response(message)


@router.get("", response_model=list[OutreachMessageResponse])
async def list_messages(
    status: str | None = None,
    channel: str | None = None,
    skip: int = 0,
    limit: int = Query(default=50, le=100),
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    query = select(OutreachMessage).where(OutreachMessage.candidate_id == candidate.id)
    if status:
        query = query.where(OutreachMessage.status == status)
    if channel:
        query = query.where(OutreachMessage.channel == channel)
    query = query.order_by(OutreachMessage.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    messages = result.scalars().all()
    return [_message_to_response(m) for m in messages]


@router.get("/{message_id}", response_model=OutreachMessageResponse)
async def get_message(
    message_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    msg = await _get_candidate_message(db, message_id, candidate.id)
    return _message_to_response(msg)


@router.patch("/{message_id}", response_model=OutreachMessageResponse)
async def edit_message(
    message_id: str,
    data: OutreachEditRequest,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    msg = await _get_candidate_message(db, message_id, candidate.id)
    if msg.status != "draft":
        raise HTTPException(status_code=400, detail="Can only edit draft messages")

    if data.subject is not None:
        msg.subject = data.subject
    if data.body is not None:
        msg.body = data.body

    await db.commit()
    await db.refresh(msg)
    logger.info("outreach_edited", message_id=message_id)
    return _message_to_response(msg)


@router.post("/{message_id}/send", response_model=OutreachMessageResponse)
async def send_message(
    message_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    msg = await _get_candidate_message(db, message_id, candidate.id)
    if msg.status not in ("draft", "approved"):
        raise HTTPException(status_code=400, detail=f"Cannot send message with status '{msg.status}'")

    # Email sending is handled by email_service (Step 7)
    from app.services.email_service import send_outreach
    try:
        msg = await send_outreach(db, msg.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _message_to_response(msg)


@router.patch("/{message_id}/mark-replied", response_model=OutreachMessageResponse)
async def mark_replied(
    message_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    msg = await _get_candidate_message(db, message_id, candidate.id)
    msg.status = "replied"
    msg.replied_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(msg)
    logger.info("outreach_marked_replied", message_id=message_id)
    return _message_to_response(msg)


async def _get_candidate_message(
    db: AsyncSession, message_id: str, candidate_id
) -> OutreachMessage:
    result = await db.execute(
        select(OutreachMessage).where(
            OutreachMessage.id == _uuid.UUID(message_id),
            OutreachMessage.candidate_id == candidate_id,
        )
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return msg
