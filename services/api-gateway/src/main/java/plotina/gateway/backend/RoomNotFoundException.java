package plotina.gateway.backend;

public class RoomNotFoundException extends RuntimeException {

  public RoomNotFoundException(String roomId) {
    super("Room not found: " + roomId);
  }

}
