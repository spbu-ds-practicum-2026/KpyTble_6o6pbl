import asyncio
import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.enums import ParticipantRole, RoomStatus
from app.integrations.events import EventPublisher
from app.models import Participant, Room
from app.repository import load_room
from app.snapshot import build_room_state
from app.timeutils import ensure_utc, utcnow

logger = logging.getLogger("room_service.handover")


def earliest_connected(
    room: Room, *, exclude_id: uuid.UUID | None = None
) -> Participant | None:
    candidates = [
        participant
        for participant in room.participants
        if participant.is_active
        and participant.connected
        and participant.id != exclude_id
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: (ensure_utc(p.joined_at), str(p.id)))


def transfer_host_now(
    room: Room, leaving: Participant, now: datetime | None = None
) -> uuid.UUID | None:
    """Immediate transfer for explicit leave. Caller bumps state_version."""
    if leaving.role != ParticipantRole.HOST:
        return None

    successor = earliest_connected(room, exclude_id=leaving.id)
    if successor is None:
        return None

    leaving.role = ParticipantRole.MEMBER
    successor.role = ParticipantRole.HOST
    return successor.id


class HandoverManager:
    """Tracks host disconnect grace periods.

    Timers and per-room locks are in memory, which matches the prototype
    constraint of a single Room Service instance.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        locks,
        events: EventPublisher,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._locks = locks
        self._events = events
        self._grace_seconds = settings.host_disconnect_grace_seconds
        self._tasks: dict[uuid.UUID, asyncio.Task] = {}

    def schedule(
        self,
        room_id: uuid.UUID,
        participant_id: uuid.UUID,
        connection_generation: int,
    ) -> None:
        self.cancel(participant_id)
        task = asyncio.create_task(
            self._run(room_id, participant_id, connection_generation)
        )
        self._tasks[participant_id] = task

    def cancel(self, participant_id: uuid.UUID) -> None:
        task = self._tasks.pop(participant_id, None)
        if task is not None and not task.done():
            task.cancel()

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(
        self,
        room_id: uuid.UUID,
        participant_id: uuid.UUID,
        connection_generation: int,
    ) -> None:
        try:
            await asyncio.sleep(self._grace_seconds)
            event = await self.process(room_id, participant_id, connection_generation)
            if event is not None:
                await self._events.publish(event)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception(
                "host handover failed for room=%s participant=%s",
                room_id,
                participant_id,
            )
        finally:
            current = self._tasks.get(participant_id)
            if current is asyncio.current_task():
                self._tasks.pop(participant_id, None)

    async def process(
        self,
        room_id: uuid.UUID,
        participant_id: uuid.UUID,
        connection_generation: int,
    ) -> dict | None:
        async with self._locks.for_room(room_id), self._session_factory() as session:
            room = await load_room(session, room_id)
            if room is None or room.status != RoomStatus.ACTIVE:
                return None

            current_host = next(
                (p for p in room.participants if p.id == participant_id), None
            )
            if current_host is None:
                return None

            # The grace period must belong to the current disconnect, and the
            # participant must still be disconnected and still be the host.
            if (
                current_host.connected
                or not current_host.is_active
                or current_host.role != ParticipantRole.HOST
                or current_host.connection_generation != connection_generation
            ):
                return None

            successor = earliest_connected(room, exclude_id=current_host.id)
            if successor is None:
                return None

            current_host.role = ParticipantRole.MEMBER
            successor.role = ParticipantRole.HOST
            room.state_version += 1

            snapshot = build_room_state(room, utcnow()).model_dump(mode="json")
            await session.commit()

            return {
                "type": "host_changed",
                "room_id": str(room_id),
                "participant_id": str(successor.id),
                "state_version": room.state_version,
                "state": snapshot,
            }
