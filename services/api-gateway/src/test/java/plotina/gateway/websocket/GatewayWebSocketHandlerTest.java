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
import plotina.gateway.backend.RoomBackend;
import plotina.gateway.backend.RoomNotFoundException;
import plotina.gateway.backend.RoomSnapshot;
import plotina.gateway.command.RoomCommandService;
import plotina.gateway.chat.ChatBackend;
import plotina.gateway.chat.ChatMessage;
import plotina.gateway.chat.ChatService;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.clearInvocations;
import static org.mockito.Mockito.verifyNoInteractions;

class GatewayWebSocketHandlerTest {

  private final ObjectMapper objectMapper = new ObjectMapper();

  private SessionBackend sessionBackend;
  private WebSocketSession socket;
  private GatewayWebSocketHandler handler;
  private RoomBackend roomBackend;
  private RoomBroadcaster broadcaster;
  private ChatBackend chatBackend;

  @BeforeEach
  void setUp() {
    chatBackend = mock(ChatBackend.class);
    sessionBackend = mock(SessionBackend.class);
    socket = mock(WebSocketSession.class);
    roomBackend = mock(RoomBackend.class);
    broadcaster = mock(RoomBroadcaster.class);

    when(socket.getAttributes()).thenReturn(new HashMap<>());
    when(socket.getId()).thenReturn("socket-1");

    handler = new GatewayWebSocketHandler(
        objectMapper,
        sessionBackend,
        new ConnectionRegistry(),
        new WebSocketSender(objectMapper),
        new RoomCommandService(roomBackend, sessionBackend),
        broadcaster,
        new ChatService(sessionBackend, chatBackend));
  }

  @Test
  void shouldSendChatMessageAndBroadcastIt() throws Exception {
    authenticateSocket();

    ChatMessage message = new ChatMessage(
        "message-1",
        "room-1",
        "user-1",
        "Привет!",
        "2026-11-15T12:00:00Z");

    when(chatBackend.sendMessage(
        "room-1",
        "user-1",
        "valid-token",
        "chat-1",
        "Привет!")).thenReturn(message);

    handler.handleTextMessage(socket, new TextMessage("""
        {
          "type": "chat.send",
          "requestId": "request-chat",
          "payload": {
            "sessionToken": "valid-token",
            "commandId": "chat-1",
            "text": "Привет!"
          }
        }
        """));

    JsonNode response = readSentMessage();

    assertEquals("command.ack", response.path("type").asText());
    assertEquals(
        "request-chat",
        response.path("requestId").asText());
    assertEquals(
        "chat-1",
        response.path("payload").path("commandId").asText());
    assertEquals(
        "message-1",
        response.path("payload").path("messageId").asText());

    verify(chatBackend).sendMessage(
        "room-1",
        "user-1",
        "valid-token",
        "chat-1",
        "Привет!");

    verify(broadcaster).broadcast(
        "room-1",
        new ServerMessage("chat.message", null, message));

    verifyNoInteractions(roomBackend);
  }

  @Test
  void shouldRejectBlankChatMessage() throws Exception {
    authenticateSocket();

    handler.handleTextMessage(socket, new TextMessage("""
        {
          "type": "chat.send",
          "requestId": "request-empty",
          "payload": {
            "sessionToken": "valid-token",
            "commandId": "chat-empty",
            "text": "   "
          }
        }
        """));

    JsonNode response = readSentMessage();

    assertEquals(
        "INVALID_MESSAGE",
        response.path("payload").path("code").asText());

    verifyNoInteractions(chatBackend, broadcaster, roomBackend);
  }

  @Test
  void shouldRejectChatWithAnotherUsersToken() throws Exception {
    authenticateSocket();

    when(sessionBackend.findByToken("another-token"))
        .thenReturn(Optional.of(
            new SessionInfo(
                "another-token",
                "user-2",
                "room-1")));

    handler.handleTextMessage(socket, new TextMessage("""
        {
          "type": "chat.send",
          "requestId": "request-forbidden-chat",
          "payload": {
            "sessionToken": "another-token",
            "commandId": "chat-forbidden",
            "text": "Привет!"
          }
        }
        """));

    JsonNode response = readSentMessage();

    assertEquals(
        "FORBIDDEN",
        response.path("payload").path("code").asText());

    verifyNoInteractions(chatBackend, broadcaster, roomBackend);
  }

  @Test
  void shouldSeekRoomAndBroadcastState() throws Exception {
    authenticateSocket();

    RoomSnapshot state = new RoomSnapshot(
        "room-1",
        2L,
        true,
        120.5);

    when(roomBackend.seek(
        "room-1",
        "valid-token",
        "command-seek",
        120.5)).thenReturn(state);

    handler.handleTextMessage(socket, new TextMessage("""
        {
          "type": "playback.seek",
          "requestId": "request-seek",
          "payload": {
            "commandId": "command-seek",
            "sessionToken": "valid-token",
            "positionSeconds": 120.5
          }
        }
        """));

    JsonNode response = readSentMessage();

    assertEquals(
        "command.ack",
        response.path("type").asText());

    verify(roomBackend).seek(
        "room-1",
        "valid-token",
        "command-seek",
        120.5);

    verify(broadcaster).broadcast(
        "room-1",
        new ServerMessage("room.state", null, state));
  }

  @Test
  void shouldRejectNegativeSeekPosition() throws Exception {
    authenticateSocket();

    handler.handleTextMessage(socket, new TextMessage("""
        {
          "type": "playback.seek",
          "requestId": "request-invalid-seek",
          "payload": {
            "commandId": "command-invalid-seek",
            "sessionToken": "valid-token",
            "positionSeconds": -10
          }
        }
        """));

    JsonNode response = readSentMessage();

    assertEquals(
        "INVALID_MESSAGE",
        response.path("payload").path("code").asText());

    verifyNoInteractions(roomBackend, broadcaster);
  }

  private void authenticateSocket() throws Exception {
    when(sessionBackend.findByToken("valid-token"))
        .thenReturn(Optional.of(
            new SessionInfo(
                "valid-token",
                "user-1",
                "room-1")));

    handler.handleTextMessage(socket, new TextMessage("""
        {
          "type": "session.authenticate",
          "requestId": "auth-setup",
          "payload": {
            "sessionToken": "valid-token"
          }
        }
        """));

    clearInvocations(socket);
  }

  @Test
  void shouldPauseRoomAndBroadcastState() throws Exception {
    authenticateSocket();

    RoomSnapshot state = new RoomSnapshot(
        "room-1",
        2L,
        true,
        12.5);

    when(roomBackend.pause(
        "room-1",
        "valid-token",
        "command-1")).thenReturn(state);

    handler.handleTextMessage(socket, new TextMessage("""
        {
          "type": "playback.pause",
          "requestId": "request-1",
          "payload": {
            "commandId": "command-1",
            "sessionToken": "valid-token"
          }
        }
        """));

    JsonNode response = readSentMessage();

    assertEquals(
        "command.ack",
        response.path("type").asText());
    assertEquals(
        "request-1",
        response.path("requestId").asText());
    assertEquals(
        "command-1",
        response.path("payload").path("commandId").asText());
    assertEquals(
        2L,
        response.path("payload").path("stateVersion").asLong());

    verify(roomBackend).pause(
        "room-1",
        "valid-token",
        "command-1");

    verify(broadcaster).broadcast(
        "room-1",
        new ServerMessage("room.state", null, state));
  }

  @Test
  void shouldPlayRoomAndBroadcastState() throws Exception {
    authenticateSocket();

    RoomSnapshot state = new RoomSnapshot(
        "room-1",
        2L,
        false,
        12.5);

    when(roomBackend.play(
        "room-1",
        "valid-token",
        "command-play")).thenReturn(state);

    handler.handleTextMessage(socket, new TextMessage("""
        {
          "type": "playback.play",
          "requestId": "request-play",
          "payload": {
            "commandId": "command-play",
            "sessionToken": "valid-token"
          }
        }
        """));

    JsonNode response = readSentMessage();

    assertEquals(
        "command.ack",
        response.path("type").asText());
    assertEquals(
        "request-play",
        response.path("requestId").asText());
    assertEquals(
        "command-play",
        response.path("payload").path("commandId").asText());
    assertEquals(
        2L,
        response.path("payload").path("stateVersion").asLong());

    verify(roomBackend).play(
        "room-1",
        "valid-token",
        "command-play");

    verify(broadcaster).broadcast(
        "room-1",
        new ServerMessage("room.state", null, state));
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
  void shouldRejectPauseWithAnotherUsersToken() throws Exception {
    authenticateSocket();

    when(sessionBackend.findByToken("another-token"))
        .thenReturn(Optional.of(
            new SessionInfo(
                "another-token",
                "user-2",
                "room-1")));

    handler.handleTextMessage(socket, new TextMessage("""
        {
          "type": "playback.pause",
          "requestId": "request-forbidden",
          "payload": {
            "commandId": "command-forbidden",
            "sessionToken": "another-token"
          }
        }
        """));

    JsonNode response = readSentMessage();

    assertEquals("error", response.path("type").asText());
    assertEquals(
        "FORBIDDEN",
        response.path("payload").path("code").asText());

    verifyNoInteractions(roomBackend, broadcaster);
  }

  @Test
  void shouldReturnErrorWhenPauseRoomIsMissing() throws Exception {
    authenticateSocket();

    when(roomBackend.pause(
        "room-1",
        "valid-token",
        "command-1")).thenThrow(new RoomNotFoundException("room-1"));

    handler.handleTextMessage(socket, new TextMessage("""
        {
          "type": "playback.pause",
          "requestId": "request-1",
          "payload": {
            "commandId": "command-1",
            "sessionToken": "valid-token"
          }
        }
        """));

    JsonNode response = readSentMessage();

    assertEquals("error", response.path("type").asText());
    assertEquals(
        "ROOM_NOT_FOUND",
        response.path("payload").path("code").asText());

    verifyNoInteractions(broadcaster);
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
