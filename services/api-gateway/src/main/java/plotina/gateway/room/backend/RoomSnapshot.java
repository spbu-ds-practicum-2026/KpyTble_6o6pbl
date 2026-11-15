package plotina.gateway.room.backend;

import java.util.List;

public record RoomSnapshot(
    String roomId,
    long version,
    boolean paused,
    double positionSeconds,
    QueueItem currentVideo,
    List<QueueItem> queue) {

  public RoomSnapshot {
    queue = List.copyOf(queue);
  }

  public RoomSnapshot(
      String roomId,
      long version,
      boolean paused,
      double positionSeconds) {
    this(
        roomId,
        version,
        paused,
        positionSeconds,
        null,
        List.of());
  }
}
