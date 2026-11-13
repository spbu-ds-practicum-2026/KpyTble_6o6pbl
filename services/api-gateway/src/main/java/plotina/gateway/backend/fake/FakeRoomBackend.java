package plotina.gateway.backend.fake;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.stereotype.Service;

import plotina.gateway.backend.RoomBackend;
import plotina.gateway.backend.RoomSnapshot;

@Service
public class FakeRoomBackend implements RoomBackend {

  private final Map<String, RoomSnapshot> rooms = new ConcurrentHashMap<>();

  @Override
  public RoomSnapshot getSnapshot(String roomId) {
    return new RoomSnapshot(
        roomId,
        1,
        true,
        0.0);
  }

  @Override
  public RoomSnapshot createRoom() {
    String roomId = UUID.randomUUID().toString();

    RoomSnapshot snapshot = new RoomSnapshot(
        roomId,
        1,
        true,
        0.0);

    rooms.put(roomId, snapshot);

    return snapshot;
  }

}
