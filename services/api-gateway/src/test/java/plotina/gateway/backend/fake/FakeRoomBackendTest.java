package plotina.gateway.backend.fake;

import org.junit.jupiter.api.Test;

import plotina.gateway.backend.RoomSnapshot;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class FakeRoomBackendTest {

  @Test
  void shouldPlayAndPauseCreatedRoom() {
    FakeRoomBackend backend = new FakeRoomBackend();

    RoomSnapshot created = backend.createRoom();

    assertTrue(created.paused());

    RoomSnapshot playing = backend.play(
        created.roomId(),
        "test-token",
        "command-play");

    assertFalse(playing.paused());
    assertEquals(created.version() + 1, playing.version());

    RoomSnapshot paused = backend.pause(
        created.roomId(),
        "test-token",
        "command-pause");

    assertTrue(paused.paused());
    assertEquals(playing.version() + 1, paused.version());

    assertEquals(
        paused,
        backend.getSnapshot(created.roomId()));
  }
}
