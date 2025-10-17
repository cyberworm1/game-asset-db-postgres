"""Utility helpers for optional OpenCue integration."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    import opencue  # type: ignore
    from opencue import Cuebot  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    opencue = None  # type: ignore
    Cuebot = None  # type: ignore


@dataclass
class RenderStatusCounts:
    """Aggregate rendering counts for common status buckets."""

    cued: int = 0
    running: int = 0
    success: int = 0
    fail: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "cued": self.cued,
            "running": self.running,
            "success": self.success,
            "fail": self.fail,
        }


class OpenCueIntegration:
    """Wrapper that exposes simplified OpenCue status summaries."""

    STATUS_MAP = {
        "pending": "cued",
        "ready": "cued",
        "waiting": "cued",
        "depend": "cued",
        "cued": "cued",
        "running": "running",
        "checkpoint": "running",
        "eaten": "running",
        "success": "success",
        "succeeded": "success",
        "succeed": "success",
        "finished": "success",
        "complete": "success",
        "completed": "success",
        "done": "success",
        "failed": "fail",
        "dead": "fail",
        "dequeued": "fail",
        "cancelled": "fail",
        "canceled": "fail",
        "failed_checkpoint": "fail",
    }

    def __init__(self) -> None:
        hosts_raw = os.getenv("OPENCUE_HOSTS", "")
        self._hosts = [host.strip() for host in hosts_raw.split(",") if host.strip()]
        self.enabled = bool(self._hosts)
        self._show = os.getenv("OPENCUE_DEFAULT_SHOW")
        self._facility = os.getenv("OPENCUE_FACILITY")
        self._last_summary: Optional[Dict[str, Any]] = None
        self._initialized = False

    def _ensure_client(self) -> None:
        if not self.enabled:
            raise RuntimeError("OpenCue integration disabled")
        if Cuebot is None:
            raise RuntimeError("opencue Python client is not installed")
        if not self._initialized:
            Cuebot.setHosts(self._hosts)
            self._initialized = True

    def _fetch_jobs(self) -> Iterable[Any]:
        self._ensure_client()
        if opencue is None:  # pragma: no cover - defensive
            return []

        filters: Dict[str, Any] = {}
        if self._show:
            filters["show"] = self._show
        if self._facility:
            filters["facility"] = self._facility

        try:
            if hasattr(opencue.api, "findJobs"):
                return opencue.api.findJobs(**filters)
            if hasattr(opencue.api, "getJobs"):
                return opencue.api.getJobs(**filters)
        except Exception as exc:  # pragma: no cover - network errors
            logger.warning("Failed to query OpenCue", exc_info=exc)
            raise
        return []

    @staticmethod
    def _call_or_value(obj: Any) -> Any:
        if callable(obj):
            try:
                return obj()
            except Exception:  # pragma: no cover - defensive
                return None
        return obj

    @classmethod
    def _extract_attr(cls, obj: Any, *names: str) -> Any:
        for name in names:
            if obj is None:
                return None
            if isinstance(obj, dict):
                if name in obj:
                    return cls._call_or_value(obj[name])
                continue
            attr = getattr(obj, name, None)
            if attr is not None:
                value = cls._call_or_value(attr)
                if value is not None:
                    return value
        return None

    @classmethod
    def _normalize_datetime(cls, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc)
        if isinstance(value, (int, float)):
            # OpenCue timestamps are seconds since epoch
            return datetime.fromtimestamp(value, tz=timezone.utc)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    @classmethod
    def _normalize_status(cls, status: Any) -> str:
        if status is None:
            return "cued"
        if isinstance(status, bytes):
            status = status.decode("utf-8", errors="ignore")
        status_str = str(status).strip().lower()
        if not status_str:
            return "cued"
        return cls.STATUS_MAP.get(status_str, "cued")

    def _summarize_jobs(self, jobs: Iterable[Any]) -> Dict[str, Any]:
        counts = RenderStatusCounts()
        details: List[Dict[str, Any]] = []

        for job in jobs:
            raw_status = self._extract_attr(job, "state", "status")
            normalized_status = self._normalize_status(raw_status)
            if normalized_status == "cued":
                counts.cued += 1
            elif normalized_status == "running":
                counts.running += 1
            elif normalized_status == "success":
                counts.success += 1
            elif normalized_status == "fail":
                counts.fail += 1

            stats_obj = self._extract_attr(job, "jobStats", "stats")
            stats: Dict[str, Any] = {}
            if stats_obj:
                stats = {
                    "frame_count": self._extract_attr(
                        stats_obj,
                        "totalFrames",
                        "frameCount",
                        "countFrames",
                    ),
                    "running_frames": self._extract_attr(
                        stats_obj,
                        "runningFrames",
                        "running",
                    ),
                    "succeeded_frames": self._extract_attr(
                        stats_obj,
                        "succeededFrames",
                        "success",
                    ),
                    "failed_frames": self._extract_attr(
                        stats_obj,
                        "failedFrames",
                        "failed",
                    ),
                }

            detail = {
                "id": self._extract_attr(job, "id"),
                "name": self._extract_attr(job, "name"),
                "show": self._extract_attr(job, "show"),
                "shot": self._extract_attr(job, "shot"),
                "layer": self._extract_attr(job, "layer"),
                "user": self._extract_attr(job, "user"),
                "status": normalized_status,
                "host": self._extract_attr(job, "lastResource", "lastHost"),
                "started_at": self._normalize_datetime(
                    self._extract_attr(job, "startTime", "startedAt", "started")
                ),
                "updated_at": self._normalize_datetime(
                    self._extract_attr(job, "updateTime", "lastUpdated", "updated")
                ),
                **stats,
            }
            details.append(detail)

        now = datetime.now(timezone.utc)
        payload = {
            "enabled": True,
            "available": True,
            "summary": counts.as_dict(),
            "jobs": details,
            "last_updated": now,
            "source": "OpenCue",
            "message": None,
        }
        self._last_summary = payload
        return payload

    def get_summary(self) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "enabled": False,
                "available": False,
                "summary": RenderStatusCounts().as_dict(),
                "jobs": [],
                "last_updated": datetime.now(timezone.utc),
                "source": "OpenCue",
                "message": "OpenCue integration is disabled.",
            }
        if Cuebot is None:
            return {
                "enabled": True,
                "available": False,
                "summary": RenderStatusCounts().as_dict(),
                "jobs": [],
                "last_updated": datetime.now(timezone.utc),
                "source": "OpenCue",
                "message": "Install the opencue Python client to enable integration.",
            }
        try:
            jobs = list(self._fetch_jobs())
        except Exception as exc:  # pragma: no cover - external dependency
            logger.warning("Error retrieving OpenCue summary", exc_info=exc)
            return {
                "enabled": True,
                "available": False,
                "summary": RenderStatusCounts().as_dict(),
                "jobs": [],
                "last_updated": datetime.now(timezone.utc),
                "source": "OpenCue",
                "message": f"Failed to query OpenCue: {exc}",
            }
        return self._summarize_jobs(jobs)

    def get_details(self) -> Dict[str, Any]:
        """Alias for get_summary to keep interface symmetric."""

        return self.get_summary()


integration = OpenCueIntegration()
