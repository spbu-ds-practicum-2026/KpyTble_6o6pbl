package plotina.gateway.backend.fake;

import org.junit.jupiter.api.Test;

import plotina.gateway.backend.InvalidQueuePositionException;
import plotina.gateway.backend.RoomSnapshot;

import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
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

  @Test
  void shouldMoveVideoToFinalIndex() {
    FakeRoomBackend backend = new FakeRoomBackend();
    String roomId = backend.createRoom().roomId();

    backend.addVideo(
        roomId, "token", "add-1",
        "https://rutube.ru/video/first/");

    RoomSnapshot added = backend.addVideo(
        roomId, "token", "add-2",
        "https://rutube.ru/video/second/");

    String secondId = added.queue().get(1).itemId();

    RoomSnapshot moved = backend.moveVideo(
        roomId, "token", "move-1", secondId, 0);

    assertEquals(secondId, moved.queue().get(0).itemId());
    assertEquals(added.version() + 1, moved.version());

    assertThrows(
        InvalidQueuePositionException.class,
        () -> backend.moveVideo(
            roomId, "token", "move-invalid", secondId, 2));

    assertEquals(moved, backend.getSnapshot(roomId));
  }

  @Test
  void shouldSelectNextVideoAndClearAfterLast() {
    FakeRoomBackend backend = new FakeRoomBackend();
    String roomId = backend.createRoom().roomId();

    backend.addVideo(
        roomId, "token", "add-1",
        "https://rutube.ru/video/first/");

    RoomSnapshot added = backend.addVideo(
        roomId, "token", "add-2",
        "https://rutube.ru/video/second/");

    RoomSnapshot first = backend.next(roomId, "token", "next-1");

    assertEquals(added.queue().get(0), first.currentVideo());
    assertTrue(first.paused());
    assertEquals(0.0, first.positionSeconds());

    RoomSnapshot second = backend.next(roomId, "token", "next-2");

    assertEquals(added.queue().get(1), second.currentVideo());

    RoomSnapshot finished = backend.next(roomId, "token", "next-3");

    assertNull(finished.currentVideo());
    assertTrue(finished.paused());
    assertEquals(0.0, finished.positionSeconds());
    assertEquals(added.queue(), finished.queue());
  }

  @Test
  void shouldSelectNextOnCurrentVideoRemoval() {
    FakeRoomBackend backend = new FakeRoomBackend();
    String roomId = backend.createRoom().roomId();

    backend.addVideo(
        roomId, "token", "add-1",
        "https://rutube.ru/video/first/");

    RoomSnapshot added = backend.addVideo(
        roomId, "token", "add-2",
        "https://rutube.ru/video/second/");

    RoomSnapshot selected = backend.next(
        roomId, "token", "next-1");

    RoomSnapshot removed = backend.removeVideo(
        roomId, "token", "remove-1",
        selected.currentVideo().itemId());

    assertEquals(added.queue().get(1), removed.currentVideo());
    assertTrue(removed.paused());
    assertEquals(0.0, removed.positionSeconds());

    RoomSnapshot empty = backend.removeVideo(
        roomId, "token", "remove-2",
        removed.currentVideo().itemId());

    assertNull(empty.currentVideo());
    assertTrue(empty.paused());
    assertTrue(empty.queue().isEmpty());
  }

  @Test
  void shouldRemoveVideoFromQueue() {
    FakeRoomBackend backend = new FakeRoomBackend();
    RoomSnapshot created = backend.createRoom();

    RoomSnapshot withVideo = backend.addVideo(
        created.roomId(),
        "test-token",
        "command-add",
        "https://rutube.ru/video/example/");

    String itemId = withVideo.queue().get(0).itemId();

    RoomSnapshot updated = backend.removeVideo(
        created.roomId(),
        "test-token",
        "command-remove",
        itemId);

    assertTrue(updated.queue().isEmpty());
    assertEquals(withVideo.version() + 1, updated.version());
    assertEquals(updated, backend.getSnapshot(created.roomId()));
  }

  @Test
  void shouldAddVideoWithoutSelectingIt() {
    FakeRoomBackend backend = new FakeRoomBackend();
    RoomSnapshot created = backend.createRoom();

    RoomSnapshot updated = backend.addVideo(
        created.roomId(),
        "test-token",
        "command-add",
        "https://rutube.ru/video/example/");

    assertEquals(created.version() + 1, updated.version());
    assertEquals(1, updated.queue().size());
    assertEquals(
        "https://rutube.ru/video/example/",
        updated.queue().get(0).url());
    org.junit.jupiter.api.Assertions.assertNull(
        updated.currentVideo());
    assertEquals(
        updated,
        backend.getSnapshot(created.roomId()));
  }

}
