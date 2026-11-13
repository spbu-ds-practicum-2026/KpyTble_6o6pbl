package plotina.gateway.http;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.hamcrest.Matchers.emptyOrNullString;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;

@SpringBootTest
@AutoConfigureMockMvc
class RoomControllerTest {

  private final MockMvc mockMvc;

  @Autowired
  RoomControllerTest(MockMvc mockMvc) {
    this.mockMvc = mockMvc;
  }

  @Test
  void shouldReturnRoomState() throws Exception {
    mockMvc.perform(get("/rooms/demo/state"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.roomId").value("demo"))
        .andExpect(jsonPath("$.version").value(1))
        .andExpect(jsonPath("$.paused").value(true))
        .andExpect(jsonPath("$.positionSeconds").value(0.0));
  }

  @Test
  void shouldCreateRoom() throws Exception {
    mockMvc.perform(post("/rooms"))
        .andExpect(status().isCreated())
        .andExpect(header().exists("Location"))
        .andExpect(jsonPath("$.roomId").value(not(emptyOrNullString())))
        .andExpect(jsonPath("$.version").value(1))
        .andExpect(jsonPath("$.positionSeconds").value(0.0));
  }

}
