import { useState, type FormEvent } from "react";
import type { ControlMode, RoomBootstrap } from "./api/protocol";
import { ApiError, createRoom, joinRoom } from "./api/restClient";
import { RoomPage } from "./room/RoomPage";
import { createDemoBootstrap } from "./room/demoBootstrap";
import { clearSession, saveSession } from "./room/sessionStorage";

function getInviteCodeFromUrl(): string {
  const url = new URL(window.location.href);
  const fromQuery =
    url.searchParams.get("invite") ?? url.searchParams.get("code");

  if (fromQuery) {
    return fromQuery;
  }

  const fromPath = url.pathname.match(/\/rooms\/([^/]+)/);
  return fromPath ? decodeURIComponent(fromPath[1]) : "";
}

function rememberInvite(bootstrap: RoomBootstrap): void {
  const url = new URL(window.location.href);

  url.searchParams.set("invite", bootstrap.inviteCode);
  window.history.replaceState(null, "", url.toString());
}

function isDemoRequested(): boolean {
  const url = new URL(window.location.href);

  return (
    url.searchParams.get("demo") === "1" ||
    url.hash === "#demo" ||
    url.pathname === "/demo"
  );
}

export default function App() {
  const [displayName, setDisplayName] = useState("Alice");
  const [inviteCode, setInviteCode] = useState(getInviteCodeFromUrl);
  const [controlMode, setControlMode] =
    useState<ControlMode>("host_only");
  const [bootstrap, setBootstrap] = useState<RoomBootstrap | null>(
    () => (isDemoRequested() ? createDemoBootstrap() : null)
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run(
    operation: () => Promise<RoomBootstrap>
  ): Promise<void> {
    setLoading(true);
    setError("");

    try {
      const result = await operation();

      saveSession(result.session);
      rememberInvite(result);
      setBootstrap(result);
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        setError(`${caughtError.code}: ${caughtError.message}`);
      } else {
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Произошла неизвестная ошибка"
        );
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(): Promise<void> {
    const name = displayName.trim();

    if (!name) {
      return;
    }

    await run(() => createRoom(name, controlMode));
  }

  async function handleJoin(event: FormEvent): Promise<void> {
    event.preventDefault();

    const code = inviteCode.trim();
    const name = displayName.trim();

    if (!code || !name) {
      return;
    }

    await run(() => joinRoom(code, name));
  }

  function handleLeave(): void {
    clearSession();
    setBootstrap(null);
  }

  if (bootstrap) {
    return (
      <RoomPage bootstrap={bootstrap} onLeave={handleLeave} />
    );
  }

  return (
    <main className="landing">
      <section className="landing-card">
        <span className="corner corner--tl" aria-hidden="true" />
        <span className="corner corner--tr" aria-hidden="true" />
        <span className="corner corner--bl" aria-hidden="true" />
        <span className="corner corner--br" aria-hidden="true" />

        <header className="landing-header">
          <span className="eyebrow">
            ПЛОТИНА // ПУЛЬТ СОВМЕСТНОГО ПРОСМОТРА
          </span>
          <h1>
            ПЛОТИНА<span className="title-spark">✦</span>
          </h1>
          <p className="landing-tagline">
            СМОТРИ ВМЕСТЕ. УПРАВЛЯЙ КАК БОГ. НЕ ДАЙ ОЧЕРЕДИ
            УЛЕТЕТЬ В ЧЁРНУЮ ДЫРУ.
          </p>
        </header>

        {error && (
          <div className="error" role="alert">
            <span className="error__icon" aria-hidden="true">
              !
            </span>
            <div>
              <strong>СБОЙ СИСТЕМЫ</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        <div className="landing-grid">
          <label className="field">
            <span>01 / ПОЗЫВНОЙ</span>
            <input
              id="display-name"
              value={displayName}
              onChange={(event) =>
                setDisplayName(event.target.value)
              }
              placeholder="Alice"
              required
            />
          </label>

          <label className="field">
            <span>02 / РЕЖИМ</span>
            <select
              id="control-mode"
              value={controlMode}
              onChange={(event) =>
                setControlMode(event.target.value as ControlMode)
              }
            >
              <option value="host_only">ТОЛЬКО ВЕДУЩИЙ</option>
              <option value="all">ВСЯ КОМАНДА</option>
            </select>
          </label>
        </div>

        <button
          type="button"
          className="button button--hero"
          onClick={() => {
            void handleCreate();
          }}
          disabled={loading}
        >
          🚀 СОЗДАТЬ КОМНАТУ
        </button>

        <button
          type="button"
          className="button button--demo"
          onClick={() => setBootstrap(createDemoBootstrap())}
        >
          ✨ ДЕМО-РЕЙС БЕЗ СЕРВИСОВ
        </button>

        <div className="separator">
          <span>ИЛИ ПРИСОЕДИНИТЬСЯ К ЭКИПАЖУ</span>
        </div>

        <form className="join-form" onSubmit={handleJoin}>
          <label className="field">
            <span>03 / КОД ПРИГЛАШЕНИЯ</span>
            <input
              id="invite-code"
              value={inviteCode}
              onChange={(event) =>
                setInviteCode(event.target.value)
              }
              placeholder="AbCdEf_12345"
              required
            />
          </label>

          <button
            className="button button--join"
            type="submit"
            disabled={loading}
          >
            ВОЙТИ В КОМНАТУ →
          </button>
        </form>

        {loading && <p className="hint">СОЕДИНЕНИЕ СО СТАНЦИЕЙ...</p>}

        <footer className="landing-footer">
          Space — плей/пауза · ← → — перемотка на 10 секунд
        </footer>
      </section>
    </main>
  );
}
