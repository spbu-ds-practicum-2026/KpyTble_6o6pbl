package plotina.gateway.room;

import plotina.gateway.session.backend.SessionInfo;

public record CreateRoomResponse(
    String roomId,
    long version,
    boolean paused,
    double positionSeconds,
    SessionInfo session) {
}
