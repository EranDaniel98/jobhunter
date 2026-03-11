"""In-process event bus -- publish/subscribe for decoupled service communication.

Designed as an in-process bus for now, with a clear upgrade path to Redis Pub/Sub
or a message queue for multi-worker deployments.
"""

from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger()

EventHandler = Callable[["Event"], Coroutine[Any, Any, None]]


@dataclass
class Event:
    """Domain event with type, payload, and metadata."""

    event_type: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""


class EventBus:
    """Simple in-process async event bus."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)
        logger.info("event_bus_subscribed", event_type=event_type, handler=handler.__name__)

    async def publish(self, event_type: str, payload: dict[str, Any], source: str = "") -> None:
        event = Event(event_type=event_type, payload=payload, source=source)
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
