"""Event handlers -- react to domain events for analytics, logging, etc."""

import structlog

from app.events.bus import Event

logger = structlog.get_logger()


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
