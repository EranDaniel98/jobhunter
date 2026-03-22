import uuid
from datetime import UTC, datetime
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_admin, get_db, get_email_client
from app.infrastructure.dossier_cache import invalidate_dossier
from app.infrastructure.protocols import EmailClientProtocol
from app.infrastructure.redis_client import get_redis
from app.models.candidate import Candidate
from app.models.waitlist import WaitlistEntry
from app.rate_limit import limiter
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
    WaitlistBatchRequest,
    WaitlistBatchResponse,
    WaitlistInviteResponse,
    WaitlistListResponse,
)
from app.schemas.billing import UpdatePlanRequest
from app.services import admin_service
from app.services.dns_health_service import check_email_dns_health
from app.services.invite_service import create_system_invite

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
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_activity_feed(db, skip=skip, limit=limit)


@router.get("/audit-log", response_model=list[AuditLogItem])
async def get_audit_log(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_audit_log(db, skip=skip, limit=limit)


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
    return await admin_service.broadcast_email(db, admin.id, body.subject, body.body, email_client)


@router.patch("/users/{user_id}/plan", response_model=UserDetail)
async def update_user_plan(
    user_id: uuid.UUID,
    body: UpdatePlanRequest,
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin endpoint to change a user's plan tier."""
    try:
        candidate = await admin_service.update_user_plan(db, user_id, body.plan_tier, admin.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    if not candidate:
        raise HTTPException(status_code=404, detail="User not found")
    return await admin_service.get_user_detail(db, user_id)


@router.get("/api-costs")
async def get_api_costs(
    days: int = Query(7, ge=1, le=90),
    user_id: uuid.UUID | None = Query(None),
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated API costs, optionally filtered by user."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func, select

    from app.models.billing import ApiUsageRecord

    since = datetime.now(UTC) - timedelta(days=days)
    base_filter = [ApiUsageRecord.created_at >= since]
    if user_id:
        base_filter.append(ApiUsageRecord.candidate_id == user_id)

    # Aggregate by user
    result = await db.execute(
        select(
            ApiUsageRecord.candidate_id,
            func.sum(ApiUsageRecord.tokens_in).label("total_tokens_in"),
            func.sum(ApiUsageRecord.tokens_out).label("total_tokens_out"),
            func.sum(ApiUsageRecord.estimated_cost_cents).label("total_cost_cents"),
            func.count(ApiUsageRecord.id).label("request_count"),
        )
        .where(*base_filter)
        .group_by(ApiUsageRecord.candidate_id)
        .order_by(func.sum(ApiUsageRecord.estimated_cost_cents).desc())
        .limit(50)
    )
    rows = result.all()
    return [
        {
            "candidate_id": str(row.candidate_id),
            "total_tokens_in": row.total_tokens_in or 0,
            "total_tokens_out": row.total_tokens_out or 0,
            "total_cost_cents": row.total_cost_cents or 0,
            "request_count": row.request_count or 0,
        }
        for row in rows
    ]


@router.get("/db-pool-stats")
async def get_db_pool_stats(
    _: Candidate = Depends(get_current_admin),
):
    from app.infrastructure.database import _config, engine

    pool = engine.pool
    return {
        "connection_mode": _config["mode"],
        "pool_size": pool.size(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "checked_in": pool.checkedin(),
    }


@router.delete("/cache/dossier/{domain}")
async def clear_dossier_cache(
    domain: str,
    _: Candidate = Depends(get_current_admin),
):
    deleted = await invalidate_dossier(domain)
    return {"deleted": deleted, "domain": domain}


@router.get("/email-health")
async def get_email_health(
    force: bool = False,
    _: Candidate = Depends(get_current_admin),
):
    """Check SPF, DKIM, and DMARC health for the configured sender domain."""
    domain = settings.SENDER_EMAIL.split("@")[1] if "@" in settings.SENDER_EMAIL else settings.SENDER_EMAIL
    return await check_email_dns_health(domain, force=force)


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
    metric: Literal["messages_sent", "companies_added"] = Query("messages_sent"),
    limit: int = Query(10, ge=1, le=50),
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.get_top_users(db, metric=metric, limit=limit)


# ---------------------------------------------------------------------------
# Waitlist management
# ---------------------------------------------------------------------------

DAILY_INVITE_QUOTA_KEY = "admin:daily_invites:{date}"


async def _get_daily_quota_used(redis) -> int:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    key = DAILY_INVITE_QUOTA_KEY.format(date=today)
    val = await redis.get(key)
    return int(val) if val else 0


async def _try_reserve_quota(redis, amount: int = 1) -> bool:
    """Atomically reserve invite quota. Returns True if within limit."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    key = DAILY_INVITE_QUOTA_KEY.format(date=today)
    new_val = await redis.incrby(key, amount)
    await redis.expire(key, 172800)
    if new_val > settings.MAX_DAILY_INVITES:
        await redis.decrby(key, amount)
        return False
    return True


@router.get("/waitlist", response_model=WaitlistListResponse)
async def list_waitlist(
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List waitlist entries, optionally filtered by status."""
    q = select(WaitlistEntry).order_by(WaitlistEntry.created_at.asc())
    if status:
        q = q.where(WaitlistEntry.status == status)

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0

    entries_result = await db.execute(q.offset(skip).limit(limit))
    entries = list(entries_result.scalars().all())

    return WaitlistListResponse(entries=entries, total=total)


@router.post("/waitlist/{entry_id}/invite", response_model=WaitlistInviteResponse)
async def invite_waitlist_entry(
    entry_id: int,
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    email_client: EmailClientProtocol = Depends(get_email_client),
    redis=Depends(get_redis),
):
    """Send an invite to a single waitlist entry. Idempotent for already-invited entries."""
    # Fetch entry
    result = await db.execute(select(WaitlistEntry).where(WaitlistEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")

    # Idempotent: already invited — return existing invite code
    if entry.status == "invited" and entry.invite_code_id is not None:
        from app.models.invite import InviteCode

        code_result = await db.execute(select(InviteCode).where(InviteCode.id == entry.invite_code_id))
        existing_code = code_result.scalar_one_or_none()
        if existing_code:
            return WaitlistInviteResponse(
                code=existing_code.code,
                email=entry.email,
                expires_at=existing_code.expires_at,
            )

    # Quota check (atomic reserve)
    if not await _try_reserve_quota(redis):
        logger.warning(
            "waitlist_invite_quota_exceeded",
            feature="waitlist",
            action="invite",
            admin_id=str(admin.id),
            limit=settings.MAX_DAILY_INVITES,
        )
        return JSONResponse(
            status_code=429,
            content={"detail": "Daily invite quota exceeded. Resets at midnight UTC."},
            headers={"Retry-After": "86400"},
        )

    # Create invite code and update entry
    invite = await create_system_invite(db, entry.email)
    entry.status = "invited"
    entry.invited_at = datetime.now(UTC)
    entry.invite_code_id = invite.id
    entry.invite_error = None
    await db.commit()
    await db.refresh(invite)

    # Send email
    try:
        await email_client.send(
            to=entry.email,
            from_email=settings.SENDER_EMAIL,
            subject="You're invited to JobHunter!",
            body=(
                f"Hi,\n\nYou're invited to join JobHunter. Use the link below to register:\n\n"
                f"{settings.FRONTEND_URL}/register?invite={invite.code}\n\n"
                f"This invite expires in {settings.INVITE_EXPIRE_DAYS} days.\n\nGood luck!"
            ),
        )
    except Exception as exc:
        logger.error(
            "waitlist_invite_email_failed",
            feature="waitlist",
            action="invite",
            entry_id=entry_id,
            email=entry.email,
            error=str(exc),
        )
        entry.invite_error = str(exc)
        await db.commit()

    # Audit log
    await admin_service.create_audit_log(
        db,
        admin.id,
        "invite_waitlist",
        details={"entry_id": entry_id, "email": entry.email, "invite_code": invite.code},
    )

    logger.info(
        "waitlist_entry_invited",
        feature="waitlist",
        action="invite",
        entry_id=entry_id,
        email=entry.email,
        admin_id=str(admin.id),
    )

    return WaitlistInviteResponse(
        code=invite.code,
        email=entry.email,
        expires_at=invite.expires_at,
    )


@router.post("/waitlist/invite-batch", response_model=WaitlistBatchResponse)
async def invite_waitlist_batch(
    body: WaitlistBatchRequest,
    admin: Candidate = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    email_client: EmailClientProtocol = Depends(get_email_client),
    redis=Depends(get_redis),
):
    """Send invites to a batch of waitlist entries (max 50). Best-effort per item."""
    if len(body.ids) > 50:
        raise HTTPException(status_code=400, detail="Batch size cannot exceed 50")

    # Quota check up-front (non-reserving)
    used = await _get_daily_quota_used(redis)
    if used >= settings.MAX_DAILY_INVITES:
        return JSONResponse(
            status_code=429,
            content={"detail": "Daily invite quota exceeded. Resets at midnight UTC."},
            headers={"Retry-After": "86400"},
        )

    invited = 0
    skipped = 0
    failed = 0
    errors: list[str] = []

    for entry_id in body.ids:
        # Atomically reserve quota per item
        if not await _try_reserve_quota(redis):
            skipped += len(body.ids) - invited - skipped - failed
            break

        result = await db.execute(select(WaitlistEntry).where(WaitlistEntry.id == entry_id))
        entry = result.scalar_one_or_none()

        if not entry:
            skipped += 1
            errors.append(f"Entry {entry_id} not found")
            continue

        if entry.status == "invited":
            skipped += 1
            continue

        try:
            invite = await create_system_invite(db, entry.email)
            entry.status = "invited"
            entry.invited_at = datetime.now(UTC)
            entry.invite_code_id = invite.id
            entry.invite_error = None
            await db.flush()
            await db.refresh(invite)

            await email_client.send(
                to=entry.email,
                from_email=settings.SENDER_EMAIL,
                subject="You're invited to JobHunter!",
                body=(
                    f"Hi,\n\nYou're invited to join JobHunter. Use the link below to register:\n\n"
                    f"{settings.FRONTEND_URL}/register?invite={invite.code}\n\n"
                    f"This invite expires in {settings.INVITE_EXPIRE_DAYS} days.\n\nGood luck!"
                ),
            )
            invited += 1
        except Exception as exc:
            failed += 1
            errors.append(f"Entry {entry_id} ({entry.email}): {exc}")
            logger.error(
                "waitlist_batch_invite_item_failed",
                feature="waitlist",
                action="invite_batch",
                entry_id=entry_id,
                error=str(exc),
            )

    await db.commit()

    # Audit log for the batch
    await admin_service.create_audit_log(
        db,
        admin.id,
        "invite_waitlist_batch",
        details={"ids": body.ids, "invited": invited, "skipped": skipped, "failed": failed},
    )

    logger.info(
        "waitlist_batch_invite_complete",
        feature="waitlist",
        action="invite_batch",
        admin_id=str(admin.id),
        invited=invited,
        skipped=skipped,
        failed=failed,
    )

    final_used = await _get_daily_quota_used(redis)
    return WaitlistBatchResponse(
        invited=invited,
        skipped=skipped,
        failed=failed,
        errors=errors,
        daily_quota_remaining=max(0, settings.MAX_DAILY_INVITES - final_used),
    )
