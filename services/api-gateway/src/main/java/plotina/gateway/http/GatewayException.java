package plotina.gateway.http;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.JsonNodeFactory;

public class GatewayException extends RuntimeException {
  private final int status;
  private final JsonNode error;

  public GatewayException(int status, String code, String message) {
    this(status, JsonNodeFactory.instance.objectNode().put("code", code).put("message", message));
  }

  public GatewayException(int status, JsonNode error) {
    super(error.path("message").asText());
    this.status = status;
    this.error = error.deepCopy();
  }

  public int status() { return status; }
  public JsonNode error() { return error; }
}
