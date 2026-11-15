package plotina.gateway.websocket;

import java.io.IOException;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.socket.WebSocketSession;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class RoomBroadcasterTest {

  private ConnectionRegistry registry;
  private WebSocketSender sender;
  private RoomBroadcaster broadcaster;

  @BeforeEach
  void setUp() {
    registry = new ConnectionRegistry();
    sender = mock(WebSocketSender.class);
    broadcaster = new RoomBroadcaster(registry, sender);
  }

  @Test
  void shouldBroadcastOnlyToTargetRoom() throws Exception {
    WebSocketSession first = socket("socket-1", true);
    WebSocketSession second = socket("socket-2", true);
    WebSocketSession otherRoom = socket("socket-3", true);

    registry.register(first, "user-1", "room-1");
    registry.register(second, "user-2", "room-1");
    registry.register(otherRoom, "user-3", "room-2");

    ServerMessage event = event();

    broadcaster.broadcast("room-1", event);

    verify(sender).send(first, event);
    verify(sender).send(second, event);
    verify(sender, never()).send(otherRoom, event);
  }

  @Test
  void shouldKeepMultipleConnectionsOfSameUser() {
    registry.register(
        socket("socket-1", true),
        "user-1",
        "room-1");
    registry.register(
        socket("socket-2", true),
        "user-1",
        "room-1");

    assertEquals(2, registry.findByRoom("room-1").size());

    registry.remove("socket-1");

    assertEquals(1, registry.findByRoom("room-1").size());
    assertEquals(
        "socket-2",
        registry.findByRoom("room-1")
            .get(0)
            .socket()
            .getId());
  }

  @Test
  void shouldAttemptOtherConnectionsWhenOneSendFails()
      throws Exception {
    WebSocketSession failing = socket("socket-1", true);
    WebSocketSession healthy = socket("socket-2", true);

    registry.register(failing, "user-1", "room-1");
    registry.register(healthy, "user-2", "room-1");

    ServerMessage event = event();

    doThrow(new IOException("Test send failure"))
        .when(sender)
        .send(failing, event);

    broadcaster.broadcast("room-1", event);

    verify(sender).send(failing, event);
    verify(sender).send(healthy, event);
  }

  @Test
  void shouldRemoveClosedConnection() throws Exception {
    WebSocketSession closed = socket("socket-1", false);

    registry.register(closed, "user-1", "room-1");

    broadcaster.broadcast("room-1", event());

    assertEquals(0, registry.findByRoom("room-1").size());
    verify(sender, never()).send(any(), any());
  }

  @Test
  void shouldSerializeMessageForSocket() throws Exception {
    ObjectMapper objectMapper = new ObjectMapper();
    WebSocketSender realSender = new WebSocketSender(objectMapper);

    WebSocketSession socket = socket("socket-1", true);
    ServerMessage event = event();

    realSender.send(socket, event);

    verify(socket).sendMessage(
        new org.springframework.web.socket.TextMessage(
            objectMapper.writeValueAsString(event)));
  }

  private WebSocketSession socket(String id, boolean open) {
    WebSocketSession socket = mock(WebSocketSession.class);

    when(socket.getId()).thenReturn(id);
    when(socket.isOpen()).thenReturn(open);

    return socket;
  }

  private ServerMessage event() {
    return new ServerMessage(
        "room.state",
        null,
        new GatewayWebSocketHandler.PongPayload("test"));
  }
}
