from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from omnisaver_downloader.url_detection import Platform


class MediaType(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"


@dataclass(frozen=True)
class MediaFile:
    type: MediaType
    path: Path
    mime_type: str
    size_bytes: int
    thumbnail_path: Path | None = None


@dataclass(frozen=True)
class MediaResult:
    platform: Platform
    source_url: str
    title: str
    caption: str
    media: tuple[MediaFile, ...]
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthenticatedSession:
    platform: Platform
    owner_user_id: str
    payload: bytes = field(repr=False)
