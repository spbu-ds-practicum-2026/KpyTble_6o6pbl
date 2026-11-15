package plotina.gateway.websocket;

import com.fasterxml.jackson.databind.JsonNode;

public record ClientMessage(
    String type,
    String requestId,
    JsonNode payload) {
}
