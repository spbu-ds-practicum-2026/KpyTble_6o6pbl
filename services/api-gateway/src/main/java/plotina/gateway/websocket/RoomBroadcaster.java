package plotina.gateway.websocket;

import java.io.IOException;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketSession;

@Component
public class RoomBroadcaster {

    private static final Logger log =
        LoggerFactory.getLogger(RoomBroadcaster.class);

    private final ConnectionRegistry connectionRegistry;
    private final WebSocketSender sender;

    public RoomBroadcaster(
        ConnectionRegistry connectionRegistry,
        WebSocketSender sender
    ) {
        this.connectionRegistry = connectionRegistry;
        this.sender = sender;
    }

    public void broadcast(
        String roomId,
        ServerMessage message
    ) {
        for (ConnectionRegistry.Connection connection
            : connectionRegistry.findByRoom(roomId)) {

            WebSocketSession socket = connection.socket();

            if (!socket.isOpen()) {
                connectionRegistry.remove(socket.getId());
                continue;
            }

            try {
                sender.send(socket, message);
            } catch (IOException exception) {
                log.warn(
                    "Failed to send WebSocket message to connection {}",
                    socket.getId()
                );
            }
        }
    }
}
