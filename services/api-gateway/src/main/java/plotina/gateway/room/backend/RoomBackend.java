package plotina.gateway.room.backend;

import plotina.gateway.room.RoomEntryService.RoomEntryResult;

public interface RoomBackend {

  RoomEntryResult createRoom();

  RoomEntryResult joinRoom(String roomId);

  RoomSnapshot getSnapshot(String roomId);

  RoomSnapshot pause(
      String roomId,
      String sessionToken,
      String commandId);

  RoomSnapshot play(
      String roomId,
      String sessionToken,
      String commandId);

  RoomSnapshot seek(
      String roomId,
      String sessionToken,
      String commandId,
      double positionSeconds);

  RoomSnapshot addVideo(
      String roomId,
      String sessionToken,
      String commandId,
      String url);

  RoomSnapshot removeVideo(
      String roomId,
      String sessionToken,
      String commandId,
      String itemId);

  RoomSnapshot moveVideo(
      String roomId,
      String sessionToken,
      String commandId,
      String itemId,
      int toIndex);

  RoomSnapshot next(
      String roomId,
      String sessionToken,
      String commandId);

}
