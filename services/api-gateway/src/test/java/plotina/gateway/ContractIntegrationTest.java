package plotina.gateway;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.*;
import java.util.List;
import java.util.Map;
import java.util.concurrent.*;
import com.sun.net.httpserver.HttpServer;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import static org.junit.jupiter.api.Assertions.*;

/** Real Gateway HTTP and WebSocket sockets; upstream HTTP fixtures implement the contract only. */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
    "gateway.state-refresh-ms=3600000", "gateway.heartbeat-interval-ms=3600000"})
class ContractIntegrationTest {
  static final ObjectMapper JSON = new ObjectMapper();
  static final List<Call> calls = new CopyOnWriteArrayList<>();
  static final HttpServer room = fixture(false);
  static final HttpServer chat = fixture(true);
  static volatile String failureCode;
  static volatile boolean duplicate;
  static final String STATE = """
      {"status":"active","control_mode":"host_only","state_version":3,
       "current_video_id":null,"playback":{"video_id":null,"position_seconds":0,"is_playing":false},
       "queue":[],"participants":[{"display_name":"Alice","role":"host","connected":true}]}
      """;
  @LocalServerPort int port;
  @Autowired ObjectMapper mapper;
  final HttpClient client = HttpClient.newHttpClient();

  @DynamicPropertySource
  static void properties(DynamicPropertyRegistry registry) {
    registry.add("gateway.room-service-url", () -> "http://localhost:" + room.getAddress().getPort());
    registry.add("gateway.chat-service-url", () -> "http://localhost:" + chat.getAddress().getPort());
  }

  static HttpServer fixture(boolean isChat) {
    try {
      HttpServer server = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
      server.createContext("/", exchange -> {
        String body = new String(exchange.getRequestBody().readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
        String path = exchange.getRequestURI().getPath();
        calls.add(new Call(isChat, exchange.getRequestMethod(), path,
            exchange.getRequestHeaders().getFirst("Authorization"), body));
        int status = 200;
        String response;
        if (path.endsWith("/commands") && failureCode != null) {
          status = 403;
          response = "{\"error\":{\"code\":\"" + failureCode + "\",\"message\":\"Rejected\"}}";
        } else if (path.equals("/rooms") || path.equals("/rooms/join")) {
          status = 201;
          String name = JSON.readTree(body).path("display_name").asText();
          response = "{\"room_id\":\"room-1\",\"invite_code\":\"invite\","
              + "\"invite_link\":\"http://localhost:3000/rooms/invite\",\"token\":\"" + name
              + "-token\",\"participant\":{\"display_name\":\"" + name
              + "\",\"role\":\"host\",\"connected\":true},\"state\":" + STATE + "}";
        } else if ("Bearer invalid".equals(exchange.getRequestHeaders().getFirst("Authorization"))) {
          status = 401;
          response = "{\"error\":{\"code\":\"unauthorized\",\"message\":\"Invalid token\"}}";
        } else if (path.endsWith("/messages/seq")) response = "{\"messageSeq\":42}";
        else if (path.endsWith("/commands")) {
          response = "{\"command_id\":\"" + JSON.readTree(body).path("command_id").asText()
              + "\",\"duplicate\":" + duplicate + ",\"state\":" + STATE + "}";
        } else if (path.endsWith("/messages")) {
          response = "{\"command_id\":\"cmd-1\",\"duplicate\":" + duplicate
              + ",\"message\":{\"message_id\":\"message-1\",\"messageSeq\":43,"
              + "\"participant_id\":\"participant-1\",\"text\":\"Привет!\",\"created_at\":\"2026-11-19T12:00:00Z\"}}";
        } else if (path.endsWith("/leave")) response = "{\"left\":true}";
        else response = STATE;
        byte[] bytes = response.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, bytes.length);
        exchange.getResponseBody().write(bytes);
        exchange.close();
      });
      server.start();
      return server;
    } catch (IOException exception) { throw new ExceptionInInitializerError(exception); }
  }

  @BeforeEach void reset() { calls.clear(); duplicate = false; failureCode = null; }
  @AfterAll static void stopFixtures() { room.stop(0); chat.stop(0); }

  HttpResponse<String> post(String path, String body) throws Exception {
    return client.send(HttpRequest.newBuilder(URI.create("http://localhost:" + port + path))
        .header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofString(body)).build(),
        HttpResponse.BodyHandlers.ofString());
  }

  void create(String name) throws Exception {
    assertEquals(201, post("/rooms", "{\"display_name\":\"" + name + "\",\"control_mode\":\"host_only\"}").statusCode());
  }

  @Test void createAndJoinMatchContract() throws Exception {
    var response = post("/rooms", "{\"display_name\":\"Alice\",\"control_mode\":\"host_only\"}");
    assertEquals(201, response.statusCode());
    JsonNode body = mapper.readTree(response.body());
    assertEquals("Alice-token", body.path("token").asText());
    assertEquals(mapper.readTree(STATE), body.path("state"));
    assertNull(calls.getFirst().auth());
    response = post("/rooms/join", "{\"invite_code\":\"invite\",\"display_name\":\"Bob\"}");
    assertEquals(201, response.statusCode());
    assertEquals("Bob-token", mapper.readTree(response.body()).path("token").asText());
    assertEquals("/rooms/join", calls.getLast().path());
  }

  @Test void malformedRestUsesContractError() throws Exception {
    for (String body : List.of("{", "{}", "{\"display_name\":\"A\",\"control_mode\":\"admin\"}")) {
      var response = post("/rooms", body);
      assertEquals(422, response.statusCode());
      assertEquals("invalid_payload", mapper.readTree(response.body()).path("error").path("code").asText());
    }
    assertTrue(calls.isEmpty());
  }

  @ParameterizedTest
  @CsvSource(delimiter = '|', value = {
      "playpause|playpause|{}", "nextVideo|next|{}", "seek|seek|{\"position_seconds\":30}",
      "addVideo|add_video|{\"url\":\"https://rutube.ru/video/abc123/\"}",
      "removeVideo|remove_video|{\"video_id\":\"video-1\"}",
      "changeQueue|change_queue|{\"video_ids\":[\"video-2\",\"video-1\"]}",
      "setSettings|set_control_mode|{\"mode\":\"all\"}"})
  void routesEveryRoomCommand(String type, String upstreamType, String payload) throws Exception {
    create(type);
    try (Peer peer = connect()) {
      peer.send(command(type, type + "-token", payload));
      JsonNode initial = peer.take();
      assertEquals("sendState", initial.path("type").asText());
      assertEquals(42, initial.path("initialMessageSeq").asInt());
      JsonNode ack = peer.take();
      assertEquals("commandConfirm", ack.path("type").asText());
      assertEquals("cmd-1", ack.path("commandId").asText());
      assertFalse(ack.path("duplicate").asBoolean());
      assertEquals(mapper.readTree(STATE), ack.path("state"));
      JsonNode broadcast = peer.take();
      assertEquals("sendState", broadcast.path("type").asText());
      assertFalse(broadcast.has("commandId"));
      assertFalse(broadcast.has("token"));
      Call call = calls.stream().filter(c -> c.path().endsWith("/commands")).findFirst().orElseThrow();
      assertEquals("POST", call.method());
      assertEquals("Bearer " + type + "-token", call.auth());
      assertEquals(mapper.readTree("{\"command_id\":\"cmd-1\",\"type\":\"" + upstreamType
          + "\",\"payload\":" + payload + "}"), mapper.readTree(call.body()));
    }
  }

  @Test void readsHaveNoCommandIdAndReconnectGetsNewBaseline() throws Exception {
    create("reader");
    for (int attempt = 0; attempt < 2; attempt++) {
      try (Peer peer = connect()) {
        peer.send("{\"type\":\"getState\",\"token\":\"reader-token\",\"payload\":{}}");
        assertEquals(42, peer.take().path("initialMessageSeq").asInt());
        peer.send("{\"type\":\"getChatSeq\",\"token\":\"reader-token\",\"payload\":{}}");
        JsonNode result = peer.take();
        assertEquals(mapper.readTree("{\"type\":\"commandConfirm\",\"messageSeq\":42}"), result);
        peer.send("{\"type\":\"getState\",\"token\":\"reader-token\",\"payload\":{}}");
        result = peer.take();
        assertEquals("sendState", result.path("type").asText());
        assertFalse(result.has("initialMessageSeq"));
      }
    }
  }

  @Test void chatBroadcastIncludesAuthorAndDuplicateKeepsSequence() throws Exception {
    create("writer");
    try (Peer peer = connect()) {
      peer.send(command("sendMessage", "writer-token", "{\"text\":\"Привет!\"}"));
      peer.take();
      JsonNode ack = peer.take();
      JsonNode broadcast = peer.take();
      assertEquals(43, ack.path("message").path("messageSeq").asInt());
      assertEquals("sendMessage", broadcast.path("type").asText());
      assertEquals(ack.path("message"), broadcast.path("message"));
      Call call = calls.stream().filter(c -> c.path().endsWith("/messages")).findFirst().orElseThrow();
      assertEquals("Bearer writer-token", call.auth());
      assertEquals(mapper.readTree("{\"command_id\":\"cmd-1\",\"text\":\"Привет!\"}"), mapper.readTree(call.body()));
      duplicate = true;
      peer.send(command("sendMessage", "writer-token", "{\"text\":\"Привет!\"}"));
      assertTrue(peer.take().path("duplicate").asBoolean());
      assertEquals(broadcast, peer.take());
    }
  }

  @Test void backendRejectionAndDuplicateStateAreNotBroadcast() throws Exception {
    create("retry");
    try (Peer peer = connect()) {
      peer.send("{\"type\":\"getState\",\"token\":\"retry-token\",\"payload\":{}}");
      peer.take();
      failureCode = "host_only_mode";
      peer.send(command("playpause", "retry-token", "{}"));
      assertEquals(mapper.readTree("{\"type\":\"commandConfirm\",\"commandId\":\"cmd-1\","
          + "\"error\":{\"code\":\"host_only_mode\",\"message\":\"Rejected\"}}"), peer.take());
      failureCode = null;
      duplicate = true;
      peer.send(command("playpause", "retry-token", "{}"));
      assertTrue(peer.take().path("duplicate").asBoolean());
      assertNull(peer.messages.poll(150, TimeUnit.MILLISECONDS));
    }
  }

  @Test void invalidMessagesNeverReachServices() throws Exception {
    try (Peer peer = connect()) {
      for (String request : List.of("{", "[]", "null",
          command("seek", "unknown", "{\"position_seconds\":\"30\"}"),
          command("addVideo", "unknown", "{\"url\":\"u\",\"title\":\"forbidden\"}"),
          command("changeQueue", "unknown", "{\"video_ids\":[\"v\",\"v\"]}"),
          command("playpause", "unknown", "{}"))) {
        peer.send(request);
        assertTrue(peer.take().has("error"));
      }
      assertTrue(calls.isEmpty());
    }
  }

  @Test void stateBroadcastReachesAnotherMemberWithoutCommandIdOrToken() throws Exception {
    create("host-broadcast");
    create("member-broadcast");
    try (Peer host = connect(); Peer member = connect()) {
      host.send("{\"type\":\"getState\",\"token\":\"host-broadcast-token\",\"payload\":{}}");
      host.take();
      member.send("{\"type\":\"getState\",\"token\":\"member-broadcast-token\",\"payload\":{}}");
      member.take();
      host.send(command("playpause", "host-broadcast-token", "{}"));
      assertEquals("commandConfirm", host.take().path("type").asText());
      JsonNode event = member.take();
      assertEquals("sendState", event.path("type").asText());
      assertEquals(mapper.readTree(STATE), event.path("state"));
      assertFalse(event.has("commandId"));
      assertFalse(event.has("token"));
      assertEquals(event, host.take());
    }
  }

  @Test void cannotSwitchTokenOrOpenTwoConnectionsWithSameToken() throws Exception {
    create("locked-session");
    create("other-session");
    try (Peer first = connect(); Peer second = connect()) {
      first.send("{\"type\":\"getState\",\"token\":\"locked-session-token\",\"payload\":{}}");
      first.take();
      calls.clear();
      first.send(command("playpause", "other-session-token", "{}"));
      assertEquals("unauthorized", first.take().path("error").path("code").asText());
      second.send("{\"type\":\"getState\",\"token\":\"locked-session-token\",\"payload\":{}}");
      assertEquals("unauthorized", second.take().path("error").path("code").asText());
      assertTrue(calls.isEmpty());
    }
  }

  @Test void leaveHasNoBodyAndClosesSocket() throws Exception {
    create("leaver");
    try (Peer peer = connect()) {
      peer.send(command("leaveRoom", "leaver-token", "{}"));
      peer.take();
      assertEquals(mapper.readTree("{\"type\":\"commandConfirm\",\"commandId\":\"cmd-1\",\"left\":true}"), peer.take());
      assertEquals(1000, peer.closed.get(3, TimeUnit.SECONDS));
      Call call = calls.stream().filter(c -> c.path().endsWith("/leave")).findFirst().orElseThrow();
      assertEquals("", call.body());
      assertEquals("Bearer leaver-token", call.auth());
    }
  }

  Peer connect() { return new Peer(client, "ws://localhost:" + port + "/ws"); }
  static String command(String type, String token, String payload) {
    return "{\"type\":\"" + type + "\",\"commandId\":\"cmd-1\",\"token\":\"" + token + "\",\"payload\":" + payload + "}";
  }
  record Call(boolean chat, String method, String path, String auth, String body) {}

  static class Peer implements WebSocket.Listener, AutoCloseable {
    final BlockingQueue<JsonNode> messages = new LinkedBlockingQueue<>();
    final CompletableFuture<Integer> closed = new CompletableFuture<>();
    final StringBuilder buffer = new StringBuilder();
    final WebSocket socket;
    Peer(HttpClient client, String url) { socket = client.newWebSocketBuilder().buildAsync(URI.create(url), this).join(); }
    @Override public void onOpen(WebSocket socket) { socket.request(1); }
    @Override public CompletionStage<?> onText(WebSocket socket, CharSequence text, boolean last) {
      buffer.append(text);
      if (last) {
        try { messages.add(JSON.readTree(buffer.toString())); }
        catch (IOException exception) { throw new RuntimeException(exception); }
        buffer.setLength(0);
      }
      socket.request(1);
      return null;
    }
    @Override public CompletionStage<?> onClose(WebSocket socket, int status, String reason) {
      closed.complete(status);
      return null;
    }
    void send(String text) { socket.sendText(text, true).join(); }
    JsonNode take() throws Exception {
      JsonNode message = messages.poll(5, TimeUnit.SECONDS);
      assertNotNull(message, "Expected a WebSocket message");
      return message;
    }
    @Override public void close() throws Exception {
      if (!socket.isOutputClosed()) socket.sendClose(1000, "test done").join();
      closed.get(3, TimeUnit.SECONDS);
    }
  }
}
