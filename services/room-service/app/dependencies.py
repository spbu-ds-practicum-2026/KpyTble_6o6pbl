import uuid
from collections.abc import AsyncIterator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ForbiddenError, UnauthorizedError
from app.models import Participant
from app.repository import load_participant_by_token_hash
from app.runtime import Runtime
from app.security import extract_session_token, hash_session_token

# Documents the Authorization header in OpenAPI/Swagger and enables the
# "Authorize" button. The custom X-Session-Token header still works as fallback.
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Токен из POST /rooms или POST /rooms/join",
)


def get_runtime(request: Request) -> Runtime:
    return request.app.state.runtime


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    runtime: Runtime = request.app.state.runtime
    async with runtime.session_factory() as session:
        yield session


async def get_current_participant(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> Participant:
    token = (
        credentials.credentials
        if credentials is not None
        else extract_session_token(request)
    )
    if not token:
        raise UnauthorizedError("Токен сессии не передан", code="missing_token")

    participant = await load_participant_by_token_hash(
        session, hash_session_token(token)
    )
    if participant is None or not participant.is_active:
        raise UnauthorizedError("Недействительный токен сессии", code="invalid_token")

    return participant


async def get_room_participant(
    room_id: uuid.UUID,
    participant: Participant = Depends(get_current_participant),
) -> Participant:
    if participant.room_id != room_id:
        raise ForbiddenError("Токен не принадлежит этой комнате", code="wrong_room")
    return participant
