from pathlib import Path

import pytest
from omnisaver_config import load_settings


def test_load_settings_uses_defaults() -> None:
    settings = load_settings({})

    assert settings.public_base_url == "http://localhost:8000"
    assert settings.session_connect_token_ttl_seconds == 600
    assert settings.postgres_db == "omnisaver"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.download_storage_path == Path("storage/downloads")
    assert settings.log_level == "INFO"
    assert settings.environment == "local"


def test_load_settings_parses_environment_values() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "bot-token",
            "TELEGRAM_WEBHOOK_URL": "https://example.com/webhook",
            "PUBLIC_BASE_URL": "https://example.com",
            "SESSION_CONNECT_TOKEN_TTL_SECONDS": "900",
            "POSTGRES_DB": "custom_db",
            "POSTGRES_USER": "custom_user",
            "POSTGRES_PASSWORD": "db-secret",
            "DATABASE_URL": "postgresql://custom_user:db-secret@postgres:5432/custom_db",
            "REDIS_URL": "redis://redis:6379/1",
            "SESSION_VAULT_MASTER_KEY_BASE64": "vault-secret",
            "COOKIE_ENCRYPTION_KEY_ID": "key-1",
            "DOWNLOAD_STORAGE_PATH": "/tmp/downloads",
            "MAX_DOWNLOAD_SIZE_MB": "50",
            "TEMP_FILE_TTL_HOURS": "12",
            "YTDLP_BIN": "/usr/local/bin/yt-dlp",
            "GALLERY_DL_BIN": "/usr/local/bin/gallery-dl",
            "FFMPEG_BIN": "/usr/local/bin/ffmpeg",
            "LOG_LEVEL": "debug",
            "ENVIRONMENT": "test",
        }
    )

    assert settings.telegram_bot_token == "bot-token"
    assert settings.telegram_webhook_url == "https://example.com/webhook"
    assert settings.public_base_url == "https://example.com"
    assert settings.session_connect_token_ttl_seconds == 900
    assert settings.postgres_db == "custom_db"
    assert settings.postgres_user == "custom_user"
    assert settings.postgres_password == "db-secret"
    assert settings.database_url == "postgresql://custom_user:db-secret@postgres:5432/custom_db"
    assert settings.redis_url == "redis://redis:6379/1"
    assert settings.session_vault_master_key_base64 == "vault-secret"
    assert settings.cookie_encryption_key_id == "key-1"
    assert settings.download_storage_path == Path("/tmp/downloads")
    assert settings.max_download_size_mb == 50
    assert settings.temp_file_ttl_hours == 12
    assert settings.ytdlp_bin == "/usr/local/bin/yt-dlp"
    assert settings.gallery_dl_bin == "/usr/local/bin/gallery-dl"
    assert settings.ffmpeg_bin == "/usr/local/bin/ffmpeg"
    assert settings.log_level == "DEBUG"
    assert settings.environment == "test"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("SESSION_CONNECT_TOKEN_TTL_SECONDS", "not-an-int"),
        ("MAX_DOWNLOAD_SIZE_MB", "0"),
        ("TEMP_FILE_TTL_HOURS", "0"),
        ("LOG_LEVEL", "verbose"),
        ("ENVIRONMENT", "dev"),
    ],
)
def test_load_settings_rejects_invalid_values(key: str, value: str) -> None:
    with pytest.raises(ValueError):
        load_settings({key: value})


def test_redacted_summary_does_not_expose_secrets() -> None:
    settings = load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "bot-token",
            "POSTGRES_PASSWORD": "db-secret",
            "DATABASE_URL": "postgresql://omnisaver:db-secret@postgres:5432/omnisaver",
            "SESSION_VAULT_MASTER_KEY_BASE64": "vault-secret",
        }
    )

    summary = settings.redacted_summary()
    rendered = repr(summary)

    assert "bot-token" not in rendered
    assert "db-secret" not in rendered
    assert "vault-secret" not in rendered
    assert summary["telegram_bot_token"] == "<redacted>"
    assert summary["postgres_password"] == "<redacted>"
    assert summary["database_url"] == "postgresql://omnisaver:<redacted>@postgres:5432/omnisaver"
    assert summary["session_vault_master_key_base64"] == "<redacted>"
