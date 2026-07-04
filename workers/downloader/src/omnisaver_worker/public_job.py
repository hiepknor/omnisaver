from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from omnisaver_downloader import (
    DownloadError,
    ErrorCode,
    MediaResult,
    cleanup_job_output,
    job_output_dir,
    telegram_upload_failed,
)


class JobStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class PublicDownloadJob:
    job_id: str
    telegram_user_id: int
    chat_id: int
    url: str


@dataclass(frozen=True)
class PublicDownloadJobResult:
    job_id: str
    status: JobStatus
    media_result: MediaResult | None = None
    error: DownloadError | None = None


class TelegramSender(Protocol):
    def send_media_result(self, *, chat_id: int, result: MediaResult) -> None:
        pass


class PublicDownloadManager(Protocol):
    def download_public(self, url: str, output_dir: Path) -> MediaResult:
        pass


@dataclass(frozen=True)
class PublicDownloadJobRunner:
    downloader: PublicDownloadManager
    sender: TelegramSender
    storage_root: Path

    def run(self, job: PublicDownloadJob) -> PublicDownloadJobResult:
        output_dir = job_output_dir(self.storage_root, job.job_id)
        try:
            try:
                result = self.downloader.download_public(job.url, output_dir)
            except DownloadError as exc:
                return PublicDownloadJobResult(
                    job_id=job.job_id,
                    status=JobStatus.FAILED,
                    error=exc,
                )
            except Exception:
                return PublicDownloadJobResult(
                    job_id=job.job_id,
                    status=JobStatus.FAILED,
                    error=DownloadError(
                        code=ErrorCode.INTERNAL_ERROR,
                        safe_message="Something went wrong. Please try again later.",
                        retryable=True,
                    ),
                )
            try:
                self.sender.send_media_result(chat_id=job.chat_id, result=result)
            except Exception:
                return PublicDownloadJobResult(
                    job_id=job.job_id,
                    status=JobStatus.FAILED,
                    error=telegram_upload_failed(),
                )
            return PublicDownloadJobResult(
                job_id=job.job_id,
                status=JobStatus.COMPLETED,
                media_result=result,
            )
        finally:
            cleanup_job_output(self.storage_root, job.job_id)
