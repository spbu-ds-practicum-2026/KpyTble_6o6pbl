package plotina.gateway.backend.fake;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.ArrayList;

import org.springframework.stereotype.Service;

import plotina.gateway.backend.QueueItemNotFoundException;
import plotina.gateway.backend.QueueItem;
import plotina.gateway.backend.RoomBackend;
import plotina.gateway.backend.RoomNotFoundException;
import plotina.gateway.backend.RoomSnapshot;
import plotina.gateway.backend.InvalidQueuePositionException;

@Service
public class FakeRoomBackend implements RoomBackend {

  private final Map<String, RoomSnapshot> rooms = new ConcurrentHashMap<>();

  @Override
  public RoomSnapshot moveVideo(
      String roomId,
      String sessionToken,
      String commandId,
      String itemId,
      int toIndex) {
    return rooms.compute(roomId, (id, current) -> {
      if (current == null) {
        throw new RoomNotFoundException(id);
      }

      var queue = new ArrayList<>(current.queue());

      int fromIndex = -1;

      for (int i = 0; i < queue.size(); i++) {
        if (queue.get(i).itemId().equals(itemId)) {
          fromIndex = i;
          break;
        }
      }

      if (fromIndex == -1) {
        throw new QueueItemNotFoundException(itemId);
      }

      if (toIndex < 0 || toIndex >= queue.size()) {
        throw new InvalidQueuePositionException(toIndex);
      }

      QueueItem item = queue.remove(fromIndex);
      queue.add(toIndex, item);

      return new RoomSnapshot(
          current.roomId(),
          current.version() + 1,
          current.paused(),
          current.positionSeconds(),
          current.currentVideo(),
          queue);
    });
  }

  @Override
  public RoomSnapshot next(
      String roomId,
      String sessionToken,
      String commandId) {
    return rooms.compute(roomId, (id, current) -> {
      if (current == null) {
        throw new RoomNotFoundException(id);
      }

      int nextIndex = 0;

      if (current.currentVideo() != null) {
        int currentIndex = -1;

        for (int i = 0; i < current.queue().size(); i++) {
          if (current.queue().get(i).itemId()
              .equals(current.currentVideo().itemId())) {
            currentIndex = i;
            break;
          }
        }

        if (currentIndex == -1) {
          throw new QueueItemNotFoundException(
              current.currentVideo().itemId());
        }

        nextIndex = currentIndex + 1;
      }

      QueueItem selected = nextIndex < current.queue().size()
          ? current.queue().get(nextIndex)
          : null;

      return new RoomSnapshot(
          current.roomId(),
          current.version() + 1,
          true,
          0.0,
          selected,
          current.queue());
    });
  }

  @Override
  public RoomSnapshot getSnapshot(String roomId) {
    RoomSnapshot snapshot = rooms.get(roomId);
    if (snapshot == null) {
      throw new RoomNotFoundException(roomId);
    }
    return snapshot;
  }

  @Override
  public RoomSnapshot createRoom() {
    String roomId = UUID.randomUUID().toString();

    RoomSnapshot snapshot = new RoomSnapshot(
        roomId,
        1,
        true,
        0.0);

    rooms.put(roomId, snapshot);

    return snapshot;
  }

  @Override
  public RoomSnapshot removeVideo(
      String roomId,
      String sessionToken,
      String commandId,
      String itemId) {
    return rooms.compute(roomId, (id, current) -> {
      if (current == null) {
        throw new RoomNotFoundException(id);
      }

      var queue = new ArrayList<>(current.queue());

      int index = -1;

      for (int i = 0; i < queue.size(); i++) {
        if (queue.get(i).itemId().equals(itemId)) {
          index = i;
          break;
        }
      }

      if (index == -1) {
        throw new QueueItemNotFoundException(itemId);
      }

      boolean removingCurrent = current.currentVideo() != null
          && current.currentVideo().itemId().equals(itemId);

      queue.remove(index);

      QueueItem selected = current.currentVideo();
      boolean paused = current.paused();
      double position = current.positionSeconds();

      if (removingCurrent) {
        selected = index < queue.size()
            ? queue.get(index)
            : null;

        paused = true;
        position = 0.0;
      }

      return new RoomSnapshot(
          current.roomId(),
          current.version() + 1,
          paused,
          position,
          selected,
          queue);
    });
  }

  @Override
  public RoomSnapshot pause(
      String roomId,
      String sessionToken,
      String commandId) {
    return rooms.compute(roomId, (id, current) -> {
      if (current == null) {
        throw new RoomNotFoundException(id);
      }

      return new RoomSnapshot(
          current.roomId(),
          current.version() + 1,
          true,
          current.positionSeconds(),
          current.currentVideo(),
          current.queue());
    });
  }

  @Override
  public RoomSnapshot play(
      String roomId,
      String sessionToken,
      String commandId) {
    return rooms.compute(roomId, (id, current) -> {
      if (current == null) {
        throw new RoomNotFoundException(id);
      }

      return new RoomSnapshot(
          current.roomId(),
          current.version() + 1,
          false,
          current.positionSeconds(),
          current.currentVideo(),
          current.queue());
    });
  }

  @Override
  public RoomSnapshot seek(
      String roomId,
      String sessionToken,
      String commandId,
      double positionSeconds) {
    return rooms.compute(roomId, (id, current) -> {
      if (current == null) {
        throw new RoomNotFoundException(id);
      }

      return new RoomSnapshot(
          current.roomId(),
          current.version() + 1,
          current.paused(),
          positionSeconds,
          current.currentVideo(),
          current.queue());
    });

  }

  @Override
  public RoomSnapshot addVideo(
      String roomId,
      String sessionToken,
      String commandId,
      String url) {
    return rooms.compute(roomId, (id, current) -> {
      if (current == null) {
        throw new RoomNotFoundException(id);
      }

      QueueItem item = new QueueItem(
          UUID.randomUUID().toString(),
          url);

      var queue = new ArrayList<>(current.queue());
      queue.add(item);

      return new RoomSnapshot(
          current.roomId(),
          current.version() + 1,
          current.paused(),
          current.positionSeconds(),
          current.currentVideo(),
          queue);
    });
  }

}
