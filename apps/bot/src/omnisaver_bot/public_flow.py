from __future__ import annotations

from uuid import uuid4

from omnisaver_downloader import UnsupportedUrlError, detect_url, extract_urls
from omnisaver_worker.job_queue import JobQueue
from omnisaver_worker.public_job import PublicDownloadJob


def create_public_download_job_from_message(
    *,
    message: str,
    telegram_user_id: int,
    chat_id: int,
) -> PublicDownloadJob:
    urls = extract_urls(message)
    if not urls:
        raise UnsupportedUrlError("Vui lòng gửi một link media được hỗ trợ.")

    detected = detect_url(urls[0])
    return PublicDownloadJob(
        job_id=str(uuid4()),
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        platform=detected.platform,
        url=detected.url,
    )


def enqueue_public_download_job_from_message(
    *,
    queue: JobQueue,
    message: str,
    telegram_user_id: int,
    chat_id: int,
) -> PublicDownloadJob:
    job = create_public_download_job_from_message(
        message=message,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
    )
    queue.enqueue(job)
    return job
