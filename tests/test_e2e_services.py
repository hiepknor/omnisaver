from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import psycopg
import pytest
import redis
from fastapi.testclient import TestClient

from omnisaver_bot.runtime import BotDependencies, message_handler
from omnisaver_db import (
    DownloadJobStatus,
    PostgresDownloadJobRepository,
    PostgresSessionRepository,
)
from omnisaver_downloader import (
    AuthenticatedSession,
    DownloadError,
    ErrorCode,
    MediaFile,
    MediaResult,
    MediaType,
    Platform,
)
from omnisaver_session_vault import SessionVault
from omnisaver_web import BasicSessionValidator, PortalDependencies, create_app
from omnisaver_worker import (
    PublicDownloadJob,
    PublicDownloadJobRunner,
    VaultSessionResolver,
    WorkerService,
    build_redis_job_queue,
)

SERVICE_E2E_ENV = "OMNISAVER_RUN_SERVICE_E2E"
DATABASE_URL = os.environ.get(
    "OMNISAVER_E2E_DATABASE_URL",
    "postgresql://omnisaver:change-me@localhost:5432/omnisaver",
)
REDIS_URL = os.environ.get("OMNISAVER_E2E_REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME = "omnisaver:e2e_download_jobs"
INSTAGRAM_COOKIES = "\n".join(
    [
        "# Netscape HTTP Cookie File",
        ".instagram.com\tTRUE\t/\tTRUE\t1893456000\tsessionid\tprivate-session",
        ".instagram.com\tTRUE\t/\tTRUE\t1893456000\tcsrftoken\tcsrf-token",
        ".instagram.com\tTRUE\t/\tTRUE\t1893456000\tds_user_id\t123",
    ]
)

pytestmark = pytest.mark.skipif(
    os.environ.get(SERVICE_E2E_ENV) != "1",
    reason=f"set {SERVICE_E2E_ENV}=1 and start local PostgreSQL/Redis services",
)


@dataclass
class FakeUser:
    id: int


@dataclass
class FakeChat:
    id: int


@dataclass
class FakeMessage:
    text: str
    replies: list[str] = field(default_factory=list)

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


@dataclass
class FakeUpdate:
    effective_message: FakeMessage
    effective_user: FakeUser = field(default_factory=lambda: FakeUser(id=123))
    effective_chat: FakeChat = field(default_factory=lambda: FakeChat(id=456))


@dataclass
class FakeApplication:
    bot_data: dict[str, object]


@dataclass
class FakeContext:
    application: FakeApplication


class FakeDownloader:
    def __init__(self) -> None:
        self.public_calls: list[str] = []
        self.authenticated_sessions: list[AuthenticatedSession] = []

    def download_public(self, url: str, output_dir: Path) -> MediaResult:
        self.public_calls.append(url)
        output_dir.mkdir(parents=True, exist_ok=True)
        media_path = output_dir / "public.txt"
        media_path.write_text("public media")
        return _media_result(platform=Platform.YOUTUBE, url=url, media_path=media_path)

    def download_authenticated(
        self,
        url: str,
        output_dir: Path,
        session: AuthenticatedSession,
    ) -> MediaResult:
        self.authenticated_sessions.append(session)
        if session.payload != INSTAGRAM_COOKIES.encode("utf-8"):
            raise DownloadError(
                code=ErrorCode.ACCESS_DENIED,
                safe_message="wrong session payload",
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        media_path = output_dir / "private.txt"
        media_path.write_text("private media")
        return _media_result(platform=session.platform, url=url, media_path=media_path)


class FakeSender:
    def __init__(self) -> None:
        self.sent_chat_ids: list[int] = []

    def send_media_result(self, *, chat_id: int, result: MediaResult) -> None:
        self.sent_chat_ids.append(chat_id)


@pytest.fixture()
def service_environment() -> Generator[None, None, None]:
    _apply_schema()
    _clear_database()
    _redis_client().delete(QUEUE_NAME)
    yield
    _redis_client().delete(QUEUE_NAME)
    _clear_database()


def test_public_download_e2e_uses_bot_queue_worker_and_postgres(
    service_environment: None,
    tmp_path: Path,
) -> None:
    queue = build_redis_job_queue(REDIS_URL, queue_name=QUEUE_NAME)
    session_repository = _session_repository()
    history_repository = _download_repository()
    dependencies = BotDependencies(
        queue=queue,
        session_repository=session_repository,
        history_repository=history_repository,
        public_base_url="https://omnisaver.onio.cc",
        connect_token_ttl_seconds=600,
    )
    update = FakeUpdate(
        effective_message=FakeMessage("save https://www.youtube.com/watch?v=abc")
    )
    downloader = FakeDownloader()
    sender = FakeSender()
    worker = WorkerService(
        queue=queue,
        repository=_download_repository(),
        runner=PublicDownloadJobRunner(
            downloader=downloader,
            sender=sender,
            storage_root=tmp_path,
        ),
    )

    asyncio.run(
        message_handler(
            cast(Any, update),
            cast(Any, FakeContext(FakeApplication({"dependencies": dependencies}))),
        )
    )
    processed = worker.process_one()

    assert processed is True
    assert "Queued youtube download. Job ID:" in update.effective_message.replies[0]
    assert downloader.public_calls == ["https://www.youtube.com/watch?v=abc"]
    assert sender.sent_chat_ids == [456]
    jobs = history_repository.list_recent_jobs_for_telegram_user(123, limit=1)
    assert len(jobs) == 1
    assert jobs[0].status is DownloadJobStatus.COMPLETED
    assert jobs[0].platform == Platform.YOUTUBE.value


def test_authorized_download_e2e_uses_web_session_worker_and_postgres(
    service_environment: None,
    tmp_path: Path,
) -> None:
    vault = SessionVault.from_base64_key(SessionVault.generate_master_key_base64(), key_id="e2e")
    session_repository = _session_repository()
    token, _record = session_repository.create_connect_token(
        telegram_user_id=123,
        platform=Platform.INSTAGRAM.value,
        ttl_seconds=600,
    )
    app = create_app(
        PortalDependencies(
            repository=session_repository,
            vault=vault,
            validator=BasicSessionValidator(),
        )
    )
    queue = build_redis_job_queue(REDIS_URL, queue_name=QUEUE_NAME)
    downloader = FakeDownloader()
    sender = FakeSender()
    worker = WorkerService(
        queue=queue,
        repository=_download_repository(),
        runner=PublicDownloadJobRunner(
            downloader=downloader,
            sender=sender,
            storage_root=tmp_path,
            session_resolver=VaultSessionResolver(
                repository=_session_repository(),
                vault=vault,
            ),
        ),
    )

    response = TestClient(app).post(
        "/connect/instagram",
        json={"token": token, "session_payload": INSTAGRAM_COOKIES},
    )
    assert response.status_code == 200

    owner_job = PublicDownloadJob(
        job_id=str(uuid4()),
        telegram_user_id=123,
        chat_id=456,
        platform=Platform.INSTAGRAM,
        url="https://www.instagram.com/p/private",
        requires_auth=True,
    )
    other_user_job = PublicDownloadJob(
        job_id=str(uuid4()),
        telegram_user_id=999,
        chat_id=777,
        platform=Platform.INSTAGRAM,
        url="https://www.instagram.com/p/private",
        requires_auth=True,
    )
    queue.enqueue(owner_job)
    queue.enqueue(other_user_job)

    assert worker.process_one() is True
    assert worker.process_one() is True

    owner_record = _download_repository().get_job(UUID(owner_job.job_id))
    other_record = _download_repository().get_job(
        UUID(other_user_job.job_id)
    )
    assert owner_record is not None
    assert other_record is not None
    assert owner_record.status is DownloadJobStatus.COMPLETED
    assert other_record.status is DownloadJobStatus.FAILED
    assert other_record.error_code == ErrorCode.SESSION_MISSING.value
    assert len(downloader.authenticated_sessions) == 1
    assert downloader.authenticated_sessions[0].platform is Platform.INSTAGRAM
    assert sender.sent_chat_ids == [456]


def _media_result(*, platform: Platform, url: str, media_path: Path) -> MediaResult:
    return MediaResult(
        platform=platform,
        source_url=url,
        title="",
        caption="",
        media=(
            MediaFile(
                type=MediaType.DOCUMENT,
                path=media_path,
                mime_type="text/plain",
                size_bytes=media_path.stat().st_size,
            ),
        ),
    )


def _apply_schema() -> None:
    migration = Path("packages/db/migrations/001_initial.sql").read_text()
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(migration)
        connection.commit()


def _clear_database() -> None:
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                TRUNCATE TABLE
                    audit_events,
                    download_results,
                    download_jobs,
                    connect_tokens,
                    user_sessions,
                    users
                CASCADE
                """
            )
        connection.commit()


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL)


def _download_repository() -> PostgresDownloadJobRepository:
    repository = PostgresDownloadJobRepository.connect(DATABASE_URL)
    repository.connection.autocommit = True
    return repository


def _session_repository() -> PostgresSessionRepository:
    repository = PostgresSessionRepository.connect(DATABASE_URL)
    repository.connection.autocommit = True
    return repository
