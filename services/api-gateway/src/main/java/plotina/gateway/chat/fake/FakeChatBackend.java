package plotina.gateway.chat.fake;

import java.time.Instant;
import java.util.UUID;

import org.springframework.stereotype.Service;

import plotina.gateway.chat.ChatBackend;
import plotina.gateway.chat.ChatMessage;

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
        UUID.randomUUID().toString(),
        roomId,
        userId,
        text,
        Instant.now().toString());
  }
}
