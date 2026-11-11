package plotina.gateway.backend;

public record RoomSnapshot(
    String roomId,
    long version,
    boolean paused,
    double positionSeconds) {
}
