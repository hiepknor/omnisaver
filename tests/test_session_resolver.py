import base64
from datetime import UTC, datetime, timedelta

import pytest

from omnisaver_db import InMemorySessionRepository, SessionStatus
from omnisaver_downloader import DownloadError, ErrorCode, Platform
from omnisaver_session_vault import SessionVault, session_associated_data
from omnisaver_worker import VaultSessionResolver


def _vault() -> SessionVault:
    return SessionVault.from_base64_key(
        base64.b64encode(b"4" * 32).decode("ascii"),
        key_id="key-1",
    )


def _store_session(
    *,
    repository: InMemorySessionRepository,
    vault: SessionVault,
    telegram_user_id: int = 123,
    platform: Platform = Platform.INSTAGRAM,
    expires_at: datetime | None = None,
) -> None:
    user_id = repository._user_id_for_telegram_id(telegram_user_id)
    encrypted = vault.encrypt(
        b'{"session":"sensitive-marker"}',
        associated_data=session_associated_data(
            user_id=str(user_id),
            platform=platform.value,
        ),
    )
    repository.store_encrypted_session(
        telegram_user_id=telegram_user_id,
        platform=platform.value,
        encrypted_session=encrypted.payload,
        encryption_key_id=encrypted.key_id,
        expires_at=expires_at,
    )


def test_vault_session_resolver_decrypts_only_requesting_user_session() -> None:
    repository = InMemorySessionRepository()
    vault = _vault()
    _store_session(repository=repository, vault=vault, telegram_user_id=123)
    resolver = VaultSessionResolver(repository=repository, vault=vault)

    session = resolver.resolve(telegram_user_id=123, platform=Platform.INSTAGRAM)

    assert session.platform is Platform.INSTAGRAM
    assert session.payload == b'{"session":"sensitive-marker"}'
    assert "sensitive-marker" not in repr(session)

    with pytest.raises(DownloadError) as exc_info:
        resolver.resolve(telegram_user_id=456, platform=Platform.INSTAGRAM)

    assert exc_info.value.code is ErrorCode.SESSION_MISSING


def test_vault_session_resolver_rejects_revoked_session() -> None:
    repository = InMemorySessionRepository()
    vault = _vault()
    _store_session(repository=repository, vault=vault, telegram_user_id=123)
    repository.revoke_session(telegram_user_id=123, platform=Platform.INSTAGRAM.value)
    resolver = VaultSessionResolver(repository=repository, vault=vault)

    with pytest.raises(DownloadError) as exc_info:
        resolver.resolve(telegram_user_id=123, platform=Platform.INSTAGRAM)

    assert exc_info.value.code is ErrorCode.SESSION_MISSING


def test_vault_session_resolver_rejects_expired_session() -> None:
    repository = InMemorySessionRepository()
    vault = _vault()
    _store_session(
        repository=repository,
        vault=vault,
        telegram_user_id=123,
        expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1),
    )
    resolver = VaultSessionResolver(repository=repository, vault=vault)

    with pytest.raises(DownloadError) as exc_info:
        resolver.resolve(telegram_user_id=123, platform=Platform.INSTAGRAM)

    assert exc_info.value.code is ErrorCode.SESSION_EXPIRED


def test_vault_session_resolver_rejects_expired_status() -> None:
    repository = InMemorySessionRepository()
    vault = _vault()
    _store_session(repository=repository, vault=vault, telegram_user_id=123)
    record = repository.get_session(telegram_user_id=123, platform=Platform.INSTAGRAM.value)
    assert record is not None
    repository.sessions[(123, Platform.INSTAGRAM.value)] = record.__class__(
        **{**record.__dict__, "status": SessionStatus.EXPIRED}
    )
    resolver = VaultSessionResolver(repository=repository, vault=vault)

    with pytest.raises(DownloadError) as exc_info:
        resolver.resolve(telegram_user_id=123, platform=Platform.INSTAGRAM)

    assert exc_info.value.code is ErrorCode.SESSION_EXPIRED
