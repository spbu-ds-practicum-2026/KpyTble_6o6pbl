import {
  type ChatMessage,
  type CommandConfirmMessage,
  type ConnectionStatus,
  type GatewayError,
  type RoomState,
  type ServerMessage,
  type Session,
  normalizeChatMessage,
  normalizeRoomState
} from "../api/protocol";

interface PendingCommand {
  commandId: string;
  type: string;
  payload: Record<string, unknown>;
}

interface RoomSocketCallbacks {
  onStatusChange?: (status: ConnectionStatus) => void;
  onConnected?: () => void;
  onRoomState?: (
    state: RoomState,
    initialMessageSeq?: number
  ) => void;
  onChatMessage?: (message: ChatMessage) => void;
  onCommandConfirm?: (confirm: CommandConfirmMessage) => void;
  onError?: (error: GatewayError) => void;
}

interface RoomSocketOptions {
  session: Session;
  callbacks?: RoomSocketCallbacks;
  retryPendingCommands?: boolean;
  heartbeatTimeoutMs?: number;
}

const MIN_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 15000;

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
  private readonly heartbeatTimeoutMs: number;

  private socket: WebSocket | null = null;
  private manuallyClosed = false;

  private reconnectAttempt = 0;
  private reconnectTimer: number | null = null;
  private pigTimeoutTimer: number | null = null;

  private readonly pendingCommands = new Map<
    string,
    PendingCommand
  >();

  constructor(options: RoomSocketOptions) {
    this.session = options.session;
    this.callbacks = options.callbacks ?? {};
    this.retryPendingCommands =
      options.retryPendingCommands ?? true;
    this.heartbeatTimeoutMs =
      options.heartbeatTimeoutMs ?? 20_000;
  }

  connect(): void {
    if (
      this.socket?.readyState === WebSocket.OPEN ||
      this.socket?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    this.manuallyClosed = false;

    this.setStatus(
      this.reconnectAttempt === 0 ? "connecting" : "reconnecting"
    );

    const socket = new WebSocket(getDefaultWsUrl());
    this.socket = socket;

    socket.addEventListener("open", () => {
      if (socket !== this.socket) {
        return;
      }

      this.reconnectAttempt = 0;
      this.setStatus("connected");
      this.resetPigWatchdog();

      if (this.retryPendingCommands) {
        this.resendPendingCommands();
      }

      this.callbacks.onConnected?.();
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
      this.clearPigWatchdog();

      if (this.manuallyClosed) {
        this.setStatus("disconnected");
        return;
      }

      this.scheduleReconnect();
    });
  }

  close(): void {
    this.manuallyClosed = true;

    this.clearReconnectTimer();
    this.clearPigWatchdog();

    this.socket?.close(1000, "Client closed connection");
    this.socket = null;

    this.setStatus("disconnected");
  }

  playpause(): string {
    return this.sendCommand("playpause", {});
  }

  nextVideo(): string {
    return this.sendCommand("nextVideo", {});
  }

  seek(positionSeconds: number): string {
    return this.sendCommand("seek", {
      position_seconds: positionSeconds
    });
  }

  addVideo(url: string): string {
    return this.sendCommand("addVideo", { url });
  }

  removeVideo(videoId: string): string {
    return this.sendCommand("removeVideo", {
      video_id: videoId
    });
  }

  changeQueue(videoIds: string[]): string {
    return this.sendCommand("changeQueue", {
      video_ids: videoIds
    });
  }

  setSettings(mode: "host_only" | "all"): string {
    return this.sendCommand("setSettings", { mode });
  }

  sendMessage(text: string): string {
    return this.sendCommand("sendMessage", { text });
  }

  leaveRoom(): string {
    return this.sendCommand("leaveRoom", {});
  }

  getState(): void {
    this.sendRead("getState");
  }

  getChatSeq(): void {
    this.sendRead("getChatSeq");
  }

  private sendCommand(
    type: string,
    payload: Record<string, unknown>
  ): string {
    const commandId = crypto.randomUUID();

    this.pendingCommands.set(commandId, {
      commandId,
      type,
      payload
    });

    try {
      this.sendClientMessage({
        type,
        token: this.session.token,
        commandId,
        payload
      });
    } catch (error) {
      this.pendingCommands.delete(commandId);
      throw error;
    }

    return commandId;
  }

  private sendRead(type: string): void {
    this.sendClientMessage({
      type,
      token: this.session.token,
      payload: {}
    });
  }

  private sendClientMessage(message: Record<string, unknown>): void {
    if (this.socket?.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not open");
    }

    this.socket.send(JSON.stringify(message));
  }

  private handleMessage(rawMessage: unknown): void {
    let message: ServerMessage;

    try {
      message = JSON.parse(String(rawMessage)) as ServerMessage;
    } catch {
      this.callbacks.onError?.({
        code: "INVALID_SERVER_MESSAGE",
        message: "Gateway вернул некорректный JSON"
      });
      return;
    }

    switch (message.type) {
      case "pig":
        this.handlePig(message.pigId);
        return;

      case "sendState":
        this.handleSendState(message.state, message.initialMessageSeq);
        return;

      case "sendMessage":
        this.handleSendMessage(message.message);
        return;

      case "commandConfirm":
        this.handleCommandConfirm(message);
        return;

      default:
        this.callbacks.onError?.({
          code: "UNKNOWN_SERVER_MESSAGE",
          message: "Gateway вернул неизвестный тип сообщения"
        });
    }
  }

  private handlePig(pigId: string): void {
    this.clearPigWatchdog();

    if (typeof pigId === "string") {
      try {
        this.sendClientMessage({ type: "pong", pigId });
      } catch {
        this.socket?.close();
        return;
      }
    }

    this.resetPigWatchdog();
  }

  private handleSendState(
    payload: Parameters<typeof normalizeRoomState>[0],
    initialMessageSeq?: number
  ): void {
    try {
      this.callbacks.onRoomState?.(
        normalizeRoomState(payload, this.session.roomId),
        initialMessageSeq
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

  private handleSendMessage(
    payload: Parameters<typeof normalizeChatMessage>[0]
  ): void {
    try {
      this.callbacks.onChatMessage?.(normalizeChatMessage(payload));
    } catch (error) {
      this.callbacks.onError?.({
        code: "INVALID_CHAT_MESSAGE",
        message:
          error instanceof Error
            ? error.message
            : "Некорректное сообщение чата"
      });
    }
  }

  private handleCommandConfirm(confirm: CommandConfirmMessage): void {
    if (typeof confirm.commandId === "string") {
      this.pendingCommands.delete(confirm.commandId);
    }

    this.callbacks.onCommandConfirm?.(confirm);
  }

  private resendPendingCommands(): void {
    for (const pending of this.pendingCommands.values()) {
      try {
        this.sendClientMessage({
          type: pending.type,
          token: this.session.token,
          commandId: pending.commandId,
          payload: pending.payload
        });
      } catch {
        // Соединение уже закрыто — команда останется в очереди
        // и будет отправлена после следующего переподключения.
      }
    }
  }

  private resetPigWatchdog(): void {
    this.clearPigWatchdog();

    this.pigTimeoutTimer = window.setTimeout(() => {
      this.callbacks.onError?.({
        code: "HEARTBEAT_TIMEOUT",
        message: "Gateway не прислал pig вовремя"
      });

      this.socket?.close(4000, "Heartbeat timeout");
    }, this.heartbeatTimeoutMs);
  }

  private clearPigWatchdog(): void {
    if (this.pigTimeoutTimer !== null) {
      window.clearTimeout(this.pigTimeoutTimer);
      this.pigTimeoutTimer = null;
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
