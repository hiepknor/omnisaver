from __future__ import annotations

from uuid import uuid4

from omnisaver_downloader import UnsupportedUrlError, detect_url, extract_urls
from omnisaver_worker.public_job import PublicDownloadJob


def create_public_download_job_from_message(
    *,
    message: str,
    telegram_user_id: int,
    chat_id: int,
) -> PublicDownloadJob:
    urls = extract_urls(message)
    if not urls:
        raise UnsupportedUrlError("Send a supported media URL.")

    detected = detect_url(urls[0])
    return PublicDownloadJob(
        job_id=str(uuid4()),
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        url=detected.url,
    )
