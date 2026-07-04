from __future__ import annotations

from html import escape
from typing import Protocol

from omnisaver_downloader import DownloadError, ErrorCode
from omnisaver_worker.public_job import PublicDownloadJob

PLATFORM_LABELS = {
    "facebook": "Facebook",
    "generic": "Liên kết media",
    "instagram": "Instagram",
    "pinterest": "Pinterest",
    "reddit": "Reddit",
    "tiktok": "TikTok",
    "x_twitter": "X/Twitter",
    "youtube": "YouTube",
}

CONNECT_COMMANDS = {
    "facebook": "/connect_facebook",
    "instagram": "/connect_instagram",
    "pinterest": "/connect_pinterest",
}


class JobNotifier(Protocol):
    def send_text_message(self, *, chat_id: int, text: str) -> None:
        pass


def failure_notification(job: PublicDownloadJob, error: DownloadError) -> str:
    platform = PLATFORM_LABELS.get(job.platform.value, job.platform.value.replace("_", " ").title())
    action = _action_for(job, error)
    return (
        "⚠️ <b>Job tải media thất bại</b>\n\n"
        f"🌐 <b>Nền tảng:</b> {platform}\n"
        f"🆔 <b>Mã job:</b> <code>{escape(job.job_id.split('-', 1)[0])}</code>\n"
        f"📌 <b>Lý do:</b> {escape(error.safe_message)}"
        f"{action}"
    )


def _action_for(job: PublicDownloadJob, error: DownloadError) -> str:
    command = CONNECT_COMMANDS.get(job.platform.value)
    if error.code in {
        ErrorCode.LOGIN_REQUIRED,
        ErrorCode.SESSION_MISSING,
        ErrorCode.SESSION_EXPIRED,
    } and command is not None:
        return f"\n\n🔐 Hãy dùng {command} rồi gửi lại link."
    if error.code is ErrorCode.RATE_LIMITED:
        return "\n\n⏱️ Vui lòng thử lại sau ít phút."
    if error.code is ErrorCode.MEDIA_TOO_LARGE:
        return "\n\n📦 File vượt giới hạn gửi qua Telegram."
    return "\n\nBạn có thể gửi lại link sau hoặc thử một link khác."
