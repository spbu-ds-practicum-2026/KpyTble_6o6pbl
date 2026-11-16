export interface Session {
  sessionToken: string;
  userId: string;
  roomId: string;
}

export interface QueueItem {
  itemId: string;
  url: string;
}

export type ParticipantRole = "HOST" | "PARTICIPANT";

export interface Participant {
  userId: string;
  role: ParticipantRole | string;
  connected?: boolean;
  joinedAt?: string;
}

export interface GatewayRoomState {
  roomId: string;

  // Текущее имя поля Gateway.
  version?: number;

  // Имя из ТР.
  stateVersion?: number;

  paused: boolean;
  positionSeconds: number;
  currentVideo: QueueItem | null;
  queue: QueueItem[];

  // Будущие поля, необходимые по ТР.
  positionUpdatedAt?: string;
  serverTime?: string;
  participants?: Participant[];
  controlMode?: "HOST_ONLY" | "EVERYONE";
}

export interface RoomState {
  roomId: string;
  stateVersion: number;
  paused: boolean;
  positionSeconds: number;
  currentVideo: QueueItem | null;
  queue: QueueItem[];
  positionUpdatedAt?: string;
  serverTime?: string;
  participants: Participant[];
  controlMode?: "HOST_ONLY" | "EVERYONE";
}

export interface ChatMessage {
  messageId: string;
  roomId: string;
  userId: string;
  text: string;
  sentAt: string;

  // Пока Gateway этого поля не возвращает.
  messageSeq?: number;
}

export interface RoomBootstrap {
  state: RoomState;
  session: Session;
}

export interface GatewayEnvelope<T = unknown> {
  type: string;
  requestId: string | null;
  payload: T;
}

export interface GatewayError {
  code: string;
  message: string;
}

export interface CommandAck {
  commandId: string;
  stateVersion?: number;
  messageId?: string;
}

export interface SessionAuthenticated {
  userId: string;
  roomId: string;
}

export type ConnectionStatus =
  | "idle"
  | "connecting"
  | "authenticating"
  | "connected"
  | "reconnecting"
  | "disconnected";

export function normalizeRoomState(
  state: GatewayRoomState
): RoomState {
  const version = state.stateVersion ?? state.version;

  if (version === undefined || !Number.isInteger(version)) {
    throw new Error("Gateway returned state without a valid version");
  }

  return {
    roomId: state.roomId,
    stateVersion: version,
    paused: state.paused,
    positionSeconds: state.positionSeconds,
    currentVideo: state.currentVideo,
    queue: state.queue ?? [],
    positionUpdatedAt: state.positionUpdatedAt,
    serverTime: state.serverTime,
    participants: state.participants ?? [],
    controlMode: state.controlMode
  };
}