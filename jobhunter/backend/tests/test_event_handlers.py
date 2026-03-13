"""Tests for event handlers in app/events/handlers.py."""

import pytest

from app.events.bus import Event
from app.events.handlers import (
    log_event,
    on_company_approved,
    on_outreach_sent,
    on_resume_parsed,
)


def _make_event(event_type: str = "test", **payload) -> Event:
    return Event(event_type=event_type, payload=payload, source="test")


@pytest.mark.asyncio
async def test_log_event():
    event = _make_event("some.event", key="value")
    await log_event(event)  # should not raise


@pytest.mark.asyncio
async def test_on_resume_parsed():
    event = _make_event(
        "resume_parsed",
        candidate_id="abc-123",
        skills=["python", "sql"],
    )
    await on_resume_parsed(event)  # should not raise


@pytest.mark.asyncio
async def test_on_resume_parsed_missing_skills():
    event = _make_event("resume_parsed", candidate_id="abc-123")
    await on_resume_parsed(event)  # defaults to empty list


@pytest.mark.asyncio
async def test_on_outreach_sent():
    event = _make_event(
        "outreach_sent",
        candidate_id="abc-123",
        contact_id="contact-456",
    )
    await on_outreach_sent(event)


@pytest.mark.asyncio
async def test_on_company_approved():
    event = _make_event(
        "company_approved",
        candidate_id="abc-123",
        company_id="comp-789",
    )
    await on_company_approved(event)
