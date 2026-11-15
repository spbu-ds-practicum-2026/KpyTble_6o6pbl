package plotina.gateway.room.backend.fake;

import org.junit.jupiter.api.Test;

import plotina.gateway.room.backend.RoomBackend;
import plotina.gateway.room.backend.RoomSnapshot;
import plotina.gateway.chat.backend.ChatBackend;
import plotina.gateway.chat.ChatService;
import plotina.gateway.room.RoomCommandService;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

class FakeRoomBackendTest {

  @Test
  void fakeShouldReturnSamplesWithoutKeepingRoomState() {
    FakeRoomBackend backend = new FakeRoomBackend();
    RoomSnapshot sample = backend.getSnapshot("demo-room");

    assertEquals(sample, backend.seek("demo-room", "token", "seek", 120));
    assertEquals(sample, backend.addVideo("demo-room", "token", "add", "anything"));
    assertEquals(sample, backend.getSnapshot("demo-room"));
    assertEquals("demo-host-token", backend.createRoom().session().sessionToken());
  }

  @Test
  void roomServiceShouldForwardValuesWithoutBusinessValidation() {
    RoomBackend backend = mock(RoomBackend.class);
    RoomCommandService service = new RoomCommandService(backend);
    RoomSnapshot response = new RoomSnapshot("room-1", 42, true, 0);

    when(backend.addVideo("room-1", "token", "add", "not-a-rutube-link"))
        .thenReturn(response);

    assertEquals(response, service.addVideo("user-1", "room-1", "token", "add", "not-a-rutube-link"));
    service.seek("user-1", "room-1", "token", "seek", -10);
    service.moveVideo("user-1", "room-1", "token", "move", "item", -1);

    verify(backend).seek("room-1", "token", "seek", -10);
    verify(backend).moveVideo("room-1", "token", "move", "item", -1);
  }

  @Test
  void chatServiceShouldLetBackendDecideWhetherBlankTextIsAllowed() {
    ChatBackend backend = mock(ChatBackend.class);
    new ChatService(backend).sendMessage("user-1", "room-1", "token", "chat", "   ");

    verify(backend).sendMessage("room-1", "user-1", "token", "chat", "   ");
  }
}
