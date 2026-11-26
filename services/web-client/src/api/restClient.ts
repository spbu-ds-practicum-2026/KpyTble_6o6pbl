import {
  type ControlMode,
  type ContractRoomResponse,
  type GatewayError,
  type RoomBootstrap,
  normalizeBootstrap
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

function extractError(body: unknown, status: number): GatewayError {
  const candidate = (body ?? {}) as {
    error?: { code?: unknown; message?: unknown };
    code?: unknown;
    message?: unknown;
  };

  const code =
    typeof candidate.error?.code === "string"
      ? candidate.error.code
      : typeof candidate.code === "string"
        ? candidate.code
        : "HTTP_ERROR";

  const message =
    typeof candidate.error?.message === "string"
      ? candidate.error.message
      : typeof candidate.message === "string"
        ? candidate.message
        : `Gateway returned HTTP ${status}`;

  return { code, message };
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  token?: string
): Promise<T> {
  const headers = new Headers(init.headers);

  headers.set("Accept", "application/json");

  if (init.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
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
      error = extractError(await response.json(), response.status);
    } catch {
      // Сервер может вернуть не JSON — оставляем базовую ошибку.
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

export async function createRoom(
  displayName: string,
  controlMode: ControlMode
): Promise<RoomBootstrap> {
  const response = await request<ContractRoomResponse>("/rooms", {
    method: "POST",
    body: JSON.stringify({
      display_name: displayName,
      control_mode: controlMode
    })
  });

  return normalizeBootstrap(response);
}

export async function joinRoom(
  inviteCode: string,
  displayName: string
): Promise<RoomBootstrap> {
  const response = await request<ContractRoomResponse>(
    "/rooms/join",
    {
      method: "POST",
      body: JSON.stringify({
        invite_code: inviteCode,
        display_name: displayName
      })
    }
  );

  return normalizeBootstrap(response);
}
