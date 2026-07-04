from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from omnisaver_downloader import (
    AuthenticatedSession,
    DownloadError,
    ErrorCode,
    MediaResult,
    Platform,
    cleanup_job_output,
    job_output_dir,
    session_expired,
    telegram_upload_failed,
)
from omnisaver_media_processor import MediaProcessingContext, MediaProcessor, NoopMediaProcessor
from omnisaver_worker.session_resolver import SessionResolver, resolve_session_or_error


class JobStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class PublicDownloadJob:
    job_id: str
    telegram_user_id: int
    chat_id: int
    platform: Platform
    url: str
    requires_auth: bool = False


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

    def download_authenticated(
        self,
        url: str,
        output_dir: Path,
        session: AuthenticatedSession,
    ) -> MediaResult:
        pass


@dataclass(frozen=True)
class PublicDownloadJobRunner:
    downloader: PublicDownloadManager
    sender: TelegramSender
    storage_root: Path
    session_resolver: SessionResolver | None = None
    media_processor: MediaProcessor = field(default_factory=NoopMediaProcessor)

    def run(self, job: PublicDownloadJob) -> PublicDownloadJobResult:
        output_dir = job_output_dir(
            self.storage_root,
            job.job_id,
            telegram_user_id=job.telegram_user_id,
        )
        try:
            try:
                if job.requires_auth:
                    result = self._download_authenticated(job, output_dir)
                else:
                    result = self.downloader.download_public(job.url, output_dir)
                result = self.media_processor.process(
                    result,
                    context=MediaProcessingContext(
                        storage_root=self.storage_root,
                        output_dir=output_dir,
                        telegram_user_id=job.telegram_user_id,
                        job_id=job.job_id,
                    ),
                )
            except DownloadError as exc:
                if exc.code is ErrorCode.LOGIN_REQUIRED and not job.requires_auth:
                    try:
                        result = self._download_authenticated(job, output_dir)
                        result = self.media_processor.process(
                            result,
                            context=MediaProcessingContext(
                                storage_root=self.storage_root,
                                output_dir=output_dir,
                                telegram_user_id=job.telegram_user_id,
                                job_id=job.job_id,
                            ),
                        )
                    except DownloadError as auth_exc:
                        return PublicDownloadJobResult(
                            job_id=job.job_id,
                            status=JobStatus.FAILED,
                            error=auth_exc,
                        )
                else:
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
                        safe_message="Có lỗi xảy ra. Vui lòng thử lại sau.",
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
            cleanup_job_output(
                self.storage_root,
                job.job_id,
                telegram_user_id=job.telegram_user_id,
            )

    def _download_authenticated(self, job: PublicDownloadJob, output_dir: Path) -> MediaResult:
        session = resolve_session_or_error(
            resolver=self.session_resolver,
            telegram_user_id=job.telegram_user_id,
            platform=job.platform,
        )
        try:
            return self.downloader.download_authenticated(job.url, output_dir, session)
        except DownloadError as exc:
            if exc.code is ErrorCode.LOGIN_REQUIRED:
                raise session_expired(job.platform.value) from exc
            raise
