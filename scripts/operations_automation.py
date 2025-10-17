#!/usr/bin/env python3
"""Automate operational runbooks for the asset depot stack."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_REPLICA_SCRIPT = Path(__file__).with_name("replica_health_check.sh")


def _run_command(command: List[str]) -> Dict[str, Any]:
    """Run a shell command and capture stdout/stderr."""

    start = time.monotonic()
    process = subprocess.run(command, capture_output=True, text=True)
    duration = time.monotonic() - start
    return {
        "command": command,
        "returncode": process.returncode,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
        "duration_seconds": round(duration, 3),
    }


def _find_latest_backup(backup_dir: Path) -> Optional[Path]:
    if not backup_dir.exists() or not backup_dir.is_dir():
        return None
    candidates = [p for p in backup_dir.iterdir() if p.is_file()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def check_backups(backup_dir: Path) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "status": "skipped",
        "backup_dir": str(backup_dir),
        "details": {},
    }
    latest = _find_latest_backup(backup_dir)
    if latest is None:
        report["status"] = "failed"
        report["details"] = {"message": "No backups found"}
        return report

    report["details"]["latest_file"] = str(latest)
    report["details"]["size_bytes"] = latest.stat().st_size

    command = ["pg_restore", "--list", str(latest)]
    result = _run_command(command)
    report["details"]["verification"] = result
    if result["returncode"] == 0:
        report["status"] = "passed"
    else:
        report["status"] = "failed"
        report["details"]["message"] = "pg_restore validation failed"
    return report


def check_wal_archive(archive_dir: Path, max_age_minutes: int) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "status": "skipped",
        "archive_dir": str(archive_dir),
        "details": {},
    }
    if not archive_dir.exists():
        report["details"]["message"] = "Archive directory does not exist"
        return report
    if not archive_dir.is_dir():
        report["status"] = "failed"
        report["details"]["message"] = "Archive path is not a directory"
        return report

    wal_files = [p for p in archive_dir.iterdir() if p.is_file()]
    if not wal_files:
        report["status"] = "failed"
        report["details"]["message"] = "No WAL files found"
        return report

    wal_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    latest = wal_files[0]
    age_seconds = time.time() - latest.stat().st_mtime
    report["details"]["latest_file"] = str(latest)
    report["details"]["age_seconds"] = round(age_seconds, 1)

    if age_seconds <= max_age_minutes * 60:
        report["status"] = "passed"
    else:
        report["status"] = "failed"
        report["details"]["message"] = (
            f"Latest WAL archive is older than {max_age_minutes} minutes"
        )
    return report


def check_replica(script_path: Path, replica_url: Optional[str], promote_on_failure: bool) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "status": "skipped",
        "details": {},
    }
    if not replica_url:
        report["details"]["message"] = "Replica URL not provided"
        return report
    if not script_path.exists():
        report["status"] = "failed"
        report["details"]["message"] = f"Replica script not found at {script_path}"
        return report

    command = [str(script_path), replica_url]
    if promote_on_failure:
        command.append("--promote-on-failure")

    result = _run_command(command)
    report["details"]["execution"] = result
    if result["returncode"] == 0:
        report["status"] = "passed"
    else:
        report["status"] = "failed"
    return report


def check_service_health(url: Optional[str], timeout: int) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "status": "skipped",
        "details": {},
    }
    if not url:
        report["details"]["message"] = "Health URL not provided"
        return report

    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            report["details"]["http_status"] = response.status
            payload = response.read(1024)
            if payload:
                try:
                    report["details"]["body"] = json.loads(payload)
                except json.JSONDecodeError:
                    report["details"]["body"] = payload.decode("utf-8", errors="ignore")
            report["status"] = "passed" if response.status < 500 else "failed"
    except urllib.error.URLError as exc:  # pragma: no cover - network failure path
        report["status"] = "failed"
        report["details"]["error"] = str(exc)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automate operational runbooks")
    parser.add_argument(
        "--backup-dir",
        default="./backups",
        type=Path,
        help="Directory containing logical backups",
    )
    parser.add_argument(
        "--archive-dir",
        default=Path("./backups/wal"),
        type=Path,
        help="Directory where WAL archives are stored",
    )
    parser.add_argument(
        "--archive-max-age-minutes",
        default=60,
        type=int,
        help="Maximum allowable age of the newest WAL file",
    )
    parser.add_argument(
        "--replica-url",
        help="Connection URL for replica health checks",
    )
    parser.add_argument(
        "--replica-script",
        default=DEFAULT_REPLICA_SCRIPT,
        type=Path,
        help="Path to replica_health_check.sh",
    )
    parser.add_argument(
        "--promote-on-failure",
        action="store_true",
        help="Pass --promote-on-failure to the replica health script",
    )
    parser.add_argument(
        "--health-url",
        default="http://localhost:8000/health",
        help="Service health endpoint to poll",
    )
    parser.add_argument(
        "--health-timeout",
        default=5,
        type=int,
        help="HTTP timeout when calling the health endpoint",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the JSON report",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    summary: Dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "results": {},
    }

    summary["results"]["backup_verification"] = check_backups(args.backup_dir)
    summary["results"]["wal_archive"] = check_wal_archive(
        args.archive_dir, args.archive_max_age_minutes
    )
    summary["results"]["replica_health"] = check_replica(
        args.replica_script, args.replica_url, args.promote_on_failure
    )
    summary["results"]["service_health"] = check_service_health(
        args.health_url, args.health_timeout
    )

    failed = any(result.get("status") == "failed" for result in summary["results"].values())

    payload = json.dumps(summary, indent=2)
    print(payload)
    if args.output:
        args.output.write_text(payload)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
