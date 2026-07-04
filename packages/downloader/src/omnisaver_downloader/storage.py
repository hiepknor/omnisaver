from __future__ import annotations

import shutil
from pathlib import Path


def job_output_dir(storage_root: Path, job_id: str) -> Path:
    return storage_root / job_id


def cleanup_job_output(storage_root: Path, job_id: str) -> None:
    shutil.rmtree(job_output_dir(storage_root, job_id), ignore_errors=True)
