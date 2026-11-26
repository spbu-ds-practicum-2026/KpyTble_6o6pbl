from math import isfinite
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import CommandType, ControlMode, ParticipantRole, RoomStatus


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NonBlankModel(StrictModel):
    @field_validator("display_name", check_fields=False)
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("display_name не может быть пустым")
        return value


class ParticipantOut(BaseModel):
    display_name: str
    role: ParticipantRole
    connected: bool


class VideoOut(BaseModel):
    id: UUID
    url: str
    position: int


class PlaybackState(BaseModel):
    video_id: UUID | None
    position_seconds: float
    is_playing: bool


class RoomState(BaseModel):
    status: RoomStatus
    control_mode: ControlMode
    state_version: int
    current_video_id: UUID | None
    playback: PlaybackState
    queue: list[VideoOut]
    participants: list[ParticipantOut]


class CreateRoomRequest(NonBlankModel):
    display_name: str = Field(min_length=1, max_length=100)
    control_mode: ControlMode


class CreateRoomResponse(BaseModel):
    room_id: UUID
    invite_code: str
    invite_link: str
    token: str
    participant: ParticipantOut
    state: RoomState


class JoinRoomRequest(NonBlankModel):
    invite_code: str = Field(max_length=2048)
    display_name: str = Field(min_length=1, max_length=100)


class JoinRoomResponse(BaseModel):
    room_id: UUID
    invite_code: str
    invite_link: str
    token: str
    participant: ParticipantOut
    state: RoomState


class CommandRequest(StrictModel):
    command_id: str = Field(min_length=1, max_length=128)
    type: CommandType
    payload: dict[str, Any]

    @field_validator("command_id")
    @classmethod
    def normalize_command_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("command_id не может быть пустым")
        return value


class CommandResponse(BaseModel):
    command_id: str
    duplicate: bool
    state: RoomState


class LeaveResponse(BaseModel):
    left: bool = True


class MembershipResponse(BaseModel):
    is_member: bool | None = None
    room_id: UUID
    participant_id: UUID | None = None
    display_name: str | None = None
    role: ParticipantRole | None = None
    connected: bool | None = None


class EmptyPayload(StrictModel):
    pass


class SeekPayload(StrictModel):
    position_seconds: float = Field(ge=0)

    @field_validator("position_seconds")
    @classmethod
    def finite_position(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("position_seconds должно быть конечным числом")
        return value


class AddVideoPayload(StrictModel):
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def non_blank_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("url не может быть пустым")
        return value


class RemoveVideoPayload(StrictModel):
    video_id: UUID


class ChangeQueuePayload(StrictModel):
    video_ids: list[UUID]


class SetControlModePayload(StrictModel):
    mode: ControlMode
