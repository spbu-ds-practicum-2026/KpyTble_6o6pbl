package plotina.gateway.http;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.io.IOException;
import java.time.Duration;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/** No automatic mutation retries: a timeout does not imply the command was not committed. */
@Component
public class ServiceClient {
  private final ObjectMapper mapper;
  private final HttpClient client;
  private final String roomUrl;
  private final String chatUrl;
  private final Duration timeout;

  public ServiceClient(ObjectMapper mapper,
      @Value("${gateway.room-service-url:http://localhost:8000}") String roomUrl,
      @Value("${gateway.chat-service-url:http://localhost:8001}") String chatUrl,
      @Value("${gateway.request-timeout-ms:3000}") long timeoutMs) {
    this.mapper = mapper;
    this.roomUrl = roomUrl.replaceAll("/+$", "");
    this.chatUrl = chatUrl.replaceAll("/+$", "");
    this.timeout = Duration.ofMillis(timeoutMs);
    this.client = HttpClient.newBuilder().connectTimeout(timeout).build();
  }

  public JsonNode room(String method, String path, String token, JsonNode body) {
    return request(roomUrl, method, path, token, body);
  }

  public JsonNode chat(String method, String path, String token, JsonNode body) {
    return request(chatUrl, method, path, token, body);
  }

  private JsonNode request(String base, String method, String path, String token, JsonNode body) {
    try {
      HttpRequest.Builder request = HttpRequest.newBuilder(URI.create(base + path))
          .timeout(timeout).header("Accept", "application/json");
      if (token != null) request.header("Authorization", "Bearer " + token);
      if (body != null) request.header("Content-Type", "application/json");
      request.method(method, body == null ? HttpRequest.BodyPublishers.noBody()
          : HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(body)));
      HttpResponse<String> response = client.send(request.build(), HttpResponse.BodyHandlers.ofString());
      JsonNode result;
      try {
        result = mapper.readTree(response.body());
      } catch (IOException exception) {
        throw new GatewayException(502, "bad_gateway", "Service returned invalid JSON");
      }
      if (result == null || !result.isObject()) {
        throw new GatewayException(502, "bad_gateway", "Service returned an invalid response");
      }
      if (response.statusCode() >= 400) {
        JsonNode error = result.path("error");
        if (!error.path("code").isTextual() || !error.path("message").isTextual()) {
          throw new GatewayException(502, "bad_gateway", "Service returned an invalid error");
        }
        throw new GatewayException(response.statusCode(), error);
      }
      if (response.statusCode() < 200 || response.statusCode() >= 300) {
        throw new GatewayException(502, "bad_gateway", "Unexpected service status");
      }
      return result;
    } catch (HttpTimeoutException exception) {
      throw new GatewayException(504, "gateway_timeout", "Service request timed out; retry with the same commandId");
    } catch (InterruptedException exception) {
      Thread.currentThread().interrupt();
      throw new GatewayException(503, "service_unavailable", "Service request interrupted");
    } catch (IOException exception) {
      throw new GatewayException(502, "service_unavailable", "Service is unavailable");
    }
  }
}
