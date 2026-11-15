package plotina.gateway.websocket;

import java.util.HashMap;
import java.util.Optional;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

import plotina.gateway.session.SessionBackend;
import plotina.gateway.session.SessionInfo;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class GatewayWebSocketHandlerTest {

  private final ObjectMapper objectMapper = new ObjectMapper();

  private SessionBackend sessionBackend;
  private WebSocketSession socket;
  private GatewayWebSocketHandler handler;

  @BeforeEach
  void setUp() {
    sessionBackend = mock(SessionBackend.class);
    socket = mock(WebSocketSession.class);

    when(socket.getAttributes()).thenReturn(new HashMap<>());

    handler = new GatewayWebSocketHandler(
        objectMapper,
        sessionBackend);
  }

  @Test
  void shouldAuthenticateWithValidToken() throws Exception {
    when(sessionBackend.findByToken("valid-token"))
        .thenReturn(Optional.of(
            new SessionInfo(
                "valid-token",
                "user-1",
                "room-1")));

    handler.handleTextMessage(socket, new TextMessage("""
        {
          "type": "session.authenticate",
          "requestId": "auth-1",
          "payload": {
            "sessionToken": "valid-token"
          }
        }
        """));

    JsonNode response = readSentMessage();

    assertEquals(
        "session.authenticated",
        response.path("type").asText());
    assertEquals(
        "auth-1",
        response.path("requestId").asText());
    assertEquals(
        "user-1",
        response.path("payload").path("userId").asText());
    assertEquals(
        "room-1",
        response.path("payload").path("roomId").asText());

    GatewayWebSocketHandler.AuthenticatedSession identity = socket.getAttributes().values().stream()
        .filter(
            GatewayWebSocketHandler.AuthenticatedSession.class::isInstance)
        .map(
            GatewayWebSocketHandler.AuthenticatedSession.class::cast)
        .findFirst()
        .orElseThrow();

    assertEquals("user-1", identity.userId());
    assertEquals("room-1", identity.roomId());
  }

  @Test
  void shouldRejectInvalidToken() throws Exception {
    when(sessionBackend.findByToken("wrong-token"))
        .thenReturn(Optional.empty());

    handler.handleTextMessage(socket, new TextMessage("""
        {
          "type": "session.authenticate",
          "requestId": "auth-2",
          "payload": {
            "sessionToken": "wrong-token"
          }
        }
        """));

    JsonNode response = readSentMessage();

    assertEquals("error", response.path("type").asText());
    assertEquals(
        "UNAUTHORIZED",
        response.path("payload").path("code").asText());
    assertEquals(0, socket.getAttributes().size());
  }

  @Test
  void shouldRejectMissingToken() throws Exception {
    handler.handleTextMessage(socket, new TextMessage("""
        {
          "type": "session.authenticate",
          "requestId": "auth-3",
          "payload": {}
        }
        """));

    JsonNode response = readSentMessage();

    assertEquals(
        "INVALID_MESSAGE",
        response.path("payload").path("code").asText());

    verify(sessionBackend, never()).findByToken(any());
  }

  @Test
  void shouldRejectProtectedMessageBeforeAuthentication()
      throws Exception {
    handler.handleTextMessage(socket, new TextMessage("""
        {
          "type": "playback.pause",
          "requestId": "command-1",
          "payload": {}
        }
        """));

    JsonNode response = readSentMessage();

    assertEquals(
        "UNAUTHORIZED",
        response.path("payload").path("code").asText());
  }

  private JsonNode readSentMessage() throws Exception {
    ArgumentCaptor<TextMessage> captor = ArgumentCaptor.forClass(TextMessage.class);

    verify(socket).sendMessage(captor.capture());

    return objectMapper.readTree(
        captor.getValue().getPayload());
  }
}
