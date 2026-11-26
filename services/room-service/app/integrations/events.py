"""Integration boundary with API Gateway.

Room Service publishes a `room_state_changed` event after every committed
change. The HTTP publisher posts it to the Gateway endpoint declared in
api-contract.md; other publishers are kept for local development and tests.
"""

import json
import logging
from typing import Any, Protocol
from uuid import UUID

import httpx

from app.config import Settings
from app.schemas import RoomState

logger = logging.getLogger("room_service.events")


class EventPublisher(Protocol):
    async def publish(self, event: dict[str, Any]) -> None: ...

    async def aclose(self) -> None: ...


class NullEventPublisher:
    async def publish(self, event: dict[str, Any]) -> None:
        return None

    async def aclose(self) -> None:
        return None


class LoggingEventPublisher:
    async def publish(self, event: dict[str, Any]) -> None:
        logger.info("outbox event: %s", json.dumps(event, ensure_ascii=False))

    async def aclose(self) -> None:
        return None


class HttpEventPublisher:
    def __init__(self, url: str, timeout_seconds: float) -> None:
        self._url = url
        self._timeout = httpx.Timeout(timeout_seconds)

    async def publish(self, event: dict[str, Any]) -> None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._url, json=event)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("не удалось отправить событие в API Gateway: %s", exc)

    async def aclose(self) -> None:
        return None


def state_changed_event(room_id: UUID, state: RoomState, reason: str) -> dict[str, Any]:
    return {
        "type": "room_state_changed",
        "room_id": str(room_id),
        "state_version": state.state_version,
        "reason": reason,
        "state": state.model_dump(mode="json"),
    }


async def publish_state_change(
    events: EventPublisher, room_id: UUID, state: RoomState, reason: str
) -> None:
    await events.publish(state_changed_event(room_id, state, reason))


def build_event_publisher(settings: Settings) -> EventPublisher:
    mode = settings.event_publisher.lower()
    if mode == "null":
        return NullEventPublisher()
    if mode == "logging":
        return LoggingEventPublisher()
    return HttpEventPublisher(
        url=settings.api_events_url,
        timeout_seconds=settings.api_events_timeout_seconds,
    )
