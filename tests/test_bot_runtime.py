from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast
from unittest.mock import patch
from uuid import uuid4

import pytest

from omnisaver_bot.main import main
from omnisaver_bot.runtime import (
    HELP_TEXT,
    START_TEXT,
    BotDependencies,
    connect_instagram_handler,
    disconnect_handler,
    help_handler,
    history_handler,
    message_handler,
    sessions_handler,
    start_handler,
)
from omnisaver_db import DownloadJobRecord, DownloadJobStatus, InMemorySessionRepository
from omnisaver_worker import InMemoryJobQueue


@dataclass
class FakeUser:
    id: int


@dataclass
class FakeChat:
    id: int
    type: str = "private"


@dataclass
class FakeMessage:
    text: str | None
    replies: list[str] = field(default_factory=list)
    reply_options: list[dict[str, object]] = field(default_factory=list)

    async def reply_text(
        self,
        text: str,
        *,
        parse_mode: str | None = None,
        disable_web_page_preview: bool | None = None,
    ) -> None:
        self.replies.append(text)
        self.reply_options.append(
            {
                "disable_web_page_preview": disable_web_page_preview,
                "parse_mode": parse_mode,
            }
        )


@dataclass
class FakeUpdate:
    effective_message: FakeMessage
    effective_user: FakeUser = field(default_factory=lambda: FakeUser(id=123))
    effective_chat: FakeChat = field(default_factory=lambda: FakeChat(id=456))


@dataclass
class FakeApplication:
    bot_data: dict[str, object]


@dataclass
class FakeBot:
    username: str = "mentor"


@dataclass
class FakeContext:
    application: FakeApplication
    args: list[str] = field(default_factory=list)
    bot: FakeBot = field(default_factory=FakeBot)


class FakeHistoryRepository:
    def __init__(self, jobs: list[DownloadJobRecord] | None = None) -> None:
        self.jobs = jobs or []
        self.calls: list[tuple[int, int]] = []

    def list_recent_jobs_for_telegram_user(
        self,
        telegram_user_id: int,
        *,
        limit: int = 5,
    ) -> list[DownloadJobRecord]:
        self.calls.append((telegram_user_id, limit))
        return self.jobs[:limit]


def _dependencies(
    *,
    queue: InMemoryJobQueue | None = None,
    repository: InMemorySessionRepository | None = None,
    history_repository: FakeHistoryRepository | None = None,
) -> BotDependencies:
    return BotDependencies(
        queue=queue or InMemoryJobQueue(),
        session_repository=repository or InMemorySessionRepository(),
        history_repository=history_repository or FakeHistoryRepository(),
        public_base_url="https://omnisaver.onio.cc",
        connect_token_ttl_seconds=600,
    )


def _context(
    dependencies: BotDependencies,
    *,
    args: list[str] | None = None,
    bot_username: str = "mentor",
) -> FakeContext:
    return FakeContext(
        application=FakeApplication(bot_data={"dependencies": dependencies}),
        args=args or [],
        bot=FakeBot(username=bot_username),
    )


def _update(text: str | None = None, *, chat_type: str = "private") -> FakeUpdate:
    return FakeUpdate(
        effective_message=FakeMessage(text=text),
        effective_chat=FakeChat(id=456, type=chat_type),
    )


def _job(
    *,
    platform: str,
    status: DownloadJobStatus,
    error_message: str | None = None,
) -> DownloadJobRecord:
    return DownloadJobRecord(
        id=uuid4(),
        user_id=uuid4(),
        telegram_chat_id=456,
        platform=platform,
        url=f"https://example.com/{platform}",
        status=status,
        error_code=None,
        error_message=error_message,
        created_at=datetime(2026, 7, 4),
    )


def test_start_and_help_handlers_match_command_spec() -> None:
    dependencies = _dependencies()
    start_update = _update()
    help_update = _update()

    asyncio.run(start_handler(cast(Any, start_update), cast(Any, _context(dependencies))))
    asyncio.run(help_handler(cast(Any, help_update), cast(Any, _context(dependencies))))

    assert start_update.effective_message.replies == [START_TEXT]
    assert help_update.effective_message.replies == [HELP_TEXT]
    assert "không bypass" in HELP_TEXT.lower()
    assert "/connect_instagram" in HELP_TEXT
    assert start_update.effective_message.reply_options == [
        {"disable_web_page_preview": True, "parse_mode": "HTML"}
    ]


def test_connect_handler_creates_owner_bound_token_link() -> None:
    repository = InMemorySessionRepository()
    dependencies = _dependencies(repository=repository)
    update = _update()

    asyncio.run(connect_instagram_handler(cast(Any, update), cast(Any, _context(dependencies))))

    reply = update.effective_message.replies[0]
    assert "https://omnisaver.onio.cc/connect/instagram?token=" in reply
    assert "Link hết hạn sau <b>10 phút</b>" in reply
    assert len(repository.connect_tokens) == 1
    token_record = next(iter(repository.connect_tokens.values()))
    assert token_record.telegram_user_id == 123
    assert token_record.platform == "instagram"


def test_account_commands_require_private_chat_in_groups() -> None:
    repository = InMemorySessionRepository()
    history = FakeHistoryRepository(
        [_job(platform="instagram", status=DownloadJobStatus.COMPLETED)]
    )
    dependencies = _dependencies(repository=repository, history_repository=history)

    connect_update = _update(chat_type="supergroup")
    sessions_update = _update(chat_type="group")
    disconnect_update = _update(chat_type="group")
    history_update = _update(chat_type="group")

    asyncio.run(
        connect_instagram_handler(cast(Any, connect_update), cast(Any, _context(dependencies)))
    )
    asyncio.run(sessions_handler(cast(Any, sessions_update), cast(Any, _context(dependencies))))
    asyncio.run(
        disconnect_handler(
            cast(Any, disconnect_update),
            cast(Any, _context(dependencies, args=["instagram"])),
        )
    )
    asyncio.run(history_handler(cast(Any, history_update), cast(Any, _context(dependencies))))

    for update in (connect_update, sessions_update, disconnect_update, history_update):
        assert "Vui lòng mở chat riêng" in update.effective_message.replies[0]
    assert repository.connect_tokens == {}
    assert history.calls == []


def test_sessions_handler_lists_statuses() -> None:
    repository = InMemorySessionRepository()
    repository.store_encrypted_session(
        telegram_user_id=123,
        platform="instagram",
        encrypted_session=b"encrypted",
        encryption_key_id="key-1",
    )
    dependencies = _dependencies(repository=repository)
    update = _update()

    asyncio.run(sessions_handler(cast(Any, update), cast(Any, _context(dependencies))))

    reply = update.effective_message.replies[0]
    assert "<b>Instagram</b>: đã kết nối" in reply
    assert "<b>Pinterest</b>: chưa kết nối" in reply
    assert "<b>Facebook</b>: chưa kết nối" in reply


def test_disconnect_handler_revokes_requested_session() -> None:
    repository = InMemorySessionRepository()
    repository.store_encrypted_session(
        telegram_user_id=123,
        platform="facebook",
        encrypted_session=b"encrypted",
        encryption_key_id="key-1",
    )
    dependencies = _dependencies(repository=repository)
    update = _update()

    asyncio.run(
        disconnect_handler(
            cast(Any, update),
            cast(Any, _context(dependencies, args=["facebook"])),
        )
    )

    assert update.effective_message.replies == ["✅ <b>Đã ngắt kết nối Facebook</b>"]
    session = repository.get_session(telegram_user_id=123, platform="facebook")
    assert session is not None
    assert session.encrypted_session == b""


def test_disconnect_handler_rejects_missing_or_unsupported_platform() -> None:
    dependencies = _dependencies()
    missing = _update()
    unsupported = _update()

    asyncio.run(disconnect_handler(cast(Any, missing), cast(Any, _context(dependencies))))
    asyncio.run(
        disconnect_handler(
            cast(Any, unsupported),
            cast(Any, _context(dependencies, args=["youtube"])),
        )
    )

    assert "Thiếu nền tảng" in missing.effective_message.replies[0]
    assert "/disconnect instagram" in missing.effective_message.replies[0]
    assert "Nền tảng session chưa hỗ trợ" in unsupported.effective_message.replies[0]


def test_history_handler_lists_recent_jobs() -> None:
    history = FakeHistoryRepository(
        [
            _job(platform="instagram", status=DownloadJobStatus.COMPLETED),
            _job(
                platform="pinterest",
                status=DownloadJobStatus.FAILED,
                error_message="login required",
            ),
        ]
    )
    dependencies = _dependencies(history_repository=history)
    update = _update()

    asyncio.run(history_handler(cast(Any, update), cast(Any, _context(dependencies))))

    assert history.calls == [(123, 5)]
    reply = update.effective_message.replies[0]
    assert "Lịch sử gần đây" in reply
    assert "<b>Instagram</b> · Hoàn tất" in reply
    assert "<b>Pinterest</b> · Thất bại" in reply
    assert "Lý do: login required" in reply


def test_history_handler_handles_empty_history() -> None:
    dependencies = _dependencies(history_repository=FakeHistoryRepository())
    update = _update()

    asyncio.run(history_handler(cast(Any, update), cast(Any, _context(dependencies))))

    assert update.effective_message.replies == ["📭 <b>Chưa có lịch sử tải gần đây.</b>"]


def test_message_handler_enqueues_job_without_downloading() -> None:
    queue = InMemoryJobQueue()
    dependencies = _dependencies(queue=queue)
    update = _update("save https://www.youtube.com/watch?v=abc")

    asyncio.run(message_handler(cast(Any, update), cast(Any, _context(dependencies))))

    queued = queue.dequeue()
    assert queued is not None
    assert queued.telegram_user_id == 123
    assert queued.chat_id == 456
    assert queued.url == "https://www.youtube.com/watch?v=abc"
    reply = update.effective_message.replies[0]
    assert "Đã nhận link và đưa vào hàng đợi" in reply
    assert "<b>Nền tảng:</b> YouTube" in reply
    assert "<b>Mã job:</b> <code>" in reply


def test_message_handler_ignores_group_url_without_bot_mention() -> None:
    queue = InMemoryJobQueue()
    dependencies = _dependencies(queue=queue)
    update = _update("save https://www.youtube.com/watch?v=abc", chat_type="supergroup")

    asyncio.run(message_handler(cast(Any, update), cast(Any, _context(dependencies))))

    assert queue.dequeue() is None
    assert update.effective_message.replies == []


def test_message_handler_allows_group_url_with_bot_mention_and_sender_session_identity() -> None:
    queue = InMemoryJobQueue()
    dependencies = _dependencies(queue=queue)
    update = _update(
        "@mentor save https://www.youtube.com/watch?v=abc",
        chat_type="supergroup",
    )

    asyncio.run(message_handler(cast(Any, update), cast(Any, _context(dependencies))))

    queued = queue.dequeue()
    assert queued is not None
    assert queued.telegram_user_id == 123
    assert queued.chat_id == 456
    assert "Đã nhận link và đưa vào hàng đợi" in update.effective_message.replies[0]


def test_message_handler_returns_safe_unsupported_url_error() -> None:
    dependencies = _dependencies()
    update = _update("no url here")

    asyncio.run(message_handler(cast(Any, update), cast(Any, _context(dependencies))))

    assert "Chưa hỗ trợ link này" in update.effective_message.replies[0]
    assert "Vui lòng gửi một link media được hỗ trợ." in update.effective_message.replies[0]


def test_bot_health_command_does_not_start_polling(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("sys.argv", ["omnisaver_bot", "health"]),
        patch("omnisaver_bot.main.build_application") as build_application,
    ):
        main()

    build_application.assert_not_called()
    assert capsys.readouterr().out == "ok\n"
