from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse


class Platform(StrEnum):
    INSTAGRAM = "instagram"
    PINTEREST = "pinterest"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    X_TWITTER = "x_twitter"
    REDDIT = "reddit"
    GENERIC = "generic"


class UrlDetectionError(ValueError):
    code = "UNSUPPORTED_URL"
    safe_message = "Link này chưa được hỗ trợ."


class UnsupportedUrlError(UrlDetectionError):
    def __init__(self, message: str | None = None) -> None:
        safe_message = message or UrlDetectionError.safe_message
        super().__init__(safe_message)
        self.safe_message = safe_message


@dataclass(frozen=True)
class DetectedUrl:
    url: str
    platform: Platform


_URL_RE = re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,!?;:)]}"


def extract_urls(message: str) -> list[str]:
    urls: list[str] = []
    for match in _URL_RE.finditer(message):
        url = _strip_trailing_punctuation(match.group(0))
        if url:
            urls.append(url)
    return urls


def detect_url(url: str) -> DetectedUrl:
    return DetectedUrl(url=url, platform=detect_platform(url))


def detect_urls(message: str) -> list[DetectedUrl]:
    return [detect_url(url) for url in extract_urls(message)]


def detect_platform(url: str) -> Platform:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise UnsupportedUrlError(UrlDetectionError.safe_message)

    host = _normalize_host(parsed.netloc)
    path = parsed.path.lower()

    if _is_instagram(host, path):
        return Platform.INSTAGRAM
    if _is_pinterest(host, path):
        return Platform.PINTEREST
    if _is_facebook(host, path):
        return Platform.FACEBOOK
    if _is_tiktok(host, path):
        return Platform.TIKTOK
    if _is_youtube(host, path):
        return Platform.YOUTUBE
    if _is_x_twitter(host):
        return Platform.X_TWITTER
    if _is_reddit(host):
        return Platform.REDDIT
    if _is_known_platform_host(host):
        raise UnsupportedUrlError(UrlDetectionError.safe_message)
    if _is_generic_http_url(host):
        return Platform.GENERIC

    raise UnsupportedUrlError(UrlDetectionError.safe_message)


def _strip_trailing_punctuation(url: str) -> str:
    while url and url[-1] in _TRAILING_PUNCTUATION:
        url = url[:-1]
    return url


def _normalize_host(netloc: str) -> str:
    host = netloc.rsplit("@", 1)[-1].split(":", 1)[0].lower().rstrip(".")
    if host.startswith("www."):
        return host[4:]
    return host


def _is_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _is_instagram(host: str, path: str) -> bool:
    return _is_domain(host, "instagram.com") and path.startswith(("/p/", "/reel/", "/stories/"))


def _is_pinterest(host: str, path: str) -> bool:
    return (host == "pin.it" and path != "/") or (
        _is_domain(host, "pinterest.com") and path.startswith("/pin/")
    )


def _is_facebook(host: str, path: str) -> bool:
    if not (
        _is_domain(host, "facebook.com")
        or _is_domain(host, "fb.watch")
        or _is_domain(host, "m.facebook.com")
    ):
        return False
    return path.startswith(("/reel/", "/watch/")) or "/videos/" in path


def _is_tiktok(host: str, path: str) -> bool:
    return (_is_domain(host, "tiktok.com") and "/video/" in path) or host == "vm.tiktok.com"


def _is_youtube(host: str, path: str) -> bool:
    return (_is_domain(host, "youtube.com") and path == "/watch") or host == "youtu.be"


def _is_x_twitter(host: str) -> bool:
    return _is_domain(host, "x.com") or _is_domain(host, "twitter.com")


def _is_reddit(host: str) -> bool:
    return _is_domain(host, "reddit.com") or host == "redd.it"


def _is_known_platform_host(host: str) -> bool:
    return (
        _is_domain(host, "instagram.com")
        or _is_domain(host, "pinterest.com")
        or host == "pin.it"
        or _is_domain(host, "facebook.com")
        or host == "fb.watch"
        or _is_domain(host, "tiktok.com")
        or host == "vm.tiktok.com"
        or _is_domain(host, "youtube.com")
        or host == "youtu.be"
        or _is_domain(host, "x.com")
        or _is_domain(host, "twitter.com")
        or _is_domain(host, "reddit.com")
        or host == "redd.it"
    )


def _is_generic_http_url(host: str) -> bool:
    return "." in host and " " not in host
