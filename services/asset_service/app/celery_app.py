"""Celery application for asynchronous automation workers."""
from __future__ import annotations

import os
from celery import Celery


def _default_broker() -> str:
    return os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")


def _default_backend() -> str:
    return os.getenv("CELERY_RESULT_BACKEND", _default_broker())


celery_app = Celery("asset_service", broker=_default_broker(), backend=_default_backend())
celery_app.conf.update(
    task_default_queue=os.getenv("CELERY_DEFAULT_QUEUE", "branch_merges"),
    task_acks_late=True,
    worker_prefetch_multiplier=int(os.getenv("CELERY_PREFETCH_MULTIPLIER", "1")),
    task_track_started=True,
)

# Ensure tasks are registered when the worker starts.
celery_app.autodiscover_tasks(["app"])
