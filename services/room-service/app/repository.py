import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Participant, Room


async def load_room(session: AsyncSession, room_id: uuid.UUID) -> Room | None:
    stmt = (
        select(Room)
        .options(selectinload(Room.participants), selectinload(Room.videos))
        .where(Room.id == room_id)
    )
    result = await session.execute(stmt.execution_options(populate_existing=True))
    return result.scalar_one_or_none()


async def load_room_by_invite_code(
    session: AsyncSession, invite_code: str
) -> Room | None:
    stmt = (
        select(Room)
        .options(selectinload(Room.participants), selectinload(Room.videos))
        .where(Room.invite_code == invite_code)
    )
    result = await session.execute(stmt.execution_options(populate_existing=True))
    return result.scalar_one_or_none()


async def load_participant_by_token_hash(
    session: AsyncSession, token_hash: str
) -> Participant | None:
    return await session.scalar(
        select(Participant).where(Participant.session_token_hash == token_hash)
    )


def find_participant(room: Room, participant_id: uuid.UUID) -> Participant | None:
    for participant in room.participants:
        if participant.id == participant_id:
            return participant
    return None
