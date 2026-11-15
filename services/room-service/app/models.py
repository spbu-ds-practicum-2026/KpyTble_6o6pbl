import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ControlMode, ParticipantRole, RoomStatus
from app.timeutils import utcnow


def enum_column(enum_cls: type[PyEnum], length: int = 32) -> SAEnum:
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda cls: [member.value for member in cls],
    )


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invite_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    status: Mapped[RoomStatus] = mapped_column(
        enum_column(RoomStatus), default=RoomStatus.ACTIVE
    )
    control_mode: Mapped[ControlMode] = mapped_column(
        enum_column(ControlMode), default=ControlMode.HOST_ONLY
    )

    state_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    current_video_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    position_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_playing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    participants: Mapped[list["Participant"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    videos: Mapped[list["Video"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Video.order_index",
    )


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[ParticipantRole] = mapped_column(
        enum_column(ParticipantRole), default=ParticipantRole.MEMBER, nullable=False
    )

    # Only a hash is stored. The raw token is returned to the client once.
    session_token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )

    connected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    connection_generation: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    disconnected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    room: Mapped[Room] = relationship(back_populates="participants")

    @property
    def is_active(self) -> bool:
        return self.left_at is None


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    added_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    room: Mapped[Room] = relationship(back_populates="videos")

    __table_args__ = (Index("ix_videos_room_order", "room_id", "order_index"),)


class CommandRecord(Base):
    __tablename__ = "command_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    command_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    command_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
