package plotina.gateway.room;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.JsonNodeFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import plotina.gateway.http.ContractValidation;
import plotina.gateway.http.GatewayException;
import plotina.gateway.http.ServiceClient;
import plotina.gateway.session.SessionDirectory;
import plotina.gateway.websocket.RoomBroadcaster;

@RestController
@RequestMapping("/rooms")
public class RoomController {
  private final ServiceClient services;
  private final SessionDirectory sessions;
  private final RoomBroadcaster broadcaster;

  public RoomController(ServiceClient services, SessionDirectory sessions, RoomBroadcaster broadcaster) {
    this.services = services;
    this.sessions = sessions;
    this.broadcaster = broadcaster;
  }

  @PostMapping
  public ResponseEntity<JsonNode> create(@RequestBody JsonNode request) {
    ContractValidation.fields(request, "display_name", "control_mode");
    ContractValidation.text(request, "display_name");
    ContractValidation.mode(request, "control_mode");
    return enter("/rooms", request);
  }

  @PostMapping("/join")
  public ResponseEntity<JsonNode> join(@RequestBody JsonNode request) {
    ContractValidation.fields(request, "invite_code", "display_name");
    ContractValidation.text(request, "invite_code");
    ContractValidation.text(request, "display_name");
    return enter("/rooms/join", request);
  }

  private ResponseEntity<JsonNode> enter(String path, JsonNode request) {
    JsonNode response = services.room("POST", path, null, request);
    if (!response.path("token").isTextual() || !response.path("room_id").isTextual()
        || !response.path("state").isObject()) {
      throw new GatewayException(502, "bad_gateway", "Invalid room entry response");
    }
    String room = response.path("room_id").asText();
    sessions.remember(response.path("token").asText(), room);
    broadcaster.broadcast(room, JsonNodeFactory.instance.objectNode()
        .put("type", "sendState").set("state", response.path("state")));
    return ResponseEntity.status(201).body(response);
  }
}
