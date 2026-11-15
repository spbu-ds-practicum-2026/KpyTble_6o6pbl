package plotina.gateway.room.backend.fake;

import org.springframework.stereotype.Service;

import plotina.gateway.room.backend.RoomBackend;
import plotina.gateway.room.backend.RoomSnapshot;
import plotina.gateway.room.RoomEntryService.RoomEntryResult;
import plotina.gateway.session.backend.SessionInfo;

/**
 * Stateless sample responses, not a room implementation or persistent storage.
 */
@Service
public class FakeRoomBackend implements RoomBackend {

  @Override
  public RoomEntryResult createRoom() {
    return new RoomEntryResult(sample("demo-room"),
        new SessionInfo("demo-host-token", "demo-host", "demo-room"));
  }

  @Override
  public RoomEntryResult joinRoom(String roomId) {
    return new RoomEntryResult(sample("demo-room"),
        new SessionInfo("demo-guest-token", "demo-guest", "demo-room"));
  }

  @Override
  public RoomSnapshot getSnapshot(String roomId) {
    return sample(roomId);
  }

  @Override
  public RoomSnapshot pause(String roomId, String token, String commandId) {
    return sample(roomId);
  }

  @Override
  public RoomSnapshot play(String roomId, String token, String commandId) {
    return sample(roomId);
  }

  @Override
  public RoomSnapshot seek(String roomId, String token, String commandId, double position) {
    return sample(roomId);
  }

  @Override
  public RoomSnapshot addVideo(String roomId, String token, String commandId, String url) {
    return sample(roomId);
  }

  @Override
  public RoomSnapshot removeVideo(String roomId, String token, String commandId, String itemId) {
    return sample(roomId);
  }

  @Override
  public RoomSnapshot moveVideo(String roomId, String token, String commandId, String itemId, int index) {
    return sample(roomId);
  }

  @Override
  public RoomSnapshot next(String roomId, String token, String commandId) {
    return sample(roomId);
  }

  private RoomSnapshot sample(String roomId) {
    return new RoomSnapshot(roomId, 1L, true, 0.0);
  }
}
