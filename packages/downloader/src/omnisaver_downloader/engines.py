from __future__ import annotations

import mimetypes
import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from omnisaver_downloader.errors import (
    DownloadError,
    access_denied,
    download_failed,
    login_required,
    media_too_large,
    rate_limited,
    unsupported_url,
)
from omnisaver_downloader.models import AuthenticatedSession, MediaFile, MediaResult, MediaType
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

    def build_command(
        self,
        url: str,
        output_dir: Path,
        session: AuthenticatedSession | None = None,
    ) -> list[str]:
        raise NotImplementedError

    def download(
        self,
        url: str,
        platform: Platform,
        output_dir: Path,
        session: AuthenticatedSession | None = None,
    ) -> MediaResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        cookie_file = _write_session_cookie_file(output_dir, session)
        before = _list_files(output_dir)
        try:
            completed = self.runner.run(
                self.build_command(url, output_dir, session),
                cwd=output_dir,
            )
        except FileNotFoundError:
            raise download_failed(f"Engine {self.name} chưa được cài đặt.") from None
        finally:
            _delete_session_cookie_file(cookie_file)
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

    def build_command(
        self,
        url: str,
        output_dir: Path,
        session: AuthenticatedSession | None = None,
    ) -> list[str]:
        return [
            self.binary,
            "--no-playlist",
            *(_cookie_args("--cookies", output_dir) if session is not None else []),
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

    def build_command(
        self,
        url: str,
        output_dir: Path,
        session: AuthenticatedSession | None = None,
    ) -> list[str]:
        return [
            self.binary,
            "--dest",
            str(output_dir),
            *(_cookie_args("--cookies", output_dir) if session is not None else []),
            url,
        ]


class InstaloaderWrapper(EngineWrapper):
    @property
    def name(self) -> str:
        return "instaloader"

    def build_command(
        self,
        url: str,
        output_dir: Path,
        session: AuthenticatedSession | None = None,
    ) -> list[str]:
        return [
            self.binary,
            "--dirname-pattern",
            str(output_dir),
            "--filename-pattern",
            "{shortcode}",
            "--no-metadata-json",
            "--no-compress-json",
            *(_cookie_args("--cookiefile", output_dir) if session is not None else []),
            "--",
            _instaloader_target(url),
        ]


def _engine_error(platform: Platform, completed: subprocess.CompletedProcess[str]) -> DownloadError:
    output = f"{completed.stdout}\n{completed.stderr}".lower()
    if "unsupported url" in output or "no suitable extractor" in output:
        return unsupported_url()
    if "too large" in output or "file size" in output or "exceeds" in output:
        return media_too_large()
    if "rate limit" in output or "too many requests" in output or "http error 429" in output:
        return rate_limited(platform.value)
    if "access denied" in output or "forbidden" in output or "not authorized" in output:
        return access_denied(platform.value)
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


def _write_session_cookie_file(
    output_dir: Path,
    session: AuthenticatedSession | None,
) -> Path | None:
    if session is None:
        return None
    cookie_file = _session_cookie_path(output_dir)
    cookie_file.write_bytes(session.payload)
    os.chmod(cookie_file, 0o600)
    return cookie_file


def _delete_session_cookie_file(cookie_file: Path | None) -> None:
    if cookie_file is None:
        return
    try:
        cookie_file.unlink()
    except FileNotFoundError:
        return


def _cookie_args(option: str, output_dir: Path) -> list[str]:
    return [option, str(_session_cookie_path(output_dir))]


def _session_cookie_path(output_dir: Path) -> Path:
    return output_dir / ".omnisaver-session-cookies.txt"


def _instaloader_target(url: str) -> str:
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) >= 2 and path_parts[0].lower() in {"p", "reel", "tv"}:
        return f"-{path_parts[1]}"
    return url
