#!/usr/bin/env bash
set -euo pipefail

REPLICA_DIR=${1:-$(pwd)/replica-data}
PRIMARY_HOST=${PRIMARY_HOST:-localhost}
PRIMARY_PORT=${PRIMARY_PORT:-5432}
PRIMARY_USER=${PRIMARY_USER:-postgres}

if ! command -v pg_basebackup >/dev/null 2>&1; then
  echo "pg_basebackup is required" >&2
  exit 1
fi

mkdir -p "$REPLICA_DIR"
rm -rf "$REPLICA_DIR"/*

echo "Creating replica base backup in $REPLICA_DIR"
pg_basebackup \
  --pgdata="$REPLICA_DIR" \
  --format=p \
  --write-recovery-conf \
  --wal-method=stream \
  --host="$PRIMARY_HOST" \
  --port="$PRIMARY_PORT" \
  --username="$PRIMARY_USER" \
  --progress

echo "Replica bootstrap complete. Start a postgres container mounting $REPLICA_DIR to launch the standby."
