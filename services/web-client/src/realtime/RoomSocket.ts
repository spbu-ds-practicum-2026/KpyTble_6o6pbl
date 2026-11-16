import {
  type ChatMessage,
  type CommandAck,
  type ConnectionStatus,
  type GatewayEnvelope,
  type GatewayError,
  type GatewayRoomState,
  type RoomState,
  type Session,
  type SessionAuthenticated,
  normalizeRoomState
} from "../api/protocol";

interface RoomSocketCallbacks {
  onStatusChange?: (status: ConnectionStatus) => void;
  onAuthenticated?: (payload: SessionAuthenticated) => void;
  onRoomState?: (state: RoomState) => void;
  onChatMessage?: (message: ChatMessage) => void;
  onCommandAck?: (ack: CommandAck) => void;
  onError?: (error: GatewayError) => void;
}

interface PendingCommand {
  commandId: string;
  envelope: GatewayEnvelope<Record<string, unknown>>;
}

interface RoomSocketOptions {
  session: Session;
  callbacks?: RoomSocketCallbacks;
  retryPendingCommands?: boolean;
  heartbeatIntervalMs?: number;
  heartbeatTimeoutMs?: number;
}

const MIN_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 15000;

function createId(): string {
  return crypto.randomUUID();
}

function getDefaultWsUrl(): string {
  const configuredUrl = import.meta.env.VITE_WS_URL?.trim();

  if (configuredUrl) {
    return configuredUrl;
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws`;
}

export class RoomSocket {
  private readonly session: Session;
  private readonly callbacks: RoomSocketCallbacks;
  private readonly retryPendingCommands: boolean;
  private readonly heartbeatIntervalMs: number;
  private readonly heartbeatTimeoutMs: number;

  private socket: WebSocket | null = null;
  private manuallyClosed = false;
  private authenticated = false;

  private reconnectAttempt = 0;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private heartbeatTimeoutTimer: number | null = null;

  private readonly pendingCommands = new Map<string, PendingCommand>();
  private readonly commandByRequestId = new Map<string, string>();

  constructor(options: RoomSocketOptions) {
    this.session = options.session;
    this.callbacks = options.callbacks ?? {};
    this.retryPendingCommands =
      options.retryPendingCommands ?? false;
    this.heartbeatIntervalMs =
      options.heartbeatIntervalMs ?? 15_000;
    this.heartbeatTimeoutMs =
      options.heartbeatTimeoutMs ?? 8_000;
  }

  connect(): void {
    if (
      this.socket?.readyState === WebSocket.OPEN ||
      this.socket?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    this.manuallyClosed = false;
    this.authenticated = false;

    this.setStatus(
      this.reconnectAttempt === 0 ? "connecting" : "reconnecting"
    );

    const socket = new WebSocket(getDefaultWsUrl());
    this.socket = socket;

    socket.addEventListener("open", () => {
      if (socket !== this.socket) {
        return;
      }

      this.setStatus("authenticating");

      this.sendEnvelope({
        type: "session.authenticate",
        requestId: createId(),
        payload: {
          sessionToken: this.session.sessionToken
        }
      });
    });

    socket.addEventListener("message", (event) => {
      if (socket !== this.socket) {
        return;
      }

      this.handleMessage(event.data);
    });

    socket.addEventListener("error", () => {
      this.callbacks.onError?.({
        code: "WEBSOCKET_ERROR",
        message: "Ошибка WebSocket-соединения"
      });
    });

    socket.addEventListener("close", () => {
      if (socket !== this.socket) {
        return;
      }

      this.socket = null;
      this.authenticated = false;
      this.stopHeartbeat();

      if (this.manuallyClosed) {
        this.setStatus("disconnected");
        return;
      }

      this.scheduleReconnect();
    });
  }

  close(): void {
    this.manuallyClosed = true;
    this.authenticated = false;

    this.clearReconnectTimer();
    this.stopHeartbeat();

    this.socket?.close(1000, "Client closed connection");
    this.socket = null;

    this.setStatus("disconnected");
  }

  play(): string {
    return this.sendCommand("playback.play");
  }

  pause(): string {
    return this.sendCommand("playback.pause");
  }

  seek(positionSeconds: number): string {
    return this.sendCommand("playback.seek", {
      positionSeconds
    });
  }

  next(): string {
    return this.sendCommand("playback.next");
  }

  addVideo(url: string): string {
    return this.sendCommand("queue.add", { url });
  }

  removeVideo(itemId: string): string {
    return this.sendCommand("queue.remove", { itemId });
  }

  moveVideo(itemId: string, toIndex: number): string {
    return this.sendCommand("queue.move", {
      itemId,
      toIndex
    });
  }

  sendChatMessage(text: string): string {
    return this.sendCommand("chat.send", { text });
  }

  private sendCommand(
    type: string,
    data: Record<string, unknown> = {}
  ): string {
    if (!this.authenticated) {
      throw new Error("WebSocket is not authenticated");
    }

    const requestId = createId();
    const commandId = createId();

    const envelope: GatewayEnvelope<Record<string, unknown>> = {
      type,
      requestId,
      payload: {
        sessionToken: this.session.sessionToken,
        commandId,
        ...data
      }
    };

    this.pendingCommands.set(commandId, {
      commandId,
      envelope
    });

    this.commandByRequestId.set(requestId, commandId);
    this.sendEnvelope(envelope);

    return commandId;
  }

  private sendEnvelope(envelope: GatewayEnvelope): void {
    if (this.socket?.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not open");
    }

    this.socket.send(JSON.stringify(envelope));
  }

  private handleMessage(rawMessage: unknown): void {
    let envelope: GatewayEnvelope;

    try {
      envelope = JSON.parse(String(rawMessage)) as GatewayEnvelope;
    } catch {
      this.callbacks.onError?.({
        code: "INVALID_SERVER_MESSAGE",
        message: "Gateway вернул некорректный JSON"
      });
      return;
    }

    switch (envelope.type) {
      case "pong":
        this.clearHeartbeatTimeout();
        return;

      case "session.authenticated":
        this.handleAuthenticated(
          envelope.payload as SessionAuthenticated
        );
        return;

      case "room.state":
        this.handleRoomState(envelope.payload as GatewayRoomState);
        return;

      case "chat.message":
        this.callbacks.onChatMessage?.(
          envelope.payload as ChatMessage
        );
        return;

      case "command.ack":
        this.handleCommandAck(envelope.payload as CommandAck);
        return;

      case "error":
        this.handleError(
          envelope.requestId,
          envelope.payload as GatewayError
        );
        return;

      default:
        this.callbacks.onError?.({
          code: "UNKNOWN_SERVER_MESSAGE",
          message: `Неизвестный тип сообщения: ${envelope.type}`
        });
    }
  }

  private handleAuthenticated(
    payload: SessionAuthenticated
  ): void {
    if (
      payload.roomId !== this.session.roomId ||
      payload.userId !== this.session.userId
    ) {
      this.callbacks.onError?.({
        code: "SESSION_MISMATCH",
        message: "Gateway вернул другую привязку сессии"
      });

      this.socket?.close(1008, "Session mismatch");
      return;
    }

    this.authenticated = true;
    this.reconnectAttempt = 0;
    this.setStatus("connected");
    this.startHeartbeat();

    this.callbacks.onAuthenticated?.(payload);

    if (this.retryPendingCommands) {
      this.resendPendingCommands();
    }
  }

  private handleRoomState(payload: GatewayRoomState): void {
    try {
      this.callbacks.onRoomState?.(
        normalizeRoomState(payload)
      );
    } catch (error) {
      this.callbacks.onError?.({
        code: "INVALID_ROOM_STATE",
        message:
          error instanceof Error
            ? error.message
            : "Некорректное состояние комнаты"
      });
    }
  }

  private handleCommandAck(ack: CommandAck): void {
    if (typeof ack.commandId === "string") {
      this.pendingCommands.delete(ack.commandId);

      for (const [requestId, commandId] of this.commandByRequestId) {
        if (commandId === ack.commandId) {
          this.commandByRequestId.delete(requestId);
        }
      }
    }

    this.callbacks.onCommandAck?.(ack);
  }

  private handleError(
    requestId: string | null,
    error: GatewayError
  ): void {
    if (requestId) {
      const commandId = this.commandByRequestId.get(requestId);

      if (commandId) {
        // Отклонённую сервером команду повторять нельзя.
        this.pendingCommands.delete(commandId);
        this.commandByRequestId.delete(requestId);
      }
    }

    this.callbacks.onError?.(error);
  }

  private resendPendingCommands(): void {
    for (const pending of this.pendingCommands.values()) {
      const newRequestId = createId();

      const repeatedEnvelope: GatewayEnvelope<Record<string, unknown>> = {
        ...pending.envelope,
        requestId: newRequestId
      };

      pending.envelope = repeatedEnvelope;
      this.commandByRequestId.set(
        newRequestId,
        pending.commandId
      );

      this.sendEnvelope(repeatedEnvelope);
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();

    this.heartbeatTimer = window.setInterval(() => {
      if (
        !this.authenticated ||
        this.socket?.readyState !== WebSocket.OPEN
      ) {
        return;
      }

      const requestId = createId();

      try {
        this.sendEnvelope({
          type: "ping",
          requestId,
          payload: {}
        });

        this.clearHeartbeatTimeout();

        this.heartbeatTimeoutTimer = window.setTimeout(() => {
          this.callbacks.onError?.({
            code: "HEARTBEAT_TIMEOUT",
            message: "Gateway не ответил на heartbeat"
          });

          this.socket?.close(4000, "Heartbeat timeout");
        }, this.heartbeatTimeoutMs);
      } catch {
        this.socket?.close();
      }
    }, this.heartbeatIntervalMs);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      window.clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }

    this.clearHeartbeatTimeout();
  }

  private clearHeartbeatTimeout(): void {
    if (this.heartbeatTimeoutTimer !== null) {
      window.clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();

    const exponentialDelay =
      MIN_RECONNECT_DELAY_MS * 2 ** this.reconnectAttempt;

    const delay = Math.min(
      exponentialDelay,
      MAX_RECONNECT_DELAY_MS
    );

    this.reconnectAttempt += 1;
    this.setStatus("reconnecting");

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private setStatus(status: ConnectionStatus): void {
    this.callbacks.onStatusChange?.(status);
  }
}