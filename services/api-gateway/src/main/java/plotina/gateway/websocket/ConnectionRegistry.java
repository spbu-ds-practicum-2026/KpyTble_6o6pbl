package plotina.gateway.websocket;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketSession;

@Component
public class ConnectionRegistry {

  private final Map<String, Connection> connections = new ConcurrentHashMap<>();

  public void register(
      WebSocketSession socket,
      String userId,
      String roomId) {
    connections.put(
        socket.getId(),
        new Connection(socket, userId, roomId));
  }

  public void remove(String connectionId) {
    connections.remove(connectionId);
  }

  public List<Connection> findByRoom(String roomId) {
    return connections.values().stream()
        .filter(connection -> connection.roomId().equals(roomId))
        .toList();
  }

  public record Connection(
      WebSocketSession socket,
      String userId,
      String roomId) {
  }
}
