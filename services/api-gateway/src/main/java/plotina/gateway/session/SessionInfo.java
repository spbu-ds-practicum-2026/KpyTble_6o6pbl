package plotina.gateway.session;

public record SessionInfo(
    String sessionToken,
    String userId,
    String roomId) {
}
