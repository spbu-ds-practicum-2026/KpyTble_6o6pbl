package plotina.gateway.http;

import java.net.InetSocketAddress;
import java.util.concurrent.atomic.AtomicInteger;
import com.sun.net.httpserver.HttpServer;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ServiceClientTest {
  @Test void internalCallsUseHttp11WithoutUpgrade() throws Exception {
    HttpServer server = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
    var headers = new java.util.concurrent.CompletableFuture<com.sun.net.httpserver.Headers>();
    var protocol = new java.util.concurrent.CompletableFuture<String>();
    server.createContext("/", exchange -> {
      headers.complete(exchange.getRequestHeaders());
      protocol.complete(exchange.getProtocol());
      byte[] body = "{\"ok\":true}".getBytes(java.nio.charset.StandardCharsets.UTF_8);
      exchange.sendResponseHeaders(200, body.length);
      exchange.getResponseBody().write(body);
      exchange.close();
    });
    server.start();
    try {
      String url = "http://localhost:" + server.getAddress().getPort();
      var mapper = new ObjectMapper();
      var client = new ServiceClient(mapper, url, url, 1000);
      client.room("POST", "/rooms", null, mapper.createObjectNode());
      assertEquals("HTTP/1.1", protocol.get());
      assertNull(headers.get().getFirst("Upgrade"));
      assertNull(headers.get().getFirst("HTTP2-Settings"));
    } finally { server.stop(0); }
  }

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
