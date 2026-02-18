import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsEvent
from app.models.company import Company
from app.models.contact import Contact
from app.models.outreach import OutreachMessage

logger = structlog.get_logger()


async def log_event(
    db: AsyncSession,
    candidate_id: uuid.UUID,
    event_type: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> AnalyticsEvent:
    event = AnalyticsEvent(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_=metadata,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.commit()
    return event


async def get_funnel(db: AsyncSession, candidate_id: uuid.UUID) -> dict:
    """Count outreach messages by status for conversion funnel."""
    result = await db.execute(
        select(OutreachMessage.status, func.count())
        .where(OutreachMessage.candidate_id == candidate_id)
        .group_by(OutreachMessage.status)
    )
    counts = dict(result.all())
    return {
        "drafted": counts.get("draft", 0),
        "sent": counts.get("sent", 0),
        "delivered": counts.get("delivered", 0),
        "opened": counts.get("opened", 0),
        "replied": counts.get("replied", 0),
        "bounced": counts.get("bounced", 0),
    }


async def get_outreach_stats(db: AsyncSession, candidate_id: uuid.UUID) -> dict:
    """Get outreach performance statistics."""
    result = await db.execute(
        select(OutreachMessage)
        .where(OutreachMessage.candidate_id == candidate_id)
    )
    messages = result.scalars().all()

    total_sent = sum(1 for m in messages if m.status in ("sent", "delivered", "opened", "replied"))
    total_opened = sum(1 for m in messages if m.status in ("opened", "replied"))
    total_replied = sum(1 for m in messages if m.status == "replied")

    by_channel = {}
    for m in messages:
        ch = m.channel
        if ch not in by_channel:
            by_channel[ch] = {"sent": 0, "opened": 0, "replied": 0}
        if m.status in ("sent", "delivered", "opened", "replied"):
            by_channel[ch]["sent"] += 1
        if m.status in ("opened", "replied"):
            by_channel[ch]["opened"] += 1
        if m.status == "replied":
            by_channel[ch]["replied"] += 1

    return {
        "total_sent": total_sent,
        "total_opened": total_opened,
        "total_replied": total_replied,
        "open_rate": total_opened / total_sent if total_sent > 0 else 0.0,
        "reply_rate": total_replied / total_sent if total_sent > 0 else 0.0,
        "by_channel": by_channel,
    }


async def get_pipeline_stats(db: AsyncSession, candidate_id: uuid.UUID) -> dict:
    """Get company pipeline statistics."""
    result = await db.execute(
        select(Company.status, func.count())
        .where(Company.candidate_id == candidate_id)
        .group_by(Company.status)
    )
    counts = dict(result.all())

    # Count researched (approved + completed research)
    researched = await db.execute(
        select(func.count())
        .select_from(Company)
        .where(
            Company.candidate_id == candidate_id,
            Company.research_status == "completed",
        )
    )
    researched_count = researched.scalar() or 0

    # Count contacted (companies with at least one sent message)
    contacted = await db.execute(
        select(func.count(func.distinct(Company.id)))
        .select_from(Company)
        .join(Contact, Contact.company_id == Company.id)
        .join(OutreachMessage, OutreachMessage.contact_id == Contact.id)
        .where(
            Company.candidate_id == candidate_id,
            OutreachMessage.status.in_(["sent", "delivered", "opened", "replied"]),
        )
    )
    contacted_count = contacted.scalar() or 0

    return {
        "suggested": counts.get("suggested", 0),
        "approved": counts.get("approved", 0),
        "rejected": counts.get("rejected", 0),
        "researched": researched_count,
        "contacted": contacted_count,
    }
