"""Helper utilities for interacting with merge automation workers."""
from __future__ import annotations

import os
from typing import Iterable

from .tasks import execute_merge_job, run_merge_job

DISABLE_AUTOMATION = os.getenv("DISABLE_MERGE_AUTOMATION", "false").lower() in {"1", "true", "yes"}


def is_worker_enabled() -> bool:
    return not DISABLE_AUTOMATION


def enqueue_merge_job(job_id: str) -> None:
    if not job_id:
        return
    if DISABLE_AUTOMATION:
        run_merge_job(job_id)
    else:
        execute_merge_job.apply_async(args=[job_id])


def enqueue_many(job_ids: Iterable[str]) -> None:
    for job_id in job_ids:
        enqueue_merge_job(job_id)
