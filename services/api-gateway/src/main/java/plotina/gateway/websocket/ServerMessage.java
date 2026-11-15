package plotina.gateway.websocket;

public record ServerMessage(
    String type,
    String requestId,
    Object payload) {
}
