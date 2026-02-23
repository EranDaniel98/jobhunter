import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import case, func, select
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
    """Get outreach performance statistics using SQL aggregation."""
    sent_statuses = ("sent", "delivered", "opened", "replied")
    opened_statuses = ("opened", "replied")

    result = await db.execute(
        select(
            OutreachMessage.channel,
            func.count(
                case((OutreachMessage.status.in_(sent_statuses), 1))
            ).label("sent"),
            func.count(
                case((OutreachMessage.status.in_(opened_statuses), 1))
            ).label("opened"),
            func.count(
                case((OutreachMessage.status == "replied", 1))
            ).label("replied"),
        )
        .where(OutreachMessage.candidate_id == candidate_id)
        .group_by(OutreachMessage.channel)
    )
    rows = result.all()

    total_sent = sum(r.sent for r in rows)
    total_opened = sum(r.opened for r in rows)
    total_replied = sum(r.replied for r in rows)

    by_channel = {
        r.channel: {"sent": r.sent, "opened": r.opened, "replied": r.replied}
        for r in rows
    }

    return {
        "total_sent": total_sent,
        "total_opened": total_opened,
        "total_replied": total_replied,
        "open_rate": total_opened / total_sent if total_sent > 0 else 0.0,
        "reply_rate": total_replied / total_sent if total_sent > 0 else 0.0,
        "by_channel": by_channel,
    }


async def get_pipeline_stats(db: AsyncSession, candidate_id: uuid.UUID) -> dict:
    """Get company pipeline statistics (2 queries instead of 3)."""
    # Combined query: status counts + researched count in one pass
    result = await db.execute(
        select(
            func.count(case((Company.status == "suggested", 1))).label("suggested"),
            func.count(case((Company.status == "approved", 1))).label("approved"),
            func.count(case((Company.status == "rejected", 1))).label("rejected"),
            func.count(case((Company.research_status == "completed", 1))).label("researched"),
        )
        .where(Company.candidate_id == candidate_id)
    )
    row = result.one()

    # Contacted requires JOIN through Contact→OutreachMessage (separate query)
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
        "suggested": row.suggested,
        "approved": row.approved,
        "rejected": row.rejected,
        "researched": row.researched,
        "contacted": contacted_count,
    }
