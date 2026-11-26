import { useCallback, useEffect, useRef, useState } from "react";
import type { QueueItem } from "../api/protocol";
import { getRutubeEmbedUrl } from "./rutube";

interface RutubePlayerProps {
  video: QueueItem | null;
  isPlaying: boolean;
  positionSeconds: number;
  canControl: boolean;
  demo: boolean;
  onPlayPause: () => void;
  onSeekBy: (deltaSeconds: number) => void;
}

interface PlayerMessage {
  type: string;
  data: Record<string, unknown>;
}

function formatClock(value: number): string {
  const safe = Math.max(0, value);
  const minutes = Math.floor(safe / 60);
  const seconds = Math.floor(safe % 60);
  const tenths = Math.floor((safe % 1) * 10);

  return `${String(minutes).padStart(2, "0")}:${String(
    seconds
  ).padStart(2, "0")}.${tenths}`;
}

/**
 * Rutube-плеер внутри iframe слушает JSON в postMessage:
 * player:play / player:pause / player:setCurrentTime /
 * player:relativelySeek. Сообщения до player:ready складываем в очередь.
 */
export function RutubePlayer({
  video,
  isPlaying,
  positionSeconds,
  canControl,
  demo,
  onPlayPause,
  onSeekBy
}: RutubePlayerProps) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const readyRef = useRef(false);
  const pendingRef = useRef<PlayerMessage[]>([]);
  const [displayPosition, setDisplayPosition] =
    useState(positionSeconds);

  const embedUrl = video ? getRutubeEmbedUrl(video.url) : null;

  const sendPlayerMessage = useCallback(
    (message: PlayerMessage): void => {
      if (!readyRef.current) {
        pendingRef.current.push(message);
        return;
      }

      iframeRef.current?.contentWindow?.postMessage(
        JSON.stringify(message),
        "*"
      );
    },
    []
  );

  const flushPending = useCallback((): void => {
    readyRef.current = true;

    const pending = pendingRef.current.splice(0);

    for (const message of pending) {
      iframeRef.current?.contentWindow?.postMessage(
        JSON.stringify(message),
        "*"
      );
    }
  }, []);

  useEffect(() => {
    readyRef.current = false;
    pendingRef.current = [];
  }, [video?.id]);

  useEffect(() => {
    function handleMessage(event: MessageEvent): void {
      if (typeof event.data !== "string") {
        return;
      }

      let message: { type?: string } | null = null;

      try {
        message = JSON.parse(event.data) as { type?: string };
      } catch {
        return;
      }

      if (
        (message?.type === "player:ready" ||
          message?.type === "player:canPlay") &&
        event.source === iframeRef.current?.contentWindow
      ) {
        flushPending();
      }
    }

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [flushPending]);

  useEffect(() => {
    setDisplayPosition(positionSeconds);
  }, [positionSeconds, video?.id]);

  useEffect(() => {
    sendPlayerMessage({
      type: "player:setCurrentTime",
      data: { time: positionSeconds }
    });
  }, [positionSeconds, video?.id, sendPlayerMessage]);

  useEffect(() => {
    sendPlayerMessage({
      type: isPlaying ? "player:play" : "player:pause",
      data: {}
    });
  }, [isPlaying, video?.id, sendPlayerMessage]);

  useEffect(() => {
    if (!demo || !isPlaying) {
      return;
    }

    const timer = window.setInterval(() => {
      setDisplayPosition((value) => value + 0.1);
    }, 100);

    return () => window.clearInterval(timer);
  }, [demo, isPlaying, video?.id]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      if (!canControl || event.repeat) {
        return;
      }

      const target = event.target;

      if (
        target instanceof HTMLElement &&
        target.closest("input, textarea, select, [contenteditable='true']")
      ) {
        return;
      }

      if (event.code === "Space") {
        // На кнопке/ссылке пробел уже вызывает их обычное действие.
        if (target instanceof HTMLElement && target.closest("button, a")) {
          return;
        }

        event.preventDefault();
        sendPlayerMessage({
          type: isPlaying ? "player:pause" : "player:play",
          data: {}
        });
        onPlayPause();
        return;
      }

      if (event.key === "ArrowLeft") {
        event.preventDefault();
        sendPlayerMessage({
          type: "player:relativelySeek",
          data: { time: -10 }
        });
        onSeekBy(-10);
        return;
      }

      if (event.key === "ArrowRight") {
        event.preventDefault();
        sendPlayerMessage({
          type: "player:relativelySeek",
          data: { time: 10 }
        });
        onSeekBy(10);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [canControl, isPlaying, onPlayPause, onSeekBy, sendPlayerMessage]);

  function handleSeekBy(delta: number): void {
    sendPlayerMessage({
      type: "player:relativelySeek",
      data: { time: delta }
    });
    onSeekBy(delta);
  }

  function handlePlayPause(): void {
    sendPlayerMessage({
      type: isPlaying ? "player:pause" : "player:play",
      data: {}
    });
    onPlayPause();
  }

  const spinner = (
    <div className="player-caption">
      <span className="player-caption__label">ГЛАВНЫЙ ЭКРАН</span>
      <span className="player-caption__signal">
        <span className="signal-bars" aria-hidden="true">
          <i />
          <i />
          <i />
          <i />
        </span>
        LIVE SYNC
      </span>
    </div>
  );

  if (!video) {
    return (
      <section className="player-shell">
        {spinner}

        <div className="player-empty-state">
          <span className="player-empty-state__radar" aria-hidden="true">
            ◎
          </span>
          <h2>НЕТ СИГНАЛА</h2>
          <p>
            В очереди пока нет выбранного видео. Закиньте ссылку —
            и экран оживёт.
          </p>
        </div>
      </section>
    );
  }

  if (!embedUrl) {
    return (
      <section className="player-shell">
        {spinner}

        <div className="player-empty-state">
          <span className="player-empty-state__radar" aria-hidden="true">
            ⚠
          </span>
          <h2>БИТЫЙ КОД ТРАНСЛЯЦИИ</h2>
          <p>Не удалось распознать ссылку Rutube.</p>
          <a href={video.url} target="_blank" rel="noreferrer">
            Открыть исходную ссылку →
          </a>
        </div>
      </section>
    );
  }

  const progress = ((displayPosition % 300) / 300) * 100;

  return (
    <section className="player-shell">
      {spinner}

      <div className="player-frame">
        <iframe
          ref={iframeRef}
          key={video.id}
          src={embedUrl}
          title="Rutube player"
          allow="autoplay; fullscreen; picture-in-picture"
          allowFullScreen
        />

        <div className="player-vignette" aria-hidden="true" />

        <div className="player-hud">
          <button
            type="button"
            className="hud-button"
            title="Назад на 10 секунд"
            aria-label="Перемотать назад на 10 секунд"
            onClick={() => handleSeekBy(-10)}
            disabled={!canControl}
          >
            ↺<small>10</small>
          </button>

          <button
            type="button"
            className="hud-button hud-button--main"
            title={isPlaying ? "Пауза" : "Воспроизвести"}
            aria-label={isPlaying ? "Пауза" : "Воспроизвести"}
            onClick={handlePlayPause}
            disabled={!canControl}
          >
            {isPlaying ? "❚❚" : "▶"}
          </button>

          <button
            type="button"
            className="hud-button"
            title="Вперёд на 10 секунд"
            aria-label="Перемотать вперёд на 10 секунд"
            onClick={() => handleSeekBy(10)}
            disabled={!canControl}
          >
            ↻<small>10</small>
          </button>

          <div className="player-hud__time">
            <strong>{formatClock(displayPosition)}</strong>
            <span>{isPlaying ? "В ЭФИРЕ" : "ПАУЗА"}</span>
          </div>
        </div>
      </div>

      <div className="player-timeline" aria-hidden="true">
        <span style={{ width: `${progress}%` }} />
      </div>

      <div className="player-footer">
        <span>
          СЕРВЕР: {formatClock(positionSeconds)} ·{" "}
          {isPlaying ? "PLAY" : "PAUSE"}
        </span>
        <span>Space / ← / → — управление с клавиатуры</span>
      </div>
    </section>
  );
}
