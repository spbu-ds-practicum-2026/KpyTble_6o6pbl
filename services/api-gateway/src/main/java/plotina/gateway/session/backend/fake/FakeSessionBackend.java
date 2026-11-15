package plotina.gateway.session.backend.fake;

import java.util.Optional;

import org.springframework.stereotype.Service;

import plotina.gateway.session.backend.SessionBackend;
import plotina.gateway.session.backend.SessionInfo;

@Service
public class FakeSessionBackend implements SessionBackend {

  @Override
  public Optional<SessionInfo> findByToken(String token) {
    if ("demo-host-token".equals(token)) {
      return Optional.of(new SessionInfo(token, "demo-host", "demo-room"));
    }
    if ("demo-guest-token".equals(token)) {
      return Optional.of(new SessionInfo(token, "demo-guest", "demo-room"));
    }
    return Optional.empty();
  }
}
