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
      typeof value.token !== "string" ||
      typeof value.roomId !== "string" ||
      typeof value.displayName !== "string" ||
      typeof value.role !== "string"
    ) {
      clearSession();
      return null;
    }

    return {
      token: value.token,
      roomId: value.roomId,
      displayName: value.displayName,
      role: value.role
    };
  } catch {
    clearSession();
    return null;
  }
}

export function clearSession(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}
