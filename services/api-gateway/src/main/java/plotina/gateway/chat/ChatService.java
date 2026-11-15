package plotina.gateway.chat;

import org.springframework.stereotype.Service;

import plotina.gateway.command.CommandRejectedException;
import plotina.gateway.session.SessionBackend;
import plotina.gateway.session.SessionInfo;

@Service
public class ChatService {

  private final SessionBackend sessionBackend;
  private final ChatBackend chatBackend;

  public ChatService(
      SessionBackend sessionBackend,
      ChatBackend chatBackend) {
    this.sessionBackend = sessionBackend;
    this.chatBackend = chatBackend;
  }

  public ChatMessage sendMessage(
      String connectionUserId,
      String connectionRoomId,
      String sessionToken,
      String commandId,
      String text) {
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

    if (text == null || text.isBlank()) {
      throw new CommandRejectedException(
          "INVALID_MESSAGE",
          "Message text must not be blank");
    }

    return chatBackend.sendMessage(
        connectionRoomId,
        connectionUserId,
        sessionToken,
        commandId,
        text);
  }
}
