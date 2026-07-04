import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from omnisaver_downloader import (
    DownloadError,
    ErrorCode,
    GalleryDlWrapper,
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
        self.calls: list[tuple[str, Platform, Path]] = []

    def download(self, url: str, platform: Platform, output_dir: Path) -> MediaResult:
        self.calls.append((url, platform, output_dir))
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


class _UnusedRunner:
    def run(self, command: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        raise AssertionError("not used")
