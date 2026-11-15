package plotina.gateway.health;

import org.springframework.stereotype.Service;

@Service
public class HealthService {

  public String getStatus() {
    return "ok";
  }

}
