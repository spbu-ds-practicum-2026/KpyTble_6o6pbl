package plotina.gateway.backend;

public interface RoomBackend {

  RoomSnapshot createRoom();

  RoomSnapshot getSnapshot(String roomId);

  RoomSnapshot pause(
      String roomId,
      String sessionToken,
      String commandId);

}
