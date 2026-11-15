package plotina.gateway.command;

import org.springframework.stereotype.Service;

import plotina.gateway.backend.RoomBackend;
import plotina.gateway.backend.RoomSnapshot;
import plotina.gateway.session.SessionBackend;
import plotina.gateway.session.SessionInfo;

@Service
public class RoomCommandService {

  private final RoomBackend roomBackend;
  private final SessionBackend sessionBackend;

  public RoomCommandService(
      RoomBackend roomBackend,
      SessionBackend sessionBackend) {
    this.roomBackend = roomBackend;
    this.sessionBackend = sessionBackend;
  }

  public RoomSnapshot pause(
      String connectionUserId,
      String connectionRoomId,
      String sessionToken,
      String commandId) {
    verifySession(
        connectionUserId,
        connectionRoomId,
        sessionToken);

    return roomBackend.pause(
        connectionRoomId,
        sessionToken,
        commandId);
  }

  public RoomSnapshot seek(
      String connectionUserId,
      String connectionRoomId,
      String sessionToken,
      String commandId,
      double positionSeconds) {
    verifySession(
        connectionUserId,
        connectionRoomId,
        sessionToken);

    if (!Double.isFinite(positionSeconds) || positionSeconds < 0) {
      throw new CommandRejectedException(
          "INVALID_MESSAGE",
          "Position must be a finite non-negative number");
    }

    return roomBackend.seek(
        connectionRoomId,
        sessionToken,
        commandId,
        positionSeconds);
  }

  public RoomSnapshot executePlayback(
      String type,
      String connectionUserId,
      String connectionRoomId,
      String sessionToken,
      String commandId) {
    return switch (type) {
      case "playback.play" -> play(
          connectionUserId,
          connectionRoomId,
          sessionToken,
          commandId);

      case "playback.pause" -> pause(
          connectionUserId,
          connectionRoomId,
          sessionToken,
          commandId);

      default -> throw new CommandRejectedException(
          "UNKNOWN_MESSAGE_TYPE",
          "Unsupported playback command");
    };
  }

  public RoomSnapshot play(
      String connectionUserId,
      String connectionRoomId,
      String sessionToken,
      String commandId) {
    verifySession(
        connectionUserId,
        connectionRoomId,
        sessionToken);

    return roomBackend.play(
        connectionRoomId,
        sessionToken,
        commandId);
  }

  private void verifySession(
      String connectionUserId,
      String connectionRoomId,
      String sessionToken) {
    SessionInfo identity = sessionBackend
        .findByToken(sessionToken)
        .orElseThrow(() -> new CommandRejectedException(
            "UNAUTHORIZED",
            "Valid session is required"));

    if (!connectionUserId.equals(identity.userId())
        || !connectionRoomId.equals(identity.roomId())) {
      throw new CommandRejectedException(
          "FORBIDDEN",
          "Command session does not match the connection");
    }
  }
}
