import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Imported for side effects: registers tables in Base.metadata.
from app import models  # noqa: F401
from app.api.internal import router as internal_router
from app.api.rooms import router as rooms_router
from app.config import Settings
from app.database import Base, create_engine_and_session_factory
from app.errors import DomainError
from app.integrations.events import EventPublisher, build_event_publisher
from app.runtime import RoomLockRegistry, Runtime
from app.services.handover import HandoverManager

logging.basicConfig(level=logging.INFO)


def create_app(
    settings: Settings | None = None, events: EventPublisher | None = None
) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine, session_factory = create_engine_and_session_factory(settings)

        if settings.auto_create_tables:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        publisher = events or build_event_publisher(settings)
        locks = RoomLockRegistry()
        handover = HandoverManager(session_factory, locks, publisher, settings)

        app.state.runtime = Runtime(
            settings=settings,
            session_factory=session_factory,
            events=publisher,
            locks=locks,
            handover=handover,
        )

        try:
            yield
        finally:
            await handover.shutdown()
            await publisher.aclose()
            await engine.dispose()

    app = FastAPI(
        title="Plotina Room Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_payload",
                    "message": "Некорректные параметры запроса",
                }
            },
        )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(rooms_router)
    app.include_router(internal_router)

    return app


app = create_app()
