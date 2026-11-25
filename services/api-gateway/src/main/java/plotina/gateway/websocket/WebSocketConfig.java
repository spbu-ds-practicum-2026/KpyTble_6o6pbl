package plotina.gateway.websocket;

import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;
import plotina.gateway.http.BrowserAccessConfig;

@Configuration
@EnableWebSocket
@EnableScheduling
public class WebSocketConfig implements WebSocketConfigurer {

  private final GatewayWebSocketHandler handler;
  private final BrowserAccessConfig browserAccess;

  public WebSocketConfig(GatewayWebSocketHandler handler, BrowserAccessConfig browserAccess) {
    this.handler = handler;
    this.browserAccess = browserAccess;
  }

  @Override
  public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
    registry.addHandler(handler, "/ws").setAllowedOrigins(browserAccess.allowedOrigins());
  }

}
