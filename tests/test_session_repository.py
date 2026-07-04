from datetime import UTC, datetime, timedelta

from omnisaver_db import InMemorySessionRepository, SessionStatus, hash_connect_token


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
