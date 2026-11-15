package plotina.gateway.room;

import org.springframework.stereotype.Service;

import plotina.gateway.backend.RoomBackend;
import plotina.gateway.backend.RoomSnapshot;
import plotina.gateway.session.SessionBackend;
import plotina.gateway.session.SessionInfo;

@Service
public class RoomEntryService {

  private final RoomBackend roomBackend;
  private final SessionBackend sessionBackend;

  public RoomEntryService(
      RoomBackend roomBackend,
      SessionBackend sessionBackend) {
    this.roomBackend = roomBackend;
    this.sessionBackend = sessionBackend;
  }

  public RoomEntryResult createRoom() {
    RoomSnapshot state = roomBackend.createRoom();

    SessionInfo session = sessionBackend.createSession(
        state.roomId());

    return new RoomEntryResult(state, session);
  }

  public RoomEntryResult joinRoom(String roomId) {
    RoomSnapshot state = roomBackend.getSnapshot(roomId);

    SessionInfo session = sessionBackend.createSession(roomId);

    return new RoomEntryResult(state, session);
  }

  public record RoomEntryResult(
      RoomSnapshot state,
      SessionInfo session) {
  }
}
