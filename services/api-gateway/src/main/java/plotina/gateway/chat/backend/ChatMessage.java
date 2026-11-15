package plotina.gateway.chat.backend;

public record ChatMessage(
    String messageId,
    String roomId,
    String userId,
    String text,
    String sentAt) {
}
