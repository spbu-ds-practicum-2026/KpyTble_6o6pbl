const titleCache = new Map<string, string | null>();

export function getRutubeVideoId(sourceUrl: string): string | null {
  try {
    const url = new URL(sourceUrl);

    if (
      url.hostname !== "rutube.ru" &&
      url.hostname !== "www.rutube.ru"
    ) {
      return null;
    }

    const pathParts = url.pathname
      .split("/")
      .filter((part) => part.length > 0);

    const videoIndex = pathParts.indexOf("video");

    if (videoIndex === -1 || !pathParts[videoIndex + 1]) {
      return null;
    }

    return pathParts[videoIndex + 1];
  } catch {
    return null;
  }
}

export function getRutubeEmbedUrl(
  sourceUrl: string
): string | null {
  const videoId = getRutubeVideoId(sourceUrl);

  if (!videoId) {
    return null;
  }

  return `https://rutube.ru/play/embed/${encodeURIComponent(
    videoId
  )}`;
}

export function getCachedRutubeTitle(videoId: string): string | null | undefined {
  return titleCache.get(videoId);
}

/**
 * Rutube не отдаёт CORS-заголовок для браузера, поэтому в dev-режиме запросы
 * идут через Vite-прокси `/rutube-api`. Несколько вызовов с одним video id
 * кэшируются, чтобы очередь не дёргала API при каждом обновлении состояния.
 */
export async function fetchRutubeTitle(
  sourceUrl: string,
  signal?: AbortSignal
): Promise<string | null> {
  const videoId = getRutubeVideoId(sourceUrl);

  if (!videoId) {
    return null;
  }

  const cached = titleCache.get(videoId);

  if (cached !== undefined) {
    return cached;
  }

  const apiBase =
    import.meta.env.VITE_RUTUBE_API_BASE_URL?.trim() || "/rutube-api";

  const response = await fetch(
    `${apiBase}/video/${encodeURIComponent(videoId)}/?format=json`,
    { signal }
  );

  if (!response.ok) {
    throw new Error(`Rutube responded with ${response.status}`);
  }

  const data = (await response.json()) as { title?: unknown };
  const title =
    typeof data.title === "string" && data.title.trim()
      ? data.title.trim()
      : null;

  titleCache.set(videoId, title);
  return title;
}
