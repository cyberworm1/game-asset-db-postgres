# Operational Runbook

This guide extends the base README with pragmatic procedures for operating the asset depot in production-like environments.

## Services Overview

| Service | Purpose |
|---------|---------|
| `db` | Primary PostgreSQL instance with WAL archiving enabled for PITR and replication. |
| `asset-service` | FastAPI application that exposes REST APIs, handles authentication, and stores binary files on the depot volume. |
| `pgadmin` | Web-based administration console for Postgres. |
| `pgbackups` | Cron-like job that performs nightly logical backups (`pg_dump`). |

## Depot Storage Layout

- Asset payloads are written into a content-addressable store rooted under `ASSET_STORAGE_PATH` (default `/var/lib/asset-depot`).
- Binary data is compressed and deduplicated by SHA-256, landing in `objects/<sha-prefix>/<sha>.bin.gz`. Pointer manifests are emitted per project in `refs/<project_id>/<timestamp>_<asset_id>.json` so restores know which logical asset references which physical blob.
- Set `ASSET_STORAGE_REPLICA_PATH` to a mounted object store or NAS path to automatically mirror each object for off-host redundancy. Replica directories mirror the primary layout, allowing `rsync` or cloud lifecycle tooling to manage retention.

## Backups & PITR

1. **Automated Dumps** – The `pgbackups` container writes timestamped dumps to `./backups`. Rotate via the `BACKUP_KEEP_*` variables.
2. **Manual Point-in-Time Recovery** – Use WAL archive files written to `/var/lib/postgresql/data/archive` inside the `db` container.
   ```bash
   docker-compose exec db bash -c 'ls /var/lib/postgresql/data/archive'
   ```
   Restore by replaying WAL files to a target timestamp after restoring the last base backup.
3. **Ad-hoc Base Backup** – Run `scripts/backup.sh` for an immediate dump before maintenance.

## Creating a Hot Standby Replica

The `scripts/create-replica.sh` helper performs a `pg_basebackup` and configures a streaming replica container.

1. Ensure the primary is running with WAL enabled (default in this repository).
2. Execute `./scripts/create-replica.sh` to provision a replica data directory in `./replica-data`.
3. Start a new container with:
   ```bash
   docker run --rm -it \
     -v $(pwd)/replica-data:/var/lib/postgresql/data \
     -e POSTGRES_PASSWORD=password \
     -p 5433:5432 \
     postgres:16
   ```
4. Promote the replica (if the primary fails) by executing inside the replica container:
   ```bash
   pg_ctl promote -D /var/lib/postgresql/data
   ```

## Replica Health Automation

- Schedule `scripts/replica_health_check.sh` via cron (e.g., every 5 minutes) against each standby. The script emits JSON logs that can feed Loki/FluentBit and optionally promotes a replica if `--promote-on-failure` is supplied.
- Configure `REPLAY_LAG_THRESHOLD_SECONDS` to the maximum lag tolerated by downstream teams. Default is 120 seconds.
- Forward the JSON output to your monitoring stack to drive alerts on `status != "healthy"`.

Example cron entry:

```
*/5 * * * * /opt/game-asset-db/scripts/replica_health_check.sh \
  "postgres://replica:secret@standby:5432/postgres" >> /var/log/game-asset-db/replica.log 2>&1
```

## Backup Verification Drills

- Add a weekly job that restores the most recent base backup into an ephemeral container and runs `SELECT COUNT(*) FROM assets;` as a smoke test.
- Use the `scripts/restore.sh` helper in CI to ensure WAL archives replay successfully before expiring older backups.
- Record restore outcomes in the ops wiki for auditing.

## Automated Runbooks

- Use `scripts/operations_automation.py` to orchestrate nightly maintenance. The script validates the newest logical backup with `pg_restore --list`, checks WAL archive freshness, pings the service health endpoint, and proxies `scripts/replica_health_check.sh`.
- Example cron entry writing a JSON report:

  ```
  0 1 * * * /opt/game-asset-db/scripts/operations_automation.py \
      --backup-dir /opt/game-asset-db/backups \
      --archive-dir /opt/game-asset-db/backups/wal \
      --replica-url "postgres://replica:secret@standby:5432/postgres" \
      --output /var/log/game-asset-db/ops-report.json >>/var/log/game-asset-db/ops.log 2>&1
  ```
- Treat the JSON payload as an observability feed—ship it to Loki, Splunk, or Grafana Loki to mirror the integrated dashboards available in Helix Core.

## Disaster Recovery Checklist

- [ ] Confirm last successful automated backup in `./backups`.
- [ ] Capture WAL sequence from the archive directory.
- [ ] Run `scripts/backup.sh` for additional safety before risky operations.
- [ ] Validate replica catch-up via `SELECT pg_last_wal_replay_lsn();` on the standby.
- [ ] Document failover in the project wiki.

## Monitoring Hooks

- The FastAPI service exposes `/health` for container orchestration health checks.
- Postgres metrics can be scraped by adding `postgres_exporter`; pair this with the replica health script for end-to-end visibility.

## Auth & Permission Notes

- Application components must call `SELECT set_app_user('<uuid>')` at the start of each request to satisfy RLS.
- pgAdmin connections bypass RLS; restrict to admin users only.

## Changelist & Merge Runbook

- Use the new `/changelists` endpoints to create atomic submissions that bundle multiple asset versions from a workspace. Shelves can be linked to a changelist to keep QA staging aligned with the bundle.
- Pipeline automation should call `/changelists/{id}/submit` only after verifying that all items have passed validation, because the API enforces the target branch requirement and rejects empty bundles.
- Branch integration tooling can record merges through `/branch-merges`; populate conflict details via `/branch-merges/{id}/conflicts` so production teams can track resolution history inside the database.
- Periodically poll `/projects/{project_id}/branch-merges` to surface outstanding `pending` or `conflicted` merges in dashboards and ensure follow-up automation (e.g., automated resolve jobs) has context.
- Queue orchestration tasks with `/branch-merges/{id}/jobs` and update them via `/merge-jobs/{job_id}`. Default merges include `auto_integrate`, `conflict_staging`, and optional `submit_gate` jobs that mirror Helix stream workflows.
- A merge cannot transition to `merged` or set `completed_at` until submit-gate jobs report success (`status=completed` and `submit_gate_passed=true`) and all conflicts are resolved, ensuring content flows stay atomic.

## Future Enhancements

- Add Prometheus/Grafana stack.
- Extend the merge job queue with worker automation (Celery/Arq) to execute `auto_integrate` runs server-side.
- Expand object storage replication with lifecycle policies (e.g., S3 Intelligent-Tiering) for long-term archive hygiene.
- Automate switchover with Patroni or repmgr for clustered deployments.
