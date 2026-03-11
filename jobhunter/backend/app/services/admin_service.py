import asyncio
import csv
import io
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.redis_client import redis_safe_get, redis_safe_setex
from app.models.analytics import AnalyticsEvent
from app.models.audit import AdminAuditLog
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import MessageStatus
from app.models.invite import InviteCode
from app.models.outreach import OutreachMessage
from app.schemas.admin import (
    ActivityFeedItem,
    AuditLogItem,
    BroadcastResponse,
    InviteChainItem,
    RegistrationTrend,
    SystemOverview,
    TopUserItem,
    UserDetail,
    UserListItem,
    UserListResponse,
)

logger = structlog.get_logger()


OVERVIEW_CACHE_KEY = "admin:overview"
OVERVIEW_CACHE_TTL = 60  # seconds


async def get_system_overview(db: AsyncSession) -> SystemOverview:
    # Check Redis cache first
    cached = await redis_safe_get(OVERVIEW_CACHE_KEY)
    if cached:
        return SystemOverview.model_validate_json(cached)

    now = datetime.now(UTC)

    total_users = (await db.execute(select(func.count(Candidate.id)))).scalar() or 0
    total_companies = (await db.execute(select(func.count(Company.id)))).scalar() or 0
    total_contacts = (await db.execute(select(func.count(Contact.id)))).scalar() or 0

    total_messages_sent = (
        await db.execute(select(func.count(OutreachMessage.id)).where(OutreachMessage.status != MessageStatus.DRAFT))
    ).scalar() or 0

    total_invites_used = (
        await db.execute(
            select(func.count(InviteCode.id)).where(InviteCode.is_used == True)  # noqa: E712
        )
    ).scalar() or 0

    # Active users = users who have updated_at within N days (proxy for activity)
    active_7d = (
        await db.execute(select(func.count(Candidate.id)).where(Candidate.updated_at >= now - timedelta(days=7)))
    ).scalar() or 0

    active_30d = (
        await db.execute(select(func.count(Candidate.id)).where(Candidate.updated_at >= now - timedelta(days=30)))
    ).scalar() or 0

    overview = SystemOverview(
        total_users=total_users,
        total_companies=total_companies,
        total_messages_sent=total_messages_sent,
        total_contacts=total_contacts,
        total_invites_used=total_invites_used,
        active_users_7d=active_7d,
        active_users_30d=active_30d,
    )

    # Cache in Redis (graceful degradation if Redis is down)
    await redis_safe_setex(OVERVIEW_CACHE_KEY, OVERVIEW_CACHE_TTL, overview.model_dump_json())

    return overview


async def list_users(db: AsyncSession, skip: int = 0, limit: int = 20, search: str | None = None) -> UserListResponse:
    # Count query
    count_q = select(func.count(Candidate.id))
    if search:
        pattern = f"%{search}%"
        count_q = count_q.where(Candidate.email.ilike(pattern) | Candidate.full_name.ilike(pattern))
    total = (await db.execute(count_q)).scalar() or 0

    # Correlated scalar subqueries to avoid Cartesian product
    companies_sub = (
        select(func.count(Company.id))
        .where(Company.candidate_id == Candidate.id)
        .correlate(Candidate)
        .scalar_subquery()
        .label("companies_count")
    )
    messages_sub = (
        select(func.count(OutreachMessage.id))
        .where(
            OutreachMessage.candidate_id == Candidate.id,
            OutreachMessage.status != MessageStatus.DRAFT,
        )
        .correlate(Candidate)
        .scalar_subquery()
        .label("messages_sent_count")
    )

    q = (
        select(
            Candidate.id,
            Candidate.email,
            Candidate.full_name,
            Candidate.is_admin,
            Candidate.is_active,
            Candidate.created_at,
            companies_sub,
            messages_sub,
        )
        .order_by(Candidate.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    if search:
        pattern = f"%{search}%"
        q = q.where(Candidate.email.ilike(pattern) | Candidate.full_name.ilike(pattern))

    rows = (await db.execute(q)).all()

    users = [
        UserListItem(
            id=str(row.id),
            email=row.email,
            full_name=row.full_name,
            is_admin=row.is_admin,
            is_active=row.is_active,
            created_at=row.created_at,
            companies_count=row.companies_count or 0,
            messages_sent_count=row.messages_sent_count or 0,
        )
        for row in rows
    ]

    return UserListResponse(users=users, total=total)


async def get_user_detail(db: AsyncSession, user_id: uuid.UUID) -> UserDetail | None:
    result = await db.execute(select(Candidate).where(Candidate.id == user_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        return None

    # Get company count
    companies_count = (
        await db.execute(select(func.count(Company.id)).where(Company.candidate_id == user_id))
    ).scalar() or 0

    # Get messages sent count
    messages_sent_count = (
        await db.execute(
            select(func.count(OutreachMessage.id)).where(
                OutreachMessage.candidate_id == user_id,
                OutreachMessage.status != MessageStatus.DRAFT,
            )
        )
    ).scalar() or 0

    # Get invite info (which invite code was used to register this user)
    invite_result = await db.execute(
        select(InviteCode, Candidate.email.label("inviter_email"))
        .join(Candidate, Candidate.id == InviteCode.invited_by_id)
        .where(InviteCode.used_by_id == user_id)
    )
    invite_row = invite_result.first()

    invited_by_email = None
    invite_code_used = None
    if invite_row:
        invited_by_email = invite_row.inviter_email
        invite_code_used = invite_row.InviteCode.code

    return UserDetail(
        id=str(candidate.id),
        email=candidate.email,
        full_name=candidate.full_name,
        is_admin=candidate.is_admin,
        is_active=candidate.is_active,
        created_at=candidate.created_at,
        companies_count=companies_count,
        messages_sent_count=messages_sent_count,
        invited_by_email=invited_by_email,
        invite_code_used=invite_code_used,
    )


async def get_registration_trend(db: AsyncSession, days: int = 30) -> list[RegistrationTrend]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date_trunc("day", Candidate.created_at).label("day"),
            func.count(Candidate.id).label("count"),
        )
        .where(Candidate.created_at >= cutoff)
        .group_by("day")
        .order_by("day")
    )
    return [RegistrationTrend(date=row.day.strftime("%Y-%m-%d"), count=row.count) for row in result.all()]


async def get_invite_chain(db: AsyncSession) -> list[InviteChainItem]:
    inviter = Candidate.__table__.alias("inviter")
    invitee = Candidate.__table__.alias("invitee")

    result = await db.execute(
        select(
            inviter.c.email.label("inviter_email"),
            inviter.c.full_name.label("inviter_name"),
            invitee.c.email.label("invitee_email"),
            invitee.c.full_name.label("invitee_name"),
            InviteCode.code,
            InviteCode.updated_at.label("used_at"),
            InviteCode.is_used,
        )
        .join(inviter, inviter.c.id == InviteCode.invited_by_id)
        .outerjoin(invitee, invitee.c.id == InviteCode.used_by_id)
        .order_by(InviteCode.created_at.desc())
    )

    return [
        InviteChainItem(
            inviter_email=row.inviter_email,
            inviter_name=row.inviter_name,
            invitee_email=row.invitee_email if row.is_used else None,
            invitee_name=row.invitee_name if row.is_used else None,
            code=row.code,
            used_at=row.used_at if row.is_used else None,
        )
        for row in result.all()
    ]


async def get_top_users(db: AsyncSession, metric: str = "messages_sent", limit: int = 10) -> list[TopUserItem]:
    if metric == "messages_sent":
        q = (
            select(
                Candidate.email,
                Candidate.full_name,
                func.count(OutreachMessage.id).label("metric_value"),
            )
            .join(OutreachMessage, OutreachMessage.candidate_id == Candidate.id)
            .where(OutreachMessage.status != MessageStatus.DRAFT)
            .group_by(Candidate.id)
            .order_by(func.count(OutreachMessage.id).desc())
            .limit(limit)
        )
    elif metric == "companies_added":
        q = (
            select(
                Candidate.email,
                Candidate.full_name,
                func.count(Company.id).label("metric_value"),
            )
            .join(Company, Company.candidate_id == Candidate.id)
            .group_by(Candidate.id)
            .order_by(func.count(Company.id).desc())
            .limit(limit)
        )
    else:
        return []

    result = await db.execute(q)
    return [
        TopUserItem(
            email=row.email,
            full_name=row.full_name,
            metric_value=row.metric_value,
            metric_name=metric,
        )
        for row in result.all()
    ]


async def toggle_user_admin(
    db: AsyncSession, user_id: uuid.UUID, is_admin: bool, admin_id: uuid.UUID | None = None
) -> Candidate | None:
    result = await db.execute(select(Candidate).where(Candidate.id == user_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        return None
    candidate.is_admin = is_admin
    await db.commit()
    await db.refresh(candidate)
    logger.info("admin_toggled", user_id=str(user_id), is_admin=is_admin)
    if admin_id:
        await create_audit_log(db, admin_id, "toggle_admin", target_user_id=user_id, details={"is_admin": is_admin})
    return candidate


async def delete_user(db: AsyncSession, user_id: uuid.UUID, admin_id: uuid.UUID | None = None) -> bool:
    result = await db.execute(select(Candidate).where(Candidate.id == user_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        return False
    email = candidate.email
    if admin_id:
        await create_audit_log(db, admin_id, "delete_user", target_user_id=user_id, details={"email": email})
    await db.delete(candidate)
    await db.commit()
    logger.info("user_deleted", user_id=str(user_id), email=email)
    return True


async def toggle_user_active(
    db: AsyncSession, user_id: uuid.UUID, is_active: bool, admin_id: uuid.UUID | None = None
) -> Candidate | None:
    result = await db.execute(select(Candidate).where(Candidate.id == user_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        return None
    candidate.is_active = is_active
    await db.commit()
    await db.refresh(candidate)
    logger.info("user_active_toggled", user_id=str(user_id), is_active=is_active)
    if admin_id:
        await create_audit_log(db, admin_id, "toggle_active", target_user_id=user_id, details={"is_active": is_active})
    return candidate


async def get_activity_feed(db: AsyncSession, limit: int = 50) -> list[ActivityFeedItem]:
    result = await db.execute(
        select(
            AnalyticsEvent.id,
            AnalyticsEvent.event_type,
            AnalyticsEvent.entity_type,
            AnalyticsEvent.metadata_.label("details"),
            AnalyticsEvent.occurred_at,
            Candidate.email.label("user_email"),
            Candidate.full_name.label("user_name"),
        )
        .join(Candidate, Candidate.id == AnalyticsEvent.candidate_id)
        .order_by(AnalyticsEvent.occurred_at.desc())
        .limit(limit)
    )
    return [
        ActivityFeedItem(
            id=str(row.id),
            user_email=row.user_email,
            user_name=row.user_name,
            event_type=row.event_type,
            entity_type=row.entity_type,
            details=row.details,
            occurred_at=row.occurred_at,
        )
        for row in result.all()
    ]


async def export_users_csv(db: AsyncSession) -> str:
    companies_sub = (
        select(func.count(Company.id))
        .where(Company.candidate_id == Candidate.id)
        .correlate(Candidate)
        .scalar_subquery()
        .label("companies_count")
    )
    messages_sub = (
        select(func.count(OutreachMessage.id))
        .where(
            OutreachMessage.candidate_id == Candidate.id,
            OutreachMessage.status != MessageStatus.DRAFT,
        )
        .correlate(Candidate)
        .scalar_subquery()
        .label("messages_sent_count")
    )
    q = select(
        Candidate.id,
        Candidate.email,
        Candidate.full_name,
        Candidate.is_admin,
        Candidate.is_active,
        Candidate.created_at,
        companies_sub,
        messages_sub,
    ).order_by(Candidate.created_at.desc())
    rows = (await db.execute(q)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Email", "Full Name", "Is Admin", "Is Active", "Created At", "Companies", "Messages Sent"])
    for row in rows:
        writer.writerow(
            [
                str(row.id),
                row.email,
                row.full_name,
                row.is_admin,
                row.is_active,
                row.created_at.isoformat(),
                row.companies_count or 0,
                row.messages_sent_count or 0,
            ]
        )
    return output.getvalue()


async def create_audit_log(
    db: AsyncSession,
    admin_id: uuid.UUID,
    action: str,
    target_user_id: uuid.UUID | None = None,
    details: dict | None = None,
) -> AdminAuditLog:
    log = AdminAuditLog(
        id=uuid.uuid4(),
        admin_id=admin_id,
        action=action,
        target_user_id=target_user_id,
        details=details,
    )
    db.add(log)
    await db.commit()
    logger.info("audit_log_created", action=action, admin_id=str(admin_id))
    return log


async def get_audit_log(db: AsyncSession, limit: int = 50) -> list[AuditLogItem]:
    admin_alias = Candidate.__table__.alias("admin_user")
    target_alias = Candidate.__table__.alias("target_user")

    result = await db.execute(
        select(
            AdminAuditLog.id,
            AdminAuditLog.action,
            AdminAuditLog.details,
            AdminAuditLog.created_at,
            admin_alias.c.email.label("admin_email"),
            admin_alias.c.full_name.label("admin_name"),
            target_alias.c.email.label("target_email"),
            target_alias.c.full_name.label("target_name"),
        )
        .outerjoin(admin_alias, admin_alias.c.id == AdminAuditLog.admin_id)
        .outerjoin(target_alias, target_alias.c.id == AdminAuditLog.target_user_id)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(limit)
    )
    return [
        AuditLogItem(
            id=str(row.id),
            admin_email=row.admin_email,
            admin_name=row.admin_name,
            action=row.action,
            target_email=row.target_email,
            target_name=row.target_name,
            details=row.details,
            created_at=row.created_at,
        )
        for row in result.all()
    ]


async def broadcast_email(
    db: AsyncSession,
    admin_id: uuid.UUID,
    subject: str,
    body: str,
    email_client,
) -> BroadcastResponse:
    from app.config import settings as app_settings

    # Query all active candidates who haven't opted out and aren't suppressed
    from app.models.suppression import EmailSuppression

    suppressed_emails = select(EmailSuppression.email).scalar_subquery()
    result = await db.execute(
        select(Candidate).where(
            Candidate.is_active == True,  # noqa: E712
            Candidate.email.notin_(suppressed_emails),
        )
    )
    candidates = result.scalars().all()

    sender = getattr(app_settings, "SENDER_EMAIL", "noreply@example.com")

    # Split eligible vs opted-out
    eligible = []
    skipped_count = 0
    for candidate in candidates:
        prefs = candidate.preferences or {}
        if prefs.get("email_notifications") is False:
            skipped_count += 1
        else:
            eligible.append(candidate)

    # Send concurrently with semaphore to limit parallelism
    sem = asyncio.Semaphore(10)

    async def _send(candidate):
        async with sem:
            try:
                await email_client.send(
                    to=candidate.email,
                    from_email=sender,
                    subject=subject,
                    body=body,
                )
                return True
            except Exception as e:
                logger.warning("broadcast_send_failed", email=candidate.email, error=str(e))
                return False

    results = await asyncio.gather(*[_send(c) for c in eligible])
    sent_count = sum(1 for r in results if r)
    skipped_count += sum(1 for r in results if not r)

    await create_audit_log(
        db,
        admin_id,
        "broadcast_sent",
        details={"subject": subject, "sent_count": sent_count, "skipped_count": skipped_count},
    )

    return BroadcastResponse(sent_count=sent_count, skipped_count=skipped_count)
