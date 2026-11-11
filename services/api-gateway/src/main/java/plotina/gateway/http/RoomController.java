package plotina.gateway.http;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
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

  @GetMapping("/{roomId}/state")
  public RoomSnapshot getState(
      @PathVariable("roomId") String roomId) {
    return roomBackend.getSnapshot(roomId);
  }

}
