import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.integrations.events import EventPublisher
from app.services.handover import HandoverManager


class RoomLockRegistry:
    """One asyncio lock per room serializes commands in this process."""

    def __init__(self) -> None:
        self._locks: dict[uuid.UUID, asyncio.Lock] = {}

    def for_room(self, room_id: uuid.UUID) -> asyncio.Lock:
        lock = self._locks.get(room_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[room_id] = lock
        return lock


@dataclass
class Runtime:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    events: EventPublisher
    locks: RoomLockRegistry
    handover: HandoverManager
