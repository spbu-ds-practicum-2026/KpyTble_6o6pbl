import httpx
import pytest_asyncio
from asgi_lifespan import LifespanManager

from app.config import Settings
from app.main import create_app


@pytest_asyncio.fixture
async def client(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'room-service.db'}",
        host_disconnect_grace_seconds=0.4,
        event_publisher="null",
        auto_create_tables=True,
        sql_echo=False,
    )
    app = create_app(settings)

    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as http_client:
            yield http_client
