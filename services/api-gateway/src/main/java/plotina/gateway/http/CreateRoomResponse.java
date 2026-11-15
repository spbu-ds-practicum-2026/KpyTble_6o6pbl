package plotina.gateway.http;

import plotina.gateway.session.SessionInfo;

public record CreateRoomResponse(
    String roomId,
    long version,
    boolean paused,
    double positionSeconds,
    SessionInfo session) {
}
