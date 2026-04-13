"""Event handlers -- react to domain events for analytics, logging, etc."""

import uuid
from datetime import UTC, datetime

import structlog

from app.events.bus import Event

logger = structlog.get_logger()

# Maps bus event_type → (analytics_event_type, entity_type, entity_id_key)
_EVENT_MAP: dict[str, tuple[str, str, str]] = {
    "company_approved": ("company_approved", "company", "company_id"),
    "resume_parsed": ("resume_parsed", "resume", "resume_id"),
    "outreach_sent": ("email_sent", "message", "message_id"),
}


async def persist_analytics(event: Event) -> None:
    """Persist a domain event to the analytics_events table."""
    mapping = _EVENT_MAP.get(event.event_type)
    if mapping is None:
        return

    analytics_event_type, entity_type, entity_id_key = mapping

    raw_candidate_id = event.payload.get("candidate_id")
    raw_entity_id = event.payload.get(entity_id_key)

    if raw_candidate_id is None:
        logger.warning("persist_analytics_missing_candidate_id", event_type=event.event_type)
        return

    try:
        candidate_id = uuid.UUID(str(raw_candidate_id))
        entity_id = uuid.UUID(str(raw_entity_id)) if raw_entity_id is not None else None
    except (ValueError, AttributeError) as exc:
        logger.warning("persist_analytics_invalid_uuid", event_type=event.event_type, error=str(exc))
        return

    from app.infrastructure.database import async_session_factory
    from app.models.analytics import AnalyticsEvent

    async with async_session_factory() as session:
        record = AnalyticsEvent(
            candidate_id=candidate_id,
            event_type=analytics_event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            occurred_at=datetime.now(UTC),
        )
        session.add(record)
        await session.commit()


async def log_event(event: Event) -> None:
    """Log all events for audit trail."""
    logger.info(
        "domain_event",
        event_type=event.event_type,
        source=event.source,
        payload_keys=list(event.payload.keys()),
    )


async def on_resume_parsed(event: Event) -> None:
    """Handle resume_parsed -- could trigger downstream analytics."""
    logger.info(
        "resume_parsed_event",
        candidate_id=event.payload.get("candidate_id"),
        skills_count=len(event.payload.get("skills", [])),
    )


async def on_outreach_sent(event: Event) -> None:
    """Handle outreach_sent -- track email analytics."""
    logger.info(
        "outreach_sent_event",
        candidate_id=event.payload.get("candidate_id"),
        contact_id=event.payload.get("contact_id"),
    )


async def on_company_approved(event: Event) -> None:
    """Handle company_approved -- could trigger research pipeline."""
    logger.info(
        "company_approved_event",
        candidate_id=event.payload.get("candidate_id"),
        company_id=event.payload.get("company_id"),
    )
