package plotina.gateway.session;

import java.util.concurrent.ConcurrentHashMap;
import java.util.Map;
import org.springframework.stereotype.Component;
import plotina.gateway.http.GatewayException;

/** Routing hints issued by create/join, NOT authorization or a source of roles. */
@Component
public class SessionDirectory {
  private final Map<String, String> rooms = new ConcurrentHashMap<>();

  public void remember(String token, String roomId) { rooms.put(token, roomId); }
  public void forget(String token) { rooms.remove(token); }

  public String room(String token) {
    String room = rooms.get(token);
    if (room == null) throw new GatewayException(401, "unauthorized", "Unknown session; create or join a room first");
    return room;
  }
}
