from __future__ import annotations

import shutil
from contextlib import suppress
from pathlib import Path


def user_storage_dir(storage_root: Path, telegram_user_id: int) -> Path:
    return storage_root / str(telegram_user_id)


def job_output_dir(
    storage_root: Path,
    job_id: str,
    *,
    telegram_user_id: int | None = None,
) -> Path:
    if telegram_user_id is None:
        return storage_root / job_id
    return user_storage_dir(storage_root, telegram_user_id) / job_id


def cleanup_job_output(
    storage_root: Path,
    job_id: str,
    *,
    telegram_user_id: int | None = None,
) -> None:
    shutil.rmtree(
        job_output_dir(storage_root, job_id, telegram_user_id=telegram_user_id),
        ignore_errors=True,
    )


def cleanup_expired_temp_files(storage_root: Path, *, older_than_epoch_seconds: float) -> int:
    removed = 0
    if not storage_root.exists():
        return removed
    for path in storage_root.rglob("*"):
        if not path.is_file() or path.stat().st_mtime >= older_than_epoch_seconds:
            continue
        path.unlink(missing_ok=True)
        removed += 1
    for directory in sorted(
        (path for path in storage_root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        with suppress(OSError):
            directory.rmdir()
    return removed


def user_temp_storage_bytes(storage_root: Path, telegram_user_id: int) -> int:
    directory = user_storage_dir(storage_root, telegram_user_id)
    if not directory.exists():
        return 0
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())
