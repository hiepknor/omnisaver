from omnisaver_bot import create_connect_link, disconnect_session, list_session_statuses
from omnisaver_db import InMemorySessionRepository, SessionStatus


def test_create_connect_link_uses_one_time_token_url_without_storing_plaintext_token() -> None:
    repository = InMemorySessionRepository()

    link = create_connect_link(
        repository=repository,
        public_base_url="https://omnisaver.onio.cc/",
        telegram_user_id=123,
        platform="instagram",
        ttl_seconds=600,
    )

    assert link.platform == "instagram"
    assert link.url.startswith("https://omnisaver.onio.cc/connect/instagram?token=")
    token = link.url.rsplit("=", 1)[1]
    assert token not in repository.connect_tokens
    assert repository.get_valid_connect_token(token=token, platform="instagram") is not None


def test_list_session_statuses_and_disconnect() -> None:
    repository = InMemorySessionRepository()
    repository.store_encrypted_session(
        telegram_user_id=123,
        platform="instagram",
        encrypted_session=b"encrypted",
        encryption_key_id="key-1",
    )

    lines = list_session_statuses(repository=repository, telegram_user_id=123)

    assert lines[0].startswith("instagram: connected, last checked ")
    assert "pinterest: not connected" in lines
    assert disconnect_session(
        repository=repository,
        telegram_user_id=123,
        platform="instagram",
    ) == "instagram: disconnected"
    revoked = repository.get_session(telegram_user_id=123, platform="instagram")
    assert revoked is not None
    assert revoked.status is SessionStatus.REVOKED
