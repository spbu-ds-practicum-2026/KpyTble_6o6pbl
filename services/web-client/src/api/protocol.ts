export type ControlMode = "host_only" | "all";
export type ParticipantRole = "host" | "member";

/** Сетевые модели из api-contract.md (snake_case). */
export interface ContractParticipant {
  display_name: string;
  role: ParticipantRole | string;
  connected: boolean;
}

export interface ContractPlayback {
  video_id: string | null;
  position_seconds: number;
  is_playing: boolean;
}

export interface ContractQueueItem {
  id: string;
  url: string;
  position: number;
}

export interface ContractRoomState {
  status: string;
  control_mode: ControlMode | string;
  state_version: number;
  current_video_id: string | null;
  playback: ContractPlayback;
  queue: ContractQueueItem[];
  participants: ContractParticipant[];
}

export interface ContractRoomResponse {
  room_id: string;
  invite_code: string;
  invite_link: string;
  token: string;
  participant: ContractParticipant;
  state: ContractRoomState;
}

export interface ContractChatMessage {
  message_id: string;
  messageSeq: number;
  participant_id: string;
  text: string;
  created_at: string;
}

export interface ContractError {
  code: string;
  message: string;
}

export interface CommandConfirmMessage {
  type: "commandConfirm";
  commandId?: string;
  duplicate?: boolean;
  state?: ContractRoomState;
  message?: ContractChatMessage;
  messageSeq?: number;
  left?: boolean;
  error?: ContractError;
}

export interface SendStateMessage {
  type: "sendState";
  initialMessageSeq?: number;
  state: ContractRoomState;
}

export interface SendChatMessage {
  type: "sendMessage";
  message: ContractChatMessage;
}

export interface PigMessage {
  type: "pig";
  pigId: string;
}

export type ServerMessage =
  | CommandConfirmMessage
  | SendStateMessage
  | SendChatMessage
  | PigMessage;

/** Внутренние модели клиента. */
export interface QueueItem {
  id: string;
  url: string;
  position: number;
}

export interface Participant {
  displayName: string;
  role: ParticipantRole | string;
  connected: boolean;
}

export interface Playback {
  videoId: string | null;
  positionSeconds: number;
  isPlaying: boolean;
}

export interface RoomState {
  roomId: string;
  status: string;
  controlMode: ControlMode | string;
  stateVersion: number;
  currentVideoId: string | null;
  playback: Playback;
  queue: QueueItem[];
  participants: Participant[];
}

export interface Session {
  token: string;
  roomId: string;
  displayName: string;
  role: ParticipantRole | string;
}

export interface ChatMessage {
  messageId: string;
  messageSeq: number;
  participantId: string;
  text: string;
  createdAt: string;
}

export interface GatewayError {
  code: string;
  message: string;
}

export interface RoomBootstrap {
  session: Session;
  state: RoomState;
  inviteCode: string;
  inviteLink: string;

  // Локальный режим для просмотра интерфейса без Gateway.
  demo?: boolean;
}

export type ConnectionStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected";

export function normalizeRoomState(
  state: ContractRoomState,
  roomId: string
): RoomState {
  if (!Number.isInteger(state.state_version)) {
    throw new Error("Gateway returned state without a valid version");
  }

  const playback = state.playback ?? {
    video_id: null,
    position_seconds: 0,
    is_playing: false
  };

  return {
    roomId,
    status: state.status ?? "active",
    controlMode: state.control_mode ?? "host_only",
    stateVersion: state.state_version,
    currentVideoId: state.current_video_id ?? null,
    playback: {
      videoId: playback.video_id ?? null,
      positionSeconds:
        typeof playback.position_seconds === "number"
          ? playback.position_seconds
          : 0,
      isPlaying: playback.is_playing === true
    },
    queue: Array.isArray(state.queue)
      ? state.queue.map((item, index) => ({
          id: item.id,
          url: item.url,
          position:
            typeof item.position === "number" ? item.position : index
        }))
      : [],
    participants: Array.isArray(state.participants)
      ? state.participants.map((participant) => ({
          displayName: participant.display_name,
          role: participant.role,
          connected: participant.connected === true
        }))
      : []
  };
}

export function normalizeChatMessage(
  message: ContractChatMessage
): ChatMessage {
  if (
    !message ||
    typeof message.message_id !== "string" ||
    !Number.isInteger(message.messageSeq) ||
    typeof message.text !== "string"
  ) {
    throw new Error("Gateway returned an invalid chat message");
  }

  return {
    messageId: message.message_id,
    messageSeq: message.messageSeq,
    participantId: message.participant_id ?? "",
    text: message.text,
    createdAt: message.created_at ?? ""
  };
}

export function normalizeBootstrap(
  response: ContractRoomResponse
): RoomBootstrap {
  if (
    typeof response.room_id !== "string" ||
    typeof response.token !== "string"
  ) {
    throw new Error("Gateway returned an invalid room response");
  }

  return {
    session: {
      token: response.token,
      roomId: response.room_id,
      displayName: response.participant?.display_name ?? "",
      role: response.participant?.role ?? "member"
    },
    state: normalizeRoomState(response.state, response.room_id),
    inviteCode: response.invite_code ?? "",
    inviteLink: response.invite_link ?? ""
  };
}
