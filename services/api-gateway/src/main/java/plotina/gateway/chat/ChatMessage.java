package plotina.gateway.chat;

public record ChatMessage(
    String messageId,
    String roomId,
    String userId,
    String text,
    String sentAt) {
}
