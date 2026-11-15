package plotina.gateway.http;

import plotina.gateway.backend.RoomSnapshot;
import plotina.gateway.session.SessionInfo;

public record JoinRoomResponse(
    RoomSnapshot state,
    SessionInfo session) {
}
