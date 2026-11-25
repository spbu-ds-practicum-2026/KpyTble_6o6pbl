package plotina.gateway.websocket;

import java.io.IOException;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.*;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import plotina.gateway.http.ContractValidation;
import plotina.gateway.http.GatewayException;
import plotina.gateway.http.ServiceClient;
import plotina.gateway.session.SessionDirectory;

@Component
public class GatewayWebSocketHandler extends TextWebSocketHandler {
  private static final Logger log = LoggerFactory.getLogger(GatewayWebSocketHandler.class);
  private static final Map<String, String> ROOM_COMMANDS = Map.of(
      "playpause", "playpause", "nextVideo", "next", "seek", "seek",
      "addVideo", "add_video", "removeVideo", "remove_video",
      "changeQueue", "change_queue", "setSettings", "set_control_mode");
  private static final Set<String> READS = Set.of("getState", "getChatSeq");
  private final ObjectMapper mapper;
  private final ServiceClient services;
  private final SessionDirectory sessions;
  private final ConnectionRegistry registry;
  private final WebSocketSender sender;
  private final RoomBroadcaster broadcaster;
  private final long heartbeatTimeout;

  public GatewayWebSocketHandler(ObjectMapper mapper, ServiceClient services, SessionDirectory sessions,
      ConnectionRegistry registry, WebSocketSender sender, RoomBroadcaster broadcaster,
      @Value("${gateway.heartbeat-timeout-ms:10000}") long heartbeatTimeout) {
    this.mapper = mapper;
    this.services = services;
    this.sessions = sessions;
    this.registry = registry;
    this.sender = sender;
    this.broadcaster = broadcaster;
    this.heartbeatTimeout = heartbeatTimeout;
  }

  @Override
  public void afterConnectionEstablished(WebSocketSession socket) {
    socket.setTextMessageSizeLimit(64 * 1024);
    registry.register(socket);
  }

  @Override
  protected void handleTextMessage(WebSocketSession socket, TextMessage message) throws IOException {
    String commandId = null;
    try {
      JsonNode request;
      try { request = mapper.readTree(message.getPayload()); }
      catch (IOException exception) { throw new GatewayException(422, "invalid_payload", "Invalid JSON"); }
      if (request == null || !request.isObject()) ContractValidation.invalid("Expected a JSON object");
      if (request.path("commandId").isTextual()) commandId = request.path("commandId").asText();
      String type = ContractValidation.text(request, "type");
      var connection = registry.get(socket.getId());
      if (connection == null) throw new GatewayException(401, "unauthorized", "Connection is closed");
      if ("pong".equals(type)) {
        ContractValidation.fields(request, "type", "pigId");
        synchronized (connection) {
          if (ContractValidation.text(request, "pigId").equals(connection.pigId)) connection.pigId = null;
        }
        return;
      }
      if (!ROOM_COMMANDS.containsKey(type) && !READS.contains(type)
          && !Set.of("leaveRoom", "sendMessage").contains(type)) {
        ContractValidation.invalid("Unknown message type");
      }
      boolean read = READS.contains(type);
      if (read) ContractValidation.fields(request, "type", "token", "payload");
      else {
        ContractValidation.fields(request, "type", "commandId", "token", "payload");
        commandId = ContractValidation.text(request, "commandId");
      }
      String token = ContractValidation.text(request, "token");
      ContractValidation.payload(type, request.path("payload"));
      if (connection.token != null && !connection.token.equals(token)) {
        throw new GatewayException(401, "unauthorized", "Cannot change the session of an open connection");
      }
      String room = sessions.room(token);
      boolean initialized = connection.ready;
      if (!initialized) initialize(connection, room, token);
      String path = "/rooms/" + room;
      if ("getState".equals(type)) {
        if (initialized) sender.send(socket, event("sendState").set("state", services.room("GET", path, token, null)));
      } else if ("getChatSeq".equals(type)) {
        JsonNode seq = services.chat("GET", path + "/messages/seq", token, null);
        sender.send(socket, event("commandConfirm").set("messageSeq", seq.path("messageSeq")));
      } else if ("leaveRoom".equals(type)) {
        JsonNode result = services.room("POST", path + "/leave", token, null);
        sender.send(socket, confirm(commandId).set("left", result.path("left")));
        sessions.forget(token);
        registry.remove(socket.getId());
        socket.close(CloseStatus.NORMAL);
        refreshRoom(room);
      } else {
        ObjectNode body = mapper.createObjectNode().put("command_id", commandId);
        JsonNode result;
        if ("sendMessage".equals(type)) {
          body.set("text", request.path("payload").path("text"));
          result = services.chat("POST", path + "/messages", token, body);
        } else {
          body.put("type", ROOM_COMMANDS.get(type)).set("payload", request.path("payload"));
          result = services.room("POST", path + "/commands", token, body);
        }
        ObjectNode response = confirm(commandId).set("duplicate", result.path("duplicate"));
        String field = "sendMessage".equals(type) ? "message" : "state";
        response.set(field, result.path(field));
        sender.send(socket, response);
        // Duplicate chat delivery repairs lost events; clients deduplicate by messageSeq.
        // A saved room snapshot may be stale: never broadcast it as a new state on retry.
        if ("message".equals(field) || !result.path("duplicate").asBoolean()) {
          broadcaster.broadcast(room, event("message".equals(field) ? "sendMessage" : "sendState")
              .set(field, result.path(field)));
        }
      }
    } catch (GatewayException exception) {
      ObjectNode response = event("commandConfirm");
      if (commandId != null) response.put("commandId", commandId);
      sender.send(socket, response.set("error", exception.error()));
    } catch (RuntimeException exception) {
      log.error("Unexpected WebSocket command failure for connection {}", socket.getId());
      ObjectNode response = event("commandConfirm");
      if (commandId != null) response.put("commandId", commandId);
      sender.send(socket, response.set("error", mapper.createObjectNode()
          .put("code", "internal_error").put("message", "Internal gateway error")));
    }
  }

  private void initialize(ConnectionRegistry.Connection connection, String room, String token) throws IOException {
    // The first token-bearing message authenticates the connection. The contract has no
    // handshake token, so an initial state cannot be sent before this message arrives.
    registry.bind(connection, room, token);
    try {
      // Register before taking the chat baseline so concurrent broadcasts are buffered.
      JsonNode state = services.room("GET", "/rooms/" + room, token, null);
      JsonNode seq = services.chat("GET", "/rooms/" + room + "/messages/seq", token, null);
      if (!seq.path("messageSeq").isIntegralNumber()) {
        throw new GatewayException(502, "bad_gateway", "Invalid chat sequence response");
      }
      synchronized (connection) {
        connection.initialSeq = seq.path("messageSeq").asLong();
        sender.send(connection.socket, event("sendState").put("initialMessageSeq", connection.initialSeq)
            .set("state", state));
        for (JsonNode pending : connection.pending) {
          if (!RoomBroadcaster.isOldChat(connection, pending)) sender.send(connection.socket, pending);
        }
        connection.pending.clear();
        connection.ready = true;
      }
    } catch (RuntimeException | IOException exception) {
      synchronized (connection) {
        connection.token = null;
        connection.roomId = null;
        connection.pending.clear();
      }
      throw exception;
    }
  }

  private ObjectNode event(String type) { return mapper.createObjectNode().put("type", type); }
  private ObjectNode confirm(String id) { return event("commandConfirm").put("commandId", id); }

  @Override
  public void afterConnectionClosed(WebSocketSession socket, CloseStatus status) { registry.remove(socket.getId()); }

  @Override
  public void handleTransportError(WebSocketSession socket, Throwable exception) throws IOException {
    registry.remove(socket.getId());
    socket.close(CloseStatus.SERVER_ERROR);
  }

  @Scheduled(fixedDelayString = "${gateway.heartbeat-interval-ms:5000}")
  public void heartbeat() {
    long now = System.currentTimeMillis();
    for (var connection : registry.all()) {
      synchronized (connection) {
        try {
          if (!connection.socket.isOpen()) { registry.remove(connection.socket.getId()); continue; }
          if ((connection.pigId != null && now - connection.pigSentAt >= heartbeatTimeout)
              || (connection.token == null && now - connection.openedAt >= heartbeatTimeout)) {
            registry.remove(connection.socket.getId());
            connection.socket.close(CloseStatus.SESSION_NOT_RELIABLE);
          } else if (connection.pigId == null) {
            connection.pigId = UUID.randomUUID().toString();
            connection.pigSentAt = now;
            sender.send(connection.socket, event("pig").put("pigId", connection.pigId));
          }
        } catch (IOException exception) { registry.remove(connection.socket.getId()); }
      }
    }
  }

  // Periodic reconciliation also picks up server-side changes and recovers missed broadcasts.
  @Scheduled(fixedDelayString = "${gateway.state-refresh-ms:1000}")
  public void reconcile() {
    registry.all().stream().filter(c -> c.ready).map(c -> c.roomId).distinct().forEach(this::refreshRoom);
  }

  private void refreshRoom(String room) {
    for (var connection : registry.findByRoom(room)) {
      if (!connection.ready) continue;
      try {
        JsonNode state = services.room("GET", "/rooms/" + room, connection.token, null);
        broadcaster.broadcast(room, event("sendState").set("state", state));
        return;
      } catch (GatewayException exception) {
        // Try another active member (e.g. the previous token was revoked).
        if (exception.status() != 401 && exception.status() != 403) return;
      }
    }
  }
}
