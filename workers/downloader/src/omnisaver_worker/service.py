from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from omnisaver_db import DownloadJobCreate, DownloadJobRepository
from omnisaver_downloader import DownloadError, ErrorCode
from omnisaver_worker.job_queue import JobQueue
from omnisaver_worker.public_job import JobStatus, PublicDownloadJob, PublicDownloadJobResult


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3

    def should_retry(self, error: DownloadError, attempt: int) -> bool:
        return error.retryable and attempt < self.max_attempts


class DownloadJobRunner(Protocol):
    def run(self, job: PublicDownloadJob) -> PublicDownloadJobResult:
        pass


@dataclass(frozen=True)
class WorkerService:
    queue: JobQueue
    repository: DownloadJobRepository
    runner: DownloadJobRunner
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    def process_one(self) -> bool:
        job = self.queue.dequeue()
        if job is None:
            return False

        create = DownloadJobCreate(
            id=UUID(job.job_id),
            telegram_user_id=job.telegram_user_id,
            telegram_chat_id=job.chat_id,
            platform=job.platform.value,
            url=job.url,
        )
        if self.repository.get_job(create.id) is None:
            self.repository.create_queued_job(create)

        attempt = 1
        while True:
            self.repository.mark_started(create.id)
            result = self.runner.run(job)
            if result.status is JobStatus.COMPLETED and result.media_result is not None:
                self.repository.mark_completed(create.id, result.media_result)
                return True

            error = result.error or DownloadError(
                code=ErrorCode.INTERNAL_ERROR,
                safe_message="Something went wrong. Please try again later.",
                retryable=True,
            )
            if not self.retry_policy.should_retry(error, attempt):
                self.repository.mark_failed(create.id, error)
                return True
            attempt += 1
