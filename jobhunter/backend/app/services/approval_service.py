import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import ActionStatus
from app.models.outreach import OutreachMessage
from app.models.pending_action import PendingAction
from app.schemas.approval import PendingActionResponse

logger = structlog.get_logger()


def _action_to_response(action: PendingAction, context: dict | None = None) -> PendingActionResponse:
    ctx = context or {}
    return PendingActionResponse(
        id=str(action.id),
        candidate_id=str(action.candidate_id),
        action_type=action.action_type,
        entity_type=action.entity_type,
        entity_id=str(action.entity_id),
        status=action.status,
        ai_reasoning=action.ai_reasoning,
        metadata_=action.metadata_,
        reviewed_at=action.reviewed_at,
        expires_at=action.expires_at,
        created_at=action.created_at,
        message_subject=ctx.get("message_subject"),
        message_body=ctx.get("message_body"),
        contact_name=ctx.get("contact_name"),
        company_name=ctx.get("company_name"),
        message_type=ctx.get("message_type"),
        channel=ctx.get("channel"),
    )


async def _enrich_context(db: AsyncSession, action: PendingAction) -> dict:
    """Load entity context for display (OutreachMessage -> Contact -> Company)."""
    if action.entity_type != "outreach_message":
        return {}

    result = await db.execute(
        select(OutreachMessage).where(OutreachMessage.id == action.entity_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        return {}

    contact_result = await db.execute(select(Contact).where(Contact.id == msg.contact_id))
    contact = contact_result.scalar_one_or_none()

    company_name = None
    if contact:
        company_result = await db.execute(select(Company).where(Company.id == contact.company_id))
        company = company_result.scalar_one_or_none()
        company_name = company.name if company else None

    return {
        "message_subject": msg.subject,
        "message_body": msg.body,
        "contact_name": contact.full_name if contact else None,
        "company_name": company_name,
        "message_type": msg.message_type,
        "channel": msg.channel,
    }


async def create_pending_action(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    action_type: str,
    entity_id: uuid.UUID,
    ai_reasoning: str | None = None,
    metadata: dict | None = None,
    entity_type: str = "outreach_message",
) -> PendingAction:
    action = PendingAction(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        status=ActionStatus.PENDING,
        ai_reasoning=ai_reasoning,
        metadata_=metadata,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    logger.info("pending_action_created", action_id=str(action.id), action_type=action_type)
    return action


async def list_pending_actions(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    status: str | None = None,
    action_type: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[PendingActionResponse], int]:
    filters = [PendingAction.candidate_id == candidate_id]
    if status:
        filters.append(PendingAction.status == status)
    if action_type:
        filters.append(PendingAction.action_type == action_type)

    count_query = select(func.count()).select_from(PendingAction).where(*filters)
    total = (await db.execute(count_query)).scalar() or 0

    # Single joined query instead of N+1 _enrich_context calls
    query = (
        select(
            PendingAction,
            OutreachMessage.subject.label("msg_subject"),
            OutreachMessage.body.label("msg_body"),
            OutreachMessage.message_type.label("msg_type"),
            OutreachMessage.channel.label("msg_channel"),
            Contact.full_name.label("contact_name"),
            Company.name.label("company_name"),
        )
        .outerjoin(
            OutreachMessage,
            (PendingAction.entity_id == OutreachMessage.id)
            & (PendingAction.entity_type == "outreach_message"),
        )
        .outerjoin(Contact, OutreachMessage.contact_id == Contact.id)
        .outerjoin(Company, Contact.company_id == Company.id)
        .where(*filters)
        .order_by(PendingAction.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    rows = result.all()

    responses = []
    for row in rows:
        action = row[0]
        ctx = {
            "message_subject": row.msg_subject,
            "message_body": row.msg_body,
            "contact_name": row.contact_name,
            "company_name": row.company_name,
            "message_type": row.msg_type,
            "channel": row.msg_channel,
        }
        responses.append(_action_to_response(action, ctx))

    return responses, total


async def get_pending_action(
    db: AsyncSession, action_id: uuid.UUID, candidate_id: uuid.UUID
) -> PendingActionResponse | None:
    # Single joined query instead of N+1 _enrich_context calls
    query = (
        select(
            PendingAction,
            OutreachMessage.subject.label("msg_subject"),
            OutreachMessage.body.label("msg_body"),
            OutreachMessage.message_type.label("msg_type"),
            OutreachMessage.channel.label("msg_channel"),
            Contact.full_name.label("contact_name"),
            Company.name.label("company_name"),
        )
        .outerjoin(
            OutreachMessage,
            (PendingAction.entity_id == OutreachMessage.id)
            & (PendingAction.entity_type == "outreach_message"),
        )
        .outerjoin(Contact, OutreachMessage.contact_id == Contact.id)
        .outerjoin(Company, Contact.company_id == Company.id)
        .where(
            PendingAction.id == action_id,
            PendingAction.candidate_id == candidate_id,
        )
    )
    result = await db.execute(query)
    row = result.one_or_none()
    if not row:
        return None
    action = row[0]
    ctx = {
        "message_subject": row.msg_subject,
        "message_body": row.msg_body,
        "contact_name": row.contact_name,
        "company_name": row.company_name,
        "message_type": row.msg_type,
        "channel": row.msg_channel,
    }
    return _action_to_response(action, ctx)


async def approve_action(
    db: AsyncSession, action_id: uuid.UUID, candidate_id: uuid.UUID
) -> PendingAction | None:
    result = await db.execute(
        select(PendingAction).where(
            PendingAction.id == action_id,
            PendingAction.candidate_id == candidate_id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        return None
    if action.status != ActionStatus.PENDING:
        return action

    action.status = ActionStatus.APPROVED
    action.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(action)
    logger.info("pending_action_approved", action_id=str(action.id))
    return action


async def reject_action(
    db: AsyncSession, action_id: uuid.UUID, candidate_id: uuid.UUID
) -> PendingAction | None:
    result = await db.execute(
        select(PendingAction).where(
            PendingAction.id == action_id,
            PendingAction.candidate_id == candidate_id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        return None
    if action.status != ActionStatus.PENDING:
        return action

    action.status = ActionStatus.REJECTED
    action.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(action)
    logger.info("pending_action_rejected", action_id=str(action.id))
    return action


async def count_pending(db: AsyncSession, candidate_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(PendingAction).where(
            PendingAction.candidate_id == candidate_id,
            PendingAction.status == ActionStatus.PENDING,
        )
    )
    return result.scalar() or 0


async def expire_stale_actions(db: AsyncSession, max_age_days: int = 30) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    result = await db.execute(
        select(PendingAction).where(
            PendingAction.status == ActionStatus.PENDING,
            PendingAction.created_at < cutoff,
        )
    )
    actions = result.scalars().all()
    count = 0
    for action in actions:
        action.status = ActionStatus.EXPIRED
        action.reviewed_at = datetime.now(timezone.utc)
        count += 1
    if count:
        await db.commit()
        logger.info("stale_actions_expired", count=count)
    return count
