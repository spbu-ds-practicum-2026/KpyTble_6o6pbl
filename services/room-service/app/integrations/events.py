"""Integration boundary with API Gateway.

Room Service itself never pushes data to clients. It returns the full room state
in HTTP responses, and API Gateway broadcasts it. The only asynchronous event is
the host handover, which happens after a disconnect grace period and therefore
cannot be returned to any request.

Replace LoggingEventPublisher with an HTTP/message-bus publisher when the
Gateway exists. Nothing else in Room Service depends on this module.
"""

import json
import logging
from typing import Any, Protocol

from app.config import Settings

logger = logging.getLogger("room_service.events")


class EventPublisher(Protocol):
    async def publish(self, event: dict[str, Any]) -> None: ...


class NullEventPublisher:
    async def publish(self, event: dict[str, Any]) -> None:
        return None


class LoggingEventPublisher:
    async def publish(self, event: dict[str, Any]) -> None:
        logger.info("outbox event: %s", json.dumps(event, ensure_ascii=False))


def build_event_publisher(settings: Settings) -> EventPublisher:
    if settings.event_publisher.lower() == "null":
        return NullEventPublisher()
    return LoggingEventPublisher()
