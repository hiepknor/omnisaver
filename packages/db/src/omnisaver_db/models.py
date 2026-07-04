from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class DownloadJobStatus(StrEnum):
    QUEUED = "queued"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class DownloadJobCreate:
    id: UUID
    telegram_user_id: int
    telegram_chat_id: int
    platform: str
    url: str


@dataclass(frozen=True)
class DownloadJobRecord:
    id: UUID
    user_id: UUID
    telegram_chat_id: int
    platform: str
    url: str
    status: DownloadJobStatus
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(frozen=True)
class DownloadResultRecord:
    id: UUID
    job_id: UUID
    media_type: str
    file_path: str
    file_size: int
    mime_type: str
    telegram_file_id: str | None
    created_at: datetime
