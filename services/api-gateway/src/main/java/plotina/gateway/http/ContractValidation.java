package plotina.gateway.http;

import java.util.HashSet;
import java.util.Set;
import com.fasterxml.jackson.databind.JsonNode;

public final class ContractValidation {
  private ContractValidation() {}

  public static void fields(JsonNode node, String... fields) {
    if (node == null || !node.isObject()) invalid("Expected a JSON object");
    Set<String> expected = Set.of(fields);
    node.fieldNames().forEachRemaining(field -> {
      if (!expected.contains(field)) invalid("Unexpected field: " + field);
    });
    for (String field : fields) {
      if (!node.has(field)) invalid("Missing field: " + field);
    }
  }

  public static String text(JsonNode node, String field) {
    JsonNode value = node.path(field);
    if (!value.isTextual() || value.asText().isBlank()) invalid("Expected a non-empty string: " + field);
    return value.asText();
  }

  public static void mode(JsonNode node, String field) {
    if (!Set.of("host_only", "all").contains(text(node, field))) invalid("Invalid control mode");
  }

  public static void payload(String type, JsonNode payload) {
    switch (type) {
      case "seek" -> {
        fields(payload, "position_seconds");
        JsonNode position = payload.path("position_seconds");
        if (!position.isNumber() || !Double.isFinite(position.asDouble()) || position.asDouble() < 0) {
          invalid("position_seconds must be a finite non-negative number");
        }
      }
      case "addVideo" -> { fields(payload, "url"); text(payload, "url"); }
      case "removeVideo" -> { fields(payload, "video_id"); text(payload, "video_id"); }
      case "sendMessage" -> { fields(payload, "text"); text(payload, "text"); }
      case "setSettings" -> { fields(payload, "mode"); mode(payload, "mode"); }
      case "changeQueue" -> {
        fields(payload, "video_ids");
        JsonNode ids = payload.path("video_ids");
        if (!ids.isArray()) invalid("video_ids must be an array");
        Set<String> seen = new HashSet<>();
        for (JsonNode id : ids) {
          if (!id.isTextual() || id.asText().isBlank() || !seen.add(id.asText())) {
            invalid("video_ids must contain unique non-empty strings");
          }
        }
      }
      default -> fields(payload);
    }
  }

  public static void invalid(String message) { throw new GatewayException(422, "invalid_payload", message); }
}
