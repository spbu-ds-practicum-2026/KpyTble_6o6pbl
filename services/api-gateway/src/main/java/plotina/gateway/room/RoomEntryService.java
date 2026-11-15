package plotina.gateway.room;

import org.springframework.stereotype.Service;

import plotina.gateway.room.backend.RoomBackend;
import plotina.gateway.room.backend.RoomSnapshot;
import plotina.gateway.session.backend.SessionInfo;

@Service
public class RoomEntryService {

  private final RoomBackend roomBackend;

  public RoomEntryService(
      RoomBackend roomBackend) {
    this.roomBackend = roomBackend;
  }

  public RoomEntryResult createRoom() {
    return roomBackend.createRoom();
  }

  public RoomEntryResult joinRoom(String roomId) {
    return roomBackend.joinRoom(roomId);
  }

  public record RoomEntryResult(
      RoomSnapshot state,
      SessionInfo session) {
  }
}
