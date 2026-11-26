package plotina.gateway.websocket;

import java.io.IOException;
import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;

@Component
public class RoomBroadcaster {
  private static final Logger log = LoggerFactory.getLogger(RoomBroadcaster.class);
  private final ConnectionRegistry registry;
  private final WebSocketSender sender;

  public RoomBroadcaster(ConnectionRegistry registry, WebSocketSender sender) {
    this.registry = registry;
    this.sender = sender;
  }

  public void broadcast(String roomId, JsonNode message) {
    for (var connection : registry.findByRoom(roomId)) {
      synchronized (connection) {
        if (!connection.socket.isOpen()) {
          registry.remove(connection.socket.getId());
          continue;
        }
        try {
          if (!connection.ready || (!connection.chatReady
              && "sendMessage".equals(message.path("type").asText()))) {
            // Bounded initialization buffer; do not hold this lock during HTTP requests.
            if (connection.pending.size() >= 256) {
              connection.socket.close(CloseStatus.SESSION_NOT_RELIABLE);
              registry.remove(connection.socket.getId());
            } else connection.pending.add(message.deepCopy());
          } else if (!isOldChat(connection, message)) {
            sender.send(connection.socket, message);
          }
        } catch (IOException exception) {
          log.warn("WebSocket delivery failed for connection {}", connection.socket.getId());
          registry.remove(connection.socket.getId());
          try { connection.socket.close(CloseStatus.SERVER_ERROR); } catch (IOException ignored) { }
        }
      }
    }
  }

  static boolean isOldChat(ConnectionRegistry.Connection connection, JsonNode message) {
    return "sendMessage".equals(message.path("type").asText())
        && (!connection.chatReady
            || message.path("message").path("messageSeq").asLong() <= connection.initialSeq);
  }
}
