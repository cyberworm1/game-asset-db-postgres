#!/usr/bin/env python3
"""Automate failover promotion using repmgr primitives."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import psycopg
except ImportError as exc:  # pragma: no cover - defensive guard
    raise SystemExit("psycopg is required for failover_controller.py") from exc


def check_primary(dsn: str, *, attempts: int, interval: float) -> Dict[str, Any]:
    failures: list[str] = []
    for attempt in range(1, attempts + 1):
        try:
            with psycopg.connect(dsn, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return {"status": "healthy", "attempts": attempt}
        except Exception as exc:  # pragma: no cover - network failure path
            failures.append(str(exc))
            time.sleep(interval)
    return {"status": "unreachable", "errors": failures, "attempts": attempts}


def run_command(command: list[str], *, dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"command": command, "dry_run": True}
    result = subprocess.run(command, capture_output=True, text=True)
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def promote_standby(repmgr_bin: str, node_name: Optional[str], *, dry_run: bool) -> Dict[str, Any]:
    command = [repmgr_bin, "standby", "promote", "--log-to-file"]
    if node_name:
        command.extend(["--node-name", node_name])
    return run_command(command, dry_run=dry_run)


def follow_new_primary(repmgr_bin: str, node_name: Optional[str], *, dry_run: bool) -> Dict[str, Any]:
    command = [repmgr_bin, "cluster", "follow"]
    if node_name:
        command.extend(["--node-name", node_name])
    return run_command(command, dry_run=dry_run)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automated failover orchestration for Postgres replicas")
    parser.add_argument("--dsn", required=True, help="Connection string for the primary health probe")
    parser.add_argument("--repmgr-bin", default="repmgr", help="Path to the repmgr executable")
    parser.add_argument("--node-name", help="Optional repmgr node name for logging context")
    parser.add_argument("--health-attempts", type=int, default=3, help="Number of attempts before promoting the replica")
    parser.add_argument("--health-interval", type=float, default=5.0, help="Seconds to wait between health attempts")
    parser.add_argument("--dry-run", action="store_true", help="Do not execute repmgr commands")
    parser.add_argument("--post-promote-follow", action="store_true", help="Call `repmgr cluster follow` after promotion")
    parser.add_argument("--manifest", type=Path, help="Optional JSON manifest output path")
    args = parser.parse_args(argv)

    health = check_primary(args.dsn, attempts=args.health_attempts, interval=args.health_interval)
    summary: Dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "health": health,
        "dry_run": args.dry_run,
        "actions": [],
    }

    if health.get("status") == "healthy":
        summary["result"] = "primary_healthy"
        payload = json.dumps(summary, indent=2)
        print(payload)
        if args.manifest:
            args.manifest.write_text(payload)
        return 0

    promote_result = promote_standby(args.repmgr_bin, args.node_name, dry_run=args.dry_run)
    summary["actions"].append({"promote": promote_result})

    if promote_result.get("returncode", 0) != 0 and not args.dry_run:
        summary["result"] = "promotion_failed"
        payload = json.dumps(summary, indent=2)
        print(payload)
        if args.manifest:
            args.manifest.write_text(payload)
        return 2

    if args.post_promote_follow:
        follow_result = follow_new_primary(args.repmgr_bin, args.node_name, dry_run=args.dry_run)
        summary["actions"].append({"follow": follow_result})

    summary["result"] = "promotion_executed"
    payload = json.dumps(summary, indent=2)
    print(payload)
    if args.manifest:
        args.manifest.write_text(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
