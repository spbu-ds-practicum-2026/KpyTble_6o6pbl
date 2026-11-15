package plotina.gateway.room.backend;

public class QueueItemNotFoundException extends RuntimeException {

  public QueueItemNotFoundException(String itemId) {
    super("Queue item not found: " + itemId);
  }
}
