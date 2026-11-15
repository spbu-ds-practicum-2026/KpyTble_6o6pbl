package plotina.gateway.session.backend;

import java.util.Optional;

public interface SessionBackend {

  Optional<SessionInfo> findByToken(String sessionToken);
}
