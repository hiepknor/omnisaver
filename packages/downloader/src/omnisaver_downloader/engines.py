from __future__ import annotations

import mimetypes
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from omnisaver_downloader.errors import DownloadError, download_failed, login_required
from omnisaver_downloader.models import MediaFile, MediaResult, MediaType
from omnisaver_downloader.url_detection import Platform


class CommandRunner(Protocol):
    def run(self, command: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        pass


class SubprocessCommandRunner:
    def run(self, command: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )


@dataclass(frozen=True)
class EngineWrapper:
    binary: str
    runner: CommandRunner

    @property
    def name(self) -> str:
        raise NotImplementedError

    def build_command(self, url: str, output_dir: Path) -> list[str]:
        raise NotImplementedError

    def download(self, url: str, platform: Platform, output_dir: Path) -> MediaResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        before = _list_files(output_dir)
        completed = self.runner.run(self.build_command(url, output_dir), cwd=output_dir)
        if completed.returncode != 0:
            raise _engine_error(platform, completed)

        files = [path for path in _list_files(output_dir) if path not in before]
        media_files = tuple(_to_media_file(path) for path in files if path.is_file())
        if not media_files:
            raise download_failed("Download completed but produced no media files.")

        return MediaResult(
            platform=platform,
            source_url=url,
            title="",
            caption="",
            media=media_files,
            metadata={"engine": self.name},
        )


class YtDlpWrapper(EngineWrapper):
    @property
    def name(self) -> str:
        return "yt-dlp"

    def build_command(self, url: str, output_dir: Path) -> list[str]:
        return [
            self.binary,
            "--no-playlist",
            "--paths",
            str(output_dir),
            "--output",
            "%(title).200B.%(ext)s",
            url,
        ]


class GalleryDlWrapper(EngineWrapper):
    @property
    def name(self) -> str:
        return "gallery-dl"

    def build_command(self, url: str, output_dir: Path) -> list[str]:
        return [
            self.binary,
            "--dest",
            str(output_dir),
            url,
        ]


def _engine_error(platform: Platform, completed: subprocess.CompletedProcess[str]) -> DownloadError:
    output = f"{completed.stdout}\n{completed.stderr}".lower()
    if "login" in output or "private" in output or "authentication" in output:
        return login_required(platform.value)
    return download_failed()


def _list_files(directory: Path) -> set[Path]:
    if not directory.exists():
        return set()
    return {path for path in directory.rglob("*") if path.is_file()}


def _to_media_file(path: Path) -> MediaFile:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return MediaFile(
        type=_media_type_for_mime(mime_type),
        path=path,
        mime_type=mime_type,
        size_bytes=path.stat().st_size,
    )


def _media_type_for_mime(mime_type: str) -> MediaType:
    if mime_type.startswith("image/"):
        return MediaType.PHOTO
    if mime_type.startswith("video/"):
        return MediaType.VIDEO
    return MediaType.DOCUMENT
