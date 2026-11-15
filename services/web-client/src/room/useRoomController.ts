import { useCallback, useEffect, useRef, useState } from "react";
import {
  type ChatMessage,
  type ConnectionStatus,
  type GatewayError,
  type RoomBootstrap,
  type RoomState
} from "../api/protocol";
import { getRoomState } from "../api/restClient";
import { RoomSocket } from "../realtime/RoomSocket";

function parseNumberEnv(
  value: string | undefined,
  fallback: number
): number {
  const parsed = Number(value);

  return Number.isFinite(parsed) && parsed > 0
    ? parsed
    : fallback;
}

function shouldRetryPendingCommands(): boolean {
  return (
    import.meta.env.VITE_RETRY_PENDING_COMMANDS?.toLowerCase() ===
    "true"
  );
}

export function useRoomController(bootstrap: RoomBootstrap) {
  const [state, setState] = useState<RoomState>(bootstrap.state);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("idle");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lastError, setLastError] =
    useState<GatewayError | null>(null);

  const socketRef = useRef<RoomSocket | null>(null);

  const applyState = useCallback((incomingState: RoomState) => {
    setState((currentState) => {
      if (incomingState.roomId !== currentState.roomId) {
        return currentState;
      }

      if (
        incomingState.stateVersion < currentState.stateVersion
      ) {
        return currentState;
      }

      return incomingState;
    });
  }, []);

  const synchronizeState = useCallback(async () => {
    try {
      const actualState = await getRoomState(
        bootstrap.session.roomId,
        bootstrap.session.sessionToken
      );

      applyState(actualState);
    } catch (error) {
      setLastError({
        code: "STATE_SYNC_FAILED",
        message:
          error instanceof Error
            ? error.message
            : "Не удалось получить состояние комнаты"
      });
    }
  }, [applyState, bootstrap.session]);

  useEffect(() => {
    const socket = new RoomSocket({
      session: bootstrap.session,
      retryPendingCommands: shouldRetryPendingCommands(),
      heartbeatIntervalMs: parseNumberEnv(
        import.meta.env.VITE_HEARTBEAT_INTERVAL_MS,
        15_000
      ),
      heartbeatTimeoutMs: parseNumberEnv(
        import.meta.env.VITE_HEARTBEAT_TIMEOUT_MS,
        8_000
      ),
      callbacks: {
        onStatusChange: setConnectionStatus,

        onAuthenticated: () => {
          // В том числе вызывается после reconnect.
          void synchronizeState();
        },

        onRoomState: applyState,

        onChatMessage: (message) => {
          setMessages((currentMessages) => {
            const alreadyExists = currentMessages.some(
              (item) => item.messageId === message.messageId
            );

            if (alreadyExists) {
              return currentMessages;
            }

            // До появления messageSeq используем порядок доставки.
            return [...currentMessages, message];
          });
        },

        onError: setLastError
      }
    });

    socketRef.current = socket;
    socket.connect();

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [applyState, bootstrap.session, synchronizeState]);

  useEffect(() => {
    const intervalMs = parseNumberEnv(
      import.meta.env.VITE_STATE_SYNC_INTERVAL_MS,
      10_000
    );

    const interval = window.setInterval(() => {
      void synchronizeState();
    }, intervalMs);

    return () => {
      window.clearInterval(interval);
    };
  }, [synchronizeState]);

  const requireSocket = useCallback((): RoomSocket => {
    const socket = socketRef.current;

    if (!socket) {
      throw new Error("WebSocket ещё не создан");
    }

    return socket;
  }, []);

  const runCommand = useCallback(
    (command: (socket: RoomSocket) => void) => {
      try {
        setLastError(null);
        command(requireSocket());
      } catch (error) {
        setLastError({
          code: "COMMAND_NOT_SENT",
          message:
            error instanceof Error
              ? error.message
              : "Команда не была отправлена"
        });
      }
    },
    [requireSocket]
  );

  return {
    state,
    messages,
    connectionStatus,
    lastError,
    clearError: () => setLastError(null),
    synchronizeState,

    play: () => runCommand((socket) => socket.play()),
    pause: () => runCommand((socket) => socket.pause()),

    seek: (positionSeconds: number) =>
      runCommand((socket) => socket.seek(positionSeconds)),

    next: () => runCommand((socket) => socket.next()),

    addVideo: (url: string) =>
      runCommand((socket) => socket.addVideo(url)),

    removeVideo: (itemId: string) =>
      runCommand((socket) => socket.removeVideo(itemId)),

    moveVideo: (itemId: string, toIndex: number) =>
      runCommand((socket) => socket.moveVideo(itemId, toIndex)),

    sendChatMessage: (text: string) =>
      runCommand((socket) => socket.sendChatMessage(text))
  };
}