from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.enums import CommandType, ControlMode, ParticipantRole, RoomStatus


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    role: ParticipantRole
    connected: bool
    joined_at: datetime


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    title: str | None
    order_index: int
    added_by_id: UUID | None
    created_at: datetime


class PlaybackState(BaseModel):
    video_id: UUID | None
    position_seconds: float
    is_playing: bool
    updated_at: datetime
    server_time: datetime


class RoomState(BaseModel):
    room_id: UUID
    invite_code: str
    status: RoomStatus
    control_mode: ControlMode
    state_version: int
    current_video_id: UUID | None
    playback: PlaybackState
    queue: list[VideoOut]
    participants: list[ParticipantOut]
    created_at: datetime


class CreateRoomRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    control_mode: ControlMode = ControlMode.HOST_ONLY


class CreateRoomResponse(BaseModel):
    room_id: UUID
    invite_code: str
    invite_link: str
    token: str
    participant: ParticipantOut
    state: RoomState


class JoinRoomRequest(BaseModel):
    invite_code: str = Field(min_length=1, max_length=32)
    display_name: str = Field(min_length=1, max_length=100)


class JoinRoomResponse(BaseModel):
    token: str
    participant: ParticipantOut
    state: RoomState


class CommandRequest(BaseModel):
    command_id: str = Field(min_length=1, max_length=128)
    type: CommandType
    payload: dict[str, Any] = Field(default_factory=dict)


class CommandResponse(BaseModel):
    command_id: str
    duplicate: bool
    state: RoomState


class LeaveResponse(BaseModel):
    room_id: UUID
    left: bool
    new_host_id: UUID | None
    state: RoomState


class MembershipResponse(BaseModel):
    is_member: bool
    room_id: UUID
    participant_id: UUID | None = None
    role: ParticipantRole | None = None


# Command payloads. Unknown fields are rejected to keep command hashes stable.


class EmptyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SeekPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position_seconds: float = Field(ge=0)


class AddVideoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2048)
    title: str | None = Field(default=None, max_length=500)


class RemoveVideoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: UUID


class MoveVideoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: UUID
    position: int = Field(ge=0)


class SetControlModePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: ControlMode
