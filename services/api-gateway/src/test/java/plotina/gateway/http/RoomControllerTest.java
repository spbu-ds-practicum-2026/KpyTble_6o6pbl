package plotina.gateway.http;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

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

}
