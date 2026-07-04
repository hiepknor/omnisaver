from pathlib import Path

from omnisaver_downloader import ErrorCode, MediaFile, MediaResult, MediaType, Platform
from omnisaver_worker import JobStatus, PublicDownloadJob, PublicDownloadJobRunner


class FakeDownloader:
    def __init__(self, result: MediaResult):
        self.result = result
        self.calls: list[tuple[str, Path]] = []

    def download_public(self, url: str, output_dir: Path) -> MediaResult:
        self.calls.append((url, output_dir))
        output_dir.mkdir(parents=True, exist_ok=True)
        media_path = output_dir / "video.mp4"
        media_path.write_bytes(b"video")
        return MediaResult(
            platform=self.result.platform,
            source_url=self.result.source_url,
            title=self.result.title,
            caption=self.result.caption,
            media=(
                MediaFile(
                    type=MediaType.VIDEO,
                    path=media_path,
                    mime_type="video/mp4",
                    size_bytes=media_path.stat().st_size,
                ),
            ),
        )


class FakeSender:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple[int, MediaResult]] = []

    def send_media_result(self, *, chat_id: int, result: MediaResult) -> None:
        if self.fail:
            raise RuntimeError("upload failed")
        self.sent.append((chat_id, result))


def test_public_download_job_lifecycle_sends_media_and_cleans_temp_files(tmp_path: Path) -> None:
    source_url = "https://example.com/video.mp4"
    downloader = FakeDownloader(
        MediaResult(
            platform=Platform.GENERIC,
            source_url=source_url,
            title="",
            caption="",
            media=(),
        )
    )
    sender = FakeSender()
    runner = PublicDownloadJobRunner(downloader=downloader, sender=sender, storage_root=tmp_path)
    job = PublicDownloadJob(
        job_id="job-1",
        telegram_user_id=100,
        chat_id=200,
        url=source_url,
    )

    result = runner.run(job)

    assert result.status is JobStatus.COMPLETED
    assert result.error is None
    assert result.media_result is not None
    assert downloader.calls == [(source_url, tmp_path / "job-1")]
    assert sender.sent == [(200, result.media_result)]
    assert not (tmp_path / "job-1").exists()


def test_public_download_job_maps_sender_failure_and_cleans_temp_files(tmp_path: Path) -> None:
    source_url = "https://example.com/video.mp4"
    downloader = FakeDownloader(
        MediaResult(
            platform=Platform.GENERIC,
            source_url=source_url,
            title="",
            caption="",
            media=(),
        )
    )
    sender = FakeSender(fail=True)
    runner = PublicDownloadJobRunner(downloader=downloader, sender=sender, storage_root=tmp_path)
    job = PublicDownloadJob(
        job_id="job-2",
        telegram_user_id=100,
        chat_id=200,
        url=source_url,
    )

    result = runner.run(job)

    assert result.status is JobStatus.FAILED
    assert result.error is not None
    assert result.error.code is ErrorCode.TELEGRAM_UPLOAD_FAILED
    assert not (tmp_path / "job-2").exists()
