from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_VALID_ENVIRONMENTS = {"local", "test", "staging", "production"}


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = field(repr=False)
    telegram_webhook_url: str | None
    public_base_url: str
    session_connect_token_ttl_seconds: int
    postgres_db: str
    postgres_user: str
    postgres_password: str = field(repr=False)
    database_url: str = field(repr=False)
    redis_url: str
    session_vault_master_key_base64: str = field(repr=False)
    cookie_encryption_key_id: str
    download_storage_path: Path
    max_download_size_mb: int
    temp_file_ttl_hours: int
    ytdlp_bin: str
    gallery_dl_bin: str
    ffmpeg_bin: str
    log_level: str
    environment: str

    def redacted_summary(self) -> dict[str, str | int | None]:
        return {
            "telegram_bot_token": _redact(self.telegram_bot_token),
            "telegram_webhook_url": self.telegram_webhook_url,
            "public_base_url": self.public_base_url,
            "session_connect_token_ttl_seconds": self.session_connect_token_ttl_seconds,
            "postgres_db": self.postgres_db,
            "postgres_user": self.postgres_user,
            "postgres_password": _redact(self.postgres_password),
            "database_url": _redact_url_password(self.database_url),
            "redis_url": self.redis_url,
            "session_vault_master_key_base64": _redact(self.session_vault_master_key_base64),
            "cookie_encryption_key_id": self.cookie_encryption_key_id,
            "download_storage_path": str(self.download_storage_path),
            "max_download_size_mb": self.max_download_size_mb,
            "temp_file_ttl_hours": self.temp_file_ttl_hours,
            "ytdlp_bin": self.ytdlp_bin,
            "gallery_dl_bin": self.gallery_dl_bin,
            "ffmpeg_bin": self.ffmpeg_bin,
            "log_level": self.log_level,
            "environment": self.environment,
        }


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    source = os.environ if env is None else env

    log_level = _get_str(source, "LOG_LEVEL", "INFO").upper()
    if log_level not in _VALID_LOG_LEVELS:
        raise ValueError(f"LOG_LEVEL must be one of {sorted(_VALID_LOG_LEVELS)}")

    environment = _get_str(source, "ENVIRONMENT", "local").lower()
    if environment not in _VALID_ENVIRONMENTS:
        raise ValueError(f"ENVIRONMENT must be one of {sorted(_VALID_ENVIRONMENTS)}")

    return Settings(
        telegram_bot_token=_get_str(source, "TELEGRAM_BOT_TOKEN", ""),
        telegram_webhook_url=_get_optional_str(source, "TELEGRAM_WEBHOOK_URL"),
        public_base_url=_get_str(source, "PUBLIC_BASE_URL", "http://localhost:8000"),
        session_connect_token_ttl_seconds=_get_int(
            source, "SESSION_CONNECT_TOKEN_TTL_SECONDS", 600, minimum=60
        ),
        postgres_db=_get_str(source, "POSTGRES_DB", "omnisaver"),
        postgres_user=_get_str(source, "POSTGRES_USER", "omnisaver"),
        postgres_password=_get_str(source, "POSTGRES_PASSWORD", ""),
        database_url=_get_str(source, "DATABASE_URL", "postgresql://omnisaver@localhost/omnisaver"),
        redis_url=_get_str(source, "REDIS_URL", "redis://localhost:6379/0"),
        session_vault_master_key_base64=_get_str(source, "SESSION_VAULT_MASTER_KEY_BASE64", ""),
        cookie_encryption_key_id=_get_str(source, "COOKIE_ENCRYPTION_KEY_ID", "default"),
        download_storage_path=Path(_get_str(source, "DOWNLOAD_STORAGE_PATH", "storage/downloads")),
        max_download_size_mb=_get_int(source, "MAX_DOWNLOAD_SIZE_MB", 2000, minimum=1),
        temp_file_ttl_hours=_get_int(source, "TEMP_FILE_TTL_HOURS", 24, minimum=1),
        ytdlp_bin=_get_str(source, "YTDLP_BIN", "yt-dlp"),
        gallery_dl_bin=_get_str(source, "GALLERY_DL_BIN", "gallery-dl"),
        ffmpeg_bin=_get_str(source, "FFMPEG_BIN", "ffmpeg"),
        log_level=log_level,
        environment=environment,
    )


def _get_str(env: Mapping[str, str], key: str, default: str) -> str:
    value = env.get(key)
    if value is None or value == "":
        return default
    return value


def _get_optional_str(env: Mapping[str, str], key: str) -> str | None:
    value = env.get(key)
    if value is None or value == "":
        return None
    return value


def _get_int(env: Mapping[str, str], key: str, default: int, *, minimum: int) -> int:
    raw = _get_str(env, key, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{key} must be >= {minimum}")
    return value


def _redact(value: str) -> str:
    if not value:
        return ""
    return "<redacted>"


def _redact_url_password(value: str) -> str:
    if "://" not in value or "@" not in value:
        return _redact(value)
    scheme, rest = value.split("://", 1)
    credentials, host = rest.split("@", 1)
    if ":" not in credentials:
        return f"{scheme}://<redacted>@{host}"
    username, _password = credentials.split(":", 1)
    return f"{scheme}://{username}:<redacted>@{host}"
