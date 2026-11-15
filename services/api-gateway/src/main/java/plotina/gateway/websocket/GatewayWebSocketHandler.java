package plotina.gateway.websocket;

import org.springframework.stereotype.Component;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

@Component
public class GatewayWebSocketHandler extends TextWebSocketHandler {

  private final ObjectMapper objectMapper;

  public GatewayWebSocketHandler(ObjectMapper objectMapper) {
    this.objectMapper = objectMapper;
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

    switch (request.type()) {
      case "ping" -> send(
          session,
          new ServerMessage(
              "pong",
              request.requestId(),
              new PongPayload("ok")));

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
    String json = objectMapper.writeValueAsString(message);
    session.sendMessage(new TextMessage(json));
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
}
