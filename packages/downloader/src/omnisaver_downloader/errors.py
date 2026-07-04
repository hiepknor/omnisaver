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


def unsupported_url(message: str = "This URL is not supported yet.") -> DownloadError:
    return DownloadError(code=ErrorCode.UNSUPPORTED_URL, safe_message=message, retryable=False)


def login_required(platform: str) -> DownloadError:
    return DownloadError(
        code=ErrorCode.LOGIN_REQUIRED,
        safe_message=f"This {platform} link requires login. Connect your account first.",
        retryable=False,
    )


def session_missing(platform: str) -> DownloadError:
    return DownloadError(
        code=ErrorCode.SESSION_MISSING,
        safe_message=f"This {platform} link requires login. Connect your account first.",
        retryable=False,
    )


def session_expired(platform: str) -> DownloadError:
    return DownloadError(
        code=ErrorCode.SESSION_EXPIRED,
        safe_message=f"Your {platform} session has expired. Please reconnect.",
        retryable=False,
    )


def access_denied(platform: str) -> DownloadError:
    return DownloadError(
        code=ErrorCode.ACCESS_DENIED,
        safe_message=f"Your account does not have permission to view this {platform} content.",
        retryable=False,
    )


def download_failed(message: str = "Download failed. Please try again later.") -> DownloadError:
    return DownloadError(
        code=ErrorCode.DOWNLOAD_FAILED,
        safe_message=message,
        retryable=True,
        fallback_allowed=True,
    )


def rate_limited(platform: str) -> DownloadError:
    return DownloadError(
        code=ErrorCode.RATE_LIMITED,
        safe_message=f"{platform} is rate limiting requests. Please try again later.",
        retryable=False,
        fallback_allowed=False,
    )


def media_too_large() -> DownloadError:
    return DownloadError(
        code=ErrorCode.MEDIA_TOO_LARGE,
        safe_message="This file is too large to send through Telegram.",
        retryable=False,
        fallback_allowed=False,
    )


def telegram_upload_failed() -> DownloadError:
    return DownloadError(
        code=ErrorCode.TELEGRAM_UPLOAD_FAILED,
        safe_message="Telegram upload failed. Please try again later.",
        retryable=True,
    )
