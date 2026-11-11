package plotina.gateway.http;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import plotina.gateway.health.HealthService;

@RestController
public class HealthController {

  private final HealthService healthService;

  public HealthController(HealthService healthService) {
    this.healthService = healthService;
  }

  @GetMapping("/health")
  public HealthResponse health() {
    return new HealthResponse(healthService.getStatus());
  }

  public record HealthResponse(String status) {

  }

}
