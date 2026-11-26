from typing import Any

import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager

from app.config import Settings
from app.main import create_app


class RecordingEventPublisher:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def publish(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    async def aclose(self) -> None:
        return None


@pytest_asyncio.fixture
async def client(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'room-service.db'}",
        host_disconnect_grace_seconds=0.4,
        event_publisher="null",
        auto_create_tables=True,
        sql_echo=False,
    )
    events = RecordingEventPublisher()
    app = create_app(settings, events=events)

    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as http_client:
            http_client.event_log = events
            yield http_client


@pytest.fixture
def event_log(client):
    return client.event_log
