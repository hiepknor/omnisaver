from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from omnisaver_db import (
    InMemorySessionRepository,
    PostgresSessionRepository,
    SessionStatus,
    hash_connect_token,
)


class FakePostgresConnection:
    def __init__(self) -> None:
        self.user_id = uuid4()
        self.session_id = uuid4()
        self.token_id = uuid4()
        self.commits = 0
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.last_connect_token_hash = ""
        self.session_status = SessionStatus.CONNECTED

    def cursor(self) -> "FakePostgresCursor":
        return FakePostgresCursor(self)

    def commit(self) -> None:
        self.commits += 1


class FakePostgresCursor:
    def __init__(self, connection: FakePostgresConnection) -> None:
        self.connection = connection
        self.fetchone_result: tuple[Any, ...] | None = None
        self.fetchall_result: list[tuple[Any, ...]] = []

    def __enter__(self) -> "FakePostgresCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[Any, ...]) -> None:
        normalized = " ".join(query.split())
        self.connection.executed.append((normalized, params))
        if normalized.startswith("INSERT INTO users"):
            self.fetchone_result = (self.connection.user_id,)
            return
        if normalized.startswith("INSERT INTO connect_tokens"):
            self.connection.last_connect_token_hash = str(params[1])
            self.fetchone_result = None
            return
        if normalized.startswith("INSERT INTO user_sessions"):
            self.fetchone_result = None
            return
        if "FROM connect_tokens ct" in normalized:
            token_hash = str(params[0])
            self.fetchone_result = (
                self.connection.token_id,
                token_hash,
                self.connection.user_id,
                123,
                "instagram",
                None,
                datetime(2030, 1, 1),
                datetime(2029, 1, 1),
            )
            return
        if "FROM user_sessions us" in normalized and "WHERE u.telegram_user_id" in normalized:
            self.fetchone_result = _session_row(
                session_id=self.connection.session_id,
                user_id=self.connection.user_id,
                telegram_user_id=int(params[0]),
                platform=str(params[1]),
                encrypted_session=b"encrypted",
                status=self.connection.session_status,
            )
            self.fetchall_result = [self.fetchone_result]
            return
        if normalized.startswith("UPDATE user_sessions"):
            self.connection.session_status = SessionStatus(str(params[1]))
            self.fetchone_result = None
            return
        self.fetchone_result = None

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.fetchone_result

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.fetchall_result


def _session_row(
    *,
    session_id: UUID,
    user_id: UUID,
    telegram_user_id: int,
    platform: str,
    encrypted_session: bytes,
    status: SessionStatus,
) -> tuple[Any, ...]:
    return (
        session_id,
        user_id,
        telegram_user_id,
        platform,
        encrypted_session,
        "key-1",
        status.value,
        None,
        datetime(2029, 1, 1),
        datetime(2029, 1, 1),
        datetime(2029, 1, 1),
    )


def test_connect_tokens_are_hashed_bound_to_platform_and_one_time() -> None:
    repository = InMemorySessionRepository()
    token, record = repository.create_connect_token(
        telegram_user_id=123,
        platform="instagram",
        ttl_seconds=600,
    )

    assert token not in repository.connect_tokens
    assert record.token_hash == hash_connect_token(token)
    assert repository.get_valid_connect_token(token=token, platform="instagram") == record
    assert repository.get_valid_connect_token(token=token, platform="facebook") is None

    repository.mark_connect_token_used(token=token)

    assert repository.get_valid_connect_token(token=token, platform="instagram") is None


def test_expired_connect_token_cannot_be_used() -> None:
    repository = InMemorySessionRepository()
    token, record = repository.create_connect_token(
        telegram_user_id=123,
        platform="instagram",
        ttl_seconds=600,
    )
    repository.connect_tokens[record.token_hash] = record.__class__(
        **{
            **record.__dict__,
            "expires_at": datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1),
        }
    )

    assert repository.get_valid_connect_token(token=token, platform="instagram") is None


def test_sessions_are_owned_by_telegram_user_and_revoked_without_payload() -> None:
    repository = InMemorySessionRepository()
    session = repository.store_encrypted_session(
        telegram_user_id=123,
        platform="instagram",
        encrypted_session=b"encrypted",
        encryption_key_id="key-1",
    )

    assert repository.get_session(telegram_user_id=123, platform="instagram") == session
    assert repository.get_session(telegram_user_id=456, platform="instagram") is None

    revoked = repository.revoke_session(telegram_user_id=123, platform="instagram")

    assert revoked.status is SessionStatus.REVOKED
    assert revoked.encrypted_session == b""


def test_postgres_connect_tokens_are_hashed_before_storage() -> None:
    connection = FakePostgresConnection()
    repository = PostgresSessionRepository(cast(Any, connection))

    token, record = repository.create_connect_token(
        telegram_user_id=123,
        platform="instagram",
        ttl_seconds=600,
    )

    assert token != connection.last_connect_token_hash
    assert record.token_hash == hash_connect_token(token)
    assert connection.commits == 1
    insert_query, insert_params = connection.executed[1]
    assert insert_query.startswith("INSERT INTO connect_tokens")
    assert insert_params[1] == hash_connect_token(token)


def test_postgres_session_repository_uses_owner_and_platform_for_session_lookup() -> None:
    connection = FakePostgresConnection()
    repository = PostgresSessionRepository(cast(Any, connection))

    session = repository.get_session(telegram_user_id=123, platform="instagram")

    assert session is not None
    assert session.telegram_user_id == 123
    assert session.platform == "instagram"
    assert session.encrypted_session == b"encrypted"
    lookup_query, lookup_params = connection.executed[-1]
    assert "WHERE u.telegram_user_id = %s AND us.platform = %s" in lookup_query
    assert lookup_params == (123, "instagram")


def test_postgres_session_repository_upserts_encrypted_session() -> None:
    connection = FakePostgresConnection()
    repository = PostgresSessionRepository(cast(Any, connection))

    session = repository.store_encrypted_session(
        telegram_user_id=123,
        platform="instagram",
        encrypted_session=b"encrypted",
        encryption_key_id="key-1",
    )

    insert_query, insert_params = connection.executed[1]
    assert insert_query.startswith("INSERT INTO user_sessions")
    assert insert_params[2:6] == (
        "instagram",
        b"encrypted",
        "key-1",
        SessionStatus.CONNECTED.value,
    )
    assert session.telegram_user_id == 123
    assert session.platform == "instagram"
    assert connection.commits == 1


def test_postgres_session_repository_revokes_without_plaintext_payload() -> None:
    connection = FakePostgresConnection()
    repository = PostgresSessionRepository(cast(Any, connection))

    revoked = repository.revoke_session(telegram_user_id=123, platform="instagram")

    update_query, update_params = connection.executed[0]
    assert update_query.startswith("UPDATE user_sessions")
    assert update_params == (b"", SessionStatus.REVOKED.value, 123, "instagram")
    assert revoked.status is SessionStatus.REVOKED
    assert connection.commits == 1
