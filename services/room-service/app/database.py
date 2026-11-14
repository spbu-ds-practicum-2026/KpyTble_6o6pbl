from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import Settings


class Base(DeclarativeBase):
    pass


def create_engine_and_session_factory(
    settings: Settings,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    kwargs: dict = {"echo": settings.sql_echo, "pool_pre_ping": True}

    # SQLite is used by the test suite. In-memory databases need a single shared
    # connection, otherwise every session sees a different empty database.
    if settings.database_url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        kwargs["connect_args"] = {"timeout": 30}
        if ":memory:" in settings.database_url:
            kwargs["poolclass"] = StaticPool
            kwargs["connect_args"] = {
                "check_same_thread": False,
                "timeout": 30,
            }

    engine = create_async_engine(settings.database_url, **kwargs)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, session_factory
