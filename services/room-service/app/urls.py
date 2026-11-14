import re
from dataclasses import dataclass

from app.errors import InvalidRequestError

# Supported public, private and embed Rutube links. The video id is kept as is.
_RUTUBE_RE = re.compile(
    r"^https?://(?:www\.)?rutube\.ru/"
    r"(?:video|play/embed)/(?:private/)?([A-Za-z0-9_-]+)/?(?:\?.*)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RutubeVideo:
    video_id: str
    url: str


def parse_rutube_url(url: str) -> RutubeVideo:
    candidate = url.strip()
    match = _RUTUBE_RE.match(candidate)
    if match is None:
        raise InvalidRequestError(
            "Ссылка должна вести на видео Rutube (rutube.ru/video/... или "
            "rutube.ru/play/embed/...)",
            code="invalid_video_url",
        )
    return RutubeVideo(video_id=match.group(1), url=candidate)
