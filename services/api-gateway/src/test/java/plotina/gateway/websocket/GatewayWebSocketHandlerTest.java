package plotina.gateway.websocket;

import java.io.IOException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.web.socket.*;
import plotina.gateway.http.ServiceClient;
import plotina.gateway.http.GatewayException;
import plotina.gateway.session.SessionDirectory;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class GatewayWebSocketHandlerTest {
  final ObjectMapper mapper = new ObjectMapper();
  final ServiceClient services = mock(ServiceClient.class);
  final SessionDirectory sessions = new SessionDirectory();
  final ConnectionRegistry registry = new ConnectionRegistry();
  final WebSocketSender sender = new WebSocketSender(mapper);
  final RoomBroadcaster broadcaster = new RoomBroadcaster(registry, sender);
  final GatewayWebSocketHandler handler = new GatewayWebSocketHandler(
      mapper, services, sessions, registry, sender, broadcaster, 10000);
  WebSocketSession socket;

  @BeforeEach void setup() {
    socket = socket("one");
    handler.afterConnectionEstablished(socket);
  }

  WebSocketSession socket(String id) {
    WebSocketSession result = mock(WebSocketSession.class);
    when(result.getId()).thenReturn(id);
    when(result.isOpen()).thenReturn(true);
    return result;
  }

  @Test void matchingPongAcknowledgesPig() throws Exception {
    handler.heartbeat();
    var capture = ArgumentCaptor.forClass(TextMessage.class);
    verify(socket).sendMessage(capture.capture());
    var pig = mapper.readTree(capture.getValue().getPayload());
    assertEquals("pig", pig.path("type").asText());
    handler.handleTextMessage(socket, new TextMessage("{\"type\":\"pong\",\"pigId\":\"wrong\"}"));
    assertNotNull(registry.get("one").pigId);
    handler.handleTextMessage(socket, new TextMessage("{\"type\":\"pong\",\"pigId\":\"" + pig.path("pigId").asText() + "\"}"));
    assertNull(registry.get("one").pigId);
    verifyNoInteractions(services);
  }

  @Test void expiredPigClosesAndRemovesConnection() throws Exception {
    var connection = registry.get("one");
    connection.pigId = "expired";
    connection.pigSentAt = 0;
    handler.heartbeat();
    verify(socket).close(CloseStatus.SESSION_NOT_RELIABLE);
    assertNull(registry.get("one"));
  }

  @Test void broadcastIsRoomScopedAndContinuesAfterSendFailure() throws Exception {
    var first = registry.get("one");
    first.roomId = "a";
    first.ready = true;
    var secondSocket = socket("two");
    registry.register(secondSocket);
    var second = registry.get("two");
    second.roomId = "a";
    second.ready = true;
    var otherSocket = socket("other");
    registry.register(otherSocket);
    registry.get("other").roomId = "b";
    registry.get("other").ready = true;
    doThrow(new IOException("test")).when(socket).sendMessage(any());
    broadcaster.broadcast("a", mapper.readTree("{\"type\":\"sendState\",\"state\":{}}"));
    verify(secondSocket).sendMessage(any());
    verify(otherSocket, never()).sendMessage(any());
    verify(socket).close(CloseStatus.SERVER_ERROR);
    assertNull(registry.get("one"));
  }

  @Test void buffersDuringInitializationAndDoesNotLeakChatBeforeBaseline() throws Exception {
    var connection = registry.get("one");
    connection.roomId = "a";
    var old = mapper.readTree("{\"type\":\"sendMessage\",\"message\":{\"messageSeq\":42}}");
    broadcaster.broadcast("a", old);
    assertEquals(1, connection.pending.size());
    verify(socket, never()).sendMessage(any());
    connection.initialSeq = 42;
    connection.ready = true;
    connection.chatReady = true;
    broadcaster.broadcast("a", old);
    verify(socket, never()).sendMessage(any());
    broadcaster.broadcast("a", mapper.readTree("{\"type\":\"sendMessage\",\"message\":{\"messageSeq\":43}}"));
    verify(socket).sendMessage(any());
  }

  @Test void verifiesTokenWithRoomBeforeDeliveringInitialState() throws Exception {
    sessions.remember("invalid", "room-1");
    when(services.room("GET", "/rooms/room-1", "invalid", null))
        .thenThrow(new GatewayException(401, "unauthorized", "Invalid token"));
    handler.handleTextMessage(socket, new TextMessage("{\"type\":\"getState\",\"token\":\"invalid\",\"payload\":{}}"));
    var capture = ArgumentCaptor.forClass(TextMessage.class);
    verify(socket).sendMessage(capture.capture());
    assertEquals("unauthorized", mapper.readTree(capture.getValue().getPayload()).path("error").path("code").asText());
    assertNull(registry.get("one").roomId);
    verify(services, never()).chat(any(), any(), any(), any());
  }

  @Test void stateRefreshWorksWithoutChatService() throws Exception {
    var connection = registry.get("one");
    connection.roomId = "room-1";
    connection.token = "token";
    connection.ready = true;
    when(services.room("GET", "/rooms/room-1", "token", null)).thenReturn(mapper.readTree("{\"state_version\":9}"));
    handler.reconcile();
    verify(socket).sendMessage(any());
    verify(services, never()).chat(any(), any(), any(), any());
  }

  @Test void initializedRoomCommandsDoNotDependOnChatAvailability() throws Exception {
    sessions.remember("token", "room-1");
    var connection = registry.get("one");
    registry.bind(connection, "room-1", "token");
    connection.ready = true;
    when(services.chat(any(), any(), any(), any()))
        .thenThrow(new GatewayException(502, "service_unavailable", "Chat unavailable"));
    when(services.room(eq("POST"), eq("/rooms/room-1/commands"), eq("token"), any()))
        .thenReturn(mapper.readTree("{\"command_id\":\"cmd-1\",\"duplicate\":false,\"state\":{\"state_version\":10}}"));
    handler.handleTextMessage(socket, new TextMessage(
        "{\"type\":\"playpause\",\"commandId\":\"cmd-1\",\"token\":\"token\",\"payload\":{}}"));
    var capture = ArgumentCaptor.forClass(TextMessage.class);
    verify(socket, times(2)).sendMessage(capture.capture());
    assertEquals("commandConfirm", mapper.readTree(capture.getAllValues().getFirst().getPayload()).path("type").asText());
    verify(services, never()).chat(any(), any(), any(), any());
  }

  @Test void reconnectWithoutChatStillReceivesRoomUpdatesAndRecoversRealChatBaseline() throws Exception {
    sessions.remember("token", "room-1");
    when(services.room("GET", "/rooms/room-1", "token", null))
        .thenReturn(mapper.readTree("{\"state_version\":10}"));
    when(services.chat("GET", "/rooms/room-1/messages/seq", "token", null))
        .thenThrow(new GatewayException(502, "service_unavailable", "Chat unavailable"));
    handler.handleTextMessage(socket, new TextMessage(
        "{\"type\":\"getState\",\"token\":\"token\",\"payload\":{}}"));
    assertTrue(registry.get("one").ready);
    assertFalse(registry.get("one").chatReady);
    var capture = ArgumentCaptor.forClass(TextMessage.class);
    verify(socket).sendMessage(capture.capture());
    var initial = mapper.readTree(capture.getValue().getPayload());
    assertEquals("sendState", initial.path("type").asText());
    assertFalse(initial.has("initialMessageSeq"));
    clearInvocations(socket);
    handler.reconcile();
    verify(socket).sendMessage(any());
    when(services.room(eq("POST"), eq("/rooms/room-1/commands"), eq("token"), any()))
        .thenReturn(mapper.readTree("{\"command_id\":\"cmd-1\",\"duplicate\":false,\"state\":{\"state_version\":11}}"));
    handler.handleTextMessage(socket, new TextMessage(
        "{\"type\":\"playpause\",\"commandId\":\"cmd-1\",\"token\":\"token\",\"payload\":{}}"));
    verify(services).room(eq("POST"), eq("/rooms/room-1/commands"), eq("token"), any());
    doReturn(mapper.readTree("{\"messageSeq\":57}"))
        .when(services).chat("GET", "/rooms/room-1/messages/seq", "token", null);
    clearInvocations(socket);
    handler.recoverChats();
    assertTrue(registry.get("one").chatReady);
    verify(socket).sendMessage(capture.capture());
    assertEquals(57, mapper.readTree(capture.getValue().getPayload()).path("initialMessageSeq").asLong());
  }
}
