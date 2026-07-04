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

START_TEXT = (
    "Send me a public media link and I will try to download it.\n"
    "Use /help for supported platforms.\n"
    "Use /connect_instagram to connect your own session for links that require login."
)

HELP_TEXT = (
    "Supported platforms: Instagram, Pinterest, Facebook, TikTok, YouTube, X/Twitter, "
    "Reddit, and generic media URLs.\n"
    "Public links are queued for download. Links that require login use only your own "
    "connected session.\n"
    "OmniSaver does not bypass privacy controls or access content you are not authorized "
    "to view. Privacy rule: no bypass.\n"
    "Session commands: /connect_instagram, /connect_pinterest, /connect_facebook, "
    "/sessions, /disconnect <platform>."
)


class ReplyMessage(Protocol):
    async def reply_text(self, text: str) -> object:
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
    await _reply(update, "\n".join(_display_platform(line) for line in lines))


async def disconnect_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dependencies = _dependencies(context)
    telegram_user_id = _telegram_user_id(update)
    platform = _first_arg(context)
    if platform is None:
        await _reply(update, "Usage: /disconnect instagram|pinterest|facebook")
        return
    if platform not in SUPPORTED_SESSION_PLATFORMS:
        await _reply(update, "Unsupported session platform.")
        return
    message = disconnect_session(
        repository=dependencies.session_repository,
        telegram_user_id=telegram_user_id,
        platform=platform,
    )
    await _reply(update, _display_platform(message))


async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dependencies = _dependencies(context)
    jobs = dependencies.history_repository.list_recent_jobs_for_telegram_user(
        _telegram_user_id(update),
        limit=5,
    )
    if not jobs:
        await _reply(update, "No recent jobs.")
        return
    await _reply(
        update,
        "\n".join(_format_history_line(index, job) for index, job in enumerate(jobs, 1)),
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dependencies = _dependencies(context)
    message = _message(update)
    text = getattr(message, "text", None)
    if not isinstance(text, str) or not text.strip():
        await _reply(update, "Send a supported media URL.")
        return
    try:
        job = enqueue_public_download_job_from_message(
            queue=dependencies.queue,
            message=text,
            telegram_user_id=_telegram_user_id(update),
            chat_id=_chat_id(update),
        )
    except UnsupportedUrlError as exc:
        await _reply(update, exc.safe_message)
        return
    await _reply(update, f"Queued {job.platform.value} download. Job ID: {job.job_id}")


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
        (
            f"Connect {_title_platform(link.platform)} session:\n"
            f"{link.url}\n"
            f"This link expires in {link.expires_in_seconds} seconds."
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
    await message.reply_text(text)


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


def _display_platform(line: str) -> str:
    for platform in SUPPORTED_SESSION_PLATFORMS:
        if line.startswith(f"{platform}:"):
            return f"{_title_platform(platform)}:{line.removeprefix(f'{platform}:')}"
    return line


def _title_platform(platform: str) -> str:
    return platform.replace("_", " ").title()


def _format_history_line(index: int, job: DownloadJobRecord) -> str:
    platform = _title_platform(job.platform or "generic")
    if job.status.value == "failed" and job.error_message:
        return f"{index}. {platform} - failed: {job.error_message}"
    return f"{index}. {platform} - {job.status.value}"
