from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from omnisaver_bot.messages import (
    HELP_TEXT,
    START_TEXT,
    connect_message,
    disconnect_usage_message,
    disconnected_message,
    empty_history_message,
    empty_url_message,
    history_message,
    queued_message,
    sessions_message,
    unsupported_session_platform_message,
    unsupported_url_message,
)
from omnisaver_bot.public_flow import enqueue_public_download_job_from_message
from omnisaver_bot.session_commands import (
    create_connect_link,
    disconnect_session,
    list_session_statuses,
)
from omnisaver_config import Settings
from omnisaver_db import (
    DownloadJobRecord,
    PostgresDownloadJobRepository,
    PostgresSessionRepository,
    SessionRepository,
)
from omnisaver_downloader import UnsupportedUrlError
from omnisaver_worker import JobQueue, build_redis_job_queue

SUPPORTED_SESSION_PLATFORMS = ("instagram", "pinterest", "facebook")

__all__ = [
    "HELP_TEXT",
    "START_TEXT",
    "BotDependencies",
    "build_application",
    "build_bot_dependencies",
    "register_handlers",
]


class ReplyMessage(Protocol):
    async def reply_text(
        self,
        text: str,
        *,
        parse_mode: str | None = None,
        disable_web_page_preview: bool | None = None,
    ) -> object:
        pass


class DownloadHistoryRepository(Protocol):
    def list_recent_jobs_for_telegram_user(
        self,
        telegram_user_id: int,
        *,
        limit: int = 5,
    ) -> list[DownloadJobRecord]:
        pass


@dataclass(frozen=True)
class BotDependencies:
    queue: JobQueue
    session_repository: SessionRepository
    history_repository: DownloadHistoryRepository
    public_base_url: str
    connect_token_ttl_seconds: int


def build_bot_dependencies(settings: Settings) -> BotDependencies:
    return BotDependencies(
        queue=build_redis_job_queue(settings.redis_url),
        session_repository=PostgresSessionRepository.connect(settings.database_url),
        history_repository=PostgresDownloadJobRepository.connect(settings.database_url),
        public_base_url=settings.public_base_url,
        connect_token_ttl_seconds=settings.session_connect_token_ttl_seconds,
    )


def build_application(settings: Settings) -> Application[Any, Any, Any, Any, Any, Any]:
    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required for bot runtime")
    application = Application.builder().token(settings.telegram_bot_token).build()
    register_handlers(application, build_bot_dependencies(settings))
    return application


def register_handlers(
    application: Application[Any, Any, Any, Any, Any, Any],
    dependencies: BotDependencies,
) -> None:
    application.bot_data["dependencies"] = dependencies
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("connect_instagram", connect_instagram_handler))
    application.add_handler(CommandHandler("connect_pinterest", connect_pinterest_handler))
    application.add_handler(CommandHandler("connect_facebook", connect_facebook_handler))
    application.add_handler(CommandHandler("sessions", sessions_handler))
    application.add_handler(CommandHandler("disconnect", disconnect_handler))
    application.add_handler(CommandHandler("history", history_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, START_TEXT)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, HELP_TEXT)


async def connect_instagram_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _connect_platform(update, context, platform="instagram")


async def connect_pinterest_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _connect_platform(update, context, platform="pinterest")


async def connect_facebook_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _connect_platform(update, context, platform="facebook")


async def sessions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dependencies = _dependencies(context)
    telegram_user_id = _telegram_user_id(update)
    lines = list_session_statuses(
        repository=dependencies.session_repository,
        telegram_user_id=telegram_user_id,
        platforms=SUPPORTED_SESSION_PLATFORMS,
    )
    await _reply(update, sessions_message(lines))


async def disconnect_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dependencies = _dependencies(context)
    telegram_user_id = _telegram_user_id(update)
    platform = _first_arg(context)
    if platform is None:
        await _reply(update, disconnect_usage_message())
        return
    if platform not in SUPPORTED_SESSION_PLATFORMS:
        await _reply(update, unsupported_session_platform_message())
        return
    message = disconnect_session(
        repository=dependencies.session_repository,
        telegram_user_id=telegram_user_id,
        platform=platform,
    )
    await _reply(update, disconnected_message(message))


async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dependencies = _dependencies(context)
    jobs = dependencies.history_repository.list_recent_jobs_for_telegram_user(
        _telegram_user_id(update),
        limit=5,
    )
    if not jobs:
        await _reply(update, empty_history_message())
        return
    await _reply(update, history_message(jobs))


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dependencies = _dependencies(context)
    message = _message(update)
    text = getattr(message, "text", None)
    if not isinstance(text, str) or not text.strip():
        await _reply(update, empty_url_message())
        return
    try:
        job = enqueue_public_download_job_from_message(
            queue=dependencies.queue,
            message=text,
            telegram_user_id=_telegram_user_id(update),
            chat_id=_chat_id(update),
        )
    except UnsupportedUrlError as exc:
        await _reply(update, unsupported_url_message(exc.safe_message))
        return
    await _reply(update, queued_message(job))


async def _connect_platform(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    platform: str,
) -> None:
    dependencies = _dependencies(context)
    link = create_connect_link(
        repository=dependencies.session_repository,
        public_base_url=dependencies.public_base_url,
        telegram_user_id=_telegram_user_id(update),
        platform=platform,
        ttl_seconds=dependencies.connect_token_ttl_seconds,
    )
    await _reply(
        update,
        connect_message(
            platform=link.platform,
            url=link.url,
            expires_in_seconds=link.expires_in_seconds,
        ),
    )


def _dependencies(context: ContextTypes.DEFAULT_TYPE) -> BotDependencies:
    value = context.application.bot_data["dependencies"]
    if not isinstance(value, BotDependencies):
        raise RuntimeError("bot dependencies are not configured")
    return value


def _first_arg(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    args = getattr(context, "args", None)
    if not args:
        return None
    value = str(args[0]).strip().lower()
    return value or None


async def _reply(update: Update, text: str) -> None:
    message = _message(update)
    await message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)


def _message(update: Update) -> ReplyMessage:
    message = update.effective_message
    if message is None:
        raise RuntimeError("Telegram update has no message")
    return message


def _telegram_user_id(update: Update) -> int:
    user = update.effective_user
    if user is None:
        raise RuntimeError("Telegram update has no user")
    return int(user.id)


def _chat_id(update: Update) -> int:
    chat = update.effective_chat
    if chat is None:
        raise RuntimeError("Telegram update has no chat")
    return int(chat.id)
