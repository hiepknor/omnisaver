from pathlib import Path
from uuid import UUID

from omnisaver_db import DownloadJobStatus, InMemoryDownloadJobRepository
from omnisaver_downloader import (
    DownloadError,
    ErrorCode,
    MediaFile,
    MediaResult,
    MediaType,
    Platform,
)
from omnisaver_worker import (
    InMemoryJobQueue,
    JobStatus,
    PublicDownloadJob,
    PublicDownloadJobResult,
    RetryPolicy,
    WorkerService,
)


class FakeRunner:
    def __init__(self, results: list[PublicDownloadJobResult]):
        self.results = results
        self.calls: list[PublicDownloadJob] = []

    def run(self, job: PublicDownloadJob) -> PublicDownloadJobResult:
        self.calls.append(job)
        return self.results.pop(0)


class FakeNotifier:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[tuple[int, str]] = []

    def send_text_message(self, *, chat_id: int, text: str) -> None:
        if self.fail:
            raise RuntimeError("telegram failed")
        self.messages.append((chat_id, text))


def _job(job_id: str = "00000000-0000-0000-0000-000000000001") -> PublicDownloadJob:
    return PublicDownloadJob(
        job_id=job_id,
        telegram_user_id=100,
        chat_id=200,
        platform=Platform.GENERIC,
        url="https://example.com/video.mp4",
    )


def _media_result() -> MediaResult:
    return MediaResult(
        platform=Platform.GENERIC,
        source_url="https://example.com/video.mp4",
        title="",
        caption="",
        media=(
            MediaFile(
                type=MediaType.VIDEO,
                path=Path("video.mp4"),
                mime_type="video/mp4",
                size_bytes=5,
            ),
        ),
    )


def test_worker_service_processes_queued_job_and_records_history() -> None:
    queue = InMemoryJobQueue()
    job = _job()
    queue.enqueue(job)
    repository = InMemoryDownloadJobRepository()
    runner = FakeRunner(
        [
            PublicDownloadJobResult(
                job_id=job.job_id,
                status=JobStatus.COMPLETED,
                media_result=_media_result(),
            )
        ]
    )
    service = WorkerService(queue=queue, repository=repository, runner=runner)

    assert service.process_one() is True

    record = repository.get_job(UUID(job.job_id))
    assert record is not None
    assert record.status is DownloadJobStatus.COMPLETED
    assert record.started_at is not None
    assert record.finished_at is not None
    assert repository.results
    assert repository.list_recent_jobs(record.user_id) == [record]


def test_worker_service_retries_retryable_failure_then_completes() -> None:
    queue = InMemoryJobQueue()
    job = _job()
    queue.enqueue(job)
    repository = InMemoryDownloadJobRepository()
    runner = FakeRunner(
        [
            PublicDownloadJobResult(
                job_id=job.job_id,
                status=JobStatus.FAILED,
                error=DownloadError(
                    code=ErrorCode.DOWNLOAD_FAILED,
                    safe_message="temporary",
                    retryable=True,
                ),
            ),
            PublicDownloadJobResult(
                job_id=job.job_id,
                status=JobStatus.COMPLETED,
                media_result=_media_result(),
            ),
        ]
    )
    notifier = FakeNotifier()
    service = WorkerService(
        queue=queue,
        repository=repository,
        runner=runner,
        notifier=notifier,
        retry_policy=RetryPolicy(max_attempts=2),
    )

    assert service.process_one() is True
    assert len(runner.calls) == 2
    record = repository.get_job(UUID(job.job_id))
    assert record is not None
    assert record.status is DownloadJobStatus.COMPLETED
    assert notifier.messages == []


def test_worker_service_records_safe_failed_error_after_retries() -> None:
    queue = InMemoryJobQueue()
    job = _job()
    queue.enqueue(job)
    repository = InMemoryDownloadJobRepository()
    runner = FakeRunner(
        [
            PublicDownloadJobResult(
                job_id=job.job_id,
                status=JobStatus.FAILED,
                error=DownloadError(
                    code=ErrorCode.DOWNLOAD_FAILED,
                    safe_message="safe failure",
                    retryable=True,
                ),
            )
        ]
    )
    notifier = FakeNotifier()
    service = WorkerService(
        queue=queue,
        repository=repository,
        runner=runner,
        notifier=notifier,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    assert service.process_one() is True

    record = repository.get_job(UUID(job.job_id))
    assert record is not None
    assert record.status is DownloadJobStatus.FAILED
    assert record.error_code == "DOWNLOAD_FAILED"
    assert record.error_message == "safe failure"
    assert len(notifier.messages) == 1
    assert notifier.messages[0][0] == 200
    assert "Job tải media thất bại" in notifier.messages[0][1]
    assert "<code>00000000</code>" in notifier.messages[0][1]
    assert "safe failure" in notifier.messages[0][1]


def test_worker_service_session_failure_notification_points_to_private_chat() -> None:
    queue = InMemoryJobQueue()
    job = PublicDownloadJob(
        job_id="00000000-0000-0000-0000-000000000001",
        telegram_user_id=100,
        chat_id=-200,
        platform=Platform.INSTAGRAM,
        url="https://instagram.com/reel/private/",
    )
    queue.enqueue(job)
    repository = InMemoryDownloadJobRepository()
    runner = FakeRunner(
        [
            PublicDownloadJobResult(
                job_id=job.job_id,
                status=JobStatus.FAILED,
                error=DownloadError(
                    code=ErrorCode.SESSION_MISSING,
                    safe_message="Link instagram này cần đăng nhập.",
                    retryable=False,
                ),
            )
        ]
    )
    notifier = FakeNotifier()
    service = WorkerService(
        queue=queue,
        repository=repository,
        runner=runner,
        notifier=notifier,
    )

    assert service.process_one() is True
    assert len(notifier.messages) == 1
    assert notifier.messages[0][0] == -200
    assert "mở chat riêng với OmniSaver" in notifier.messages[0][1]
    assert "/connect_instagram" in notifier.messages[0][1]


def test_worker_service_does_not_fail_when_failure_notification_fails() -> None:
    queue = InMemoryJobQueue()
    job = _job()
    queue.enqueue(job)
    repository = InMemoryDownloadJobRepository()
    runner = FakeRunner(
        [
            PublicDownloadJobResult(
                job_id=job.job_id,
                status=JobStatus.FAILED,
                error=DownloadError(
                    code=ErrorCode.DOWNLOAD_FAILED,
                    safe_message="safe failure",
                    retryable=False,
                ),
            )
        ]
    )
    service = WorkerService(
        queue=queue,
        repository=repository,
        runner=runner,
        notifier=FakeNotifier(fail=True),
    )

    assert service.process_one() is True
    record = repository.get_job(UUID(job.job_id))
    assert record is not None
    assert record.status is DownloadJobStatus.FAILED
