package plotina.gateway.backend;

public interface RoomBackend {

  RoomSnapshot createRoom();

  RoomSnapshot getSnapshot(String roomId);

}
