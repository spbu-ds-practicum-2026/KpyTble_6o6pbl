package plotina.gateway.http;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.hamcrest.Matchers.emptyOrNullString;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

@SpringBootTest
@AutoConfigureMockMvc
class RoomControllerTest {

  private final MockMvc mockMvc;
  private final ObjectMapper objectMapper;

  @Autowired
  RoomControllerTest(MockMvc mockMvc, ObjectMapper objectMapper) {
    this.mockMvc = mockMvc;
    this.objectMapper = objectMapper;
  }

  @Test
  void shouldReturnRoomState() throws Exception {

    MvcResult creationResult = mockMvc.perform(post("/rooms"))
        .andExpect(status().isCreated())
        .andReturn();

    String responseBody = creationResult.getResponse().getContentAsString();

    String roomId = objectMapper
        .readTree(responseBody)
        .get("roomId")
        .asText();

    mockMvc.perform(get("/rooms/{roomId}/state", roomId))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.roomId").value(roomId))
        .andExpect(jsonPath("$.version").value(1))
        .andExpect(jsonPath("$.paused").value(true))
        .andExpect(jsonPath("$.positionSeconds").value(0.0));
  }

  @Test
  void shouldCreateRoom() throws Exception {
    MvcResult result = mockMvc.perform(post("/rooms"))
        .andExpect(status().isCreated())
        .andExpect(header().exists("Location"))
        .andExpect(jsonPath("$.roomId").value(
            not(emptyOrNullString())))
        .andExpect(jsonPath("$.version").value(1))
        .andExpect(jsonPath("$.paused").value(true))
        .andExpect(jsonPath("$.positionSeconds").value(0.0))
        .andExpect(jsonPath("$.session.sessionToken").value(
            not(emptyOrNullString())))
        .andExpect(jsonPath("$.session.userId").value(
            not(emptyOrNullString())))
        .andReturn();

    JsonNode body = objectMapper.readTree(
        result.getResponse().getContentAsString());

    String roomId = body.path("roomId").asText();

    assertEquals(
        roomId,
        body.path("session").path("roomId").asText());

    assertEquals(
        "/rooms/" + roomId + "/state",
        result.getResponse().getHeader("Location"));
  }

  @Test
  void shouldReturnNotFoundForUnknownRoom() throws Exception {
    mockMvc.perform(get("/rooms/unknown/state"))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("ROOM_NOT_FOUND"))
        .andExpect(jsonPath("$.message").value("Room not found: unknown"));
  }

  @Test
  void shouldJoinExistingRoomWithNewSession() throws Exception {
    MvcResult creationResult = mockMvc.perform(post("/rooms"))
        .andExpect(status().isCreated())
        .andReturn();

    JsonNode creationBody = objectMapper.readTree(
        creationResult.getResponse().getContentAsString());

    String roomId = creationBody.path("roomId").asText();
    String creatorToken = creationBody
        .path("session")
        .path("sessionToken")
        .asText();
    String creatorUserId = creationBody
        .path("session")
        .path("userId")
        .asText();

    MvcResult joinResult = mockMvc
        .perform(post("/rooms/{roomId}/join", roomId))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.state.roomId").value(roomId))
        .andExpect(jsonPath("$.session.roomId").value(roomId))
        .andExpect(jsonPath("$.session.sessionToken").value(
            not(emptyOrNullString())))
        .andExpect(jsonPath("$.session.userId").value(
            not(emptyOrNullString())))
        .andReturn();

    JsonNode joinBody = objectMapper.readTree(
        joinResult.getResponse().getContentAsString());

    String participantToken = joinBody
        .path("session")
        .path("sessionToken")
        .asText();
    String participantUserId = joinBody
        .path("session")
        .path("userId")
        .asText();

    assertNotEquals(creatorToken, participantToken);
    assertNotEquals(creatorUserId, participantUserId);
  }

  @Test
  void shouldRejectJoiningUnknownRoom() throws Exception {
    mockMvc.perform(post("/rooms/unknown/join"))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.code").value("ROOM_NOT_FOUND"));
  }

}
