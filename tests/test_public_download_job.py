from pathlib import Path

from omnisaver_downloader import (
    AuthenticatedSession,
    DownloadError,
    ErrorCode,
    MediaFile,
    MediaResult,
    MediaType,
    Platform,
)
from omnisaver_worker import JobStatus, PublicDownloadJob, PublicDownloadJobRunner


class FakeDownloader:
    def __init__(
        self,
        result: MediaResult,
        *,
        public_error: DownloadError | None = None,
        authenticated_error: DownloadError | None = None,
    ):
        self.result = result
        self.public_error = public_error
        self.authenticated_error = authenticated_error
        self.calls: list[tuple[str, Path]] = []
        self.authenticated_calls: list[tuple[str, Path, AuthenticatedSession]] = []

    def download_public(self, url: str, output_dir: Path) -> MediaResult:
        if self.public_error is not None:
            raise self.public_error
        self.calls.append((url, output_dir))
        return self._write_result(output_dir)

    def download_authenticated(
        self,
        url: str,
        output_dir: Path,
        session: AuthenticatedSession,
    ) -> MediaResult:
        if self.authenticated_error is not None:
            raise self.authenticated_error
        self.authenticated_calls.append((url, output_dir, session))
        return self._write_result(output_dir)

    def _write_result(self, output_dir: Path) -> MediaResult:
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


class FakeSessionResolver:
    def __init__(self, session: AuthenticatedSession | None = None):
        self.session = session
        self.calls: list[tuple[int, Platform]] = []

    def resolve(self, *, telegram_user_id: int, platform: Platform) -> AuthenticatedSession:
        self.calls.append((telegram_user_id, platform))
        if self.session is None:
            raise AssertionError("session required")
        return self.session


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
        platform=Platform.GENERIC,
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
        platform=Platform.GENERIC,
        url=source_url,
    )

    result = runner.run(job)

    assert result.status is JobStatus.FAILED
    assert result.error is not None
    assert result.error.code is ErrorCode.TELEGRAM_UPLOAD_FAILED
    assert not (tmp_path / "job-2").exists()


def test_public_download_job_uses_user_session_when_login_required(tmp_path: Path) -> None:
    source_url = "https://instagram.com/reel/private/"
    downloader = FakeDownloader(
        MediaResult(
            platform=Platform.INSTAGRAM,
            source_url=source_url,
            title="",
            caption="",
            media=(),
        ),
        public_error=DownloadError(
            code=ErrorCode.LOGIN_REQUIRED,
            safe_message="login required",
            retryable=False,
        ),
    )
    session = AuthenticatedSession(
        platform=Platform.INSTAGRAM,
        owner_user_id="user-1",
        payload=b"sensitive-marker",
    )
    resolver = FakeSessionResolver(session)
    sender = FakeSender()
    runner = PublicDownloadJobRunner(
        downloader=downloader,
        sender=sender,
        storage_root=tmp_path,
        session_resolver=resolver,
    )
    job = PublicDownloadJob(
        job_id="job-3",
        telegram_user_id=100,
        chat_id=200,
        platform=Platform.INSTAGRAM,
        url=source_url,
    )

    result = runner.run(job)

    assert result.status is JobStatus.COMPLETED
    assert resolver.calls == [(100, Platform.INSTAGRAM)]
    assert downloader.authenticated_calls == [(source_url, tmp_path / "job-3", session)]
    assert sender.sent == [(200, result.media_result)]
    assert not (tmp_path / "job-3").exists()


def test_public_download_job_refuses_auth_without_session_resolver(tmp_path: Path) -> None:
    source_url = "https://instagram.com/reel/private/"
    downloader = FakeDownloader(
        MediaResult(
            platform=Platform.INSTAGRAM,
            source_url=source_url,
            title="",
            caption="",
            media=(),
        ),
        public_error=DownloadError(
            code=ErrorCode.LOGIN_REQUIRED,
            safe_message="login required",
            retryable=False,
        ),
    )
    runner = PublicDownloadJobRunner(
        downloader=downloader,
        sender=FakeSender(),
        storage_root=tmp_path,
    )
    job = PublicDownloadJob(
        job_id="job-4",
        telegram_user_id=100,
        chat_id=200,
        platform=Platform.INSTAGRAM,
        url=source_url,
    )

    result = runner.run(job)

    assert result.status is JobStatus.FAILED
    assert result.error is not None
    assert result.error.code is ErrorCode.SESSION_MISSING
    assert downloader.authenticated_calls == []
    assert not (tmp_path / "job-4").exists()


def test_public_download_job_maps_authenticated_login_required_to_expired_session(
    tmp_path: Path,
) -> None:
    source_url = "https://instagram.com/reel/private/"
    downloader = FakeDownloader(
        MediaResult(
            platform=Platform.INSTAGRAM,
            source_url=source_url,
            title="",
            caption="",
            media=(),
        ),
        public_error=DownloadError(
            code=ErrorCode.LOGIN_REQUIRED,
            safe_message="login required",
            retryable=False,
        ),
        authenticated_error=DownloadError(
            code=ErrorCode.LOGIN_REQUIRED,
            safe_message="login required",
            retryable=False,
        ),
    )
    resolver = FakeSessionResolver(
        AuthenticatedSession(
            platform=Platform.INSTAGRAM,
            owner_user_id="user-1",
            payload=b"sensitive-marker",
        )
    )
    runner = PublicDownloadJobRunner(
        downloader=downloader,
        sender=FakeSender(),
        storage_root=tmp_path,
        session_resolver=resolver,
    )
    job = PublicDownloadJob(
        job_id="job-5",
        telegram_user_id=100,
        chat_id=200,
        platform=Platform.INSTAGRAM,
        url=source_url,
    )

    result = runner.run(job)

    assert result.status is JobStatus.FAILED
    assert result.error is not None
    assert result.error.code is ErrorCode.SESSION_EXPIRED
