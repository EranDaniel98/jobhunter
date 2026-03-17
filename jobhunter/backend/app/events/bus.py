"""Event bus with Redis Streams durability and in-process fallback.

Publishes events to both local handlers (immediate) and Redis Streams
(durable, cross-worker). If Redis is unavailable, falls back to in-process
only — the same behavior as before this upgrade.
"""

import asyncio
import contextlib
import json
import secrets
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger()

EventHandler = Callable[["Event"], Coroutine[Any, Any, None]]

STREAM_MAX_LEN = 10_000
CONSUMER_GROUP = "jobhunter"


@dataclass
class Event:
    """Domain event with type, payload, and metadata."""

    event_type: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""


class EventBus:
    """Async event bus with Redis Streams durability."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._redis = None
        self._consumer_name: str = f"worker-{secrets.token_hex(4)}"
        self._listener_task: asyncio.Task | None = None
        self._stopping = False

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)
        logger.info("event_bus_subscribed", event_type=event_type, handler=handler.__name__)

    async def connect(self, redis) -> None:
        """Connect to Redis for durable event streaming."""
        self._redis = redis
        # Create consumer groups for all subscribed event types
        for event_type in self._handlers:
            await self._ensure_consumer_group(event_type)
        logger.info("event_bus_redis_connected", consumer=self._consumer_name)

    async def _ensure_consumer_group(self, event_type: str) -> None:
        """Create consumer group for a stream if it doesn't exist."""
        if not self._redis:
            return
        stream = f"events:{event_type}"
        with contextlib.suppress(Exception):
            # Group already exists — expected on restart
            await self._redis.xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)

    async def publish(self, event_type: str, payload: dict[str, Any], source: str = "") -> None:
        """Publish event to local handlers and optionally to Redis Streams."""
        event = Event(event_type=event_type, payload=payload, source=source)

        # Always dispatch locally (immediate, in-process)
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    "event_handler_failed",
                    event_type=event_type,
                    handler=handler.__name__,
                    error=str(e),
                )

        # Persist to Redis Streams (best-effort)
        if self._redis:
            try:
                stream = f"events:{event_type}"
                await self._redis.xadd(
                    stream,
                    {
                        "event_type": event_type,
                        "payload": json.dumps(payload, default=str),
                        "source": source,
                        "timestamp": event.timestamp.isoformat(),
                    },
                    maxlen=STREAM_MAX_LEN,
                )
            except Exception as e:
                logger.warning("event_bus_redis_publish_failed", event_type=event_type, error=str(e))

    async def start_listening(self) -> None:
        """Start background task to consume events from Redis Streams."""
        if not self._redis:
            logger.info("event_bus_listener_skipped", reason="no redis connection")
            return

        # Ensure consumer groups exist for all subscribed event types
        for event_type in self._handlers:
            await self._ensure_consumer_group(event_type)

        self._stopping = False
        self._listener_task = asyncio.create_task(self._listen_loop())
        logger.info("event_bus_listener_started", consumer=self._consumer_name)

    async def stop_listening(self) -> None:
        """Stop the background listener task."""
        self._stopping = True
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task
        self._listener_task = None
        logger.info("event_bus_listener_stopped")

    async def _listen_loop(self) -> None:
        """XREADGROUP loop for consuming cross-worker events."""
        if self._redis is None:
            return
        streams = {f"events:{et}": ">" for et in self._handlers}
        if not streams:
            return

        while not self._stopping:
            try:
                results = await self._redis.xreadgroup(
                    CONSUMER_GROUP,
                    self._consumer_name,
                    streams,
                    count=10,
                    block=2000,
                )
                if not results:
                    continue

                for stream_name, messages in results:
                    stream_str = stream_name if isinstance(stream_name, str) else stream_name.decode()
                    for msg_id, msg_data in messages:
                        try:
                            await self._process_stream_message(stream_str, msg_id, msg_data)
                        except Exception as e:
                            logger.error(
                                "event_bus_stream_process_failed",
                                stream=stream_str,
                                msg_id=msg_id,
                                error=str(e),
                            )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("event_bus_listen_error", error=str(e))
                await asyncio.sleep(5)

    async def _process_stream_message(self, stream: str, msg_id: str, msg_data: dict) -> None:
        """Process a single message from a Redis Stream.

        If the message was published by this worker, only ACK it (handlers already
        fired during publish()). Otherwise, deserialize and dispatch to local handlers.
        """
        source = msg_data.get("source", "")
        if isinstance(source, bytes):
            source = source.decode()

        # Skip events we published ourselves (already fired in-process during publish)
        if source != self._consumer_name:
            event_type = msg_data.get("event_type", "")
            if isinstance(event_type, bytes):
                event_type = event_type.decode()

            payload_raw = msg_data.get("payload", "{}")
            if isinstance(payload_raw, bytes):
                payload_raw = payload_raw.decode()

            handlers = self._handlers.get(event_type, [])
            if handlers:
                payload = json.loads(payload_raw)
                event = Event(event_type=event_type, payload=payload, source=source)
                for handler in handlers:
                    try:
                        await handler(event)
                    except Exception as e:
                        logger.error(
                            "event_bus_cross_worker_handler_failed",
                            handler=handler.__name__,
                            event_type=event_type,
                            error=str(e),
                        )

        assert self._redis is not None  # guaranteed by _listen_loop guard
        await self._redis.xack(stream, CONSUMER_GROUP, msg_id)

    @property
    def handler_count(self) -> int:
        return sum(len(h) for h in self._handlers.values())


# Global singleton
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
