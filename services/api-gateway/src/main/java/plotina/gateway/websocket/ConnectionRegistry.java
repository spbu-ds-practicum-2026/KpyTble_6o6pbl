package plotina.gateway.websocket;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketSession;
import plotina.gateway.http.GatewayException;

@Component
public class ConnectionRegistry {
  private final Map<String, Connection> connections = new ConcurrentHashMap<>();

  public void register(WebSocketSession socket) {
    connections.put(socket.getId(), new Connection(socket));
  }

  public Connection get(String id) { return connections.get(id); }
  public void remove(String id) { connections.remove(id); }
  public List<Connection> all() { return List.copyOf(connections.values()); }
  public synchronized void bind(Connection connection, String room, String token) {
    if (connections.values().stream().anyMatch(c -> c != connection && token.equals(c.token))) {
      throw new GatewayException(401, "unauthorized", "Session already has an active connection");
    }
    connection.token = token;
    connection.roomId = room;
  }
  public List<Connection> findByRoom(String roomId) {
    return connections.values().stream().filter(c -> roomId.equals(c.roomId)).toList();
  }

  public static class Connection {
    final WebSocketSession socket;
    volatile String token;
    volatile String roomId;
    volatile boolean ready;
    volatile boolean chatReady;
    volatile String pigId;
    volatile long pigSentAt;
    final long openedAt = System.currentTimeMillis();
    // Accessed under this connection's monitor, including during initialization.
    final java.util.List<com.fasterxml.jackson.databind.JsonNode> pending = new java.util.ArrayList<>();
    long initialSeq;

    Connection(WebSocketSession socket) { this.socket = socket; }
    public WebSocketSession socket() { return socket; }
  }
}
