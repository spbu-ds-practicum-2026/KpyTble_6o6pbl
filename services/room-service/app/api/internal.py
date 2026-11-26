"""Internal API consumed by Chat Service.

This endpoint exposes Room Service as the source of truth for room membership.
It is not part of the public client API and is expected to be reachable only on
the internal network. When Chat Service appears, it calls this endpoint before
accepting a chat message.
"""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_session
from app.schemas import MembershipResponse
from app.security import extract_session_token
from app.services.rooms import check_membership

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get(
    "/rooms/{room_id}/membership",
    response_model=MembershipResponse,
    response_model_exclude_none=True,
)
async def membership(
    room_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> MembershipResponse:
    return await check_membership(session, room_id, extract_session_token(request))
