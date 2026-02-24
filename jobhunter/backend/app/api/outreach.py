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
        variant=m.variant,
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
            db, candidate.id, _uuid.UUID(data.contact_id), language=data.language
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
            db, candidate.id, _uuid.UUID(data.contact_id), language=data.language
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _message_to_response(message)


@router.post("/{contact_id}/draft-variants", response_model=list[OutreachMessageResponse], status_code=201)
@limiter.limit("10/hour")
async def draft_message_variants(
    request: Request,
    contact_id: str,
    language: str = Query(default="en"),
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    """Draft two message variants for A/B comparison."""
    try:
        variants = await outreach_service.draft_variants(
            db, candidate.id, _uuid.UUID(contact_id), language=language
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return [_message_to_response(m) for m in variants]


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


@router.post("/{message_id}/send")
async def send_message(
    message_id: str,
    attach_resume: bool = Query(default=True),
    auto_approve: bool = Query(default=False),
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    msg = await _get_candidate_message(db, message_id, candidate.id)
    if msg.status not in ("draft", "approved"):
        raise HTTPException(status_code=400, detail=f"Cannot send message with status '{msg.status}'")

    # If already approved (via approvals page), send immediately
    if msg.status == "approved" or auto_approve:
        from app.services.email_service import send_outreach
        try:
            # If auto_approve, also create approved PendingAction for audit trail
            if auto_approve and msg.status == "draft":
                from app.services.approval_service import create_pending_action
                action = await create_pending_action(
                    db, candidate.id, action_type="send_email", entity_id=msg.id,
                    metadata={"auto_approved": True, "attach_resume": attach_resume},
                )
                from app.services.approval_service import approve_action
                await approve_action(db, action.id, candidate.id)

            msg = await send_outreach(db, msg.id, attach_resume=attach_resume)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return _message_to_response(msg)

    # Otherwise, create a PendingAction for approval
    from app.services.approval_service import create_pending_action
    action = await create_pending_action(
        db, candidate.id,
        action_type="send_email",
        entity_id=msg.id,
        metadata={"attach_resume": attach_resume},
    )
    return {
        "status": "pending_approval",
        "message_id": str(msg.id),
        "action_id": str(action.id),
        "detail": "Message queued for approval",
    }


@router.delete("/{message_id}", status_code=204)
async def delete_message(
    message_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    msg = await _get_candidate_message(db, message_id, candidate.id)
    if msg.status != "draft":
        raise HTTPException(status_code=400, detail="Can only delete draft messages")
    await db.delete(msg)
    await db.commit()
    logger.info("outreach_deleted", message_id=message_id)


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
