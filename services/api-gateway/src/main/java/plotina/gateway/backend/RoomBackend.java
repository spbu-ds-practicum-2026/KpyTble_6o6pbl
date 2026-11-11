package plotina.gateway.backend;

public interface RoomBackend {

  RoomSnapshot getSnapshot(String roomId);

}
