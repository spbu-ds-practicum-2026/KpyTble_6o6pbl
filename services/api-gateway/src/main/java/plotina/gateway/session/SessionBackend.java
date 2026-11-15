package plotina.gateway.session;

import java.util.Optional;

public interface SessionBackend {

  SessionInfo createSession(String roomId);

  Optional<SessionInfo> findByToken(String sessionToken);
}
