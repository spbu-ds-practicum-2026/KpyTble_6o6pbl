package plotina.gateway.session.backend;

public record SessionInfo(
    String sessionToken,
    String userId,
    String roomId) {
}
