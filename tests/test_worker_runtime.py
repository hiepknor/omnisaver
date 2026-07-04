import base64
import sys
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest

from omnisaver_config import load_settings
from omnisaver_downloader import MediaFile, MediaResult, MediaType, Platform
from omnisaver_worker.main import build_worker_service, main
from omnisaver_worker.public_job import PublicDownloadJobRunner
from omnisaver_worker.telegram_sender import BotApiTelegramSender


class FakeOpener:
    def __init__(self) -> None:
        self.requests: list[Any] = []
        self.timeouts: list[float] = []

    def open(self, request: Any, *, timeout: float) -> object:
        self.requests.append(request)
        self.timeouts.append(timeout)
        return b'{"ok":true}'


class FakeService:
    def __init__(self, processed: bool) -> None:
        self.processed = processed
        self.calls = 0

    def process_one(self) -> bool:
        self.calls += 1
        return self.processed


def _settings() -> Any:
    return load_settings(
        {
            "TELEGRAM_BOT_TOKEN": "bot-token",
            "DATABASE_URL": "postgresql://omnisaver:secret@postgres:5432/omnisaver",
            "REDIS_URL": "redis://redis:6379/0",
            "SESSION_VAULT_MASTER_KEY_BASE64": base64.b64encode(b"4" * 32).decode("ascii"),
            "COOKIE_ENCRYPTION_KEY_ID": "key-1",
            "DOWNLOAD_STORAGE_PATH": "/tmp/omnisaver-test-downloads",
            "YTDLP_BIN": "yt-dlp",
            "GALLERY_DL_BIN": "gallery-dl",
            "INSTALOADER_BIN": "instaloader",
            "FFMPEG_BIN": "ffmpeg",
        }
    )


def test_bot_api_sender_uploads_media_without_exposing_token(tmp_path: Path) -> None:
    media_path = tmp_path / "photo.jpg"
    media_path.write_bytes(b"image-bytes")
    opener = FakeOpener()
    sender = BotApiTelegramSender(
        bot_token="secret-token",
        opener=opener,
        timeout_seconds=12,
    )

    sender.send_media_result(
        chat_id=123,
        result=MediaResult(
            platform=Platform.INSTAGRAM,
            source_url="https://instagram.com/p/abc",
            title="",
            caption="caption",
            media=(
                MediaFile(
                    type=MediaType.PHOTO,
                    path=media_path,
                    mime_type="image/jpeg",
                    size_bytes=media_path.stat().st_size,
                ),
            ),
        ),
    )

    assert len(opener.requests) == 1
    request = opener.requests[0]
    assert request.full_url == "https://api.telegram.org/botsecret-token/sendPhoto"
    assert opener.timeouts == [12]
    body = cast(bytes, request.data)
    assert b'secret-token' not in body
    assert b'name="chat_id"' in body
    assert b"123" in body
    assert b'name="caption"' in body
    assert b"caption" in body
    assert b'name="photo"; filename="photo.jpg"' in body
    assert b"image-bytes" in body


def test_bot_api_sender_sends_html_text_without_exposing_token() -> None:
    opener = FakeOpener()
    sender = BotApiTelegramSender(
        bot_token="secret-token",
        opener=opener,
        timeout_seconds=12,
    )

    sender.send_text_message(chat_id=123, text="⚠️ <b>Lỗi</b>")

    assert len(opener.requests) == 1
    request = opener.requests[0]
    assert request.full_url == "https://api.telegram.org/botsecret-token/sendMessage"
    assert opener.timeouts == [12]
    body = cast(bytes, request.data)
    assert b"secret-token" not in body
    assert b"chat_id=123" in body
    assert b"parse_mode=HTML" in body
    assert b"disable_web_page_preview=true" in body
    assert b"%3Cb%3E" in body


def test_bot_api_sender_requires_bot_token() -> None:
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        BotApiTelegramSender(bot_token="")


def test_build_worker_service_wires_runtime_dependencies() -> None:
    with (
        patch("omnisaver_worker.main.PostgresSessionRepository") as session_repository,
        patch("omnisaver_worker.main.PostgresDownloadJobRepository") as job_repository,
        patch("omnisaver_worker.main.build_redis_job_queue") as queue_builder,
    ):
        session_repository.connect.return_value = object()
        job_repository.connect.return_value = object()
        queue_builder.return_value = object()

        service = build_worker_service(_settings(), sender=cast(Any, object()))

    assert service.queue is queue_builder.return_value
    assert service.repository is job_repository.connect.return_value
    runner = cast(PublicDownloadJobRunner, service.runner)
    assert runner.storage_root == Path("/tmp/omnisaver-test-downloads")
    assert runner.session_resolver is not None
    queue_builder.assert_called_once_with("redis://redis:6379/0")
    session_repository.connect.assert_called_once_with(
        "postgresql://omnisaver:secret@postgres:5432/omnisaver"
    )
    job_repository.connect.assert_called_once_with(
        "postgresql://omnisaver:secret@postgres:5432/omnisaver"
    )


def test_worker_process_once_command_processes_one_job(capsys: pytest.CaptureFixture[str]) -> None:
    service = FakeService(processed=True)
    with (
        patch.object(sys, "argv", ["omnisaver_worker", "process-once"]),
        patch("omnisaver_worker.main.build_worker_service", return_value=service),
    ):
        main()

    assert service.calls == 1
    assert capsys.readouterr().out == "processed 1 job\n"


def test_worker_process_once_command_reports_empty_queue(
    capsys: pytest.CaptureFixture[str],
) -> None:
    service = FakeService(processed=False)
    with (
        patch.object(sys, "argv", ["omnisaver_worker", "process-once"]),
        patch("omnisaver_worker.main.build_worker_service", return_value=service),
    ):
        main()

    assert service.calls == 1
    assert capsys.readouterr().out == "no jobs available\n"
