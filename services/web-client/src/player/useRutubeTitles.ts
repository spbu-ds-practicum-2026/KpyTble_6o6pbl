import { useEffect, useState } from "react";
import type { QueueItem } from "../api/protocol";
import {
  fetchRutubeTitle,
  getCachedRutubeTitle,
  getRutubeVideoId
} from "./rutube";

function fallbackTitle(item: QueueItem): string {
  const videoId = getRutubeVideoId(item.url);

  return videoId ? `Rutube ${videoId.slice(0, 8)}` : "Видео";
}

/** Подтягивает настоящие названия Rutube для очереди, кэшируя результаты. */
export function useRutubeTitles(
  queue: QueueItem[]
): Record<string, string> {
  const [titles, setTitles] = useState<Record<string, string>>({});
  const queueKey = queue.map((item) => item.url).join("\u0000");

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    for (const item of queue) {
      const videoId = getRutubeVideoId(item.url);

      if (!videoId) {
        continue;
      }

      const cached = getCachedRutubeTitle(videoId);

      if (cached !== undefined) {
        const value = cached || fallbackTitle(item);

        setTitles((current) =>
          current[item.id] === value
            ? current
            : { ...current, [item.id]: value }
        );
        continue;
      }

      fetchRutubeTitle(item.url, controller.signal)
        .then((title) => {
          if (!active) {
            return;
          }

          const value = title || fallbackTitle(item);
          setTitles((current) => ({ ...current, [item.id]: value }));
        })
        .catch(() => {
          if (!active) {
            return;
          }

          // Очередь должна работать и без API: останется fallback-подпись.
          const value = fallbackTitle(item);
          setTitles((current) => ({ ...current, [item.id]: value }));
        });
    }

    return () => {
      active = false;
      controller.abort();
    };
    // queueKey меняется только при изменении набора ссылок в очереди.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queueKey]);

  return titles;
}
