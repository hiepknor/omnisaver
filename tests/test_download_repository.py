from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import uuid4

from omnisaver_db import DownloadJobStatus, PostgresDownloadJobRepository


class FakePostgresConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.job_id = uuid4()
        self.user_id = uuid4()

    def cursor(self) -> FakePostgresCursor:
        return FakePostgresCursor(self)


class FakePostgresCursor:
    def __init__(self, connection: FakePostgresConnection) -> None:
        self.connection = connection
        self.fetchall_result: list[tuple[Any, ...]] = []

    def __enter__(self) -> FakePostgresCursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[Any, ...]) -> None:
        normalized = " ".join(query.split())
        self.connection.executed.append((normalized, params))
        self.fetchall_result = [
            (
                self.connection.job_id,
                self.connection.user_id,
                456,
                "instagram",
                "https://example.com/reel",
                DownloadJobStatus.FAILED.value,
                "LOGIN_REQUIRED",
                "login required",
                datetime(2026, 7, 4),
                None,
                datetime(2026, 7, 4),
            )
        ]

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.fetchall_result


def test_postgres_download_repository_lists_recent_jobs_by_telegram_user() -> None:
    connection = FakePostgresConnection()
    repository = PostgresDownloadJobRepository(cast(Any, connection))

    jobs = repository.list_recent_jobs_for_telegram_user(telegram_user_id=123, limit=5)

    assert len(jobs) == 1
    assert jobs[0].id == connection.job_id
    assert jobs[0].user_id == connection.user_id
    assert jobs[0].status is DownloadJobStatus.FAILED
    assert jobs[0].error_message == "login required"
    query, params = connection.executed[0]
    assert "JOIN users u ON u.id = dj.user_id" in query
    assert "WHERE u.telegram_user_id = %s" in query
    assert params == (123, 5)
