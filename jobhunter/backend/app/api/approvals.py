import uuid as _uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_candidate, get_db
from app.models.candidate import Candidate
from app.models.enums import ActionStatus, ActionType, MessageStatus
from app.models.outreach import OutreachMessage
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
    action_id: _uuid.UUID,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    action = await approval_service.get_pending_action(db, action_id, candidate.id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@router.post("/{action_id}/approve", response_model=PendingActionResponse)
async def approve(
    action_id: _uuid.UUID,
    background_tasks: BackgroundTasks,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    action = await approval_service.approve_action(db, action_id, candidate.id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    # If this is a send action, trigger the actual send
    if (
        action.action_type in (ActionType.SEND_EMAIL, ActionType.SEND_FOLLOWUP)
        and action.status == ActionStatus.APPROVED
    ):
        thread_id = (action.metadata_ or {}).get("thread_id")
        attach_resume = (action.metadata_ or {}).get("attach_resume", True)

        if thread_id:
            # Graph-based: resume the outreach graph in background
            async def _resume_graph():
                from langgraph.types import Command

                from app.graphs.outreach import get_outreach_pipeline

                graph = get_outreach_pipeline()
                try:
                    await graph.ainvoke(
                        Command(resume={"approved": True, "attach_resume": attach_resume}),
                        config={"configurable": {"thread_id": thread_id}},
                    )
                except Exception as e:
                    logger.error("graph_resume_approve_failed", action_id=action_id, thread_id=thread_id, error=str(e))

            background_tasks.add_task(_resume_graph)
        else:
            # Legacy path: call send_outreach directly
            try:
                await send_outreach(db, action.entity_id, plan_tier=candidate.plan_tier)
            except ValueError as e:
                logger.error("approved_send_failed", action_id=action_id, error=str(e))
                raise HTTPException(status_code=422, detail=f"Approved but send failed: {e}") from e

    # Return enriched response
    response = await approval_service.get_pending_action(db, action.id, action.candidate_id)
    return response


@router.post("/{action_id}/reject")
async def reject(
    action_id: _uuid.UUID,
    background_tasks: BackgroundTasks,
    candidate: Candidate = Depends(get_current_candidate),
    db: AsyncSession = Depends(get_db),
):
    action = await approval_service.reject_action(db, action_id, candidate.id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    # If graph-based, resume with rejection so graph can finalize
    thread_id = (action.metadata_ or {}).get("thread_id")
    if thread_id:

        async def _resume_graph_reject():
            from langgraph.types import Command

            from app.graphs.outreach import get_outreach_pipeline

            graph = get_outreach_pipeline()
            try:
                await graph.ainvoke(
                    Command(resume={"approved": False}),
                    config={"configurable": {"thread_id": thread_id}},
                )
            except Exception as e:
                logger.error("graph_resume_reject_failed", action_id=action_id, thread_id=thread_id, error=str(e))

        background_tasks.add_task(_resume_graph_reject)

        # Also update OutreachMessage status to "rejected"
        if action.entity_type == "outreach_message":
            result = await db.execute(select(OutreachMessage).where(OutreachMessage.id == action.entity_id))
            msg = result.scalar_one_or_none()
            if msg and msg.status == MessageStatus.DRAFT:
                msg.status = MessageStatus.REJECTED
                await db.commit()

    response = await approval_service.get_pending_action(db, action.id, action.candidate_id)
    return response
