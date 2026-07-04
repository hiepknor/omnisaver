from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from omnisaver_downloader.engines import (
    GalleryDlWrapper,
    SubprocessCommandRunner,
    YtDlpWrapper,
)
from omnisaver_downloader.errors import DownloadError, unsupported_url
from omnisaver_downloader.models import MediaResult
from omnisaver_downloader.url_detection import Platform, detect_platform


class PublicDownloader(Protocol):
    def download(self, url: str, platform: Platform, output_dir: Path) -> MediaResult:
        pass


@dataclass(frozen=True)
class PlatformAdapter:
    platform: Platform
    engines: tuple[PublicDownloader, ...]

    def download(self, url: str, output_dir: Path) -> MediaResult:
        last_error: DownloadError | None = None
        for engine in self.engines:
            try:
                return engine.download(url, self.platform, output_dir)
            except DownloadError as exc:
                if not exc.retryable:
                    raise
                last_error = exc
        if last_error is not None:
            raise last_error
        raise unsupported_url()


@dataclass(frozen=True)
class DownloaderManager:
    adapters: dict[Platform, PlatformAdapter]

    def download_public(self, url: str, output_dir: Path) -> MediaResult:
        platform = detect_platform(url)
        adapter = self.adapters.get(platform)
        if adapter is None:
            raise unsupported_url()
        return adapter.download(url, output_dir)


def build_default_downloader_manager(
    *,
    ytdlp_bin: str = "yt-dlp",
    gallery_dl_bin: str = "gallery-dl",
) -> DownloaderManager:
    runner = SubprocessCommandRunner()
    ytdlp = YtDlpWrapper(binary=ytdlp_bin, runner=runner)
    gallery_dl = GalleryDlWrapper(binary=gallery_dl_bin, runner=runner)

    return DownloaderManager(
        adapters={
            Platform.INSTAGRAM: PlatformAdapter(Platform.INSTAGRAM, (gallery_dl, ytdlp)),
            Platform.PINTEREST: PlatformAdapter(Platform.PINTEREST, (gallery_dl, ytdlp)),
            Platform.FACEBOOK: PlatformAdapter(Platform.FACEBOOK, (ytdlp,)),
            Platform.TIKTOK: PlatformAdapter(Platform.TIKTOK, (ytdlp,)),
            Platform.YOUTUBE: PlatformAdapter(Platform.YOUTUBE, (ytdlp,)),
            Platform.X_TWITTER: PlatformAdapter(Platform.X_TWITTER, (ytdlp, gallery_dl)),
            Platform.REDDIT: PlatformAdapter(Platform.REDDIT, (gallery_dl, ytdlp)),
            Platform.GENERIC: PlatformAdapter(Platform.GENERIC, (ytdlp,)),
        }
    )
