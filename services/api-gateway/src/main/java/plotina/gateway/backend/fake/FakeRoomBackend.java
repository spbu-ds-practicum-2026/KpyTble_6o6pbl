package plotina.gateway.backend.fake;

import org.springframework.stereotype.Service;

import plotina.gateway.backend.RoomBackend;
import plotina.gateway.backend.RoomSnapshot;

@Service
public class FakeRoomBackend implements RoomBackend {

  @Override
  public RoomSnapshot getSnapshot(String roomId) {
    return new RoomSnapshot(
        roomId,
        1,
        true,
        0.0);
  }

}
