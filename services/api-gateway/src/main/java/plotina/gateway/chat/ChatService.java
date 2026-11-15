package plotina.gateway.chat;

import plotina.gateway.chat.backend.ChatBackend;
import plotina.gateway.chat.backend.ChatMessage;

import org.springframework.stereotype.Service;

@Service
public class ChatService {
  private final ChatBackend backend;

  public ChatService(ChatBackend backend) {
    this.backend = backend;
  }

  public ChatMessage sendMessage(String userId, String roomId, String token, String commandId, String text) {
    return backend.sendMessage(roomId, userId, token, commandId, text);
  }
}
