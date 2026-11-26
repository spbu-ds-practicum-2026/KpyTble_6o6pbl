import hashlib
import json
import uuid
from datetime import datetime
from typing import cast

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import CommandType
from app.errors import (
    ConflictError,
    ForbiddenError,
    InvalidRequestError,
    UnauthorizedError,
)
from app.integrations.events import publish_state_change
from app.models import CommandRecord, Participant, Room, Video
from app.permissions import ensure_can_execute
from app.repository import find_participant, load_room
from app.runtime import Runtime
from app.schemas import (
    AddVideoPayload,
    ChangeQueuePayload,
    CommandRequest,
    CommandResponse,
    EmptyPayload,
    RemoveVideoPayload,
    RoomState,
    SeekPayload,
    SetControlModePayload,
)
from app.snapshot import build_room_state, current_position, ensure_room_active
from app.timeutils import utcnow
from app.urls import parse_rutube_url

_PAYLOAD_MODELS: dict[CommandType, type[BaseModel]] = {
    CommandType.PLAYPAUSE: EmptyPayload,
    CommandType.SEEK: SeekPayload,
    CommandType.NEXT: EmptyPayload,
    CommandType.ADD_VIDEO: AddVideoPayload,
    CommandType.REMOVE_VIDEO: RemoveVideoPayload,
    CommandType.CHANGE_QUEUE: ChangeQueuePayload,
    CommandType.SET_CONTROL_MODE: SetControlModePayload,
}


def parse_payload(command_type: CommandType, payload: dict) -> BaseModel:
    model = _PAYLOAD_MODELS[command_type]
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise InvalidRequestError(
            f"Некорректные параметры команды: {exc}",
            code="invalid_payload",
        ) from exc


def payload_hash(command_type: CommandType, payload: BaseModel) -> str:
    canonical = {
        "type": command_type.value,
        "payload": payload.model_dump(mode="json"),
    }
    raw = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sorted_videos(room: Room) -> list[Video]:
    return sorted(room.videos, key=lambda video: (video.order_index, str(video.id)))


def _find_video(room: Room, video_id: uuid.UUID) -> Video | None:
    return next((video for video in room.videos if video.id == video_id), None)


def _renumber(room: Room, ordered: list[Video]) -> None:
    for order_index, video in enumerate(ordered):
        video.order_index = order_index


def _require_current_video(room: Room) -> None:
    if room.current_video_id is None:
        raise ConflictError("В комнате нет выбранного видео", code="no_current_video")


async def _apply_command(
    session: AsyncSession,
    room: Room,
    participant: Participant,
    command_type: CommandType,
    payload: BaseModel,
    now: datetime,
) -> None:
    if command_type == CommandType.PLAYPAUSE:
        _require_current_video(room)
        if room.is_playing:
            room.position_seconds = current_position(room, now)
            room.is_playing = False
        else:
            room.is_playing = True
        room.position_updated_at = now

    elif command_type == CommandType.SEEK:
        _require_current_video(room)
        room.position_seconds = cast(SeekPayload, payload).position_seconds
        room.position_updated_at = now

    elif command_type == CommandType.NEXT:
        _require_current_video(room)
        queue = _sorted_videos(room)
        current_video = next(
            (video for video in queue if video.id == room.current_video_id), None
        )
        if current_video is None:
            raise InvalidRequestError(
                "Текущее видео не найдено в комнате", code="invalid_payload"
            )

        current_index = queue.index(current_video)
        next_video = (
            queue[current_index + 1] if current_index + 1 < len(queue) else None
        )

        room.current_video_id = next_video.id if next_video is not None else None
        room.position_seconds = 0.0
        room.position_updated_at = now
        if next_video is None:
            room.is_playing = False

    elif command_type == CommandType.ADD_VIDEO:
        video_info = parse_rutube_url(cast(AddVideoPayload, payload).url)
        queue = _sorted_videos(room)
        video = Video(
            id=uuid.uuid4(),
            room_id=room.id,
            url=video_info.url,
            order_index=len(queue),
            added_by_id=participant.id,
            created_at=now,
        )
        session.add(video)
        room.videos.append(video)

        if room.current_video_id is None:
            room.current_video_id = video.id
            room.position_seconds = 0.0
            room.is_playing = False
            room.position_updated_at = now
            _renumber(room, [video])
        else:
            _renumber(room, queue + [video])

    elif command_type == CommandType.REMOVE_VIDEO:
        video_id = cast(RemoveVideoPayload, payload).video_id
        video = _find_video(room, video_id)
        if video is None:
            raise InvalidRequestError(
                "Видео не найдено в комнате", code="invalid_payload"
            )

        was_current = room.current_video_id == video.id
        room.videos.remove(video)
        await session.delete(video)

        remaining = _sorted_videos(room)
        _renumber(room, remaining)

        if was_current:
            if remaining:
                room.current_video_id = remaining[0].id
            else:
                room.current_video_id = None
            room.position_seconds = 0.0
            room.position_updated_at = now
            room.is_playing = False

    elif command_type == CommandType.CHANGE_QUEUE:
        incoming = cast(ChangeQueuePayload, payload).video_ids
        if len(set(incoming)) != len(incoming):
            raise InvalidRequestError(
                "video_ids содержат дубли", code="invalid_payload"
            )

        queue = _sorted_videos(room)
        if set(incoming) != {video.id for video in queue}:
            raise InvalidRequestError(
                "video_ids должны содержать все видео текущей очереди",
                code="invalid_payload",
            )

        by_id = {video.id: video for video in queue}
        _renumber(room, [by_id[video_id] for video_id in incoming])

    elif command_type == CommandType.SET_CONTROL_MODE:
        room.control_mode = cast(SetControlModePayload, payload).mode

    else:  # pragma: no cover - enum is exhaustive
        raise InvalidRequestError("Неизвестная команда", code="invalid_payload")


def _same_command(
    record: CommandRecord,
    room_id: uuid.UUID,
    participant_id: uuid.UUID,
    command_type: CommandType,
    digest: str,
) -> bool:
    return (
        record.room_id == room_id
        and record.participant_id == participant_id
        and record.command_type == command_type.value
        and record.payload_hash == digest
    )


async def execute_command(
    runtime: Runtime,
    session: AsyncSession,
    room_id: uuid.UUID,
    participant_id: uuid.UUID,
    request: CommandRequest,
) -> CommandResponse:
    payload = parse_payload(request.type, request.payload)
    digest = payload_hash(request.type, payload)

    async with runtime.locks.for_room(room_id):
        room = await load_room(session, room_id)
        if room is None:
            raise ForbiddenError("Токен принадлежит другой комнате", code="wrong_room")

        participant = find_participant(room, participant_id)
        if participant is None:
            raise UnauthorizedError("Токен сессии недействителен")

        # Idempotency is checked before the room status so that a repeated
        # already-executed command can be acknowledged even after room closure.
        existing = await session.scalar(
            select(CommandRecord).where(CommandRecord.command_id == request.command_id)
        )
        if existing is not None:
            if not _same_command(
                existing, room_id, participant.id, request.type, digest
            ):
                raise ConflictError(
                    "command_id уже использован с другими параметрами",
                    code="command_id_conflict",
                )
            return CommandResponse(
                command_id=request.command_id,
                duplicate=True,
                state=RoomState.model_validate(existing.response_json),
            )

        ensure_room_active(room)
        if not participant.is_active:
            raise UnauthorizedError("Токен сессии недействителен")
        ensure_can_execute(room, participant, request.type)

        now = utcnow()
        await _apply_command(session, room, participant, request.type, payload, now)
        room.state_version += 1

        state = build_room_state(room, now)
        snapshot = state.model_dump(mode="json")
        session.add(
            CommandRecord(
                command_id=request.command_id,
                room_id=room.id,
                participant_id=participant.id,
                command_type=request.type.value,
                payload_hash=digest,
                state_version=room.state_version,
                response_json=snapshot,
                created_at=now,
            )
        )

        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            existing = await session.scalar(
                select(CommandRecord).where(
                    CommandRecord.command_id == request.command_id
                )
            )
            if existing is not None and _same_command(
                existing, room_id, participant_id, request.type, digest
            ):
                return CommandResponse(
                    command_id=request.command_id,
                    duplicate=True,
                    state=RoomState.model_validate(existing.response_json),
                )
            raise ConflictError(
                "command_id уже обработан", code="command_id_conflict"
            ) from exc

        await publish_state_change(runtime.events, room.id, state, request.type.value)

        return CommandResponse(
            command_id=request.command_id,
            duplicate=False,
            state=state,
        )
