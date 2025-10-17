#!/usr/bin/env python3
"""Manage lifecycle and integrity for the asset depot replica object store."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


@dataclass
class ObjectStat:
    path: Path
    size: int
    mtime: float
    checksum: str | None = None


def iter_objects(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file():
            yield path


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_index(root: Path, *, compute_hash: bool) -> Dict[str, ObjectStat]:
    index: Dict[str, ObjectStat] = {}
    for file_path in iter_objects(root):
        relative = str(file_path.relative_to(root))
        checksum = hash_file(file_path) if compute_hash else None
        stat = file_path.stat()
        index[relative] = ObjectStat(path=file_path, size=stat.st_size, mtime=stat.st_mtime, checksum=checksum)
    return index


def apply_retention(replica_index: Dict[str, ObjectStat], *, keep_days: int, dry_run: bool) -> List[str]:
    if keep_days <= 0:
        return []
    cutoff = time.time() - keep_days * 86400
    removed: List[str] = []
    for key, info in list(replica_index.items()):
        if info.mtime < cutoff:
            removed.append(key)
            if not dry_run:
                try:
                    info.path.unlink()
                except FileNotFoundError:
                    pass
                finally:
                    replica_index.pop(key, None)
    return removed


def ensure_parity(primary: Dict[str, ObjectStat], replica: Dict[str, ObjectStat]) -> Tuple[List[str], List[str]]:
    missing: List[str] = []
    mismatched: List[str] = []
    for key, primary_stat in primary.items():
        replica_stat = replica.get(key)
        if not replica_stat:
            missing.append(key)
            continue
        if primary_stat.size != replica_stat.size:
            mismatched.append(key)
            continue
        if primary_stat.checksum and replica_stat.checksum and primary_stat.checksum != replica_stat.checksum:
            mismatched.append(key)
    return missing, mismatched


def prune_orphans(primary: Dict[str, ObjectStat], replica: Dict[str, ObjectStat], *, dry_run: bool) -> List[str]:
    orphans: List[str] = []
    for key, replica_stat in replica.items():
        if key not in primary:
            orphans.append(key)
            if not dry_run:
                try:
                    replica_stat.path.unlink()
                except FileNotFoundError:
                    continue
    return orphans


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and prune the replica object store")
    parser.add_argument("--primary", type=Path, required=True, help="Path to the primary object store root")
    parser.add_argument("--replica", type=Path, required=True, help="Path to the replica object store root")
    parser.add_argument("--retention-days", type=int, default=180, help="Delete replica files older than this many days")
    parser.add_argument("--full-hash", action="store_true", help="Compare SHA-256 hashes for parity checks")
    parser.add_argument("--dry-run", action="store_true", help="Report actions without modifying data")
    parser.add_argument("--manifest", type=Path, help="Optional path to write a JSON manifest of the run")
    args = parser.parse_args(argv)

    if not args.primary.exists() or not args.primary.is_dir():
        parser.error("Primary path must be an existing directory")
    if not args.replica.exists() or not args.replica.is_dir():
        parser.error("Replica path must be an existing directory")

    primary_index = build_index(args.primary, compute_hash=args.full_hash)
    replica_index = build_index(args.replica, compute_hash=args.full_hash)

    removed_by_retention = apply_retention(replica_index, keep_days=args.retention_days, dry_run=args.dry_run)
    missing, mismatched = ensure_parity(primary_index, replica_index)
    orphaned = prune_orphans(primary_index, replica_index, dry_run=args.dry_run)

    summary = {
        "primary_root": str(args.primary),
        "replica_root": str(args.replica),
        "dry_run": args.dry_run,
        "full_hash": args.full_hash,
        "retention_days": args.retention_days,
        "objects": {
            "primary": len(primary_index),
            "replica": len(replica_index),
            "removed_by_retention": removed_by_retention,
            "missing_in_replica": missing,
            "mismatched": mismatched,
            "orphaned_removed": orphaned,
        },
    }

    payload = json.dumps(summary, indent=2)
    print(payload)

    if args.manifest:
        args.manifest.write_text(payload)

    if missing or mismatched:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
