package plotina.gateway.session.fake;

import java.security.SecureRandom;
import java.util.Base64;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.stereotype.Service;

import plotina.gateway.session.SessionBackend;
import plotina.gateway.session.SessionInfo;

@Service
public class FakeSessionBackend implements SessionBackend {

  private final Map<String, SessionInfo> sessions = new ConcurrentHashMap<>();

  private final SecureRandom secureRandom = new SecureRandom();

  @Override
  public SessionInfo createSession(String roomId) {
    byte[] tokenBytes = new byte[32];
    secureRandom.nextBytes(tokenBytes);

    String token = Base64.getUrlEncoder()
        .withoutPadding()
        .encodeToString(tokenBytes);
    SessionInfo session = new SessionInfo(
        token,
        UUID.randomUUID().toString(),
        roomId);
    sessions.put(token, session);
    return session;
  }

  @Override
  public Optional<SessionInfo> findByToken(String sessionToken) {
    if (sessionToken == null || sessionToken.isBlank()) {
      return Optional.empty();
    }

    return Optional.ofNullable(sessions.get(sessionToken));
  }

}
