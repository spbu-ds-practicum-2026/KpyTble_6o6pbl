import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import (
    get_room_participant,
    get_runtime,
    get_session,
)
from app.models import Participant
from app.runtime import Runtime
from app.schemas import (
    CommandRequest,
    CommandResponse,
    CreateRoomRequest,
    CreateRoomResponse,
    JoinRoomRequest,
    JoinRoomResponse,
    LeaveResponse,
    RoomState,
)
from app.services import commands, rooms

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.post("", response_model=CreateRoomResponse, status_code=201)
async def create_room(
    request: CreateRoomRequest,
    runtime: Runtime = Depends(get_runtime),
    session: AsyncSession = Depends(get_session),
) -> CreateRoomResponse:
    return await rooms.create_room(runtime, session, request)


@router.post("/join", response_model=JoinRoomResponse, status_code=201)
async def join_room(
    request: JoinRoomRequest,
    runtime: Runtime = Depends(get_runtime),
    session: AsyncSession = Depends(get_session),
) -> JoinRoomResponse:
    return await rooms.join_room(runtime, session, request)


@router.get("/{room_id}", response_model=RoomState)
async def get_room(
    room_id: uuid.UUID,
    participant: Participant = Depends(get_room_participant),
    session: AsyncSession = Depends(get_session),
) -> RoomState:
    return await rooms.get_room_state(session, room_id, participant.id)


@router.post("/{room_id}/commands", response_model=CommandResponse)
async def execute_command(
    room_id: uuid.UUID,
    request: CommandRequest,
    participant: Participant = Depends(get_room_participant),
    runtime: Runtime = Depends(get_runtime),
    session: AsyncSession = Depends(get_session),
) -> CommandResponse:
    return await commands.execute_command(
        runtime, session, room_id, participant.id, request
    )


@router.post("/{room_id}/connect", response_model=RoomState)
async def connect(
    room_id: uuid.UUID,
    participant: Participant = Depends(get_room_participant),
    runtime: Runtime = Depends(get_runtime),
    session: AsyncSession = Depends(get_session),
) -> RoomState:
    return await rooms.connect_participant(runtime, session, room_id, participant.id)


@router.post("/{room_id}/disconnect", response_model=RoomState)
async def disconnect(
    room_id: uuid.UUID,
    participant: Participant = Depends(get_room_participant),
    runtime: Runtime = Depends(get_runtime),
    session: AsyncSession = Depends(get_session),
) -> RoomState:
    return await rooms.disconnect_participant(runtime, session, room_id, participant.id)


@router.post("/{room_id}/leave", response_model=LeaveResponse)
async def leave(
    room_id: uuid.UUID,
    participant: Participant = Depends(get_room_participant),
    runtime: Runtime = Depends(get_runtime),
    session: AsyncSession = Depends(get_session),
) -> LeaveResponse:
    return await rooms.leave_room(runtime, session, room_id, participant.id)
