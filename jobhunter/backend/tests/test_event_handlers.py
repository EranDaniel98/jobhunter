"""Tests for event handlers in app/events/handlers.py."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.events.bus import Event
from app.events.handlers import (
    log_event,
    on_company_approved,
    on_outreach_sent,
    on_resume_parsed,
    persist_analytics,
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


# --- persist_analytics tests ---


def _make_session_mock() -> MagicMock:
    """Return a session mock where add() is sync and commit() is async."""
    session = MagicMock()
    session.commit = AsyncMock()
    return session


def _make_async_cm(session_mock: MagicMock):
    """Return an async context manager that yields session_mock."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session_mock)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.asyncio
async def test_persist_analytics_company_approved():
    candidate_id = uuid.uuid4()
    company_id = uuid.uuid4()
    event = _make_event("company_approved", {"candidate_id": str(candidate_id), "company_id": str(company_id)})

    session_mock = _make_session_mock()
    factory_mock = MagicMock(return_value=_make_async_cm(session_mock))

    with patch("app.infrastructure.database.async_session_factory", factory_mock):
        await persist_analytics(event)

    session_mock.add.assert_called_once()
    added = session_mock.add.call_args[0][0]
    assert added.event_type == "company_approved"
    assert added.entity_type == "company"
    assert added.entity_id == company_id
    assert added.candidate_id == candidate_id
    session_mock.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_analytics_resume_parsed():
    candidate_id = uuid.uuid4()
    resume_id = uuid.uuid4()
    event = _make_event("resume_parsed", {"candidate_id": str(candidate_id), "resume_id": str(resume_id)})

    session_mock = _make_session_mock()
    factory_mock = MagicMock(return_value=_make_async_cm(session_mock))

    with patch("app.infrastructure.database.async_session_factory", factory_mock):
        await persist_analytics(event)

    session_mock.add.assert_called_once()
    added = session_mock.add.call_args[0][0]
    assert added.event_type == "resume_parsed"
    assert added.entity_type == "resume"
    assert added.entity_id == resume_id
    session_mock.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_analytics_outreach_sent():
    candidate_id = uuid.uuid4()
    message_id = uuid.uuid4()
    event = _make_event("outreach_sent", {"candidate_id": str(candidate_id), "message_id": str(message_id)})

    session_mock = _make_session_mock()
    factory_mock = MagicMock(return_value=_make_async_cm(session_mock))

    with patch("app.infrastructure.database.async_session_factory", factory_mock):
        await persist_analytics(event)

    session_mock.add.assert_called_once()
    added = session_mock.add.call_args[0][0]
    assert added.event_type == "email_sent"
    assert added.entity_type == "message"
    assert added.entity_id == message_id
    session_mock.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_analytics_unknown_event_type_is_noop():
    """Events not in _EVENT_MAP should be silently skipped."""
    event = _make_event("unknown_event", {"candidate_id": str(uuid.uuid4())})
    session_mock = _make_session_mock()
    factory_mock = MagicMock(return_value=_make_async_cm(session_mock))

    with patch("app.infrastructure.database.async_session_factory", factory_mock):
        await persist_analytics(event)

    session_mock.add.assert_not_called()
    session_mock.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_analytics_missing_candidate_id_logs_warning():
    """Missing candidate_id should log a warning and not write to DB."""
    event = _make_event("company_approved", {"company_id": str(uuid.uuid4())})
    session_mock = _make_session_mock()
    factory_mock = MagicMock(return_value=_make_async_cm(session_mock))

    with patch("app.events.handlers.logger") as mock_logger:
        with patch("app.infrastructure.database.async_session_factory", factory_mock):
            await persist_analytics(event)

    mock_logger.warning.assert_called_once()
    session_mock.add.assert_not_called()
