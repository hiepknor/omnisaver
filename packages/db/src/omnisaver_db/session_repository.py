from __future__ import annotations

import hashlib
import secrets
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from omnisaver_db.models import ConnectTokenRecord, SessionStatus, UserSessionRecord


class SessionRepository(Protocol):
    def create_connect_token(
        self,
        *,
        telegram_user_id: int,
        platform: str,
        ttl_seconds: int,
    ) -> tuple[str, ConnectTokenRecord]:
        pass

    def get_valid_connect_token(self, *, token: str, platform: str) -> ConnectTokenRecord | None:
        pass

    def mark_connect_token_used(self, *, token: str) -> ConnectTokenRecord:
        pass

    def store_encrypted_session(
        self,
        *,
        telegram_user_id: int,
        platform: str,
        encrypted_session: bytes,
        encryption_key_id: str,
        expires_at: datetime | None = None,
    ) -> UserSessionRecord:
        pass

    def get_session(
        self,
        *,
        telegram_user_id: int,
        platform: str,
    ) -> UserSessionRecord | None:
        pass

    def list_sessions(self, *, telegram_user_id: int) -> list[UserSessionRecord]:
        pass

    def revoke_session(self, *, telegram_user_id: int, platform: str) -> UserSessionRecord:
        pass


class InMemorySessionRepository:
    def __init__(self) -> None:
        self.telegram_users: dict[int, UUID] = {}
        self.connect_tokens: dict[str, ConnectTokenRecord] = {}
        self.sessions: dict[tuple[int, str], UserSessionRecord] = {}

    def create_connect_token(
        self,
        *,
        telegram_user_id: int,
        platform: str,
        ttl_seconds: int,
    ) -> tuple[str, ConnectTokenRecord]:
        token = secrets.token_urlsafe(32)
        token_hash = hash_connect_token(token)
        now = _now()
        record = ConnectTokenRecord(
            id=uuid4(),
            token_hash=token_hash,
            user_id=self._user_id_for_telegram_id(telegram_user_id),
            telegram_user_id=telegram_user_id,
            platform=platform,
            used_at=None,
            expires_at=now + timedelta(seconds=ttl_seconds),
            created_at=now,
        )
        self.connect_tokens[token_hash] = record
        return token, record

    def get_valid_connect_token(self, *, token: str, platform: str) -> ConnectTokenRecord | None:
        record = self.connect_tokens.get(hash_connect_token(token))
        if record is None or record.platform != platform:
            return None
        if record.used_at is not None or record.expires_at <= _now():
            return None
        return record

    def mark_connect_token_used(self, *, token: str) -> ConnectTokenRecord:
        token_hash = hash_connect_token(token)
        record = self.connect_tokens[token_hash]
        updated = replace(record, used_at=_now())
        self.connect_tokens[token_hash] = updated
        return updated

    def store_encrypted_session(
        self,
        *,
        telegram_user_id: int,
        platform: str,
        encrypted_session: bytes,
        encryption_key_id: str,
        expires_at: datetime | None = None,
    ) -> UserSessionRecord:
        now = _now()
        key = (telegram_user_id, platform)
        existing = self.sessions.get(key)
        record = UserSessionRecord(
            id=existing.id if existing else uuid4(),
            user_id=self._user_id_for_telegram_id(telegram_user_id),
            telegram_user_id=telegram_user_id,
            platform=platform,
            encrypted_session=encrypted_session,
            encryption_key_id=encryption_key_id,
            status=SessionStatus.CONNECTED,
            expires_at=expires_at,
            last_checked_at=now,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self.sessions[key] = record
        return record

    def get_session(
        self,
        *,
        telegram_user_id: int,
        platform: str,
    ) -> UserSessionRecord | None:
        return self.sessions.get((telegram_user_id, platform))

    def list_sessions(self, *, telegram_user_id: int) -> list[UserSessionRecord]:
        return sorted(
            (
                session
                for (owner_id, _platform), session in self.sessions.items()
                if owner_id == telegram_user_id
            ),
            key=lambda session: session.platform,
        )

    def revoke_session(self, *, telegram_user_id: int, platform: str) -> UserSessionRecord:
        key = (telegram_user_id, platform)
        session = self.sessions[key]
        updated = replace(
            session,
            encrypted_session=b"",
            status=SessionStatus.REVOKED,
            updated_at=_now(),
        )
        self.sessions[key] = updated
        return updated

    def _user_id_for_telegram_id(self, telegram_user_id: int) -> UUID:
        return self.telegram_users.setdefault(telegram_user_id, uuid4())


def hash_connect_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
