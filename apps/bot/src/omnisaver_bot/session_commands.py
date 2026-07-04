from __future__ import annotations

from dataclasses import dataclass

from omnisaver_db import SessionRepository, SessionStatus


@dataclass(frozen=True)
class ConnectLink:
    platform: str
    url: str
    expires_in_seconds: int


def create_connect_link(
    *,
    repository: SessionRepository,
    public_base_url: str,
    telegram_user_id: int,
    platform: str,
    ttl_seconds: int,
) -> ConnectLink:
    token, _record = repository.create_connect_token(
        telegram_user_id=telegram_user_id,
        platform=platform,
        ttl_seconds=ttl_seconds,
    )
    base_url = public_base_url.rstrip("/")
    return ConnectLink(
        platform=platform,
        url=f"{base_url}/connect/{platform}?token={token}",
        expires_in_seconds=ttl_seconds,
    )


def list_session_statuses(
    *,
    repository: SessionRepository,
    telegram_user_id: int,
    platforms: tuple[str, ...] = ("instagram", "pinterest", "facebook"),
) -> list[str]:
    sessions = {
        session.platform: session
        for session in repository.list_sessions(telegram_user_id=telegram_user_id)
    }
    lines: list[str] = []
    for platform in platforms:
        session = sessions.get(platform)
        if session is None:
            lines.append(f"{platform}: not connected")
        elif session.status is SessionStatus.CONNECTED:
            last_checked = (
                session.last_checked_at.date().isoformat()
                if session.last_checked_at
                else "never"
            )
            lines.append(f"{platform}: connected, last checked {last_checked}")
        else:
            lines.append(f"{platform}: {session.status.value}")
    return lines


def disconnect_session(
    *,
    repository: SessionRepository,
    telegram_user_id: int,
    platform: str,
) -> str:
    repository.revoke_session(telegram_user_id=telegram_user_id, platform=platform)
    return f"{platform}: disconnected"
