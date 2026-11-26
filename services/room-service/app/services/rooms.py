import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ParticipantRole, RoomStatus
from app.errors import ForbiddenError, InvalidRequestError, UnauthorizedError
from app.integrations.events import publish_state_change
from app.models import Participant, Room
from app.repository import (
    find_participant,
    load_participant_by_token_hash,
    load_room,
    load_room_by_invite_code,
)
from app.runtime import Runtime
from app.schemas import (
    CreateRoomRequest,
    CreateRoomResponse,
    JoinRoomRequest,
    JoinRoomResponse,
    LeaveResponse,
    MembershipResponse,
    ParticipantOut,
    RoomState,
)
from app.security import generate_session_token, hash_session_token
from app.services.handover import transfer_host_now
from app.snapshot import build_room_state, current_position, ensure_room_active
from app.timeutils import utcnow
from app.urls import parse_invite_code


async def _unique_invite_code(session: AsyncSession) -> str:
    for _ in range(20):
        code = secrets.token_urlsafe(9)
        exists = await session.scalar(select(Room.id).where(Room.invite_code == code))
        if exists is None:
            return code
    raise RuntimeError("Не удалось сгенерировать уникальный код приглашения")


def _build_state(room: Room) -> RoomState:
    return build_room_state(room, utcnow())


def _invite_link(runtime: Runtime, invite_code: str) -> str:
    return f"{runtime.settings.invite_base_url.rstrip('/')}/{invite_code}"


async def create_room(
    runtime: Runtime, session: AsyncSession, request: CreateRoomRequest
) -> CreateRoomResponse:
    now = utcnow()
    token = generate_session_token()

    room = Room(
        invite_code=await _unique_invite_code(session),
        status=RoomStatus.ACTIVE,
        control_mode=request.control_mode,
        state_version=1,
        position_seconds=0.0,
        is_playing=False,
        position_updated_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(room)
    await session.flush()

    participant = Participant(
        room_id=room.id,
        display_name=request.display_name,
        role=ParticipantRole.HOST,
        session_token_hash=hash_session_token(token),
        connected=True,
        connection_generation=0,
        joined_at=now,
        created_at=now,
    )
    session.add(participant)
    await session.commit()

    room = await load_room(session, room.id)
    assert room is not None
    state = _build_state(room)
    created = find_participant(room, participant.id)
    assert created is not None
    await publish_state_change(runtime.events, room.id, state, "created")

    return CreateRoomResponse(
        room_id=room.id,
        invite_code=room.invite_code,
        invite_link=_invite_link(runtime, room.invite_code),
        token=token,
        participant=ParticipantOut(
            display_name=created.display_name,
            role=created.role,
            connected=created.connected,
        ),
        state=state,
    )


async def join_room(
    runtime: Runtime, session: AsyncSession, request: JoinRoomRequest
) -> JoinRoomResponse:
    invite_code = parse_invite_code(request.invite_code)
    existing = await load_room_by_invite_code(session, invite_code)
    if existing is None:
        raise InvalidRequestError("Комната не найдена", code="invalid_payload")

    async with runtime.locks.for_room(existing.id):
        room = await load_room(session, existing.id)
        if room is None:
            raise ForbiddenError("Токен принадлежит другой комнате", code="wrong_room")
        ensure_room_active(room)

        now = utcnow()
        token = generate_session_token()
        participant = Participant(
            room_id=room.id,
            display_name=request.display_name,
            role=ParticipantRole.MEMBER,
            session_token_hash=hash_session_token(token),
            connected=True,
            connection_generation=0,
            joined_at=now,
            created_at=now,
        )
        session.add(participant)
        room.state_version += 1
        await session.commit()

        room = await load_room(session, room.id)
        assert room is not None
        state = _build_state(room)
        room_id = room.id
        invite_code = room.invite_code
        joined = find_participant(room, participant.id)
        assert joined is not None

    await publish_state_change(runtime.events, room_id, state, "participant_joined")

    return JoinRoomResponse(
        room_id=room_id,
        invite_code=invite_code,
        invite_link=_invite_link(runtime, invite_code),
        token=token,
        participant=ParticipantOut(
            display_name=joined.display_name,
            role=joined.role,
            connected=joined.connected,
        ),
        state=state,
    )


async def get_room_state(
    session: AsyncSession, room_id: uuid.UUID, participant_id: uuid.UUID
) -> RoomState:
    room = await load_room(session, room_id)
    if room is None:
        raise ForbiddenError("Токен принадлежит другой комнате", code="wrong_room")

    participant = find_participant(room, participant_id)
    if participant is None or not participant.is_active:
        raise UnauthorizedError("Токен сессии недействителен")

    return _build_state(room)


async def connect_participant(
    runtime: Runtime,
    session: AsyncSession,
    room_id: uuid.UUID,
    participant_id: uuid.UUID,
) -> RoomState:
    changed = False

    async with runtime.locks.for_room(room_id):
        room = await load_room(session, room_id)
        if room is None:
            raise ForbiddenError("Токен принадлежит другой комнате", code="wrong_room")

        participant = find_participant(room, participant_id)
        if participant is None or not participant.is_active:
            raise UnauthorizedError("Токен сессии недействителен")

        if not participant.connected:
            participant.connected = True
            participant.disconnected_at = None
            room.state_version += 1
            changed = True
            await session.commit()

        # A reconnect within the grace period cancels the pending handover.
        runtime.handover.cancel(participant.id)

        room = await load_room(session, room_id)
        assert room is not None
        state = _build_state(room)

    if changed:
        await publish_state_change(
            runtime.events, room_id, state, "participant_connected"
        )
    return state


async def disconnect_participant(
    runtime: Runtime,
    session: AsyncSession,
    room_id: uuid.UUID,
    participant_id: uuid.UUID,
) -> RoomState:
    generation: int | None = None
    schedule_handover = False
    changed = False
    state: RoomState

    async with runtime.locks.for_room(room_id):
        room = await load_room(session, room_id)
        if room is None:
            raise ForbiddenError("Токен принадлежит другой комнате", code="wrong_room")

        participant = find_participant(room, participant_id)
        if participant is None or not participant.is_active:
            raise UnauthorizedError("Токен сессии недействителен")

        if participant.connected:
            participant.connected = False
            participant.disconnected_at = utcnow()
            participant.connection_generation += 1
            room.state_version += 1
            generation = participant.connection_generation
            schedule_handover = participant.role == ParticipantRole.HOST
            changed = True
            await session.commit()

        room = await load_room(session, room_id)
        assert room is not None
        state = _build_state(room)

    if schedule_handover and generation is not None:
        runtime.handover.schedule(room_id, participant_id, generation)

    if changed:
        await publish_state_change(
            runtime.events, room_id, state, "participant_disconnected"
        )
    return state


async def leave_room(
    runtime: Runtime,
    session: AsyncSession,
    room_id: uuid.UUID,
    participant_id: uuid.UUID,
) -> LeaveResponse:
    async with runtime.locks.for_room(room_id):
        room = await load_room(session, room_id)
        if room is None:
            raise ForbiddenError("Токен принадлежит другой комнате", code="wrong_room")

        participant = find_participant(room, participant_id)
        if participant is None:
            raise UnauthorizedError("Токен сессии недействителен")

        if not participant.is_active:
            raise UnauthorizedError("Токен сессии недействителен")

        now = utcnow()
        participant.left_at = now
        participant.connected = False
        participant.disconnected_at = now
        participant.connection_generation += 1

        transfer_host_now(room, participant, now)

        remaining = [p for p in room.participants if p.is_active]
        room_closed = not remaining
        if room_closed and room.status == RoomStatus.ACTIVE:
            if room.is_playing:
                room.position_seconds = current_position(room, now)
            room.is_playing = False
            room.position_updated_at = now
            room.status = RoomStatus.CLOSED
            room.closed_at = now

        room.state_version += 1
        await session.commit()

        runtime.handover.cancel(participant.id)

        room = await load_room(session, room_id)
        assert room is not None
        state = _build_state(room)

    reason = "room_closed" if room_closed else "participant_left"
    await publish_state_change(runtime.events, room_id, state, reason)

    return LeaveResponse(left=True)


async def check_membership(
    session: AsyncSession, room_id: uuid.UUID, token: str | None
) -> MembershipResponse:
    if not token:
        return MembershipResponse(is_member=False, room_id=room_id)

    participant = await load_participant_by_token_hash(
        session, hash_session_token(token)
    )
    if (
        participant is None
        or participant.room_id != room_id
        or not participant.is_active
    ):
        return MembershipResponse(is_member=False, room_id=room_id)

    return MembershipResponse(
        room_id=room_id,
        participant_id=participant.id,
        display_name=participant.display_name,
        role=participant.role,
        connected=participant.connected,
    )
