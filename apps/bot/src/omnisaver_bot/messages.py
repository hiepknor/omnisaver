from __future__ import annotations

from html import escape

from omnisaver_db import DownloadJobRecord
from omnisaver_worker import PublicDownloadJob

SUPPORTED_PLATFORMS_TEXT = "Instagram, Pinterest, Facebook, TikTok, YouTube, X/Twitter, Reddit"

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

STATUS_LABELS = {
    "queued": ("⏳", "Đang chờ"),
    "started": ("🔄", "Đang xử lý"),
    "completed": ("✅", "Hoàn tất"),
    "failed": ("⚠️", "Thất bại"),
}

START_TEXT = (
    "👋 <b>Chào mừng đến với OmniSaver</b>\n\n"
    "Gửi cho tôi một link media công khai, tôi sẽ đưa vào hàng đợi "
    "và gửi lại file khi xử lý xong.\n\n"
    "🔐 Với nội dung cần đăng nhập, hãy dùng phiên của chính bạn qua /connect_instagram.\n"
    "📌 Xem hướng dẫn đầy đủ bằng /help."
)

HELP_TEXT = (
    "📘 <b>Hướng dẫn OmniSaver</b>\n\n"
    f"🌐 <b>Nền tảng hỗ trợ:</b> {SUPPORTED_PLATFORMS_TEXT} và URL media phổ biến.\n"
    "📥 <b>Cách dùng:</b> gửi một link trong tin nhắn, bot sẽ đưa job vào hàng đợi.\n"
    "🔐 <b>Link cần đăng nhập:</b> OmniSaver chỉ dùng session do chính bạn kết nối.\n"
    "🛡️ <b>Quy tắc riêng tư:</b> không bypass, không dùng session của người khác, "
    "không truy cập nội dung bạn không có quyền xem.\n\n"
    "⚙️ <b>Lệnh:</b>\n"
    "/connect_instagram - kết nối Instagram\n"
    "/connect_pinterest - kết nối Pinterest\n"
    "/connect_facebook - kết nối Facebook\n"
    "/sessions - xem trạng thái session\n"
    "/disconnect &lt;platform&gt; - ngắt kết nối\n"
    "/history - xem lịch sử gần đây"
)


def platform_label(platform: str) -> str:
    return PLATFORM_LABELS.get(platform, platform.replace("_", " ").title())


def short_job_id(job_id: str) -> str:
    return job_id.split("-", 1)[0]


def empty_url_message() -> str:
    return (
        "🔎 <b>Chưa thấy link media</b>\n\n"
        "Hãy gửi một URL hợp lệ, ví dụ:\n"
        "<code>https://www.youtube.com/watch?v=...</code>"
    )


def unsupported_url_message(message: str) -> str:
    return f"⚠️ <b>Chưa hỗ trợ link này</b>\n\n{escape(message)}"


def private_chat_required_message() -> str:
    return (
        "🔐 <b>Vui lòng mở chat riêng với OmniSaver</b>\n\n"
        "Các lệnh kết nối tài khoản, xem session, ngắt kết nối và lịch sử chỉ được xử lý "
        "trong chat riêng để tránh lộ thông tin cá nhân trong nhóm.\n\n"
        "Bạn vẫn có thể gửi link media trong nhóm; OmniSaver sẽ dùng session của chính người gửi."
    )


def queued_message(job: PublicDownloadJob) -> str:
    return (
        "⏳ <b>Đã nhận link và đưa vào hàng đợi</b>\n\n"
        f"🌐 <b>Nền tảng:</b> {platform_label(job.platform.value)}\n"
        f"🆔 <b>Mã job:</b> <code>{escape(short_job_id(job.job_id))}</code>\n"
        "📬 Tôi sẽ gửi media vào đây khi xử lý xong."
    )


def connect_message(*, platform: str, url: str, expires_in_seconds: int) -> str:
    minutes = max(1, expires_in_seconds // 60)
    return (
        f"🔐 <b>Kết nối {platform_label(platform)}</b>\n\n"
        "Mở link dưới đây để kết nối session của chính bạn:\n"
        f"{escape(url)}\n\n"
        f"⏱️ Link hết hạn sau <b>{minutes} phút</b>.\n"
        "🛡️ OmniSaver chỉ dùng session này cho yêu cầu của bạn."
    )


def sessions_message(lines: list[str]) -> str:
    rendered = "\n".join(_format_session_line(line) for line in lines)
    return f"🔐 <b>Session đã kết nối</b>\n\n{rendered}"


def disconnect_usage_message() -> str:
    return (
        "⚙️ <b>Thiếu nền tảng cần ngắt kết nối</b>\n\n"
        "Dùng: <code>/disconnect instagram</code>\n"
        "Hỗ trợ: <code>instagram</code>, <code>pinterest</code>, <code>facebook</code>"
    )


def unsupported_session_platform_message() -> str:
    return "⚠️ <b>Nền tảng session chưa hỗ trợ.</b>\n\nHỗ trợ: Instagram, Pinterest, Facebook."


def disconnected_message(message: str) -> str:
    platform = message.split(":", 1)[0]
    return f"✅ <b>Đã ngắt kết nối {platform_label(platform)}</b>"


def empty_history_message() -> str:
    return "📭 <b>Chưa có lịch sử tải gần đây.</b>"


def history_message(jobs: list[DownloadJobRecord]) -> str:
    lines = [_format_history_line(index, job) for index, job in enumerate(jobs, 1)]
    return "🧾 <b>Lịch sử gần đây</b>\n\n" + "\n".join(lines)


def _format_session_line(line: str) -> str:
    platform, _, status = line.partition(":")
    label = platform_label(platform)
    status = status.strip()
    if status.startswith("connected"):
        suffix = status.removeprefix("connected").strip()
        return f"✅ <b>{label}</b>: đã kết nối{_format_last_checked(suffix)}"
    if status == "not connected":
        return f"- <b>{label}</b>: chưa kết nối"
    if status == "revoked":
        return f"🚫 <b>{label}</b>: đã ngắt kết nối"
    if status == "expired":
        return f"⚠️ <b>{label}</b>: đã hết hạn"
    return f"📌 <b>{label}</b>: {escape(status)}"


def _format_last_checked(value: str) -> str:
    if not value:
        return ""
    value = value.removeprefix(",").strip()
    if value == "last checked never":
        return " · chưa kiểm tra"
    if value.startswith("last checked "):
        return f" · kiểm tra lần cuối {escape(value.removeprefix('last checked '))}"
    return f" · {escape(value)}"


def _format_history_line(index: int, job: DownloadJobRecord) -> str:
    icon, status = STATUS_LABELS.get(job.status.value, ("📌", job.status.value))
    platform = platform_label(job.platform or "generic")
    job_id = short_job_id(str(job.id))
    if job.status.value == "failed" and job.error_message:
        return (
            f"{index}. {icon} <b>{platform}</b> · {status} · "
            f"<code>{escape(job_id)}</code>\n"
            f"   Lý do: {escape(job.error_message)}"
        )
    return f"{index}. {icon} <b>{platform}</b> · {status} · <code>{escape(job_id)}</code>"
