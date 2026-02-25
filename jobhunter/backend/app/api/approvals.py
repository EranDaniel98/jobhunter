import uuid as _uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_candidate, get_db
from app.models.candidate import Candidate
from app.schemas.approval import PendingActionListResponse, PendingActionResponse, PendingCountResponse
from app.services import approval_service
from app.services.email_service import send_outreach

router = APIRouter(prefix="/approvals", tags=["approvals"])
logger = structlog.get_logger()


@router.get("", response_model=PendingActionListResponse)
async def list_approvals(
    status: str | None = None,
    action_type: str | None = None,
    skip: int = 0,
    limit: int = Query(default=20, le=100),
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    actions, total = await approval_service.list_pending_actions(
        db, candidate.id, status=status, action_type=action_type, skip=skip, limit=limit
    )
    return PendingActionListResponse(actions=actions, total=total)


@router.get("/count", response_model=PendingCountResponse)
async def get_pending_count(
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    count = await approval_service.count_pending(db, candidate.id)
    return PendingCountResponse(count=count)


@router.get("/{action_id}", response_model=PendingActionResponse)
async def get_approval(
    action_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    action = await approval_service.get_pending_action(db, _uuid.UUID(action_id), candidate.id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@router.post("/{action_id}/approve", response_model=PendingActionResponse)
async def approve(
    action_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    action = await approval_service.approve_action(db, _uuid.UUID(action_id), candidate.id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    # If this is a send action, trigger the actual send
    if action.action_type in ("send_email", "send_followup") and action.status == "approved":
        try:
            await send_outreach(db, action.entity_id, plan_tier=candidate.plan_tier)
        except ValueError as e:
            logger.warning("approved_send_failed", action_id=action_id, error=str(e))

    # Return enriched response
    response = await approval_service.get_pending_action(db, action.id, action.candidate_id)
    return response


@router.post("/{action_id}/reject")
async def reject(
    action_id: str,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    action = await approval_service.reject_action(db, _uuid.UUID(action_id), candidate.id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    response = await approval_service.get_pending_action(db, action.id, action.candidate_id)
    return response
