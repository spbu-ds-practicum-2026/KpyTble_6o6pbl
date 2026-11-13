package plotina.gateway.http;

import java.net.URI;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import plotina.gateway.backend.RoomBackend;
import plotina.gateway.backend.RoomSnapshot;

@RestController
@RequestMapping("/rooms")
public class RoomController {

  private final RoomBackend roomBackend;

  public RoomController(RoomBackend roomBackend) {
    this.roomBackend = roomBackend;
  }

  @PostMapping
  public ResponseEntity<RoomSnapshot> createRoom() {
    RoomSnapshot snapshot = roomBackend.createRoom();

    URI stateUri = URI.create(
        "/rooms/" + snapshot.roomId() + "/state");

    return ResponseEntity.created(stateUri).body(snapshot);
  }

  @GetMapping("/{roomId}/state")
  public RoomSnapshot getState(
      @PathVariable("roomId") String roomId) {
    return roomBackend.getSnapshot(roomId);
  }

}
