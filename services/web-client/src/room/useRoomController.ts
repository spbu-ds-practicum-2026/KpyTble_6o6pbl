import { useCallback, useEffect, useRef, useState } from "react";
import {
  type ChatMessage,
  type CommandConfirmMessage,
  type ConnectionStatus,
  type GatewayError,
  type QueueItem,
  type RoomBootstrap,
  type RoomState,
  normalizeChatMessage,
  normalizeRoomState
} from "../api/protocol";
import { RoomSocket } from "../realtime/RoomSocket";
import { DEMO_MESSAGES } from "./demoBootstrap";

interface UseRoomControllerOptions {
  onLeft?: () => void;
}

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
    import.meta.env.VITE_RETRY_PENDING_COMMANDS?.toLowerCase() !==
    "false"
  );
}

function toGatewayError(
  error: unknown,
  fallbackCode: string,
  fallbackMessage: string
): GatewayError {
  if (error instanceof Error) {
    return {
      code: fallbackCode,
      message: error.message || fallbackMessage
    };
  }

  return { code: fallbackCode, message: fallbackMessage };
}

export function useRoomController(
  bootstrap: RoomBootstrap,
  options: UseRoomControllerOptions = {}
) {
  const demo = bootstrap.demo === true;
  const demoMessages = demo ? DEMO_MESSAGES : [];

  const [state, setState] = useState<RoomState>(bootstrap.state);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>(demo ? "connected" : "idle");
  const [messages, setMessages] = useState<ChatMessage[]>([
    ...demoMessages
  ]);
  const [chatGap, setChatGap] = useState<number | null>(null);
  const [lastError, setLastError] =
    useState<GatewayError | null>(null);
  const [pendingChat, setPendingChat] = useState(false);
  const [leaving, setLeaving] = useState(false);

  const socketRef = useRef<RoomSocket | null>(null);
  const stateRef = useRef(bootstrap.state);
  const messagesRef = useRef<ChatMessage[]>([...demoMessages]);
  const bufferRef = useRef<Map<number, ChatMessage>>(new Map());
  const expectedSeqRef = useRef<number | null>(
    demo
      ? Math.max(
          ...demoMessages.map((message) => message.messageSeq),
          0
        ) + 1
      : null
  );
  const pendingChatCommandRef = useRef<string | null>(null);
  const leavingCommandRef = useRef<string | null>(null);
  const onLeftRef = useRef(options.onLeft);

  onLeftRef.current = options.onLeft;

  const bumpState = useCallback((patch: Partial<RoomState>): void => {
    const current = stateRef.current;
    const next: RoomState = {
      ...current,
      ...patch,
      stateVersion: current.stateVersion + 1
    };

    stateRef.current = next;
    setState(next);
  }, []);

  const publishMessages = useCallback(() => {
    setMessages([...messagesRef.current]);
  }, []);

  const updateChatGap = useCallback(() => {
    setChatGap(
      expectedSeqRef.current !== null && bufferRef.current.size > 0
        ? expectedSeqRef.current
        : null
    );
  }, []);

  const drainBuffer = useCallback(() => {
    const expected = expectedSeqRef.current;

    if (expected === null) {
      return;
    }

    let next = expected;
    let changed = false;

    while (bufferRef.current.has(next)) {
      const message = bufferRef.current.get(next)!;
      bufferRef.current.delete(next);
      messagesRef.current.push(message);
      next += 1;
      changed = true;
    }

    if (changed) {
      expectedSeqRef.current = next;
      publishMessages();
    }

    updateChatGap();
  }, [publishMessages, updateChatGap]);

  const acceptMessage = useCallback(
    (message: ChatMessage) => {
      const expected = expectedSeqRef.current;

      if (expected !== null && message.messageSeq < expected) {
        return;
      }

      if (bufferRef.current.has(message.messageSeq)) {
        return;
      }

      if (
        messagesRef.current.some(
          (item) =>
            item.messageId === message.messageId ||
            item.messageSeq === message.messageSeq
        )
      ) {
        return;
      }

      bufferRef.current.set(message.messageSeq, message);
      drainBuffer();
    },
    [drainBuffer]
  );

  const resetChat = useCallback(
    (initialMessageSeq: number | null) => {
      messagesRef.current = [];
      bufferRef.current.clear();
      expectedSeqRef.current =
        initialMessageSeq === null ? null : initialMessageSeq + 1;
      publishMessages();
      updateChatGap();
    },
    [publishMessages, updateChatGap]
  );

  const handleChatSeq = useCallback(
    (sequence: number) => {
      if (!Number.isInteger(sequence)) {
        return;
      }

      if (expectedSeqRef.current === null) {
        expectedSeqRef.current = sequence + 1;
        drainBuffer();
        return;
      }

      if (
        sequence >= expectedSeqRef.current &&
        bufferRef.current.size > 0
      ) {
        updateChatGap();
      }
    },
    [drainBuffer, updateChatGap]
  );

  const applyState = useCallback((incoming: RoomState) => {
    const current = stateRef.current;

    if (incoming.stateVersion < current.stateVersion) {
      return;
    }

    stateRef.current = incoming;
    setState(incoming);
  }, []);

  const handleCommandConfirm = useCallback(
    (confirm: CommandConfirmMessage) => {
      if (confirm.error) {
        setLastError({
          code: confirm.error.code,
          message: confirm.error.message
        });
      }

      if (confirm.state) {
        try {
          applyState(
            normalizeRoomState(
              confirm.state,
              bootstrap.session.roomId
            )
          );
        } catch (error) {
          setLastError(
            toGatewayError(
              error,
              "INVALID_ROOM_STATE",
              "Некорректное состояние комнаты"
            )
          );
        }
      }

      if (confirm.message) {
        try {
          acceptMessage(normalizeChatMessage(confirm.message));
        } catch (error) {
          setLastError(
            toGatewayError(
              error,
              "INVALID_CHAT_MESSAGE",
              "Некорректное сообщение чата"
            )
          );
        }
      }

      if (typeof confirm.messageSeq === "number") {
        handleChatSeq(confirm.messageSeq);
      }

      if (confirm.left === true) {
        leavingCommandRef.current = null;
        setLeaving(false);
        onLeftRef.current?.();
        return;
      }

      if (
        confirm.commandId &&
        pendingChatCommandRef.current === confirm.commandId
      ) {
        pendingChatCommandRef.current = null;
        setPendingChat(false);
      }

      if (
        confirm.commandId &&
        leavingCommandRef.current === confirm.commandId
      ) {
        leavingCommandRef.current = null;
        setLeaving(false);
      }
    },
    [
      acceptMessage,
      applyState,
      bootstrap.session.roomId,
      handleChatSeq
    ]
  );

  const requireSocket = useCallback((): RoomSocket => {
    const socket = socketRef.current;

    if (!socket) {
      throw new Error("WebSocket ещё не создан");
    }

    return socket;
  }, []);

  const synchronizeState = useCallback((): void => {
    if (demo) {
      return;
    }

    try {
      requireSocket().getState();
    } catch (error) {
      setLastError(
        toGatewayError(
          error,
          "STATE_SYNC_FAILED",
          "Не удалось запросить состояние комнаты"
        )
      );
    }
  }, [demo, requireSocket]);

  useEffect(() => {
    if (demo) {
      setConnectionStatus("connected");
      return;
    }

    const socket = new RoomSocket({
      session: bootstrap.session,
      retryPendingCommands: shouldRetryPendingCommands(),
      heartbeatTimeoutMs: parseNumberEnv(
        import.meta.env.VITE_HEARTBEAT_TIMEOUT_MS,
        20_000
      ),
      callbacks: {
        onStatusChange: setConnectionStatus,

        onConnected: () => {
          socket.getState();
          socket.getChatSeq();
        },

        onRoomState: (incoming, initialMessageSeq) => {
          applyState(incoming);

          if (initialMessageSeq !== undefined) {
            resetChat(initialMessageSeq);
          }
        },

        onChatMessage: acceptMessage,
        onCommandConfirm: handleCommandConfirm,
        onError: setLastError
      }
    });

    socketRef.current = socket;
    socket.connect();

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [
    acceptMessage,
    applyState,
    bootstrap.session,
    demo,
    handleCommandConfirm,
    resetChat
  ]);

  useEffect(() => {
    if (demo) {
      return;
    }

    const intervalMs = parseNumberEnv(
      import.meta.env.VITE_STATE_SYNC_INTERVAL_MS,
      10_000
    );

    const interval = window.setInterval(() => {
      synchronizeState();
      socketRef.current?.getChatSeq();
    }, intervalMs);

    return () => {
      window.clearInterval(interval);
    };
  }, [demo, synchronizeState]);

  const run = useCallback(
    (
      localAction: () => void,
      socketCommand?: (socket: RoomSocket) => void
    ): boolean => {
      try {
        setLastError(null);

        if (demo) {
          localAction();
          return true;
        }

        if (!socketCommand) {
          throw new Error("Действие недоступно без Gateway");
        }

        socketCommand(requireSocket());
        return true;
      } catch (error) {
        setLastError(
          toGatewayError(
            error,
            "COMMAND_NOT_SENT",
            "Команда не была отправлена"
          )
        );
        return false;
      }
    },
    [demo, requireSocket]
  );

  const canControl =
    connectionStatus === "connected" &&
    state.status === "active" &&
    (bootstrap.session.role === "host" ||
      state.controlMode === "all");

  const canSetSettings =
    connectionStatus === "connected" &&
    state.status === "active" &&
    bootstrap.session.role === "host";

  return {
    state,
    messages,
    chatGap,
    connectionStatus,
    lastError,
    pendingChat,
    leaving,
    role: bootstrap.session.role,
    canControl,
    canSetSettings,
    clearError: () => setLastError(null),
    synchronizeState,

    playpause: () =>
      run(
        () => {
          const current = stateRef.current;

          bumpState({
            playback: {
              ...current.playback,
              isPlaying: !current.playback.isPlaying
            }
          });
        },
        (socket) => {
          socket.playpause();
        }
      ),

    nextVideo: () =>
      run(
        () => {
          const current = stateRef.current;
          const index = current.queue.findIndex(
            (item) => item.id === current.currentVideoId
          );
          const next = current.queue.length
            ? current.queue[(index + 1) % current.queue.length]
            : null;

          bumpState({
            currentVideoId: next?.id ?? null,
            playback: {
              videoId: next?.id ?? null,
              positionSeconds: 0,
              isPlaying: next !== null
            }
          });
        },
        (socket) => {
          socket.nextVideo();
        }
      ),

    seek: (positionSeconds: number) =>
      run(
        () => {
          const current = stateRef.current;

          bumpState({
            playback: {
              ...current.playback,
              positionSeconds
            }
          });
        },
        (socket) => {
          socket.seek(positionSeconds);
        }
      ),

    addVideo: (url: string) =>
      run(
        () => {
          const current = stateRef.current;
          const id = `demo-video-${Date.now()}`;
          const queue = [
            ...current.queue,
            { id, url, position: current.queue.length }
          ];
          const isFirst = current.currentVideoId === null;

          bumpState({
            queue,
            currentVideoId: isFirst ? id : current.currentVideoId,
            playback: isFirst
              ? {
                  videoId: id,
                  positionSeconds: 0,
                  isPlaying: current.playback.isPlaying
                }
              : current.playback
          });
        },
        (socket) => {
          socket.addVideo(url);
        }
      ),

    removeVideo: (videoId: string) =>
      run(
        () => {
          const current = stateRef.current;
          const queue: QueueItem[] = current.queue
            .filter((item) => item.id !== videoId)
            .map((item, index) => ({ ...item, position: index }));
          const currentRemoved = current.currentVideoId === videoId;
          const nextCurrent = currentRemoved
            ? queue[0]?.id ?? null
            : current.currentVideoId;

          bumpState({
            queue,
            currentVideoId: nextCurrent,
            playback: currentRemoved
              ? {
                  videoId: nextCurrent,
                  positionSeconds: 0,
                  isPlaying:
                    nextCurrent !== null && current.playback.isPlaying
                }
              : current.playback
          });
        },
        (socket) => {
          socket.removeVideo(videoId);
        }
      ),

    changeQueue: (videoIds: string[]) =>
      run(
        () => {
          const current = stateRef.current;
          const byId = new Map(
            current.queue.map((item) => [item.id, item])
          );
          const queue: QueueItem[] = [];

          for (const id of videoIds) {
            const item = byId.get(id);

            if (item) {
              queue.push({ ...item, position: queue.length });
            }
          }

          bumpState({ queue });
        },
        (socket) => {
          socket.changeQueue(videoIds);
        }
      ),

    setSettings: (mode: "host_only" | "all") =>
      run(
        () => {
          bumpState({ controlMode: mode });
        },
        (socket) => {
          socket.setSettings(mode);
        }
      ),

    sendChatMessage: (text: string) =>
      run(
        () => {
          const nextSeq = expectedSeqRef.current ?? 1;

          acceptMessage({
            messageId: `demo-message-${nextSeq}-${Date.now()}`,
            messageSeq: nextSeq,
            participantId: bootstrap.session.displayName,
            text,
            createdAt: new Date().toISOString()
          });
        },
        (socket) => {
          if (pendingChatCommandRef.current) {
            throw new Error(
              "Предыдущее сообщение ещё не подтверждено"
            );
          }

          const commandId = socket.sendMessage(text);
          pendingChatCommandRef.current = commandId;
          setPendingChat(true);
        }
      ),

    leaveRoom: () =>
      run(
        () => {
          onLeftRef.current?.();
        },
        (socket) => {
          const commandId = socket.leaveRoom();
          leavingCommandRef.current = commandId;
          setLeaving(true);
        }
      )
  };
}
