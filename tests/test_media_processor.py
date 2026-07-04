import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from omnisaver_downloader import (
    DownloadError,
    ErrorCode,
    MediaFile,
    MediaResult,
    MediaType,
    Platform,
    cleanup_expired_temp_files,
    job_output_dir,
    user_temp_storage_bytes,
)
from omnisaver_media_processor import (
    FFmpegMediaProcessor,
    MediaProcessingContext,
    MediaProcessingOptions,
    TemporaryCleanupWorker,
    build_default_media_processor,
)


class FakeFFmpegRunner:
    def __init__(self, *, output_bytes: bytes = b"out", fail: bool = False) -> None:
        self.output_bytes = output_bytes
        self.fail = fail
        self.commands: list[list[str]] = []

    def run(self, command: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(command))
        if not self.fail:
            Path(command[-1]).write_bytes(self.output_bytes)
        return subprocess.CompletedProcess(
            args=list(command),
            returncode=1 if self.fail else 0,
            stdout="",
            stderr="",
        )


def _result(media_file: MediaFile) -> MediaResult:
    return MediaResult(
        platform=Platform.GENERIC,
        source_url="https://example.com/video.mp4",
        title="",
        caption="",
        media=(media_file,),
    )


def _context(tmp_path: Path) -> MediaProcessingContext:
    output_dir = job_output_dir(tmp_path, "job-1", telegram_user_id=100)
    output_dir.mkdir(parents=True)
    return MediaProcessingContext(
        storage_root=tmp_path,
        output_dir=output_dir,
        telegram_user_id=100,
        job_id="job-1",
    )


def test_media_processor_generates_video_thumbnail(tmp_path: Path) -> None:
    context = _context(tmp_path)
    media_path = context.output_dir / "video.mp4"
    media_path.write_bytes(b"video")
    runner = FakeFFmpegRunner(output_bytes=b"jpg")
    processor = FFmpegMediaProcessor(
        ffmpeg_bin="ffmpeg",
        options=MediaProcessingOptions(max_file_size_mb=1, max_temp_storage_mb=10),
        runner=runner,
    )

    processed = processor.process(
        _result(
            MediaFile(
                type=MediaType.VIDEO,
                path=media_path,
                mime_type="video/mp4",
                size_bytes=media_path.stat().st_size,
            )
        ),
        context=context,
    )

    assert processed.metadata["media_processor"] == "ffmpeg"
    assert processed.metadata["media_group"] == "false"
    assert processed.media[0].thumbnail_path == context.output_dir / "video.jpg"
    assert processed.media[0].thumbnail_path is not None
    assert processed.media[0].thumbnail_path.read_bytes() == b"jpg"


def test_media_processor_compresses_oversized_video(tmp_path: Path) -> None:
    context = _context(tmp_path)
    media_path = context.output_dir / "large.mp4"
    media_path.write_bytes(b"x" * 20)
    runner = FakeFFmpegRunner(output_bytes=b"small")
    processor = FFmpegMediaProcessor(
        ffmpeg_bin="ffmpeg",
        options=MediaProcessingOptions(max_file_size_mb=1, max_temp_storage_mb=10),
        runner=runner,
    )
    media = MediaFile(
        type=MediaType.VIDEO,
        path=media_path,
        mime_type="video/mp4",
        size_bytes=2 * 1024 * 1024,
    )

    processed = processor.process(_result(media), context=context)

    assert processed.media[0].path == context.output_dir / "large.compressed.mp4"
    assert processed.media[0].size_bytes == len(b"small")
    assert len(runner.commands) == 2


def test_media_processor_rejects_oversized_non_video(tmp_path: Path) -> None:
    context = _context(tmp_path)
    media_path = context.output_dir / "image.jpg"
    media_path.write_bytes(b"x")
    processor = FFmpegMediaProcessor(
        ffmpeg_bin="ffmpeg",
        options=MediaProcessingOptions(max_file_size_mb=1, max_temp_storage_mb=10),
        runner=FakeFFmpegRunner(),
    )
    media = MediaFile(
        type=MediaType.PHOTO,
        path=media_path,
        mime_type="image/jpeg",
        size_bytes=2 * 1024 * 1024,
    )

    with pytest.raises(DownloadError) as exc_info:
        processor.process(_result(media), context=context)

    assert exc_info.value.code is ErrorCode.MEDIA_TOO_LARGE


def test_media_processor_rejects_user_temp_storage_over_quota(tmp_path: Path) -> None:
    context = _context(tmp_path)
    (context.output_dir / "existing.bin").write_bytes(b"x" * (2 * 1024 * 1024))
    processor = FFmpegMediaProcessor(
        ffmpeg_bin="ffmpeg",
        options=MediaProcessingOptions(max_file_size_mb=1, max_temp_storage_mb=1),
        runner=FakeFFmpegRunner(),
    )

    with pytest.raises(DownloadError) as exc_info:
        processor.process(
            _result(
                MediaFile(
                    type=MediaType.PHOTO,
                    path=context.output_dir / "existing.bin",
                    mime_type="image/jpeg",
                    size_bytes=2 * 1024 * 1024,
                )
            ),
            context=context,
        )

    assert exc_info.value.code is ErrorCode.MEDIA_TOO_LARGE


def test_temp_storage_helpers_use_user_layout_and_cleanup_expired_files(tmp_path: Path) -> None:
    output_dir = job_output_dir(tmp_path, "job-1", telegram_user_id=100)
    output_dir.mkdir(parents=True)
    old_file = output_dir / "old.bin"
    old_file.write_bytes(b"old")
    fresh_file = output_dir / "fresh.bin"
    fresh_file.write_bytes(b"fresh")
    os.utime(old_file, (1, 1))

    assert output_dir == tmp_path / "100" / "job-1"
    assert user_temp_storage_bytes(tmp_path, 100) == len(b"old") + len(b"fresh")
    assert cleanup_expired_temp_files(tmp_path, older_than_epoch_seconds=2) == 1
    assert not old_file.exists()
    assert fresh_file.exists()


def test_build_default_media_processor_uses_configured_limits() -> None:
    processor = build_default_media_processor(
        ffmpeg_bin="custom-ffmpeg",
        max_file_size_mb=10,
        max_temp_storage_mb=20,
        video_crf=24,
        video_max_height=1080,
        thumbnail_width=640,
    )

    assert processor.ffmpeg_bin == "custom-ffmpeg"
    assert processor.options.max_file_size_mb == 10
    assert processor.options.max_temp_storage_mb == 20
    assert processor.options.video_crf == 24
    assert processor.options.video_max_height == 1080
    assert processor.options.thumbnail_width == 640


def test_temporary_cleanup_worker_removes_expired_files(tmp_path: Path) -> None:
    output_dir = job_output_dir(tmp_path, "job-old", telegram_user_id=100)
    output_dir.mkdir(parents=True)
    old_file = output_dir / "old.bin"
    old_file.write_bytes(b"old")
    os.utime(old_file, (1, 1))

    worker = TemporaryCleanupWorker(storage_root=tmp_path, ttl_hours=1)

    assert worker.run_once(now_epoch_seconds=2 * 60 * 60) == 1
    assert not old_file.exists()
