from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from omnisaver_downloader import MediaFile, MediaResult, MediaType


class UrlOpener(Protocol):
    def open(self, request: urllib.request.Request, *, timeout: float) -> object:
        pass


class DefaultUrlOpener:
    def open(self, request: urllib.request.Request, *, timeout: float) -> object:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()


@dataclass(frozen=True)
class BotApiTelegramSender:
    bot_token: str
    opener: UrlOpener = field(default_factory=DefaultUrlOpener)
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required for worker media delivery")

    def send_media_result(self, *, chat_id: int, result: MediaResult) -> None:
        for index, media_file in enumerate(result.media):
            caption = result.caption if index == 0 else ""
            self._send_media_file(chat_id=chat_id, media_file=media_file, caption=caption)

    def send_text_message(self, *, chat_id: int, text: str) -> None:
        fields = {
            "chat_id": str(chat_id),
            "disable_web_page_preview": "true",
            "parse_mode": "HTML",
            "text": text,
        }
        self._post_form(method="sendMessage", fields=fields)

    def _send_media_file(self, *, chat_id: int, media_file: MediaFile, caption: str) -> None:
        method, field_name = _telegram_method_for(media_file.type)
        fields: dict[str, str] = {"chat_id": str(chat_id)}
        if caption:
            fields["caption"] = caption
        self._post_multipart(
            method=method,
            fields=fields,
            files={
                field_name: FileUpload(
                    path=media_file.path,
                    mime_type=media_file.mime_type,
                )
            },
        )

    def _post_multipart(
        self,
        *,
        method: str,
        fields: Mapping[str, str],
        files: Mapping[str, FileUpload],
    ) -> None:
        boundary = f"omnisaver-{secrets.token_hex(16)}"
        body = _build_multipart_body(boundary=boundary, fields=fields, files=files)
        request = urllib.request.Request(
            url=f"https://api.telegram.org/bot{self.bot_token}/{method}",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
            method="POST",
        )
        try:
            self.opener.open(request, timeout=self.timeout_seconds)
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            description = _safe_telegram_error(payload)
            raise RuntimeError(f"Telegram upload failed: {description}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("Telegram upload failed: network error") from exc

    def _post_form(self, *, method: str, fields: Mapping[str, str]) -> None:
        body = urllib.parse.urlencode(fields).encode("utf-8")
        request = urllib.request.Request(
            url=f"https://api.telegram.org/bot{self.bot_token}/{method}",
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": str(len(body)),
            },
            method="POST",
        )
        try:
            self.opener.open(request, timeout=self.timeout_seconds)
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            description = _safe_telegram_error(payload)
            raise RuntimeError(f"Telegram message failed: {description}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("Telegram message failed: network error") from exc


@dataclass(frozen=True)
class FileUpload:
    path: Path
    mime_type: str


def _telegram_method_for(media_type: MediaType) -> tuple[str, str]:
    if media_type is MediaType.PHOTO:
        return "sendPhoto", "photo"
    if media_type is MediaType.VIDEO:
        return "sendVideo", "video"
    return "sendDocument", "document"


def _build_multipart_body(
    *,
    boundary: str,
    fields: Mapping[str, str],
    files: Mapping[str, FileUpload],
) -> bytes:
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    for name, upload in files.items():
        parts.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                (
                    'Content-Disposition: form-data; '
                    f'name="{name}"; filename="{upload.path.name}"\r\n'
                ).encode(),
                f"Content-Type: {upload.mime_type}\r\n\r\n".encode("ascii"),
                upload.path.read_bytes(),
                b"\r\n",
            ]
        )
    parts.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(parts)


def _safe_telegram_error(payload: str) -> str:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return "HTTP error"
    description = data.get("description")
    if not isinstance(description, str) or not description:
        return "HTTP error"
    return description
