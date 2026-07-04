from __future__ import annotations

import sys
import time
from typing import cast

from omnisaver_config import Settings, load_settings
from omnisaver_db import PostgresDownloadJobRepository, PostgresSessionRepository
from omnisaver_downloader import build_default_downloader_manager
from omnisaver_media_processor import TemporaryCleanupWorker, build_default_media_processor
from omnisaver_session_vault import SessionVault
from omnisaver_worker.job_queue import build_redis_job_queue
from omnisaver_worker.notifications import JobNotifier
from omnisaver_worker.public_job import PublicDownloadJobRunner, TelegramSender
from omnisaver_worker.service import WorkerService
from omnisaver_worker.session_resolver import VaultSessionResolver
from omnisaver_worker.telegram_sender import BotApiTelegramSender


def build_worker_service(
    settings: Settings,
    *,
    sender: TelegramSender | None = None,
) -> WorkerService:
    telegram_sender = sender or BotApiTelegramSender(settings.telegram_bot_token)
    session_repository = PostgresSessionRepository.connect(settings.database_url)
    vault = SessionVault.from_base64_key(
        settings.session_vault_master_key_base64,
        key_id=settings.cookie_encryption_key_id,
    )
    runner = PublicDownloadJobRunner(
        downloader=build_default_downloader_manager(
            ytdlp_bin=settings.ytdlp_bin,
            gallery_dl_bin=settings.gallery_dl_bin,
            instaloader_bin=settings.instaloader_bin,
        ),
        sender=telegram_sender,
        storage_root=settings.download_storage_path,
        session_resolver=VaultSessionResolver(
            repository=session_repository,
            vault=vault,
        ),
        media_processor=build_default_media_processor(
            ffmpeg_bin=settings.ffmpeg_bin,
            max_file_size_mb=settings.max_download_size_mb,
            max_temp_storage_mb=settings.media_max_temp_storage_mb,
            video_crf=settings.media_video_crf,
            video_max_height=settings.media_video_max_height,
            thumbnail_width=settings.media_thumbnail_width,
        ),
    )
    return WorkerService(
        queue=build_redis_job_queue(settings.redis_url),
        repository=PostgresDownloadJobRepository.connect(settings.database_url),
        runner=runner,
        notifier=cast(JobNotifier, telegram_sender),
    )


def run_worker(service: WorkerService, *, poll_seconds: int) -> None:
    while True:
        processed = service.process_one()
        if not processed:
            time.sleep(poll_seconds)


def main() -> None:
    settings = load_settings()
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup-once":
        removed = TemporaryCleanupWorker(
            storage_root=settings.download_storage_path,
            ttl_hours=settings.temp_file_ttl_hours,
        ).run_once()
        print(f"removed {removed} expired temporary files")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "health":
        print("ok")
        return
    service = build_worker_service(settings)
    if len(sys.argv) > 1 and sys.argv[1] == "process-once":
        processed = service.process_one()
        print("processed 1 job" if processed else "no jobs available")
        return
    run_worker(service, poll_seconds=settings.worker_poll_seconds)
