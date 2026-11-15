package plotina.gateway.websocket;

import java.io.IOException;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

@Component
public class WebSocketSender {

  private final ObjectMapper objectMapper;

  public WebSocketSender(ObjectMapper objectMapper) {
    this.objectMapper = objectMapper;
  }

  public void send(
      WebSocketSession socket,
      ServerMessage message) throws IOException {
    String json = objectMapper.writeValueAsString(message);

    synchronized (socket) {
      socket.sendMessage(new TextMessage(json));
    }
  }
}
