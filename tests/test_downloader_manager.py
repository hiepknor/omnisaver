import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from omnisaver_downloader import (
    AuthenticatedSession,
    DownloadError,
    ErrorCode,
    GalleryDlWrapper,
    InstaloaderWrapper,
    MediaFile,
    MediaResult,
    MediaType,
    Platform,
    PlatformAdapter,
    YtDlpWrapper,
    build_default_downloader_manager,
)


class FakeEngine:
    def __init__(
        self,
        name: str,
        result: MediaResult | None = None,
        error: DownloadError | None = None,
    ):
        self.name = name
        self.result = result
        self.error = error
        self.calls: list[tuple[str, Platform, Path, AuthenticatedSession | None]] = []

    def download(
        self,
        url: str,
        platform: Platform,
        output_dir: Path,
        session: AuthenticatedSession | None = None,
    ) -> MediaResult:
        self.calls.append((url, platform, output_dir, session))
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise AssertionError("FakeEngine needs result or error")
        return self.result


def _media_result(platform: Platform, url: str) -> MediaResult:
    return MediaResult(
        platform=platform,
        source_url=url,
        title="title",
        caption="caption",
        media=(
            MediaFile(
                type=MediaType.VIDEO,
                path=Path("video.mp4"),
                mime_type="video/mp4",
                size_bytes=12,
            ),
        ),
    )


def test_platform_adapter_uses_first_successful_engine(tmp_path: Path) -> None:
    result = _media_result(Platform.INSTAGRAM, "https://instagram.com/reel/abc/")
    first = FakeEngine("first", result=result)
    second = FakeEngine("second", result=result)
    adapter = PlatformAdapter(Platform.INSTAGRAM, (first, second))

    assert adapter.download("https://instagram.com/reel/abc/", tmp_path) == result
    assert len(first.calls) == 1
    assert second.calls == []


def test_platform_adapter_falls_back_after_retryable_error(tmp_path: Path) -> None:
    retryable = DownloadError(
        code=ErrorCode.DOWNLOAD_FAILED,
        safe_message="temporary failure",
        retryable=True,
        fallback_allowed=True,
    )
    result = _media_result(Platform.PINTEREST, "https://pin.it/abc")
    first = FakeEngine("first", error=retryable)
    second = FakeEngine("second", result=result)
    adapter = PlatformAdapter(Platform.PINTEREST, (first, second))

    assert adapter.download("https://pin.it/abc", tmp_path) == result
    assert len(first.calls) == 1
    assert len(second.calls) == 1


def test_platform_adapter_stops_after_non_retryable_error(tmp_path: Path) -> None:
    non_retryable = DownloadError(
        code=ErrorCode.LOGIN_REQUIRED,
        safe_message="login required",
        retryable=False,
    )
    result = _media_result(Platform.INSTAGRAM, "https://instagram.com/reel/abc/")
    first = FakeEngine("first", error=non_retryable)
    second = FakeEngine("second", result=result)
    adapter = PlatformAdapter(Platform.INSTAGRAM, (first, second))

    with pytest.raises(DownloadError) as exc_info:
        adapter.download("https://instagram.com/reel/abc/", tmp_path)

    assert exc_info.value.code is ErrorCode.LOGIN_REQUIRED
    assert len(first.calls) == 1
    assert second.calls == []


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://instagram.com/reel/abc/", Platform.INSTAGRAM),
        ("https://pin.it/abc", Platform.PINTEREST),
        ("https://facebook.com/reel/1", Platform.FACEBOOK),
        ("https://www.tiktok.com/@user/video/1", Platform.TIKTOK),
        ("https://youtube.com/watch?v=abc", Platform.YOUTUBE),
        ("https://x.com/user/status/1", Platform.X_TWITTER),
        ("https://redd.it/abc", Platform.REDDIT),
        ("https://example.com/video.mp4", Platform.GENERIC),
    ],
)
def test_default_manager_has_public_adapter_for_supported_platforms(
    tmp_path: Path, url: str, platform: Platform
) -> None:
    manager = build_default_downloader_manager()

    assert manager.adapters[platform].platform is platform
    assert manager.adapters[platform].engines


def test_engine_wrappers_build_expected_commands(tmp_path: Path) -> None:
    ytdlp = YtDlpWrapper(binary="yt-dlp", runner=_UnusedRunner())
    gallery_dl = GalleryDlWrapper(binary="gallery-dl", runner=_UnusedRunner())

    assert ytdlp.build_command("https://example.com/video", tmp_path) == [
        "yt-dlp",
        "--no-playlist",
        "--paths",
        str(tmp_path),
        "--output",
        "%(title).200B.%(ext)s",
        "https://example.com/video",
    ]
    assert gallery_dl.build_command("https://example.com/pin", tmp_path) == [
        "gallery-dl",
        "--dest",
        str(tmp_path),
        "https://example.com/pin",
    ]
    instaloader = InstaloaderWrapper(binary="instaloader", runner=_UnusedRunner())
    assert instaloader.build_command("https://www.instagram.com/p/abc/", tmp_path) == [
        "instaloader",
        "--dirname-pattern",
        str(tmp_path),
        "--filename-pattern",
        "{shortcode}",
        "--no-metadata-json",
        "--no-compress-json",
        "--",
        "https://www.instagram.com/p/abc/",
    ]


def test_engine_wrapper_maps_access_denied_to_safe_error(tmp_path: Path) -> None:
    ytdlp = YtDlpWrapper(binary="yt-dlp", runner=_AccessDeniedRunner())

    with pytest.raises(DownloadError) as exc_info:
        ytdlp.download("https://example.com/private", Platform.GENERIC, tmp_path)

    assert exc_info.value.code is ErrorCode.ACCESS_DENIED
    assert "không có quyền" in exc_info.value.safe_message


@pytest.mark.parametrize(
    ("stderr", "code"),
    [
        ("HTTP Error 429: Too Many Requests", ErrorCode.RATE_LIMITED),
        ("unsupported url", ErrorCode.UNSUPPORTED_URL),
        ("file size exceeds limit", ErrorCode.MEDIA_TOO_LARGE),
        ("private content requires login", ErrorCode.LOGIN_REQUIRED),
    ],
)
def test_engine_wrapper_normalizes_safe_errors(
    tmp_path: Path,
    stderr: str,
    code: ErrorCode,
) -> None:
    ytdlp = YtDlpWrapper(binary="yt-dlp", runner=_FailingRunner(stderr=stderr))

    with pytest.raises(DownloadError) as exc_info:
        ytdlp.download("https://example.com/private", Platform.GENERIC, tmp_path)

    assert exc_info.value.code is code


def test_platform_adapter_does_not_fallback_on_rate_limit(tmp_path: Path) -> None:
    rate_limit = DownloadError(
        code=ErrorCode.RATE_LIMITED,
        safe_message="rate limited",
        retryable=False,
        fallback_allowed=False,
    )
    result = _media_result(Platform.INSTAGRAM, "https://instagram.com/reel/abc/")
    first = FakeEngine("first", error=rate_limit)
    second = FakeEngine("second", result=result)
    adapter = PlatformAdapter(Platform.INSTAGRAM, (first, second))

    with pytest.raises(DownloadError) as exc_info:
        adapter.download("https://instagram.com/reel/abc/", tmp_path)

    assert exc_info.value.code is ErrorCode.RATE_LIMITED
    assert len(first.calls) == 1
    assert second.calls == []


def test_authenticated_download_uses_matching_user_session(tmp_path: Path) -> None:
    result = _media_result(Platform.INSTAGRAM, "https://instagram.com/reel/abc/")
    engine = FakeEngine("first", result=result)
    adapter = PlatformAdapter(Platform.INSTAGRAM, (engine,))
    manager = build_default_downloader_manager()
    manager = manager.__class__(adapters={Platform.INSTAGRAM: adapter})
    session = AuthenticatedSession(
        platform=Platform.INSTAGRAM,
        owner_user_id="user-1",
        payload=b"sensitive-marker",
    )

    assert (
        manager.download_authenticated("https://instagram.com/reel/abc/", tmp_path, session)
        == result
    )

    assert engine.calls == [
        ("https://instagram.com/reel/abc/", Platform.INSTAGRAM, tmp_path, session)
    ]
    assert "sensitive-marker" not in repr(session)


def test_authenticated_download_rejects_session_platform_mismatch(tmp_path: Path) -> None:
    manager = build_default_downloader_manager()
    session = AuthenticatedSession(
        platform=Platform.PINTEREST,
        owner_user_id="user-1",
        payload=b"sensitive-marker",
    )

    with pytest.raises(DownloadError) as exc_info:
        manager.download_authenticated("https://instagram.com/reel/abc/", tmp_path, session)

    assert exc_info.value.code is ErrorCode.UNSUPPORTED_URL


def test_default_manager_has_expected_engine_order_for_phase_7() -> None:
    manager = build_default_downloader_manager(
        ytdlp_bin="yt-dlp",
        gallery_dl_bin="gallery-dl",
        instaloader_bin="instaloader",
    )

    assert _engine_names(manager.adapters[Platform.INSTAGRAM]) == [
        "gallery-dl",
        "instaloader",
        "yt-dlp",
    ]
    assert _engine_names(manager.adapters[Platform.PINTEREST]) == ["gallery-dl", "yt-dlp"]
    assert _engine_names(manager.adapters[Platform.FACEBOOK]) == ["yt-dlp"]
    assert _engine_names(manager.adapters[Platform.TIKTOK]) == ["yt-dlp"]
    assert _engine_names(manager.adapters[Platform.YOUTUBE]) == ["yt-dlp"]
    assert _engine_names(manager.adapters[Platform.X_TWITTER]) == ["yt-dlp", "gallery-dl"]
    assert _engine_names(manager.adapters[Platform.REDDIT]) == ["gallery-dl", "yt-dlp"]
    assert _engine_names(manager.adapters[Platform.GENERIC]) == ["yt-dlp"]


def _engine_names(adapter: PlatformAdapter) -> list[str]:
    return [engine.name for engine in adapter.engines]


class _UnusedRunner:
    def run(self, command: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        raise AssertionError("not used")


class _AccessDeniedRunner:
    def run(self, command: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=list(command),
            returncode=1,
            stdout="",
            stderr="forbidden",
        )


class _FailingRunner:
    def __init__(self, *, stderr: str) -> None:
        self.stderr = stderr

    def run(self, command: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=list(command),
            returncode=1,
            stdout="",
            stderr=self.stderr,
        )
