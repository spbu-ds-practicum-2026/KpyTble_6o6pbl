import hashlib
import json
import uuid
from datetime import datetime

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import CommandType, RoomStatus
from app.errors import ConflictError, ForbiddenError, InvalidRequestError, NotFoundError
from app.models import CommandRecord, Participant, Room, Video
from app.permissions import ensure_can_execute
from app.repository import find_participant, load_room
from app.runtime import Runtime
from app.schemas import (
    AddVideoPayload,
    CommandRequest,
    CommandResponse,
    EmptyPayload,
    MoveVideoPayload,
    RemoveVideoPayload,
    RoomState,
    SeekPayload,
    SetControlModePayload,
)
from app.snapshot import build_room_state, current_position, ensure_room_active
from app.timeutils import utcnow
from app.urls import parse_rutube_url

_PAYLOAD_MODELS: dict[CommandType, type[BaseModel]] = {
    CommandType.PLAY: EmptyPayload,
    CommandType.PAUSE: EmptyPayload,
    CommandType.NEXT: EmptyPayload,
    CommandType.SEEK: SeekPayload,
    CommandType.ADD_VIDEO: AddVideoPayload,
    CommandType.REMOVE_VIDEO: RemoveVideoPayload,
    CommandType.MOVE_VIDEO: MoveVideoPayload,
    CommandType.SET_CONTROL_MODE: SetControlModePayload,
    CommandType.CLOSE_ROOM: EmptyPayload,
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


def _sorted_queue(room: Room) -> list[Video]:
    return sorted(room.videos, key=lambda video: (video.order_index, str(video.id)))


def _find_video(room: Room, video_id: uuid.UUID) -> Video | None:
    for video in room.videos:
        if video.id == video_id:
            return video
    return None


async def _apply_command(
    session: AsyncSession,
    room: Room,
    participant: Participant,
    command_type: CommandType,
    payload: BaseModel,
    now: datetime,
) -> None:
    if command_type == CommandType.PLAY:
        if room.current_video_id is None:
            raise ConflictError(
                "В комнате нет выбранного видео", code="no_current_video"
            )
        if not room.is_playing:
            room.is_playing = True
            room.position_updated_at = now

    elif command_type == CommandType.PAUSE:
        if room.is_playing:
            room.position_seconds = current_position(room, now)
            room.position_updated_at = now
            room.is_playing = False

    elif command_type == CommandType.SEEK:
        if room.current_video_id is None:
            raise ConflictError(
                "В комнате нет выбранного видео", code="no_current_video"
            )
        room.position_seconds = payload.position_seconds  # type: ignore[attr-defined]
        room.position_updated_at = now

    elif command_type == CommandType.NEXT:
        queue = _sorted_queue(room)
        current_index = next(
            (
                index
                for index, video in enumerate(queue)
                if video.id == room.current_video_id
            ),
            None,
        )
        next_video = (
            queue[current_index + 1]
            if current_index is not None and current_index + 1 < len(queue)
            else None
        )
        if next_video is not None:
            room.current_video_id = next_video.id
            room.position_seconds = 0.0
            room.position_updated_at = now
        else:
            room.current_video_id = None
            room.position_seconds = 0.0
            room.position_updated_at = now
            room.is_playing = False

    elif command_type == CommandType.ADD_VIDEO:
        video_info = parse_rutube_url(payload.url)  # type: ignore[attr-defined]
        queue = _sorted_queue(room)
        video = Video(
            id=uuid.uuid4(),
            room_id=room.id,
            url=video_info.url,
            title=payload.title,  # type: ignore[attr-defined]
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

    elif command_type == CommandType.REMOVE_VIDEO:
        video = _find_video(room, payload.video_id)  # type: ignore[attr-defined]
        if video is None:
            raise NotFoundError("Видео не найдено в очереди", code="video_not_found")

        queue = _sorted_queue(room)
        index = queue.index(video)
        next_video = queue[index + 1] if index + 1 < len(queue) else None
        was_current = room.current_video_id == video.id

        room.videos.remove(video)
        await session.delete(video)

        for order_index, remaining in enumerate(_sorted_queue(room)):
            remaining.order_index = order_index

        if was_current:
            room.current_video_id = next_video.id if next_video is not None else None
            room.position_seconds = 0.0
            room.is_playing = False
            room.position_updated_at = now

    elif command_type == CommandType.MOVE_VIDEO:
        video = _find_video(room, payload.video_id)  # type: ignore[attr-defined]
        if video is None:
            raise NotFoundError("Видео не найдено в очереди", code="video_not_found")

        queue = _sorted_queue(room)
        position = payload.position  # type: ignore[attr-defined]
        if position >= len(queue):
            raise InvalidRequestError(
                "Позиция за пределами очереди", code="invalid_position"
            )

        queue.remove(video)
        queue.insert(position, video)
        for order_index, item in enumerate(queue):
            item.order_index = order_index

    elif command_type == CommandType.SET_CONTROL_MODE:
        room.control_mode = payload.mode  # type: ignore[attr-defined]

    elif command_type == CommandType.CLOSE_ROOM:
        if room.status == RoomStatus.ACTIVE:
            if room.is_playing:
                room.position_seconds = current_position(room, now)
            room.is_playing = False
            room.position_updated_at = now
            room.status = RoomStatus.CLOSED
            room.closed_at = now

    else:  # pragma: no cover - enum is exhaustive
        raise InvalidRequestError("Неизвестная команда", code="unknown_command")


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
            raise NotFoundError("Комната не найдена", code="room_not_found")

        participant = find_participant(room, participant_id)
        if participant is None or not participant.is_active:
            raise ForbiddenError("Участник не найден в комнате", code="not_a_member")

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
                    "commandId уже использован с другими параметрами",
                    code="command_id_conflict",
                )
            return CommandResponse(
                command_id=request.command_id,
                duplicate=True,
                state=RoomState.model_validate(existing.response_json),
            )

        ensure_room_active(room)
        ensure_can_execute(room, participant, request.type)

        now = utcnow()
        await _apply_command(session, room, participant, request.type, payload, now)
        room.state_version += 1

        snapshot = build_room_state(room, now).model_dump(mode="json")
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
                "commandId уже обработан", code="command_id_conflict"
            ) from exc

        return CommandResponse(
            command_id=request.command_id,
            duplicate=False,
            state=RoomState.model_validate(snapshot),
        )
