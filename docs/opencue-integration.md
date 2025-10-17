# OpenCue Integration Module

The asset service exposes an optional OpenCue integration that surfaces render
queue status to end users and administrators. When enabled, the service queries
OpenCue for active jobs and provides two API endpoints:

- `GET /render/opencue/summary` – high level counts for cued, running, success,
  and failed renders.
- `GET /render/opencue/details` – includes the same counts plus job-level
  metadata intended for the operations panel. Administrator access is required.

## Enabling the Integration

1. Install the OpenCue Python client inside the `asset-service` image:
   ```bash
   pip install opencue grpcio
   ```
2. Configure hosts (comma separated `host:port` values) and optional filters in
   your environment. The sample `docker-compose.yml` includes placeholders that
   can be overridden:
   ```yaml
   OPENCUE_HOSTS: "cuebot:8443"
   OPENCUE_DEFAULT_SHOW: "Odyssey"
   # Optional facility filter
   OPENCUE_FACILITY: "lax"
   ```
3. Restart the API service so it can initialize the Cuebot client with the new
   configuration.

If the integration is disabled or the Python client is missing, the API returns
`enabled=false`/`available=false` along with a helpful message so UI clients can
show a graceful fallback.

## API Response Shape

Both endpoints return the following base fields:

| Field | Description |
|-------|-------------|
| `enabled` | Whether configuration is present (`OPENCUE_HOSTS`). |
| `available` | True when the Cuebot query succeeded. |
| `summary` | Aggregated counts for `cued`, `running`, `success`, and `fail`. |
| `last_updated` | Timestamp of the most recent fetch. |
| `source` | Currently `"OpenCue"`. |
| `message` | Optional human-readable diagnostic. |

The details endpoint extends the payload with a `jobs` array. Each element
includes the job identifier, show/shot/layer names when available, the
normalized status bucket, owning user, host assignment, and frame counters.
Timestamps are normalized to UTC.

## UI Surfaces

- **Workload dashboard** – displays the summary counts so artists can quickly
  gauge render progress.
- **Operations overview** – adds a table listing the detailed job metadata,
  including per-job frame counts and timestamps.

When the integration is not configured, both panels render an inline alert with
instructions to supply Cuebot connection details.
