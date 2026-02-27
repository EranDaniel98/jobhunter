import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_admin, get_db, get_email_client
from app.rate_limit import limiter
from app.infrastructure.protocols import EmailClientProtocol
from app.models.candidate import Candidate
from app.schemas.admin import (
    ActivityFeedItem,
    AuditLogItem,
    BroadcastRequest,
    BroadcastResponse,
    InviteChainItem,
    RegistrationTrend,
    SystemOverview,
    ToggleActiveRequest,
    ToggleAdminRequest,
    TopUserItem,
    UserDetail,
    UserListResponse,
)
from app.schemas.billing import UpdatePlanRequest
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])
logger = structlog.get_logger()


@router.get("/overview", response_model=SystemOverview)
async def get_overview(
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_system_overview(db)


@router.get("/activity", response_model=list[ActivityFeedItem])
async def get_activity_feed(
    limit: int = Query(50, ge=1, le=200),
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_activity_feed(db, limit=limit)


@router.get("/audit-log", response_model=list[AuditLogItem])
async def get_audit_log(
    limit: int = Query(50, ge=1, le=200),
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_audit_log(db, limit=limit)


@router.get("/users/export")
@limiter.limit("5/hour")
async def export_users_csv(
    request: Request,
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    csv_content = await admin_service.export_users_csv(db)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users_export.csv"},
    )


@router.get("/users", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_users(db, skip=skip, limit=limit, search=search)


@router.get("/users/{user_id}", response_model=UserDetail)
async def get_user(
    user_id: uuid.UUID,
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await admin_service.get_user_detail(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}", response_model=UserDetail)
async def toggle_admin(
    user_id: uuid.UUID,
    body: ToggleAdminRequest,
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    candidate = await admin_service.toggle_user_admin(db, user_id, body.is_admin, admin_id=admin.id)
    if not candidate:
        raise HTTPException(status_code=404, detail="User not found")
    user = await admin_service.get_user_detail(db, user_id)
    return user


@router.patch("/users/{user_id}/active", response_model=UserDetail)
async def toggle_active(
    user_id: uuid.UUID,
    body: ToggleActiveRequest,
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    candidate = await admin_service.toggle_user_active(db, user_id, body.is_active, admin_id=admin.id)
    if not candidate:
        raise HTTPException(status_code=404, detail="User not found")
    user = await admin_service.get_user_detail(db, user_id)
    return user


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if admin.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    deleted = await admin_service.delete_user(db, user_id, admin_id=admin.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")


@router.post("/broadcast", response_model=BroadcastResponse)
async def broadcast_email(
    body: BroadcastRequest,
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    email_client: EmailClientProtocol = Depends(get_email_client),
):
    return await admin_service.broadcast_email(
        db, admin.id, body.subject, body.body, email_client
    )


@router.patch("/users/{user_id}/plan", response_model=UserDetail)
async def update_user_plan(
    user_id: uuid.UUID,
    body: UpdatePlanRequest,
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin endpoint to change a user's plan tier."""
    from app.plans import PlanTier
    from app.models.audit import AdminAuditLog

    # Validate tier
    try:
        PlanTier(body.plan_tier)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid plan tier: {body.plan_tier}")

    # Find user
    from sqlalchemy import select
    result = await db.execute(select(Candidate).where(Candidate.id == user_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="User not found")

    old_tier = candidate.plan_tier
    candidate.plan_tier = body.plan_tier

    # Audit log
    audit = AdminAuditLog(
        id=uuid.uuid4(),
        admin_id=admin.id,
        action="change_plan",
        target_user_id=user_id,
        details={"old_tier": old_tier, "new_tier": body.plan_tier},
    )
    db.add(audit)
    await db.commit()

    logger.info("plan_changed", user_id=str(user_id), old_tier=old_tier, new_tier=body.plan_tier, admin_id=str(admin.id))
    user = await admin_service.get_user_detail(db, user_id)
    return user


@router.get("/analytics/registrations", response_model=list[RegistrationTrend])
async def get_registrations(
    days: int = Query(30, ge=1, le=365),
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_registration_trend(db, days=days)


@router.get("/analytics/invites", response_model=list[InviteChainItem])
async def get_invites(
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_invite_chain(db)


@router.get("/analytics/top-users", response_model=list[TopUserItem])
async def get_top_users(
    metric: str = Query("messages_sent"),
    limit: int = Query(10, ge=1, le=50),
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_top_users(db, metric=metric, limit=limit)
