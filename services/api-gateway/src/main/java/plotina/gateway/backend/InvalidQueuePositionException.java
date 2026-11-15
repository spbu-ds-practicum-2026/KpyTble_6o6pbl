package plotina.gateway.backend;

public class InvalidQueuePositionException extends RuntimeException {

  public InvalidQueuePositionException(int index) {
    super("Queue position is out of range: " + index);
  }
}
