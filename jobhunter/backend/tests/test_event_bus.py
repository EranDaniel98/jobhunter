"""Tests for the event bus with Redis Streams durability."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.events.bus import Event, EventBus, get_event_bus

# ---------------------------------------------------------------------------
# EventBus core behaviour (in-process, no Redis)
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


# ---------------------------------------------------------------------------
# Redis Streams integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_writes_to_redis_stream():
    """publish() should XADD to Redis when connected."""
    bus = EventBus()
    handler = AsyncMock()
    bus.subscribe("test.event", handler)

    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock()
    await bus.connect(mock_redis)

    await bus.publish("test.event", {"key": "value"}, source="test")

    # Local handler was called
    handler.assert_awaited_once()

    # Redis XADD was called
    mock_redis.xadd.assert_awaited_once()
    call_args = mock_redis.xadd.call_args
    assert call_args[0][0] == "events:test.event"
    msg_data = call_args[0][1]
    assert msg_data["event_type"] == "test.event"
    assert json.loads(msg_data["payload"]) == {"key": "value"}
    assert msg_data["source"] == "test"


@pytest.mark.asyncio
async def test_publish_fallback_on_redis_failure():
    """If Redis XADD fails, local handlers still fire."""
    bus = EventBus()
    handler = AsyncMock()
    bus.subscribe("test.event", handler)

    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock()
    mock_redis.xadd = AsyncMock(side_effect=ConnectionError("Redis down"))
    await bus.connect(mock_redis)

    await bus.publish("test.event", {"key": "value"})

    # Local handler was still called despite Redis failure
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_without_redis_works():
    """publish() works fine without Redis (in-process only)."""
    bus = EventBus()
    handler = AsyncMock()
    bus.subscribe("test.event", handler)

    # No connect() called — Redis is None
    await bus.publish("test.event", {"data": 1})

    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_connect_creates_consumer_groups():
    """connect() should create consumer groups for subscribed event types."""
    bus = EventBus()
    bus.subscribe("event_a", AsyncMock())
    bus.subscribe("event_b", AsyncMock())

    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock()
    await bus.connect(mock_redis)

    assert mock_redis.xgroup_create.await_count == 2
    calls = [c[0] for c in mock_redis.xgroup_create.call_args_list]
    streams = {c[0] for c in calls}
    assert streams == {"events:event_a", "events:event_b"}


@pytest.mark.asyncio
async def test_stop_listening_without_start():
    """stop_listening() should be safe to call without start_listening()."""
    bus = EventBus()
    await bus.stop_listening()  # Should not raise


@pytest.mark.asyncio
async def test_process_stream_message_dispatches_to_handlers():
    """Stream messages from other workers should dispatch to local handlers."""
    bus = EventBus()
    handler = AsyncMock()
    bus.subscribe("company_approved", handler)

    mock_redis = AsyncMock()
    bus._redis = mock_redis
    bus._consumer_name = "worker-aaaa"

    msg_data = {
        "event_type": "company_approved",
        "payload": '{"company_id": "123"}',
        "source": "worker-bbbb",
        "timestamp": "2026-03-17T10:00:00",
    }

    await bus._process_stream_message("events:company_approved", "msg-1", msg_data)

    handler.assert_awaited_once()
    event_arg = handler.call_args[0][0]
    assert event_arg.event_type == "company_approved"
    assert event_arg.payload == {"company_id": "123"}
    mock_redis.xack.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_stream_message_skips_self_published():
    """Stream messages from this worker should be ACKed but not dispatched."""
    bus = EventBus()
    handler = AsyncMock()
    bus.subscribe("company_approved", handler)

    mock_redis = AsyncMock()
    bus._redis = mock_redis
    bus._consumer_name = "worker-aaaa"

    msg_data = {
        "event_type": "company_approved",
        "payload": '{"company_id": "123"}',
        "source": "worker-aaaa",
        "timestamp": "2026-03-17T10:00:00",
    }

    await bus._process_stream_message("events:company_approved", "msg-1", msg_data)

    handler.assert_not_awaited()
    mock_redis.xack.assert_awaited_once()
