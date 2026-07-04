from __future__ import annotations

import sys

from omnisaver_config import load_settings
from omnisaver_media_processor import TemporaryCleanupWorker


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
    print(f"omnisaver downloader worker placeholder ({settings.environment})")
