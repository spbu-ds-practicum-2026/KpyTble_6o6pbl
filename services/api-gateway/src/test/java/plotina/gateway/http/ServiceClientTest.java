package plotina.gateway.http;

import java.net.InetSocketAddress;
import java.util.concurrent.atomic.AtomicInteger;
import com.sun.net.httpserver.HttpServer;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ServiceClientTest {
  @Test void timeoutDoesNotRetryMutation() throws Exception {
    HttpServer server = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
    AtomicInteger requests = new AtomicInteger();
    server.createContext("/", exchange -> {
      requests.incrementAndGet();
      try { Thread.sleep(300); } catch (InterruptedException exception) { Thread.currentThread().interrupt(); }
      exchange.close();
    });
    server.start();
    try {
      String url = "http://localhost:" + server.getAddress().getPort();
      var mapper = new ObjectMapper();
      var client = new ServiceClient(mapper, url, url, 100);
      GatewayException error = assertThrows(GatewayException.class,
          () -> client.room("POST", "/commands", "token", mapper.createObjectNode().put("command_id", "same")));
      assertEquals(504, error.status());
      assertEquals("gateway_timeout", error.error().path("code").asText());
      assertEquals(1, requests.get());
    } finally { server.stop(0); }
  }

  @Test void invalidJsonIsBadGateway() throws Exception {
    HttpServer server = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
    server.createContext("/", exchange -> {
      byte[] body = "not JSON".getBytes();
      exchange.sendResponseHeaders(200, body.length);
      exchange.getResponseBody().write(body);
      exchange.close();
    });
    server.start();
    try {
      String url = "http://localhost:" + server.getAddress().getPort();
      var client = new ServiceClient(new ObjectMapper(), url, url, 1000);
      var error = assertThrows(GatewayException.class, () -> client.room("GET", "/rooms/a", "token", null));
      assertEquals(502, error.status());
      assertEquals("bad_gateway", error.error().path("code").asText());
    } finally { server.stop(0); }
  }
}
