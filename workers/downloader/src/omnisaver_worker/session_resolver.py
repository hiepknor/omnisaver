from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from omnisaver_db import SessionRepository, SessionStatus, UserSessionRecord
from omnisaver_downloader import (
    AuthenticatedSession,
    DownloadError,
    Platform,
    session_expired,
    session_missing,
)
from omnisaver_session_vault import EncryptedSession, SessionVault, session_associated_data


class SessionResolver(Protocol):
    def resolve(self, *, telegram_user_id: int, platform: Platform) -> AuthenticatedSession:
        pass


@dataclass(frozen=True)
class VaultSessionResolver:
    repository: SessionRepository
    vault: SessionVault

    def resolve(self, *, telegram_user_id: int, platform: Platform) -> AuthenticatedSession:
        record = self.repository.get_session(
            telegram_user_id=telegram_user_id,
            platform=platform.value,
        )
        if record is None or record.status is SessionStatus.REVOKED:
            raise session_missing(platform.value)
        if record.status is SessionStatus.EXPIRED or _is_expired(record):
            raise session_expired(platform.value)

        payload = self.vault.decrypt(
            EncryptedSession(
                key_id=record.encryption_key_id,
                payload=record.encrypted_session,
            ),
            associated_data=session_associated_data(
                user_id=str(record.user_id),
                platform=platform.value,
            ),
        )
        return AuthenticatedSession(
            platform=platform,
            owner_user_id=str(record.user_id),
            payload=payload,
        )


def resolve_session_or_error(
    *,
    resolver: SessionResolver | None,
    telegram_user_id: int,
    platform: Platform,
) -> AuthenticatedSession:
    if resolver is None:
        raise session_missing(platform.value)
    try:
        return resolver.resolve(telegram_user_id=telegram_user_id, platform=platform)
    except DownloadError:
        raise


def _is_expired(record: UserSessionRecord) -> bool:
    return record.expires_at is not None and record.expires_at <= datetime.now(UTC).replace(
        tzinfo=None
    )
