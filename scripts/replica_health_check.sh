#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: replica_health_check.sh <connection-url> [--promote-on-failure]

Checks replication status for a PostgreSQL standby and emits structured logs that can
be scraped by monitoring pipelines. When --promote-on-failure is provided, a replica
that appears unhealthy (disconnected or with replay lag greater than the configured
threshold) will be promoted to primary.

Environment variables:
  REPLAY_LAG_THRESHOLD_SECONDS  Maximum acceptable replay lag in seconds (default: 120)
  LOGGER_PATH                   Optional file to append JSON log lines to

Examples:
  REPLAY_LAG_THRESHOLD_SECONDS=90 ./replica_health_check.sh \
      "postgres://replica:secret@localhost:5433/postgres"

  ./replica_health_check.sh "postgres://replica@standby/db" --promote-on-failure
USAGE
}

if [[ $# -lt 1 ]]; then
    usage
    exit 1
fi

CONN_URL=$1
PROMOTE_ON_FAILURE=false
if [[ ${2:-} == "--promote-on-failure" ]]; then
    PROMOTE_ON_FAILURE=true
fi

THRESHOLD=${REPLAY_LAG_THRESHOLD_SECONDS:-120}
LOGGER_PATH=${LOGGER_PATH:-}
TIMESTAMP=$(date --iso-8601=seconds)

read -r -d '' SQL <<'SQL'
SELECT
    pg_is_in_recovery() AS in_recovery,
    now() - pg_last_xact_replay_timestamp() AS replay_lag,
    EXTRACT(EPOCH FROM now() - pg_last_wal_receive_timestamp()) AS receive_lag_seconds,
    EXTRACT(EPOCH FROM now() - pg_last_xact_replay_timestamp()) AS replay_lag_seconds,
    pg_last_wal_receive_lsn() AS receive_lsn,
    pg_last_wal_replay_lsn() AS replay_lsn;
SQL

RESULT=$(psql "$CONN_URL" -Atc "$SQL" 2>&1) || {
    MESSAGE="Failed to query replica status: $RESULT"
    echo "$MESSAGE" >&2
    if [[ -n $LOGGER_PATH ]]; then
        printf "{\"timestamp\":\"%s\",\"level\":\"error\",\"message\":\"%s\"}\\n" "$TIMESTAMP" "${MESSAGE//"/\\"}" >>"$LOGGER_PATH"
    fi
    exit 2
}

IFS='|' read -r IN_RECOVERY REPLAY_LAG RECEIVE_LAG_SECONDS REPLAY_LAG_SECONDS RECEIVE_LSN REPLAY_LSN <<<"$RESULT"

if [[ $IN_RECOVERY != "t" ]]; then
    MESSAGE="Instance is not in recovery mode; replica check is not applicable."
    echo "$MESSAGE"
    if [[ -n $LOGGER_PATH ]]; then
        printf "{\"timestamp\":\"%s\",\"level\":\"warning\",\"message\":\"%s\"}\\n" "$TIMESTAMP" "${MESSAGE//"/\\"}" >>"$LOGGER_PATH"
    fi
    exit 0
fi

REPLAY_LAG_SECONDS_INT=${REPLAY_LAG_SECONDS%.*}
if [[ -z $REPLAY_LAG_SECONDS_INT ]]; then
    REPLAY_LAG_SECONDS_INT=0
fi

STATUS="healthy"
MESSAGE="Replica replay lag is ${REPLAY_LAG_SECONDS}s"

if (( REPLAY_LAG_SECONDS_INT > THRESHOLD )); then
    STATUS="unhealthy"
    MESSAGE="Replica replay lag ${REPLAY_LAG_SECONDS}s exceeds threshold ${THRESHOLD}s"
fi

echo "$MESSAGE"

if [[ -n $LOGGER_PATH ]]; then
    printf "{\"timestamp\":\"%s\",\"level\":\"info\",\"status\":\"%s\",\"receive_lsn\":\"%s\",\"replay_lsn\":\"%s\",\"replay_lag_seconds\":%s,\"receive_lag_seconds\":%s}\\n" \
        "$TIMESTAMP" "$STATUS" "$RECEIVE_LSN" "$REPLAY_LSN" "${REPLAY_LAG_SECONDS:-0}" "${RECEIVE_LAG_SECONDS:-0}" >>"$LOGGER_PATH"
fi

if [[ $STATUS == "unhealthy" && $PROMOTE_ON_FAILURE == true ]]; then
    echo "Promoting replica due to unhealthy status..."
    psql "$CONN_URL" -c "SELECT pg_promote(wait_seconds => 60);"
fi
