from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import psycopg
from psycopg import Connection

from omnisaver_db.models import DownloadJobCreate, DownloadJobRecord, DownloadJobStatus
from omnisaver_downloader import DownloadError, MediaResult


class PostgresDownloadJobRepository:
    def __init__(self, connection: Connection[tuple[object, ...]]) -> None:
        self.connection = connection

    @classmethod
    def connect(cls, database_url: str) -> PostgresDownloadJobRepository:
        return cls(psycopg.connect(database_url))

    def create_queued_job(self, job: DownloadJobCreate) -> DownloadJobRecord:
        user_id = self._upsert_user(job.telegram_user_id)
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO download_jobs (
                    id, user_id, telegram_chat_id, platform, url, status, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    job.id,
                    user_id,
                    job.telegram_chat_id,
                    job.platform,
                    job.url,
                    DownloadJobStatus.QUEUED.value,
                ),
            )
        self.connection.commit()
        return self._require_job(job.id)

    def mark_started(self, job_id: UUID) -> DownloadJobRecord:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE download_jobs
                SET status = %s, started_at = COALESCE(started_at, CURRENT_TIMESTAMP)
                WHERE id = %s
                """,
                (DownloadJobStatus.STARTED.value, job_id),
            )
        self.connection.commit()
        return self._require_job(job_id)

    def mark_completed(self, job_id: UUID, result: MediaResult) -> DownloadJobRecord:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE download_jobs
                SET status = %s,
                    error_code = NULL,
                    error_message = NULL,
                    finished_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (DownloadJobStatus.COMPLETED.value, job_id),
            )
            cursor.executemany(
                """
                INSERT INTO download_results (
                    id, job_id, media_type, file_path, file_size, mime_type, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                [
                    (
                        uuid4(),
                        job_id,
                        media_file.type.value,
                        str(media_file.path),
                        media_file.size_bytes,
                        media_file.mime_type,
                    )
                    for media_file in result.media
                ],
            )
        self.connection.commit()
        return self._require_job(job_id)

    def mark_failed(self, job_id: UUID, error: DownloadError) -> DownloadJobRecord:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE download_jobs
                SET status = %s,
                    error_code = %s,
                    error_message = %s,
                    finished_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (DownloadJobStatus.FAILED.value, error.code.value, error.safe_message, job_id),
            )
        self.connection.commit()
        return self._require_job(job_id)

    def get_job(self, job_id: UUID) -> DownloadJobRecord | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, telegram_chat_id, platform, url, status, error_code,
                       error_message, created_at, started_at, finished_at
                FROM download_jobs
                WHERE id = %s
                """,
                (job_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return _record_from_row(row)

    def list_recent_jobs(self, user_id: UUID, *, limit: int = 10) -> list[DownloadJobRecord]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, telegram_chat_id, platform, url, status, error_code,
                       error_message, created_at, started_at, finished_at
                FROM download_jobs
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            rows = cursor.fetchall()
        return [_record_from_row(row) for row in rows]

    def _upsert_user(self, telegram_user_id: int) -> UUID:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (id, telegram_user_id, status, created_at, updated_at)
                VALUES (%s, %s, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (telegram_user_id)
                DO UPDATE SET updated_at = EXCLUDED.updated_at
                RETURNING id
                """,
                (uuid4(), telegram_user_id),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError("failed to upsert user")
        return _as_uuid(row[0])

    def _require_job(self, job_id: UUID) -> DownloadJobRecord:
        record = self.get_job(job_id)
        if record is None:
            raise KeyError(f"download job not found: {job_id}")
        return record


def _record_from_row(row: tuple[object, ...]) -> DownloadJobRecord:
    return DownloadJobRecord(
        id=_as_uuid(row[0]),
        user_id=_as_uuid(row[1]),
        telegram_chat_id=_as_int(row[2]),
        platform=str(row[3]),
        url=str(row[4]),
        status=DownloadJobStatus(str(row[5])),
        error_code=_as_optional_str(row[6]),
        error_message=_as_optional_str(row[7]),
        created_at=_as_datetime(row[8]),
        started_at=_as_optional_datetime(row[9]),
        finished_at=_as_optional_datetime(row[10]),
    )


def _as_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"expected int, got {type(value).__name__}")


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    raise TypeError(f"expected datetime, got {type(value).__name__}")


def _as_optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return _as_datetime(value)
