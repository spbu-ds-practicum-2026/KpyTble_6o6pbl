package plotina.gateway.http;

import java.util.Arrays;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/** The same explicit browser origins are used for REST and WebSocket handshakes. */
@Configuration
public class BrowserAccessConfig implements WebMvcConfigurer {
  private final String[] origins;

  public BrowserAccessConfig(@Value("${gateway.allowed-origins:http://localhost:3000}") String origins) {
    this.origins = Arrays.stream(origins.split(","))
        .map(String::trim).filter(value -> !value.isEmpty()).toArray(String[]::new);
  }

  public String[] allowedOrigins() { return origins.clone(); }

  @Override
  public void addCorsMappings(CorsRegistry registry) {
    registry.addMapping("/rooms/**")
        .allowedOrigins(origins)
        .allowedMethods("POST", "OPTIONS")
        .allowedHeaders("Content-Type", "Authorization")
        .maxAge(3600);
  }
}
