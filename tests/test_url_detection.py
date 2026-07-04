import pytest

from omnisaver_downloader import (
    Platform,
    UnsupportedUrlError,
    detect_platform,
    detect_url,
    detect_urls,
    extract_urls,
)


def test_extract_urls_from_message() -> None:
    message = (
        "Save this https://www.instagram.com/reel/abc123/ and "
        "(https://youtu.be/video-id)."
    )

    assert extract_urls(message) == [
        "https://www.instagram.com/reel/abc123/",
        "https://youtu.be/video-id",
    ]


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://www.instagram.com/p/abc123/", Platform.INSTAGRAM),
        ("https://instagram.com/reel/abc123/", Platform.INSTAGRAM),
        ("https://instagram.com/stories/user/123456789/", Platform.INSTAGRAM),
        ("https://www.pinterest.com/pin/123456789/", Platform.PINTEREST),
        ("https://pin.it/abc123", Platform.PINTEREST),
        ("https://www.facebook.com/user/videos/123456789/", Platform.FACEBOOK),
        ("https://facebook.com/reel/123456789", Platform.FACEBOOK),
        ("https://www.tiktok.com/@user/video/123456789", Platform.TIKTOK),
        ("https://vm.tiktok.com/abc123/", Platform.TIKTOK),
        ("https://www.youtube.com/watch?v=abc123", Platform.YOUTUBE),
        ("https://youtu.be/abc123", Platform.YOUTUBE),
        ("https://x.com/user/status/123456789", Platform.X_TWITTER),
        ("https://twitter.com/user/status/123456789", Platform.X_TWITTER),
        ("https://www.reddit.com/r/test/comments/abc/title/", Platform.REDDIT),
        ("https://redd.it/abc123", Platform.REDDIT),
        ("https://example.com/media/file.mp4", Platform.GENERIC),
    ],
)
def test_detect_platform(url: str, platform: Platform) -> None:
    assert detect_platform(url) is platform


def test_detect_url_returns_normalized_result_model() -> None:
    result = detect_url("https://instagram.com/p/abc123/")

    assert result.url == "https://instagram.com/p/abc123/"
    assert result.platform is Platform.INSTAGRAM


def test_detect_urls_detects_multiple_urls_in_order() -> None:
    results = detect_urls("A https://pin.it/abc123 B https://x.com/user/status/1")

    assert [result.platform for result in results] == [Platform.PINTEREST, Platform.X_TWITTER]


@pytest.mark.parametrize(
    "url",
    [
        "not-a-url",
        "ftp://example.com/file",
        "https://instagram.com/accounts/login/",
        "https://pinterest.com/",
        "https://facebook.com/profile.php?id=1",
        "https://youtube.com/channel/abc123",
    ],
)
def test_detect_platform_rejects_unsupported_urls(url: str) -> None:
    with pytest.raises(UnsupportedUrlError) as exc_info:
        detect_platform(url)

    assert exc_info.value.code == "UNSUPPORTED_URL"
    assert exc_info.value.safe_message == "Link này chưa được hỗ trợ."
