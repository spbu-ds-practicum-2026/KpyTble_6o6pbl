import { useMemo, useState, type FormEvent } from "react";
import type { RoomBootstrap } from "../api/protocol";
import { RutubePlayer } from "../player/RutubePlayer";
import { useRoomController } from "./useRoomController";

interface RoomPageProps {
  bootstrap: RoomBootstrap;
  onLeave: () => void;
}

export function RoomPage({
  bootstrap,
  onLeave
}: RoomPageProps) {
  const controller = useRoomController(bootstrap);

  const [videoUrl, setVideoUrl] = useState("");
  const [chatText, setChatText] = useState("");
  const [seekPosition, setSeekPosition] = useState(
    String(controller.state.positionSeconds)
  );

  const inviteUrl = useMemo(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("room", controller.state.roomId);
    return url.toString();
  }, [controller.state.roomId]);

  function addVideo(event: FormEvent) {
    event.preventDefault();

    const normalizedUrl = videoUrl.trim();

    if (!normalizedUrl) {
      return;
    }

    controller.addVideo(normalizedUrl);
    setVideoUrl("");
  }

  function sendMessage(event: FormEvent) {
    event.preventDefault();

    const normalizedText = chatText.trim();

    if (!normalizedText) {
      return;
    }

    controller.sendChatMessage(normalizedText);
    setChatText("");
  }

  function seek(event: FormEvent) {
    event.preventDefault();

    const position = Number(seekPosition);

    if (!Number.isFinite(position) || position < 0) {
      return;
    }

    controller.seek(position);
  }

  return (
    <main className="page">
      <header className="room-header">
        <div>
          <h1>Комната {controller.state.roomId}</h1>
          <p>
            Версия состояния: {controller.state.stateVersion}
          </p>
        </div>

        <div className="header-actions">
          <span
            className={`connection connection--${controller.connectionStatus}`}
          >
            {controller.connectionStatus}
          </span>

          <button
            type="button"
            className="button button--secondary"
            onClick={() => {
              void navigator.clipboard.writeText(inviteUrl);
            }}
          >
            Скопировать приглашение
          </button>

          <button
            type="button"
            className="button button--danger"
            onClick={onLeave}
          >
            Выйти
          </button>
        </div>
      </header>

      {controller.lastError && (
        <div className="error" role="alert">
          <div>
            <strong>{controller.lastError.code}</strong>
            <p>{controller.lastError.message}</p>
          </div>

          <button
            type="button"
            onClick={controller.clearError}
            aria-label="Закрыть сообщение об ошибке"
          >
            ×
          </button>
        </div>
      )}

      <div className="room-grid">
        <section className="main-column">
          <RutubePlayer
            video={controller.state.currentVideo}
            paused={controller.state.paused}
            positionSeconds={controller.state.positionSeconds}
          />

          <section className="panel">
            <h2>Управление</h2>

            <div className="controls">
              <button
                type="button"
                className="button"
                onClick={controller.play}
                disabled={
                  controller.connectionStatus !== "connected"
                }
              >
                ▶ Продолжить
              </button>

              <button
                type="button"
                className="button"
                onClick={controller.pause}
                disabled={
                  controller.connectionStatus !== "connected"
                }
              >
                ⏸ Пауза
              </button>

              <button
                type="button"
                className="button"
                onClick={controller.next}
                disabled={
                  controller.connectionStatus !== "connected"
                }
              >
                Следующее видео
              </button>
            </div>

            <form className="inline-form" onSubmit={seek}>
              <label htmlFor="seek-position">Позиция, сек.</label>
              <input
                id="seek-position"
                min="0"
                step="0.1"
                type="number"
                value={seekPosition}
                onChange={(event) =>
                  setSeekPosition(event.target.value)
                }
              />
              <button
                className="button"
                type="submit"
                disabled={
                  controller.connectionStatus !== "connected"
                }
              >
                Перемотать
              </button>
            </form>

            <button
              type="button"
              className="button button--secondary"
              onClick={() => {
                void controller.synchronizeState();
              }}
            >
              Сверить состояние
            </button>
          </section>

          <section className="panel">
            <h2>Очередь</h2>

            <form className="inline-form" onSubmit={addVideo}>
              <input
                type="url"
                value={videoUrl}
                placeholder="https://rutube.ru/video/..."
                onChange={(event) =>
                  setVideoUrl(event.target.value)
                }
                required
              />

              <button
                className="button"
                type="submit"
                disabled={
                  controller.connectionStatus !== "connected"
                }
              >
                Добавить
              </button>
            </form>

            {controller.state.queue.length === 0 ? (
              <p className="hint">Очередь пуста.</p>
            ) : (
              <ol className="queue">
                {controller.state.queue.map((item, index) => (
                  <li
                    key={item.itemId}
                    className={
                      item.itemId ===
                      controller.state.currentVideo?.itemId
                        ? "queue__item queue__item--current"
                        : "queue__item"
                    }
                  >
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Видео {index + 1}
                    </a>

                    <div>
                      <button
                        type="button"
                        disabled={index === 0}
                        onClick={() =>
                          controller.moveVideo(
                            item.itemId,
                            index - 1
                          )
                        }
                      >
                        ↑
                      </button>

                      <button
                        type="button"
                        disabled={
                          index ===
                          controller.state.queue.length - 1
                        }
                        onClick={() =>
                          controller.moveVideo(
                            item.itemId,
                            index + 1
                          )
                        }
                      >
                        ↓
                      </button>

                      <button
                        type="button"
                        onClick={() =>
                          controller.removeVideo(item.itemId)
                        }
                      >
                        Удалить
                      </button>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </section>

        <aside className="side-column">
          <section className="panel">
            <h2>Участники</h2>

            {controller.state.participants.length === 0 ? (
              <p className="hint">
                Текущий Gateway пока не возвращает список
                участников.
              </p>
            ) : (
              <ul className="participants">
                {controller.state.participants.map((participant) => (
                  <li key={participant.userId}>
                    <span>{participant.userId}</span>
                    <span>{participant.role}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel chat-panel">
            <h2>Чат</h2>

            <div className="messages">
              {controller.messages.length === 0 ? (
                <p className="hint">Сообщений пока нет.</p>
              ) : (
                controller.messages.map((message) => (
                  <article
                    key={message.messageId}
                    className="message"
                  >
                    <header>
                      <strong>{message.userId}</strong>
                      <time dateTime={message.sentAt}>
                        {new Date(message.sentAt).toLocaleTimeString()}
                      </time>
                    </header>

                    <p>{message.text}</p>
                  </article>
                ))
              )}
            </div>

            <form className="chat-form" onSubmit={sendMessage}>
              <textarea
                value={chatText}
                placeholder="Сообщение"
                onChange={(event) =>
                  setChatText(event.target.value)
                }
              />

              <button
                className="button"
                type="submit"
                disabled={
                  controller.connectionStatus !== "connected"
                }
              >
                Отправить
              </button>
            </form>
          </section>
        </aside>
      </div>
    </main>
  );
}