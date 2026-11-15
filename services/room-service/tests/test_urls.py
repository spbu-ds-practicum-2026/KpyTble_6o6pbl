import pytest

from app.errors import InvalidRequestError
from app.urls import parse_rutube_url


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://rutube.ru/video/abc123/", "abc123"),
        ("https://rutube.ru/video/abc123", "abc123"),
        ("https://www.rutube.ru/video/abc123/?t=10", "abc123"),
        ("https://rutube.ru/play/embed/abc123/", "abc123"),
        ("https://rutube.ru/video/private/secret_1-2/", "secret_1-2"),
        ("http://rutube.ru/video/abc123/", "abc123"),
    ],
)
def test_accepts_rutube_links(url, video_id):
    parsed = parse_rutube_url(url)
    assert parsed.video_id == video_id
    assert parsed.url == url


@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com/watch?v=abc",
        "https://rutube.ru/",
        "https://rutube.ru/video/",
        "rutube.ru/video/abc123",
        "javascript:alert(1)",
        "",
    ],
)
def test_rejects_unknown_links(url):
    with pytest.raises(InvalidRequestError):
        parse_rutube_url(url)
