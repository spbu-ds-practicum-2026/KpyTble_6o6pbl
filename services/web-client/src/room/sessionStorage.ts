import type { Session } from "../api/protocol";

const STORAGE_KEY = "plotina.session";

export function saveSession(session: Session): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function loadSession(): Session | null {
  const rawValue = sessionStorage.getItem(STORAGE_KEY);

  if (!rawValue) {
    return null;
  }

  try {
    const value = JSON.parse(rawValue) as Partial<Session>;

    if (
      typeof value.sessionToken !== "string" ||
      typeof value.userId !== "string" ||
      typeof value.roomId !== "string"
    ) {
      clearSession();
      return null;
    }

    return {
      sessionToken: value.sessionToken,
      userId: value.userId,
      roomId: value.roomId
    };
  } catch {
    clearSession();
    return null;
  }
}

export function clearSession(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}