package plotina.gateway.websocket;

import com.fasterxml.jackson.databind.JsonNode;

import org.springframework.stereotype.Component;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import org.springframework.web.socket.CloseStatus;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import plotina.gateway.session.SessionBackend;
import plotina.gateway.session.SessionInfo;
import plotina.gateway.backend.RoomBackend;
import plotina.gateway.backend.RoomNotFoundException;
import plotina.gateway.backend.RoomSnapshot;
import plotina.gateway.command.CommandRejectedException;
import plotina.gateway.command.RoomCommandService;

@Component
public class GatewayWebSocketHandler extends TextWebSocketHandler {

  private static final String SESSION_ATTRIBUTE = GatewayWebSocketHandler.class.getName() + ".session";

  private final ObjectMapper objectMapper;
  private final SessionBackend sessionBackend;
  private final ConnectionRegistry connectionRegistry;
  private final WebSocketSender sender;
  private final RoomBroadcaster broadcaster;
  private final RoomCommandService roomCommandService;

  public GatewayWebSocketHandler(
      ObjectMapper objectMapper,
      SessionBackend sessionBackend,
      ConnectionRegistry connectionRegistry,
      WebSocketSender sender,
      RoomCommandService roomCommandService,
      RoomBroadcaster broadcaster) {
    this.objectMapper = objectMapper;
    this.sessionBackend = sessionBackend;
    this.connectionRegistry = connectionRegistry;
    this.sender = sender;
    this.roomCommandService = roomCommandService;
    this.broadcaster = broadcaster;
  }

  private void pause(
      WebSocketSession socket,
      ClientMessage request) throws Exception {
    JsonNode payload = request.payload();

    JsonNode tokenNode = payload == null
        ? null
        : payload.get("sessionToken");

    JsonNode commandIdNode = payload == null
        ? null
        : payload.get("commandId");

    if (tokenNode == null
        || !tokenNode.isTextual()
        || tokenNode.asText().isBlank()
        || commandIdNode == null
        || !commandIdNode.isTextual()
        || commandIdNode.asText().isBlank()) {
      sendError(
          socket,
          request.requestId(),
          "INVALID_MESSAGE",
          "Session token and command ID must be non-empty strings");
      return;
    }
    AuthenticatedSession identity = (AuthenticatedSession) socket.getAttributes()
        .get(SESSION_ATTRIBUTE);

    if (identity == null) {
      sendError(
          socket,
          request.requestId(),
          "UNAUTHORIZED",
          "Authenticate the connection first");
      return;
    }

    RoomSnapshot state;

    try {
      state = roomCommandService.pause(
          identity.userId(),
          identity.roomId(),
          tokenNode.asText(),
          commandIdNode.asText());
    } catch (CommandRejectedException exception) {
      sendError(
          socket,
          request.requestId(),
          exception.code(),
          exception.getMessage());
      return;
    } catch (RoomNotFoundException exception) {
      sendError(
          socket,
          request.requestId(),
          "ROOM_NOT_FOUND",
          "Room not found");
      return;
    }

    broadcaster.broadcast(
        state.roomId(),
        new ServerMessage("room.state", null, state));

    send(
        socket,
        new ServerMessage(
            "command.ack",
            request.requestId(),
            new CommandAck(
                commandIdNode.asText(),
                state.version())));
  }

  @Override
  public void afterConnectionClosed(
      WebSocketSession session,
      CloseStatus status) {
    connectionRegistry.remove(session.getId());
  }

  private void authenticate(
      WebSocketSession session,
      ClientMessage request) throws Exception {
    if (session.getAttributes().containsKey(SESSION_ATTRIBUTE)) {
      sendError(
          session,
          request.requestId(),
          "ALREADY_AUTHENTICATED",
          "Connection is already authenticated");
      return;
    }

    JsonNode payload = request.payload();
    JsonNode tokenNode = payload == null
        ? null
        : payload.get("sessionToken");

    if (tokenNode == null
        || !tokenNode.isTextual()
        || tokenNode.asText().isBlank()) {
      sendError(
          session,
          request.requestId(),
          "INVALID_MESSAGE",
          "Session token must be a non-empty string");
      return;
    }

    SessionInfo identity = sessionBackend
        .findByToken(tokenNode.asText())
        .orElse(null);

    if (identity == null) {
      sendError(
          session,
          request.requestId(),
          "UNAUTHORIZED",
          "Invalid session token");
      return;
    }

    AuthenticatedSession authenticatedSession = new AuthenticatedSession(
        identity.userId(),
        identity.roomId());

    session.getAttributes().put(
        SESSION_ATTRIBUTE,
        authenticatedSession);

    connectionRegistry.register(
        session,
        authenticatedSession.userId(),
        authenticatedSession.roomId());

    send(
        session,
        new ServerMessage(
            "session.authenticated",
            request.requestId(),
            authenticatedSession));
  }

  @Override
  protected void handleTextMessage(
      WebSocketSession session,
      TextMessage message) throws Exception {
    ClientMessage request;
    try {
      request = objectMapper.readValue(message.getPayload(), ClientMessage.class);
    } catch (JsonProcessingException exception) {
      sendError(session, null, "INVALID_MESSAGE",
          "Message must match the expected JSON structure");
      return;
    }

    if (request == null || request.type() == null || request.type().isBlank()) {
      sendError(session, null, "INVALID_MESSAGE",
          "Message type is required");
      return;
    }

    if (request.requestId() == null
        || request.requestId().isBlank()) {
      sendError(session, null, "INVALID_MESSAGE",
          "Request ID is required");
      return;
    }

    boolean publicMessage = request.type().equals("ping")
        || request.type().equals("session.authenticate");

    if (!publicMessage
        && !session.getAttributes().containsKey(SESSION_ATTRIBUTE)) {
      sendError(
          session,
          request.requestId(),
          "UNAUTHORIZED",
          "Authenticate the connection first");
      return;
    }

    switch (request.type()) {
      case "ping" -> send(
          session,
          new ServerMessage(
              "pong",
              request.requestId(),
              new PongPayload("ok")));

      case "session.authenticate" -> authenticate(session, request);

      case "playback.pause" -> pause(session, request);

      default -> sendError(
          session,
          request.requestId(),
          "UNKNOWN_MESSAGE_TYPE",
          "Unsupported message type");
    }

  }

  private void send(
      WebSocketSession session,
      ServerMessage message) throws Exception {
    sender.send(session, message);
  }

  private void sendError(
      WebSocketSession session,
      String requestId,
      String code,
      String message) throws Exception {
    send(
        session,
        new ServerMessage(
            "error",
            requestId,
            new ErrorPayload(code, message)));
  }

  public record PongPayload(String status) {
  }

  public record ErrorPayload(String code, String message) {
  }

  public record AuthenticatedSession(
      String userId,
      String roomId) {
  }

  public record CommandAck(
      String commandId,
      long stateVersion) {
  }

}
