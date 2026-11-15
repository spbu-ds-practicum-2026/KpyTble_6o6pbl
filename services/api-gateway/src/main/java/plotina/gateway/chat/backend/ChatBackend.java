package plotina.gateway.chat.backend;

public interface ChatBackend {

  ChatMessage sendMessage(
      String roomId,
      String userId,
      String sessionToken,
      String commandId,
      String text);
}
