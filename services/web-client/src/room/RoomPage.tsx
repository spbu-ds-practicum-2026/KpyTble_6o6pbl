import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent
} from "react";
import type { ChatMessage, RoomBootstrap } from "../api/protocol";
import { RutubePlayer } from "../player/RutubePlayer";
import { useRutubeTitles } from "../player/useRutubeTitles";
import { useRoomController } from "./useRoomController";

interface RoomPageProps {
  bootstrap: RoomBootstrap;
  onLeave: () => void;
}

function formatTime(value: string): string {
  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleTimeString();
}

function formatHost(value: string): string {
  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return value;
  }
}

function initial(value: string): string {
  return value.trim().charAt(0).toUpperCase() || "?";
}

export function RoomPage({
  bootstrap,
  onLeave
}: RoomPageProps) {
  const controller = useRoomController(bootstrap, {
    onLeft: onLeave
  });
  const videoTitles = useRutubeTitles(controller.state.queue);
  const currentVideo =
    controller.state.queue.find(
      (item) => item.id === controller.state.currentVideoId
    ) ?? null;

  function authorOf(message: ChatMessage): {
    name: string;
    isOwn: boolean;
  } {
    const isOwn =
      (bootstrap.session.participantId !== undefined &&
        message.participantId === bootstrap.session.participantId) ||
      message.participantId === bootstrap.session.displayName;

    const participant = controller.state.participants.find(
      (item) => item.id && item.id === message.participantId
    );

    const name =
      message.displayName ??
      participant?.displayName ??
      (isOwn ? bootstrap.session.displayName : undefined) ??
      (message.participantId
        ? `Участник ${message.participantId.slice(0, 8)}`
        : "Участник");

    return { name, isOwn };
  }

  const [videoUrl, setVideoUrl] = useState("");
  const [chatText, setChatText] = useState("");
  const [copied, setCopied] = useState("");
  const [seekPosition, setSeekPosition] = useState(
    String(bootstrap.state.playback.positionSeconds)
  );

  const copyTimerRef = useRef<number | null>(null);
  const seekBaseRef = useRef(
    bootstrap.state.playback.positionSeconds
  );

  useEffect(() => {
    return () => {
      if (copyTimerRef.current !== null) {
        window.clearTimeout(copyTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    seekBaseRef.current = controller.state.playback.positionSeconds;
    setSeekPosition(
      controller.state.playback.positionSeconds.toFixed(1)
    );
  }, [controller.state.playback.positionSeconds]);

  async function copyValue(value: string, label: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(label);

      if (copyTimerRef.current !== null) {
        window.clearTimeout(copyTimerRef.current);
      }

      copyTimerRef.current = window.setTimeout(() => {
        setCopied("");
        copyTimerRef.current = null;
      }, 1500);
    } catch {
      setCopied("");
    }
  }

  function seekBy(delta: number): void {
    const next = Math.max(0, seekBaseRef.current + delta);
    seekBaseRef.current = next;
    controller.seek(next);
  }

  function addVideo(event: FormEvent): void {
    event.preventDefault();

    const normalizedUrl = videoUrl.trim();

    if (!normalizedUrl || !controller.addVideo(normalizedUrl)) {
      return;
    }

    setVideoUrl("");
  }

  function submitChat(): void {
    const normalizedText = chatText.trim();

    if (!normalizedText || !controller.sendChatMessage(normalizedText)) {
      return;
    }

    setChatText("");
  }

  function sendMessage(event: FormEvent): void {
    event.preventDefault();
    submitChat();
  }

  function handleChatKeyDown(
    event: ReactKeyboardEvent<HTMLTextAreaElement>
  ): void {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      submitChat();
    }
  }

  function seek(event: FormEvent): void {
    event.preventDefault();

    const position = Number(seekPosition);

    if (!Number.isFinite(position) || position < 0) {
      return;
    }

    seekBaseRef.current = position;
    controller.seek(position);
  }

  function moveQueue(index: number, delta: number): void {
    const videoIds = controller.state.queue.map((item) => item.id);
    const target = index + delta;

    if (target < 0 || target >= videoIds.length) {
      return;
    }

    [videoIds[index], videoIds[target]] = [
      videoIds[target],
      videoIds[index]
    ];

    controller.changeQueue(videoIds);
  }

  return (
    <main className="page">
      <header className="room-header">
        <div className="room-identity">
          <span className="eyebrow">СЕАНС // plotina.live</span>

          <h1>
            <span>Комната</span> {bootstrap.state.roomId}
          </h1>

          <div className="room-meta">
            <span className="meta-chip">
              v{controller.state.stateVersion}
            </span>
            <span className="meta-chip">
              {controller.state.controlMode}
            </span>
            <span className="meta-chip">{controller.role}</span>
            <span className="meta-chip">
              {controller.state.status}
            </span>
          </div>

          <button
            type="button"
            className="invite-code"
            onClick={() => {
              void copyValue(bootstrap.inviteCode, "код");
            }}
            title="Скопировать код приглашения"
          >
            <span>КОД ПРИГЛАШЕНИЯ</span>
            <strong>{bootstrap.inviteCode}</strong>
            <span className="invite-code__icon">
              {copied === "код" ? "✓" : "⧉"}
            </span>
          </button>
        </div>

        <div className="header-actions">
          <span
            className={`connection connection--${controller.connectionStatus}`}
          >
            <span className="connection__dot" />
            {bootstrap.demo
              ? "ДЕМО-РЕЙС"
              : controller.connectionStatus.toUpperCase()}
          </span>

          <button
            type="button"
            className="button button--ghost"
            onClick={() => {
              void copyValue(bootstrap.inviteLink, "ссылка");
            }}
          >
            {copied === "ссылка" ? "✓ СКОПИРОВАНО" : "⧉ ССЫЛКА"}
          </button>

          <button
            type="button"
            className="button button--danger"
            onClick={controller.leaveRoom}
            disabled={controller.leaving}
          >
            {controller.leaving ? "ВЫХОД..." : "ВЫЙТИ ⟶"}
          </button>
        </div>
      </header>

      {bootstrap.demo && (
        <div className="demo-banner" role="status">
          <span className="demo-banner__icon" aria-hidden="true">
            🚀
          </span>
          <div>
            <strong>ДЕМО-РЕЙС АКТИВЕН</strong>
            <span>
              Gateway не нужен: кнопки и чат меняют только этот экран.
            </span>
          </div>
          <span className="demo-banner__badge">LOCAL ONLY</span>
        </div>
      )}

      {controller.lastError && (
        <div className="error" role="alert">
          <span className="error__icon" aria-hidden="true">
            !
          </span>
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
            video={currentVideo}
            videoTitle={
              currentVideo ? videoTitles[currentVideo.id] : undefined
            }
            isPlaying={controller.state.playback.isPlaying}
            positionSeconds={
              controller.state.playback.positionSeconds
            }
            canControl={controller.canControl}
            demo={bootstrap.demo === true}
            onPlayPause={controller.playpause}
            onSeekBy={seekBy}
          />

          <section className="panel panel--transport">
            <div className="panel-heading">
              <span className="panel-heading__index">01</span>
              <div>
                <span className="eyebrow">ПУЛЬТ УПРАВЛЕНИЯ</span>
                <h2>Транспорт</h2>
              </div>
              <span className="panel-heading__icon" aria-hidden="true">
                🎛
              </span>
            </div>

            <div className="transport-deck">
              <button
                type="button"
                className="transport-button"
                onClick={() => seekBy(-10)}
                disabled={!controller.canControl}
              >
                <span className="transport-button__glyph">↺</span>
                <span>10 сек назад</span>
              </button>

              <button
                type="button"
                className="transport-button transport-button--main"
                onClick={controller.playpause}
                disabled={!controller.canControl}
              >
                <span className="transport-button__glyph">
                  {controller.state.playback.isPlaying ? "❚❚" : "▶"}
                </span>
                <span>
                  {controller.state.playback.isPlaying
                    ? "Пауза"
                    : "Плей"}
                </span>
              </button>

              <button
                type="button"
                className="transport-button"
                onClick={() => seekBy(10)}
                disabled={!controller.canControl}
              >
                <span className="transport-button__glyph">↻</span>
                <span>10 сек вперёд</span>
              </button>

              <button
                type="button"
                className="transport-button"
                onClick={controller.nextVideo}
                disabled={!controller.canControl}
              >
                <span className="transport-button__glyph">⏭</span>
                <span>Следующее</span>
              </button>
            </div>

            <form className="seek-console" onSubmit={seek}>
              <label htmlFor="seek-position">
                ТОЧНАЯ ПОЗИЦИЯ / СЕКУНДЫ
              </label>
              <div className="seek-console__row">
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
                  className="button button--compact"
                  type="submit"
                  disabled={!controller.canControl}
                >
                  ПРЫЖОК →
                </button>
              </div>
            </form>

            <div className="shortcut-bar">
              <span>
                <kbd>Space</kbd> плей / пауза
              </span>
              <span>
                <kbd>←</kbd> −10 сек
              </span>
              <span>
                <kbd>→</kbd> +10 сек
              </span>
            </div>

            <button
              type="button"
              className="sync-button"
              onClick={controller.synchronizeState}
              disabled={controller.connectionStatus !== "connected"}
            >
              ⟳ СВЕРИТЬ С СЕРВЕРОМ
            </button>
          </section>

          {controller.canSetSettings && (
            <section className="panel panel--settings">
              <div className="panel-heading">
                <span className="panel-heading__index">02</span>
                <div>
                  <span className="eyebrow">ДОСТУП К ПУЛЬТУ</span>
                  <h2>Режим управления</h2>
                </div>
                <span
                  className="panel-heading__icon"
                  aria-hidden="true"
                >
                  🔐
                </span>
              </div>

              <div className="mode-switch">
                {(["host_only", "all"] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    className={`mode-switch__button ${
                      controller.state.controlMode === mode
                        ? "is-active"
                        : ""
                    }`}
                    onClick={() => controller.setSettings(mode)}
                  >
                    {mode === "host_only"
                      ? "Только ведущий"
                      : "Вся команда"}
                  </button>
                ))}
              </div>

              <p className="hint">
                Переключать режим может только ведущий.
              </p>
            </section>
          )}

          <section className="panel panel--queue">
            <div className="panel-heading">
              <span className="panel-heading__index">03</span>
              <div>
                <span className="eyebrow">ПОРЯДОК ВЗЛЁТА</span>
                <h2>Очередь</h2>
              </div>
              <span className="panel-heading__icon" aria-hidden="true">
                🛰
              </span>
            </div>

            <form className="queue-add" onSubmit={addVideo}>
              <span className="queue-add__icon" aria-hidden="true">
                ＋
              </span>
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
                className="button button--compact"
                type="submit"
                disabled={!controller.canControl}
              >
                В ОЧЕРЕДЬ
              </button>
            </form>

            {controller.state.queue.length === 0 ? (
              <div className="empty-state">
                Очередь пуста. Самое время запустить ракету с ссылкой.
              </div>
            ) : (
              <ol className="queue">
                {controller.state.queue.map((item, index) => {
                  const isCurrent =
                    item.id === controller.state.currentVideoId;

                  return (
                    <li
                      key={item.id}
                      className={`queue-card ${
                        isCurrent ? "queue-card--current" : ""
                      }`}
                    >
                      <span
                        className="queue-card__handle"
                        aria-hidden="true"
                      >
                        ⠿
                      </span>

                      <span className="queue-card__index">
                        {String(index + 1).padStart(2, "0")}
                      </span>

                      <div className="queue-card__body">
                        <a
                          className="queue-card__title"
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                          title={videoTitles[item.id] ?? item.url}
                        >
                          {videoTitles[item.id] ??
                            "Загрузка названия…"}
                        </a>
                        <span className="queue-card__host">
                          {formatHost(item.url)}
                        </span>
                      </div>

                      {isCurrent && (
                        <span className="queue-card__now">
                          НА ЭКРАНЕ
                        </span>
                      )}

                      <div className="queue-card__actions">
                        <button
                          type="button"
                          className="icon-button"
                          title="Выше"
                          aria-label="Переместить видео выше"
                          disabled={
                            !controller.canControl || index === 0
                          }
                          onClick={() => moveQueue(index, -1)}
                        >
                          ↑
                        </button>

                        <button
                          type="button"
                          className="icon-button"
                          title="Ниже"
                          aria-label="Переместить видео ниже"
                          disabled={
                            !controller.canControl ||
                            index === controller.state.queue.length - 1
                          }
                          onClick={() => moveQueue(index, 1)}
                        >
                          ↓
                        </button>

                        <button
                          type="button"
                          className="icon-button icon-button--danger"
                          title="Удалить"
                          aria-label="Удалить видео из очереди"
                          disabled={!controller.canControl}
                          onClick={() =>
                            controller.removeVideo(item.id)
                          }
                        >
                          ×
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </section>
        </section>

        <aside className="side-column">
          <section className="panel panel--crew">
            <div className="panel-heading">
              <span className="panel-heading__index">04</span>
              <div>
                <span className="eyebrow">ЭКИПАЖ НА БОРТУ</span>
                <h2>Участники</h2>
              </div>
              <span className="panel-heading__icon" aria-hidden="true">
                👽
              </span>
            </div>

            {controller.state.participants.length === 0 ? (
              <div className="empty-state">
                Gateway пока не вернул список участников.
              </div>
            ) : (
              <ul className="participants">
                {controller.state.participants.map(
                  (participant, index) => (
                    <li key={`${participant.displayName}-${index}`}>
                      <span className="avatar" aria-hidden="true">
                        {initial(participant.displayName)}
                      </span>

                      <span className="participant-info">
                        <strong>{participant.displayName}</strong>
                        <small>
                          {participant.role === "host"
                            ? "ВЕДУЩИЙ"
                            : "УЧАСТНИК"}
                        </small>
                      </span>

                      <span
                        className={`presence ${
                          participant.connected
                            ? "presence--online"
                            : "presence--offline"
                        }`}
                      >
                        <span className="presence__dot" />
                        {participant.connected
                          ? "В СЕТИ"
                          : "НЕ В СЕТИ"}
                      </span>
                    </li>
                  )
                )}
              </ul>
            )}
          </section>

          <section className="panel chat-panel">
            <div className="panel-heading">
              <span className="panel-heading__index">05</span>
              <div>
                <span className="eyebrow">РАДИОЭФИР</span>
                <h2>Чат экипажа</h2>
              </div>
              <span className="panel-heading__icon" aria-hidden="true">
                💬
              </span>
            </div>

            {controller.chatGap !== null && (
              <div className="error" role="status">
                <span className="error__icon" aria-hidden="true">
                  …
                </span>
                <div>
                  <strong>ПОТЕРЯН СИГНАЛ</strong>
                  <p>
                    Ждём сообщение №{controller.chatGap}. Следующие
                    уже в буфере.
                  </p>
                </div>
              </div>
            )}

            <div className="messages">
              {controller.messages.length === 0 ? (
                <div className="empty-state">
                  Эфир тихий. Напишите первое сообщение.
                </div>
              ) : (
                controller.messages.map((message) => {
                  const author = authorOf(message);

                  return (
                    <article
                      key={message.messageId}
                      className={`message ${
                        author.isOwn ? "message--own" : ""
                      }`}
                    >
                      <span className="message__avatar" aria-hidden="true">
                        {initial(author.name)}
                      </span>

                      <div className="message__body">
                        <header>
                          <strong>{author.name}</strong>
                          <time dateTime={message.createdAt}>
                            {formatTime(message.createdAt)}
                          </time>
                        </header>
                        <p>{message.text}</p>
                      </div>
                    </article>
                  );
                })
              )}
            </div>

            <form className="chat-form" onSubmit={sendMessage}>
              <textarea
                value={chatText}
                placeholder="Сообщение в эфир..."
                onChange={(event) =>
                  setChatText(event.target.value)
                }
                onKeyDown={handleChatKeyDown}
              />

              <button
                className="button button--send"
                type="submit"
                title="Отправить"
                aria-label="Отправить сообщение"
                disabled={
                  controller.connectionStatus !== "connected" ||
                  controller.pendingChat
                }
              >
                {controller.pendingChat ? "…" : "🚀"}
              </button>
            </form>

            <p className="hint chat-hint">
              Ctrl + Enter тоже отправляет сообщение.
            </p>
          </section>
        </aside>
      </div>
    </main>
  );
}
