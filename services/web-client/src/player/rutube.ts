export function getRutubeEmbedUrl(
  sourceUrl: string
): string | null {
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

    const videoId = pathParts[videoIndex + 1];

    return `https://rutube.ru/play/embed/${encodeURIComponent(
      videoId
    )}`;
  } catch {
    return null;
  }
}