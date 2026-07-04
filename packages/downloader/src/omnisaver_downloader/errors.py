from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    UNSUPPORTED_URL = "UNSUPPORTED_URL"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    SESSION_MISSING = "SESSION_MISSING"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    ACCESS_DENIED = "ACCESS_DENIED"
    RATE_LIMITED = "RATE_LIMITED"
    MEDIA_TOO_LARGE = "MEDIA_TOO_LARGE"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    TELEGRAM_UPLOAD_FAILED = "TELEGRAM_UPLOAD_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class DownloadError(Exception):
    code: ErrorCode
    safe_message: str
    retryable: bool = False
    fallback_allowed: bool = False

    def __str__(self) -> str:
        return self.safe_message


def unsupported_url(message: str = "Link này chưa được hỗ trợ.") -> DownloadError:
    return DownloadError(code=ErrorCode.UNSUPPORTED_URL, safe_message=message, retryable=False)


def login_required(platform: str) -> DownloadError:
    return DownloadError(
        code=ErrorCode.LOGIN_REQUIRED,
        safe_message=f"Link {platform} này cần đăng nhập. Hãy kết nối tài khoản của bạn trước.",
        retryable=False,
    )


def session_missing(platform: str) -> DownloadError:
    return DownloadError(
        code=ErrorCode.SESSION_MISSING,
        safe_message=f"Link {platform} này cần đăng nhập. Hãy kết nối tài khoản của bạn trước.",
        retryable=False,
    )


def session_expired(platform: str) -> DownloadError:
    return DownloadError(
        code=ErrorCode.SESSION_EXPIRED,
        safe_message=f"Session {platform} của bạn đã hết hạn. Vui lòng kết nối lại.",
        retryable=False,
    )


def access_denied(platform: str) -> DownloadError:
    return DownloadError(
        code=ErrorCode.ACCESS_DENIED,
        safe_message=f"Tài khoản của bạn không có quyền xem nội dung {platform} này.",
        retryable=False,
    )


def download_failed(message: str = "Tải media thất bại. Vui lòng thử lại sau.") -> DownloadError:
    return DownloadError(
        code=ErrorCode.DOWNLOAD_FAILED,
        safe_message=message,
        retryable=True,
        fallback_allowed=True,
    )


def rate_limited(platform: str) -> DownloadError:
    return DownloadError(
        code=ErrorCode.RATE_LIMITED,
        safe_message=f"{platform} đang giới hạn tần suất yêu cầu. Vui lòng thử lại sau.",
        retryable=False,
        fallback_allowed=False,
    )


def media_too_large() -> DownloadError:
    return DownloadError(
        code=ErrorCode.MEDIA_TOO_LARGE,
        safe_message="File này quá lớn để gửi qua Telegram.",
        retryable=False,
        fallback_allowed=False,
    )


def telegram_upload_failed() -> DownloadError:
    return DownloadError(
        code=ErrorCode.TELEGRAM_UPLOAD_FAILED,
        safe_message="Gửi media qua Telegram thất bại. Vui lòng thử lại sau.",
        retryable=True,
    )
