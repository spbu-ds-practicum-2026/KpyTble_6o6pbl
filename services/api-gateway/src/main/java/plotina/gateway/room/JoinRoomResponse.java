package plotina.gateway.room;

import plotina.gateway.room.backend.RoomSnapshot;
import plotina.gateway.session.backend.SessionInfo;

public record JoinRoomResponse(
    RoomSnapshot state,
    SessionInfo session) {
}
