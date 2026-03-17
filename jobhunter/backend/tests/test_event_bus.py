"""Tests for the in-process event bus."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.events.bus import Event, EventBus, get_event_bus

# ---------------------------------------------------------------------------
# EventBus core behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_publish_no_subscribers():
    """Publishing an event with no subscribers should not raise."""
    bus = EventBus()
    await bus.publish("unknown.event", {"key": "value"})  # no error


@pytest.mark.asyncio
async def test_subscribe_and_publish():
    """Subscribed handler receives the published event."""
    bus = EventBus()
    handler = AsyncMock()

    bus.subscribe("test.event", handler)
    await bus.publish("test.event", {"foo": "bar"})

    handler.assert_awaited_once()
    event = handler.call_args[0][0]
    assert isinstance(event, Event)
    assert event.event_type == "test.event"
    assert event.payload == {"foo": "bar"}


@pytest.mark.asyncio
async def test_multiple_handlers_same_event():
    """All handlers for the same event type are called."""
    bus = EventBus()
    handler_a = AsyncMock()
    handler_b = AsyncMock()

    bus.subscribe("multi.event", handler_a)
    bus.subscribe("multi.event", handler_b)
    await bus.publish("multi.event", {"x": 1})

    handler_a.assert_awaited_once()
    handler_b.assert_awaited_once()


@pytest.mark.asyncio
async def test_handler_exception_doesnt_break_others():
    """A failing handler does not prevent subsequent handlers from running."""
    bus = EventBus()

    async def bad_handler(event: Event) -> None:
        raise RuntimeError("boom")

    good_handler = AsyncMock()

    bus.subscribe("error.event", bad_handler)
    bus.subscribe("error.event", good_handler)

    await bus.publish("error.event", {})

    good_handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_event_has_correct_timestamp_and_payload():
    """Event includes a UTC timestamp and carries the published payload."""
    bus = EventBus()
    captured: list[Event] = []

    async def capture(event: Event) -> None:
        captured.append(event)

    bus.subscribe("ts.event", capture)
    before = datetime.now(UTC)
    await bus.publish("ts.event", {"data": 42}, source="test_suite")
    after = datetime.now(UTC)

    assert len(captured) == 1
    evt = captured[0]
    assert evt.payload == {"data": 42}
    assert evt.source == "test_suite"
    assert before <= evt.timestamp <= after


def test_handler_count_property():
    """handler_count returns the total number of registered handlers."""
    bus = EventBus()
    assert bus.handler_count == 0

    bus.subscribe("a", AsyncMock())
    bus.subscribe("a", AsyncMock())
    bus.subscribe("b", AsyncMock())

    assert bus.handler_count == 3


@pytest.mark.asyncio
async def test_different_event_types_isolated():
    """Handlers only fire for their subscribed event type."""
    bus = EventBus()
    handler_a = AsyncMock()
    handler_b = AsyncMock()

    bus.subscribe("type_a", handler_a)
    bus.subscribe("type_b", handler_b)

    await bus.publish("type_a", {})

    handler_a.assert_awaited_once()
    handler_b.assert_not_awaited()


def test_get_event_bus_returns_singleton():
    """get_event_bus returns the same instance on repeated calls."""
    import app.events.bus as bus_mod

    # Reset singleton for a clean test
    bus_mod._event_bus = None

    bus1 = get_event_bus()
    bus2 = get_event_bus()
    assert bus1 is bus2

    # Cleanup
    bus_mod._event_bus = None
