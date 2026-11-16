import {
  type GatewayError,
  type GatewayRoomState,
  type RoomBootstrap,
  type Session,
  normalizeRoomState
} from "./protocol";

const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL?.trim() || "/api";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

interface JoinRoomResponse {
  state: GatewayRoomState;
  session: Session;
}

/**
 * Текущий POST /rooms возвращает State в развёрнутом виде
 * и поле session рядом с ним.
 */
type CreateRoomResponse = GatewayRoomState & {
  session: Session;
};

async function request<T>(
  path: string,
  init: RequestInit = {},
  sessionToken?: string
): Promise<T> {
  const headers = new Headers(init.headers);

  headers.set("Accept", "application/json");

  if (init.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  if (sessionToken) {
    headers.set("Authorization", `Bearer ${sessionToken}`);
  }

  let response: Response;

  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers
    });
  } catch {
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      "Не удалось подключиться к API Gateway"
    );
  }

  if (!response.ok) {
    let error: GatewayError = {
      code: "HTTP_ERROR",
      message: `Gateway returned HTTP ${response.status}`
    };

    try {
      const body = (await response.json()) as Partial<GatewayError>;

      if (typeof body.code === "string") {
        error.code = body.code;
      }

      if (typeof body.message === "string") {
        error.message = body.message;
      }
    } catch {
      // Gateway пока не гарантирует единый JSON-формат всех ошибок.
    }

    throw new ApiError(response.status, error.code, error.message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function checkHealth(): Promise<boolean> {
  const response = await request<{ status: string }>("/health");
  return response.status === "ok";
}

export async function createRoom(): Promise<RoomBootstrap> {
  const response = await request<CreateRoomResponse>("/rooms", {
    method: "POST"
  });

  const { session, ...state } = response;

  return {
    session,
    state: normalizeRoomState(state)
  };
}

export async function joinRoom(
  roomId: string
): Promise<RoomBootstrap> {
  const response = await request<JoinRoomResponse>(
    `/rooms/${encodeURIComponent(roomId)}/join`,
    {
      method: "POST"
    }
  );

  return {
    session: response.session,
    state: normalizeRoomState(response.state)
  };
}

export async function getRoomState(
  roomId: string,
  sessionToken: string
) {
  const response = await request<GatewayRoomState>(
    `/rooms/${encodeURIComponent(roomId)}/state`,
    {
      method: "GET"
    },
    sessionToken
  );

  return normalizeRoomState(response);
}