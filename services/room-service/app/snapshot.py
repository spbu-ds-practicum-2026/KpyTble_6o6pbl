from datetime import datetime

from app.enums import RoomStatus
from app.errors import ConflictError
from app.models import Room
from app.schemas import ParticipantOut, PlaybackState, RoomState, VideoOut
from app.timeutils import ensure_utc, utcnow


def current_position(room: Room, now: datetime | None = None) -> float:
    if room.current_video_id is None:
        return 0.0

    if not room.is_playing:
        return max(0.0, room.position_seconds)

    now = ensure_utc(now or utcnow())
    updated_at = ensure_utc(room.position_updated_at)
    elapsed = max(0.0, (now - updated_at).total_seconds())
    return max(0.0, room.position_seconds + elapsed)


def build_room_state(room: Room, now: datetime | None = None) -> RoomState:
    now = ensure_utc(now or utcnow())

    all_videos = sorted(room.videos, key=lambda video: video.order_index)

    active_participants = sorted(
        (p for p in room.participants if p.is_active),
        key=lambda p: (ensure_utc(p.joined_at), str(p.id)),
    )

    return RoomState(
        status=room.status,
        control_mode=room.control_mode,
        state_version=room.state_version,
        current_video_id=room.current_video_id,
        playback=PlaybackState(
            video_id=room.current_video_id,
            position_seconds=round(current_position(room, now), 3),
            is_playing=room.is_playing and room.current_video_id is not None,
        ),
        queue=[
            VideoOut(id=video.id, url=video.url, position=position)
            for position, video in enumerate(all_videos)
        ],
        participants=[
            ParticipantOut(
                display_name=p.display_name, role=p.role, connected=p.connected
            )
            for p in active_participants
        ],
    )


def ensure_room_active(room: Room) -> None:
    if room.status != RoomStatus.ACTIVE:
        raise ConflictError("Комната завершена", code="room_closed")
