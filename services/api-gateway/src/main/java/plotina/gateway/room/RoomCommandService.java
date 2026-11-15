package plotina.gateway.room;

import org.springframework.stereotype.Service;
import plotina.gateway.room.backend.RoomBackend;
import plotina.gateway.room.backend.RoomSnapshot;

@Service
public class RoomCommandService {
  private final RoomBackend backend;

  public RoomCommandService(RoomBackend backend) {
    this.backend = backend;
  }

  public RoomSnapshot pause(String userId, String roomId, String token, String commandId) {
    return backend.pause(roomId, token, commandId);
  }

  public RoomSnapshot play(String userId, String roomId, String token, String commandId) {
    return backend.play(roomId, token, commandId);
  }

  public RoomSnapshot seek(String userId, String roomId, String token, String commandId, double position) {
    return backend.seek(roomId, token, commandId, position);
  }

  public RoomSnapshot next(String userId, String roomId, String token, String commandId) {
    return backend.next(roomId, token, commandId);
  }

  public RoomSnapshot addVideo(String userId, String roomId, String token, String commandId, String url) {
    return backend.addVideo(roomId, token, commandId, url);
  }

  public RoomSnapshot removeVideo(String userId, String roomId, String token, String commandId, String itemId) {
    return backend.removeVideo(roomId, token, commandId, itemId);
  }

  public RoomSnapshot moveVideo(String userId, String roomId, String token, String commandId, String itemId,
      int index) {
    return backend.moveVideo(roomId, token, commandId, itemId, index);
  }
}
