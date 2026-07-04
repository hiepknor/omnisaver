from __future__ import annotations

import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from omnisaver_downloader import (
    MediaFile,
    MediaResult,
    MediaType,
    cleanup_expired_temp_files,
    media_too_large,
    user_temp_storage_bytes,
)


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


class MediaProcessor(Protocol):
    def process(self, result: MediaResult, *, context: MediaProcessingContext) -> MediaResult:
        pass


@dataclass(frozen=True)
class MediaProcessingContext:
    storage_root: Path
    output_dir: Path
    telegram_user_id: int
    job_id: str


@dataclass(frozen=True)
class MediaProcessingOptions:
    max_file_size_mb: int
    max_temp_storage_mb: int
    video_crf: int = 28
    video_max_height: int = 720
    thumbnail_width: int = 320

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def max_temp_storage_bytes(self) -> int:
        return self.max_temp_storage_mb * 1024 * 1024


@dataclass(frozen=True)
class FFmpegMediaProcessor:
    ffmpeg_bin: str
    options: MediaProcessingOptions
    runner: CommandRunner

    def process(self, result: MediaResult, *, context: MediaProcessingContext) -> MediaResult:
        if (
            user_temp_storage_bytes(context.storage_root, context.telegram_user_id)
            > self.options.max_temp_storage_bytes
        ):
            raise media_too_large()

        media = tuple(self._process_file(media_file, context) for media_file in result.media)
        return replace(
            result,
            media=media,
            metadata={
                **result.metadata,
                "media_processor": "ffmpeg",
                "media_group": str(len(media) > 1).lower(),
            },
        )

    def _process_file(
        self,
        media_file: MediaFile,
        context: MediaProcessingContext,
    ) -> MediaFile:
        processed = media_file
        if media_file.size_bytes > self.options.max_file_size_bytes:
            if media_file.type is not MediaType.VIDEO:
                raise media_too_large()
            processed = self._compress_video(media_file, context)
            if processed.size_bytes > self.options.max_file_size_bytes:
                raise media_too_large()

        if processed.type is MediaType.VIDEO and processed.thumbnail_path is None:
            thumbnail = self._generate_thumbnail(processed, context)
            processed = replace(processed, thumbnail_path=thumbnail)
        return processed

    def _compress_video(
        self,
        media_file: MediaFile,
        context: MediaProcessingContext,
    ) -> MediaFile:
        output_path = context.output_dir / f"{media_file.path.stem}.compressed.mp4"
        command = [
            self.ffmpeg_bin,
            "-y",
            "-i",
            str(media_file.path),
            "-vf",
            f"scale=-2:min({self.options.video_max_height}\\,ih)",
            "-c:v",
            "libx264",
            "-crf",
            str(self.options.video_crf),
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            str(output_path),
        ]
        completed = self.runner.run(command, cwd=context.output_dir)
        if completed.returncode != 0 or not output_path.exists():
            raise media_too_large()
        return MediaFile(
            type=MediaType.VIDEO,
            path=output_path,
            mime_type="video/mp4",
            size_bytes=output_path.stat().st_size,
            thumbnail_path=media_file.thumbnail_path,
        )

    def _generate_thumbnail(
        self,
        media_file: MediaFile,
        context: MediaProcessingContext,
    ) -> Path | None:
        thumbnail_path = context.output_dir / f"{media_file.path.stem}.jpg"
        command = [
            self.ffmpeg_bin,
            "-y",
            "-i",
            str(media_file.path),
            "-frames:v",
            "1",
            "-vf",
            f"scale={self.options.thumbnail_width}:-1",
            str(thumbnail_path),
        ]
        completed = self.runner.run(command, cwd=context.output_dir)
        if completed.returncode != 0 or not thumbnail_path.exists():
            return None
        return thumbnail_path


class NoopMediaProcessor:
    def process(self, result: MediaResult, *, context: MediaProcessingContext) -> MediaResult:
        return result


@dataclass(frozen=True)
class TemporaryCleanupWorker:
    storage_root: Path
    ttl_hours: int

    def run_once(self, *, now_epoch_seconds: float | None = None) -> int:
        now = time.time() if now_epoch_seconds is None else now_epoch_seconds
        return cleanup_expired_temp_files(
            self.storage_root,
            older_than_epoch_seconds=now - (self.ttl_hours * 60 * 60),
        )


def build_default_media_processor(
    *,
    ffmpeg_bin: str = "ffmpeg",
    max_file_size_mb: int = 2000,
    max_temp_storage_mb: int = 5000,
    video_crf: int = 28,
    video_max_height: int = 720,
    thumbnail_width: int = 320,
) -> FFmpegMediaProcessor:
    return FFmpegMediaProcessor(
        ffmpeg_bin=ffmpeg_bin,
        options=MediaProcessingOptions(
            max_file_size_mb=max_file_size_mb,
            max_temp_storage_mb=max_temp_storage_mb,
            video_crf=video_crf,
            video_max_height=video_max_height,
            thumbnail_width=thumbnail_width,
        ),
        runner=SubprocessCommandRunner(),
    )
