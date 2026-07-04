from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from omnisaver_db.models import (
    DownloadJobCreate,
    DownloadJobRecord,
    DownloadJobStatus,
    DownloadResultRecord,
)
from omnisaver_downloader import DownloadError, MediaResult


class DownloadJobRepository(Protocol):
    def create_queued_job(self, job: DownloadJobCreate) -> DownloadJobRecord:
        pass

    def mark_started(self, job_id: UUID) -> DownloadJobRecord:
        pass

    def mark_completed(self, job_id: UUID, result: MediaResult) -> DownloadJobRecord:
        pass

    def mark_failed(self, job_id: UUID, error: DownloadError) -> DownloadJobRecord:
        pass

    def get_job(self, job_id: UUID) -> DownloadJobRecord | None:
        pass

    def list_recent_jobs(self, user_id: UUID, *, limit: int = 10) -> list[DownloadJobRecord]:
        pass


class InMemoryDownloadJobRepository:
    def __init__(self) -> None:
        self.telegram_users: dict[int, UUID] = {}
        self.jobs: dict[UUID, DownloadJobRecord] = {}
        self.results: list[DownloadResultRecord] = []

    def create_queued_job(self, job: DownloadJobCreate) -> DownloadJobRecord:
        now = _now()
        user_id = self.telegram_users.setdefault(job.telegram_user_id, uuid4())
        record = DownloadJobRecord(
            id=job.id,
            user_id=user_id,
            telegram_chat_id=job.telegram_chat_id,
            platform=job.platform,
            url=job.url,
            status=DownloadJobStatus.QUEUED,
            error_code=None,
            error_message=None,
            created_at=now,
        )
        self.jobs[record.id] = record
        return record

    def mark_started(self, job_id: UUID) -> DownloadJobRecord:
        record = self._require_job(job_id)
        updated = replace(record, status=DownloadJobStatus.STARTED, started_at=_now())
        self.jobs[job_id] = updated
        return updated

    def mark_completed(self, job_id: UUID, result: MediaResult) -> DownloadJobRecord:
        record = self._require_job(job_id)
        now = _now()
        updated = replace(
            record,
            status=DownloadJobStatus.COMPLETED,
            error_code=None,
            error_message=None,
            finished_at=now,
        )
        self.jobs[job_id] = updated
        self.results.extend(
            DownloadResultRecord(
                id=uuid4(),
                job_id=job_id,
                media_type=media_file.type.value,
                file_path=str(media_file.path),
                file_size=media_file.size_bytes,
                mime_type=media_file.mime_type,
                telegram_file_id=None,
                created_at=now,
            )
            for media_file in result.media
        )
        return updated

    def mark_failed(self, job_id: UUID, error: DownloadError) -> DownloadJobRecord:
        record = self._require_job(job_id)
        updated = replace(
            record,
            status=DownloadJobStatus.FAILED,
            error_code=error.code.value,
            error_message=error.safe_message,
            finished_at=_now(),
        )
        self.jobs[job_id] = updated
        return updated

    def get_job(self, job_id: UUID) -> DownloadJobRecord | None:
        return self.jobs.get(job_id)

    def list_recent_jobs(self, user_id: UUID, *, limit: int = 10) -> list[DownloadJobRecord]:
        return sorted(
            (job for job in self.jobs.values() if job.user_id == user_id),
            key=lambda job: job.created_at,
            reverse=True,
        )[:limit]

    def _require_job(self, job_id: UUID) -> DownloadJobRecord:
        record = self.jobs.get(job_id)
        if record is None:
            raise KeyError(f"download job not found: {job_id}")
        return record


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
