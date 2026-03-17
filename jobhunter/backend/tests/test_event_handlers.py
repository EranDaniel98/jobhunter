"""Tests for event handlers in app/events/handlers.py."""

from unittest.mock import patch

import pytest

from app.events.bus import Event
from app.events.handlers import (
    log_event,
    on_company_approved,
    on_outreach_sent,
    on_resume_parsed,
)


def _make_event(event_type: str, payload: dict) -> Event:
    return Event(event_type=event_type, payload=payload)


@pytest.mark.asyncio
async def test_log_event_logs_event_type():
    event = _make_event("test_event", {"key": "value"})
    with patch("app.events.handlers.logger") as mock_logger:
        await log_event(event)
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "test_event" in str(call_args)


@pytest.mark.asyncio
async def test_on_resume_parsed_with_skills():
    event = _make_event("resume_parsed", {"candidate_id": "abc", "skills": ["python", "fastapi"]})
    with patch("app.events.handlers.logger") as mock_logger:
        await on_resume_parsed(event)
        mock_logger.info.assert_called()


@pytest.mark.asyncio
async def test_on_outreach_sent():
    event = _make_event("outreach_sent", {"message_id": "123", "contact_email": "test@example.com"})
    with patch("app.events.handlers.logger") as mock_logger:
        await on_outreach_sent(event)
        mock_logger.info.assert_called()


@pytest.mark.asyncio
async def test_on_company_approved():
    event = _make_event("company_approved", {"company_id": "456", "candidate_id": "789"})
    with patch("app.events.handlers.logger") as mock_logger:
        await on_company_approved(event)
        mock_logger.info.assert_called()
