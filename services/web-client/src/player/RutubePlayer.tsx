import type { QueueItem } from "../api/protocol";
import { getRutubeEmbedUrl } from "./rutube";

interface RutubePlayerProps {
  video: QueueItem | null;
  paused: boolean;
  positionSeconds: number;
}

export function RutubePlayer({
  video,
  paused,
  positionSeconds
}: RutubePlayerProps) {
  if (!video) {
    return (
      <section className="player player--empty">
        <p>В очереди пока нет выбранного видео.</p>
      </section>
    );
  }

  const embedUrl = getRutubeEmbedUrl(video.url);

  if (!embedUrl) {
    return (
      <section className="player player--empty">
        <p>Не удалось распознать ссылку Rutube.</p>
        <a href={video.url} target="_blank" rel="noreferrer">
          Открыть исходную ссылку
        </a>
      </section>
    );
  }

  return (
    <section>
      <div className="player">
        <iframe
          key={video.itemId}
          src={embedUrl}
          title="Rutube player"
          allow="autoplay; fullscreen; picture-in-picture"
          allowFullScreen
        />
      </div>

      <p className="player-state">
        Серверное состояние:{" "}
        <strong>{paused ? "пауза" : "воспроизведение"}</strong>,
        позиция {positionSeconds.toFixed(1)} сек.
      </p>

      <p className="hint">
        Автоматическое применение pause/play/seek к iframe будет
        добавлено после фиксации официального API Rutube-плеера.
      </p>
    </section>
  );
}