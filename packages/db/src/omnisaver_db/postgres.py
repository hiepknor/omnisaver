from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import psycopg
from psycopg import Connection

from omnisaver_db.models import (
    ConnectTokenRecord,
    DownloadJobCreate,
    DownloadJobRecord,
    DownloadJobStatus,
    SessionStatus,
    UserSessionRecord,
)
from omnisaver_db.session_repository import hash_connect_token
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

    def list_recent_jobs_for_telegram_user(
        self,
        telegram_user_id: int,
        *,
        limit: int = 5,
    ) -> list[DownloadJobRecord]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT dj.id, dj.user_id, dj.telegram_chat_id, dj.platform, dj.url,
                       dj.status, dj.error_code, dj.error_message, dj.created_at,
                       dj.started_at, dj.finished_at
                FROM download_jobs dj
                JOIN users u ON u.id = dj.user_id
                WHERE u.telegram_user_id = %s
                ORDER BY dj.created_at DESC
                LIMIT %s
                """,
                (telegram_user_id, limit),
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


class PostgresSessionRepository:
    def __init__(self, connection: Connection[tuple[object, ...]]) -> None:
        self.connection = connection

    @classmethod
    def connect(cls, database_url: str) -> PostgresSessionRepository:
        return cls(psycopg.connect(database_url))

    def create_connect_token(
        self,
        *,
        telegram_user_id: int,
        platform: str,
        ttl_seconds: int,
    ) -> tuple[str, ConnectTokenRecord]:
        import secrets

        token = secrets.token_urlsafe(32)
        token_hash = hash_connect_token(token)
        user_id = self._upsert_user(telegram_user_id)
        token_id = uuid4()
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO connect_tokens (
                    id, token_hash, user_id, platform, used_at, expires_at, created_at
                )
                VALUES (
                    %s, %s, %s, %s, NULL,
                    CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                    CURRENT_TIMESTAMP
                )
                """,
                (token_id, token_hash, user_id, platform, ttl_seconds),
            )
        self.connection.commit()
        return token, self._require_connect_token(token_hash)

    def get_valid_connect_token(self, *, token: str, platform: str) -> ConnectTokenRecord | None:
        token_hash = hash_connect_token(token)
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT ct.id, ct.token_hash, ct.user_id, u.telegram_user_id, ct.platform,
                       ct.used_at, ct.expires_at, ct.created_at
                FROM connect_tokens ct
                JOIN users u ON u.id = ct.user_id
                WHERE ct.token_hash = %s
                  AND ct.platform = %s
                  AND ct.used_at IS NULL
                  AND ct.expires_at > CURRENT_TIMESTAMP
                """,
                (token_hash, platform),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return _connect_token_from_row(row)

    def mark_connect_token_used(self, *, token: str) -> ConnectTokenRecord:
        token_hash = hash_connect_token(token)
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE connect_tokens
                SET used_at = CURRENT_TIMESTAMP
                WHERE token_hash = %s
                """,
                (token_hash,),
            )
        self.connection.commit()
        return self._require_connect_token(token_hash)

    def store_encrypted_session(
        self,
        *,
        telegram_user_id: int,
        platform: str,
        encrypted_session: bytes,
        encryption_key_id: str,
        expires_at: datetime | None = None,
    ) -> UserSessionRecord:
        user_id = self._upsert_user(telegram_user_id)
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_sessions (
                    id, user_id, platform, encrypted_session, encryption_key_id, status,
                    expires_at, last_checked_at, created_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT (user_id, platform)
                DO UPDATE SET encrypted_session = EXCLUDED.encrypted_session,
                              encryption_key_id = EXCLUDED.encryption_key_id,
                              status = EXCLUDED.status,
                              expires_at = EXCLUDED.expires_at,
                              last_checked_at = EXCLUDED.last_checked_at,
                              updated_at = EXCLUDED.updated_at
                """,
                (
                    uuid4(),
                    user_id,
                    platform,
                    encrypted_session,
                    encryption_key_id,
                    SessionStatus.CONNECTED.value,
                    expires_at,
                ),
            )
        self.connection.commit()
        return self._require_session(telegram_user_id=telegram_user_id, platform=platform)

    def get_session(
        self,
        *,
        telegram_user_id: int,
        platform: str,
    ) -> UserSessionRecord | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT us.id, us.user_id, u.telegram_user_id, us.platform,
                       us.encrypted_session, us.encryption_key_id, us.status,
                       us.expires_at, us.last_checked_at, us.created_at, us.updated_at
                FROM user_sessions us
                JOIN users u ON u.id = us.user_id
                WHERE u.telegram_user_id = %s
                  AND us.platform = %s
                """,
                (telegram_user_id, platform),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return _user_session_from_row(row)

    def list_sessions(self, *, telegram_user_id: int) -> list[UserSessionRecord]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT us.id, us.user_id, u.telegram_user_id, us.platform,
                       us.encrypted_session, us.encryption_key_id, us.status,
                       us.expires_at, us.last_checked_at, us.created_at, us.updated_at
                FROM user_sessions us
                JOIN users u ON u.id = us.user_id
                WHERE u.telegram_user_id = %s
                ORDER BY us.platform
                """,
                (telegram_user_id,),
            )
            rows = cursor.fetchall()
        return [_user_session_from_row(row) for row in rows]

    def revoke_session(self, *, telegram_user_id: int, platform: str) -> UserSessionRecord:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_sessions
                SET encrypted_session = %s,
                    status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = (
                    SELECT id FROM users WHERE telegram_user_id = %s
                )
                  AND platform = %s
                """,
                (b"", SessionStatus.REVOKED.value, telegram_user_id, platform),
            )
        self.connection.commit()
        return self._require_session(telegram_user_id=telegram_user_id, platform=platform)

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

    def _require_connect_token(self, token_hash: str) -> ConnectTokenRecord:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT ct.id, ct.token_hash, ct.user_id, u.telegram_user_id, ct.platform,
                       ct.used_at, ct.expires_at, ct.created_at
                FROM connect_tokens ct
                JOIN users u ON u.id = ct.user_id
                WHERE ct.token_hash = %s
                """,
                (token_hash,),
            )
            row = cursor.fetchone()
        if row is None:
            raise KeyError("connect token not found")
        return _connect_token_from_row(row)

    def _require_session(self, *, telegram_user_id: int, platform: str) -> UserSessionRecord:
        record = self.get_session(telegram_user_id=telegram_user_id, platform=platform)
        if record is None:
            raise KeyError(f"session not found: {telegram_user_id}:{platform}")
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


def _connect_token_from_row(row: tuple[object, ...]) -> ConnectTokenRecord:
    return ConnectTokenRecord(
        id=_as_uuid(row[0]),
        token_hash=str(row[1]),
        user_id=_as_uuid(row[2]),
        telegram_user_id=_as_int(row[3]),
        platform=str(row[4]),
        used_at=_as_optional_datetime(row[5]),
        expires_at=_as_datetime(row[6]),
        created_at=_as_datetime(row[7]),
    )


def _user_session_from_row(row: tuple[object, ...]) -> UserSessionRecord:
    return UserSessionRecord(
        id=_as_uuid(row[0]),
        user_id=_as_uuid(row[1]),
        telegram_user_id=_as_int(row[2]),
        platform=str(row[3]),
        encrypted_session=_as_bytes(row[4]),
        encryption_key_id=str(row[5]),
        status=SessionStatus(str(row[6])),
        expires_at=_as_optional_datetime(row[7]),
        last_checked_at=_as_optional_datetime(row[8]),
        created_at=_as_datetime(row[9]),
        updated_at=_as_datetime(row[10]),
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


def _as_bytes(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, memoryview):
        return value.tobytes()
    raise TypeError(f"expected bytes, got {type(value).__name__}")


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    raise TypeError(f"expected datetime, got {type(value).__name__}")


def _as_optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return _as_datetime(value)
