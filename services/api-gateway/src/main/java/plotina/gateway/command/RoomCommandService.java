package plotina.gateway.command;

import org.springframework.stereotype.Service;

import plotina.gateway.backend.RoomBackend;
import plotina.gateway.backend.RoomSnapshot;
import plotina.gateway.session.SessionBackend;
import plotina.gateway.session.SessionInfo;

import java.net.URI;

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

  public RoomSnapshot addVideo(
      String connectionUserId,
      String connectionRoomId,
      String sessionToken,
      String commandId,
      String url) {
    verifySession(
        connectionUserId,
        connectionRoomId,
        sessionToken);

    if (url == null || url.isBlank()) {
      throw new CommandRejectedException(
          "INVALID_MESSAGE",
          "Video URL must be a non-empty string");
    }

    URI uri;

    try {
      uri = URI.create(url);
    } catch (IllegalArgumentException exception) {
      throw new CommandRejectedException(
          "INVALID_MESSAGE",
          "Invalid video URL");
    }

    if (!"https".equalsIgnoreCase(uri.getScheme())
        || !"rutube.ru".equalsIgnoreCase(uri.getHost())
        || uri.getRawUserInfo() != null
        || (uri.getPort() != -1 && uri.getPort() != 443)
        || uri.getPath() == null
        || !uri.getPath().startsWith("/video/")
        || uri.getPath().length() <= "/video/".length()) {
      throw new CommandRejectedException(
          "INVALID_MESSAGE",
          "Expected an HTTPS Rutube video URL");
    }

    return roomBackend.addVideo(
        connectionRoomId,
        sessionToken,
        commandId,
        url);
  }

  public RoomSnapshot removeVideo(
      String connectionUserId,
      String connectionRoomId,
      String sessionToken,
      String commandId,
      String itemId) {
    verifySession(
        connectionUserId,
        connectionRoomId,
        sessionToken);

    if (itemId == null || itemId.isBlank()) {
      throw new CommandRejectedException(
          "INVALID_MESSAGE",
          "Queue item ID must be a non-empty string");
    }

    return roomBackend.removeVideo(
        connectionRoomId,
        sessionToken,
        commandId,
        itemId);
  }

  public RoomSnapshot moveVideo(
      String connectionUserId,
      String connectionRoomId,
      String sessionToken,
      String commandId,
      String itemId,
      int toIndex) {
    verifySession(
        connectionUserId,
        connectionRoomId,
        sessionToken);

    if (itemId == null || itemId.isBlank() || toIndex < 0) {
      throw new CommandRejectedException(
          "INVALID_MESSAGE",
          "Item ID is required and position must be non-negative");
    }

    return roomBackend.moveVideo(
        connectionRoomId,
        sessionToken,
        commandId,
        itemId,
        toIndex);
  }

  public RoomSnapshot next(
      String connectionUserId,
      String connectionRoomId,
      String sessionToken,
      String commandId) {
    verifySession(
        connectionUserId,
        connectionRoomId,
        sessionToken);

    return roomBackend.next(
        connectionRoomId,
        sessionToken,
        commandId);
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
