package plotina.gateway.chat.backend.fake;

import org.springframework.stereotype.Service;

import plotina.gateway.chat.backend.ChatBackend;
import plotina.gateway.chat.backend.ChatMessage;

@Service
public class FakeChatBackend implements ChatBackend {

  @Override
  public ChatMessage sendMessage(
      String roomId,
      String userId,
      String sessionToken,
      String commandId,
      String text) {
    return new ChatMessage(
        "demo-message",
        roomId,
        userId,
        text,
        "2026-11-15T12:00:00Z");
  }
}
