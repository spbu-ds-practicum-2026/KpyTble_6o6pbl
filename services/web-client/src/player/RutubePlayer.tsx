import { useCallback, useEffect, useRef, useState } from "react";
import type { QueueItem } from "../api/protocol";
import { getRutubeEmbedUrl } from "./rutube";

interface RutubePlayerProps {
  video: QueueItem | null;
  videoTitle?: string;
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

/**
 * Gateway рассылает состояние раз в секунду. Если слать setCurrentTime при
 * каждом таком обновлении, iframe дёргается. Обычное расхождение в 1–2 секунды
 * игнорируем и ABS-перемотку делаем только при заметном скачке позиции.
 */
const SYNC_JUMP_THRESHOLD_SECONDS = 2;
const SYNC_EXPECTED_TOLERANCE_SECONDS = 0.75;

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
  videoTitle,
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

  // Последняя позиция, которую мы реально выставили в iframe. Дальше плеер
  // крутится сам, и мы сравниваем серверное время именно с этой точкой.
  const lastAppliedPositionRef = useRef(positionSeconds);
  const lastAppliedAtRef = useRef(performance.now());
  const playingRef = useRef(isPlaying);
  const previousIsPlayingRef = useRef(isPlaying);
  const previousVideoIdRef = useRef<string | null | undefined>(undefined);
  // Ожидаемая позиция после локальной перемотки: сервер ещё может не прислать
  // подтверждение, поэтому ABS-синхронизацию на этот тик пропускаем.
  const expectedPositionRef = useRef<number | null>(null);

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

  const localPositionAt = useCallback((now: number): number => {
    const elapsed = playingRef.current
      ? Math.max(0, (now - lastAppliedAtRef.current) / 1000)
      : 0;

    return Math.max(0, lastAppliedPositionRef.current + elapsed);
  }, []);

  const applyAbsoluteSeek = useCallback(
    (position: number, now: number): void => {
      lastAppliedPositionRef.current = position;
      lastAppliedAtRef.current = now;
      expectedPositionRef.current = null;
      setDisplayPosition(position);

      sendPlayerMessage({
        type: "player:setCurrentTime",
        data: { time: position }
      });
    },
    [sendPlayerMessage]
  );

  const applyRelativeSeek = useCallback(
    (delta: number): void => {
      const now = performance.now();
      const target = Math.max(0, localPositionAt(now) + delta);

      lastAppliedPositionRef.current = target;
      lastAppliedAtRef.current = now;
      expectedPositionRef.current = target;
      setDisplayPosition(target);

      sendPlayerMessage({
        type: "player:relativelySeek",
        data: { time: delta }
      });
      onSeekBy(delta);
    },
    [localPositionAt, onSeekBy, sendPlayerMessage]
  );

  useEffect(() => {
    const videoId = video?.id ?? null;

    if (videoId === previousVideoIdRef.current) {
      return;
    }

    previousVideoIdRef.current = videoId;
    readyRef.current = false;
    pendingRef.current = [];

    const now = performance.now();
    lastAppliedPositionRef.current = positionSeconds;
    lastAppliedAtRef.current = now;
    expectedPositionRef.current = null;
    setDisplayPosition(positionSeconds);

    if (videoId !== null) {
      sendPlayerMessage({
        type: "player:setCurrentTime",
        data: { time: positionSeconds }
      });
    }
  }, [video?.id, positionSeconds, sendPlayerMessage]);

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
    const now = performance.now();

    if (previousIsPlayingRef.current !== isPlaying) {
      lastAppliedPositionRef.current = localPositionAt(now);
      lastAppliedAtRef.current = now;
      previousIsPlayingRef.current = isPlaying;
      playingRef.current = isPlaying;
    }

    sendPlayerMessage({
      type: isPlaying ? "player:play" : "player:pause",
      data: {}
    });
  }, [isPlaying, video?.id, sendPlayerMessage, localPositionAt]);

  useEffect(() => {
    if (demo) {
      return;
    }

    const videoId = video?.id ?? null;

    if (videoId === null) {
      setDisplayPosition(positionSeconds);
      return;
    }

    const now = performance.now();
    const expected = expectedPositionRef.current;

    if (
      expected !== null &&
      Math.abs(positionSeconds - expected) <=
        SYNC_EXPECTED_TOLERANCE_SECONDS
    ) {
      expectedPositionRef.current = null;
      lastAppliedPositionRef.current = positionSeconds;
      lastAppliedAtRef.current = now;
      setDisplayPosition(positionSeconds);
      return;
    }

    const local = localPositionAt(now);
    const drift = positionSeconds - local;

    if (Math.abs(drift) > SYNC_JUMP_THRESHOLD_SECONDS) {
      applyAbsoluteSeek(positionSeconds, now);
      return;
    }

    setDisplayPosition(local);
  }, [
    positionSeconds,
    video?.id,
    demo,
    localPositionAt,
    applyAbsoluteSeek
  ]);

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
        onPlayPause();
        return;
      }

      if (event.key === "ArrowLeft") {
        event.preventDefault();
        applyRelativeSeek(-10);
        return;
      }

      if (event.key === "ArrowRight") {
        event.preventDefault();
        applyRelativeSeek(10);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [canControl, onPlayPause, applyRelativeSeek]);

  function handleSeekBy(delta: number): void {
    applyRelativeSeek(delta);
  }

  function handlePlayPause(): void {
    onPlayPause();
  }

  const spinner = (
    <div className="player-caption">
      <span className="player-caption__label" title={videoTitle}>
        {videoTitle ?? "ГЛАВНЫЙ ЭКРАН"}
      </span>
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
