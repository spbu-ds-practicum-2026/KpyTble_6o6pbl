import { useState, type FormEvent } from "react";
import type { RoomBootstrap } from "./api/protocol";
import {
  ApiError,
  createRoom,
  joinRoom
} from "./api/restClient";
import { RoomPage } from "./room/RoomPage";
import {
  clearSession,
//   loadSession,
  saveSession
} from "./room/sessionStorage";

function getRoomIdFromUrl(): string {
  return new URL(window.location.href).searchParams.get("room") ?? "";
}

export default function App() {
  const [roomId, setRoomId] = useState(getRoomIdFromUrl);
  const [bootstrap, setBootstrap] =
    useState<RoomBootstrap | null>(null);
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
    await run(createRoom);
  }

  async function handleJoin(event: FormEvent): Promise<void> {
    event.preventDefault();

    const normalizedRoomId = roomId.trim();

    if (!normalizedRoomId) {
      return;
    }

    await run(() => joinRoom(normalizedRoomId));
  }

//   async function restoreSession(): Promise<void> {
//     const session = loadSession();

//     if (!session) {
//       setError("В этой вкладке нет сохранённой сессии");
//       return;
//     }

//     await run(async () => {
//       const joined = await joinRoom(session.roomId);

//       /*
//        * Текущий Gateway не имеет отдельного REST endpoint
//        * восстановления сессии. Поэтому временно join создаёт новую
//        * сессию. После появления endpoint восстановления этот код
//        * нужно заменить.
//        */
//       return joined;
//     });
//   }

  if (bootstrap) {
    return (
      <RoomPage
        bootstrap={bootstrap}
        onLeave={() => {
          clearSession();
          setBootstrap(null);
        }}
      />
    );
  }

  return (
    <main className="landing">
      <section className="landing-card">
        <h1>Plotina</h1>
        <p>Совместный просмотр видео с очередью и чатом.</p>

        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}

        <button
          type="button"
          className="button button--large"
          onClick={() => {
            void handleCreate();
          }}
          disabled={loading}
        >
          Создать комнату
        </button>

        <div className="separator">или</div>

        <form onSubmit={handleJoin}>
          <label htmlFor="room-id">Идентификатор комнаты</label>

          <input
            id="room-id"
            value={roomId}
            onChange={(event) => setRoomId(event.target.value)}
            placeholder="demo-room"
            required
          />

          <button
            className="button button--large"
            type="submit"
            disabled={loading}
          >
            Подключиться
          </button>
        </form>

        {/* <button
          type="button"
          className="button button--secondary"
          onClick={() => {
            void restoreSession();
          }}
          disabled={loading}
        >
          Восстановить сессию вкладки
        </button> */}

        {loading && <p className="hint">Подключение…</p>}
      </section>
    </main>
  );
}