package plotina.gateway.room;

import java.net.URI;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import plotina.gateway.room.backend.RoomBackend;
import plotina.gateway.room.backend.RoomSnapshot;
import plotina.gateway.room.RoomEntryService;

@RestController
@RequestMapping("/rooms")
public class RoomController {

  private final RoomBackend roomBackend;
  private final RoomEntryService roomEntryService;

  public RoomController(
      RoomBackend roomBackend,
      RoomEntryService roomEntryService) {
    this.roomBackend = roomBackend;
    this.roomEntryService = roomEntryService;
  }

  @PostMapping
  public ResponseEntity<CreateRoomResponse> createRoom() {
    RoomEntryService.RoomEntryResult result = roomEntryService.createRoom();

    RoomSnapshot state = result.state();

    CreateRoomResponse response = new CreateRoomResponse(
        state.roomId(),
        state.version(),
        state.paused(),
        state.positionSeconds(),
        result.session());

    URI stateUri = URI.create(
        "/rooms/" + state.roomId() + "/state");

    return ResponseEntity
        .created(stateUri)
        .body(response);
  }

  @GetMapping("/{roomId}/state")
  public RoomSnapshot getState(
      @PathVariable("roomId") String roomId) {
    return roomBackend.getSnapshot(roomId);
  }

  @PostMapping("/{roomId}/join")
  public JoinRoomResponse joinRoom(
      @PathVariable("roomId") String roomId) {
    RoomEntryService.RoomEntryResult result = roomEntryService.joinRoom(roomId);

    return new JoinRoomResponse(
        result.state(),
        result.session());
  }

}
