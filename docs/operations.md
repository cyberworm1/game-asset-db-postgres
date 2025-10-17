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
- Set `LOGGER_PATH` to a log file harvested by your log stack and `PROMETHEUS_TEXTFILE` to the node exporter textfile collector directory (e.g., `/var/lib/node_exporter/textfile/replica.prom`) so the same probe populates structured logs and Prometheus metrics.
- Forward the JSON output to your monitoring stack and alert when `status != "healthy"`.

Example cron entry:

```
*/5 * * * * /opt/game-asset-db/scripts/replica_health_check.sh \
  "postgres://replica:secret@standby:5432/postgres" >> /var/log/game-asset-db/replica.log 2>&1
```

## Backup Verification Drills

- Add a weekly job that restores the most recent base backup into an ephemeral container and runs `SELECT COUNT(*) FROM assets;` as a smoke test.
- Use the `scripts/restore.sh` helper in CI to ensure WAL archives replay successfully before expiring older backups.
- Record restore outcomes in the ops wiki for auditing.

## Automated Runbooks & Metrics

- Use `scripts/operations_automation.py` to orchestrate nightly maintenance. The script validates the newest logical backup with `pg_restore --list`, checks WAL archive freshness, pings the service health endpoint, proxies `scripts/replica_health_check.sh`, and now emits Prometheus-compatible gauges when `--prometheus-textfile-dir` is specified.
- Example cron entry writing both a JSON report and metrics scrape file:

  ```
  0 1 * * * /opt/game-asset-db/scripts/operations_automation.py \
      --backup-dir /opt/game-asset-db/backups \
      --archive-dir /opt/game-asset-db/backups/wal \
      --replica-url "postgres://replica:secret@standby:5432/postgres" \
      --prometheus-textfile-dir /var/lib/node_exporter/textfile \
      --output /var/log/game-asset-db/ops-report.json >>/var/log/game-asset-db/ops.log 2>&1
  ```
- Treat the JSON payload as an observability feed—ship it to Loki, Splunk, or Grafana Loki—and allow Prometheus to ingest the generated textfile for dashboards and alerting.

## Automated Merge Workers

- Celery workers now orchestrate `/branch-merges` jobs without manual polling. Redis backs the queue; the FastAPI service enqueues jobs when merges or additional jobs are created.
- Set `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` for the API and worker containers (defaults are provided in `docker-compose.yml`). The automation uses `MERGE_AUTOMATION_USER_ID` when supplied or falls back to the first admin account to satisfy RLS.
- Inspect worker logs via `docker compose logs merge-worker` (or `journalctl -u game-asset-failover.service` on bare metal) to confirm auto-integrate and submit-gate tasks complete. Failed jobs transition branch merges to `conflicted` so human triage mirrors Helix’s merge gatekeeping.

## Observability Stack

- `docker-compose.yml` provisions Prometheus, node exporter, Redis, the Celery merge worker, and an optional Grafana profile (`docker compose --profile grafana up -d`).
- Prometheus scrapes FastAPI metrics (`/metrics`), node exporter host data, and the textfile collector fed by `operations_automation.py` and `replica_health_check.sh`. Mount `./observability/textfile` into operations cronjobs when running on Docker hosts.
- The Ansible `monitoring` role installs the same stack on bare-metal/VMs, writing metrics to `{{ prometheus_textfile_dir }}` and optionally installing Grafana when `monitoring_enable_grafana` is true.

## Replica Lifecycle & Integrity Management

- Run `scripts/object_store_replica.py --primary /var/lib/asset-depot --replica /mnt/object-store-mirror --retention-days 365 --manifest /var/log/game-asset-db/replica_audit.json` to enforce retention, prune orphaned mirror files, and verify parity.
- Use `--full-hash` for deep integrity sweeps when bandwidth/storage allow. The JSON manifest records mismatches so you can trigger re-sync jobs or escalate to storage teams.

## Automated Failover Orchestration

- `scripts/failover_controller.py` provides a repmgr-aware failover loop. Point `--dsn` at the current primary, set `--post-promote-follow` to rejoin the cluster after promotion, and hand the script to `systemd` or Kubernetes CronJobs for continuous readiness.
- The new Ansible `failover` role installs repmgr, deploys the controller script to `/opt/game-asset-db/bin`, and schedules `game-asset-failover.timer` to run at the cadence defined by `failover_timer_interval`.

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

- Wire Grafana dashboards and alert rules into the repository so new environments inherit curated visualizations.
- Extend merge workers with per-project job plugins (e.g., launching asset validation microservices) beyond the default pipeline.
