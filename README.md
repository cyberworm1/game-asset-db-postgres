# Game Asset Management Database (Postgres)

This repository provides a PostgreSQL-based database and service stack for managing game assets in a media/entertainment IT environment. It's tailored for games industry workflows across multi-project studios with 15-50 users, supporting asset metadata storage, binary depot management, versioning, hierarchical access, and immutable archiving to facilitate title releases. Use this to demonstrate expertise in database administration, schema design, service orchestration, and performance optimization.

## Features
- **Schema Design**: Tables for projects, assets, versions, users, permissions, tags, branches, shelves, workspaces, locks, and review workflows.
- **Security**: Session-aware row-level security (RLS) policies with helper functions so every request is enforced in-database.
- **Binary Depot Service**: A FastAPI-powered application server that exposes REST APIs, file upload endpoints, and a lightweight web review dashboard backed by a persistent storage volume.
- **Branching & Workspaces**: Branch, workspace, shelf, and asset locking semantics inspired by Helix stream/workspace flows.
- **Admin & Branch APIs**: FastAPI endpoints now cover project provisioning, branch/shelf management, and permission administration so Helix-equivalent concepts live beyond raw SQL tables.
- **Storage Planning**: Project storage snapshots to plan for the default 10TB allocation with room to scale.
- **Operations**: Docker Compose adds scheduled backups, pgAdmin for administration, and scripts for replication & disaster recovery runbooks.
- **Tuning**: Guide for performance in high-load scenarios (e.g., during asset uploads for game builds).
- **Sample Data**: Pre-populated with demo assets, branches, workspaces, and locks for testing.

## Prerequisites
- Docker and Docker Compose installed.
- PostgreSQL client (e.g., psql) for querying.

## Setup Instructions
1. Clone the repo: `git clone https://github.com/yourusername/game-asset-db-postgres.git`
2. Navigate to the directory: `cd game-asset-db-postgres`
3. Start the stack (database, depot API, pgAdmin, backup service): `docker-compose up -d`
4. Connect to the DB: `psql -h localhost -U postgres -d asset_db` (password: `password`)
5. Init schema & policies: The `init-db` scripts are automatically run via Docker volume mounting (including RLS policy creation).
6. Insert sample data: Run `psql -h localhost -U postgres -d asset_db -f init-db/04-sample-data.sql` if you want to re-seed data.
7. Visit the depot API docs: http://localhost:8000/docs. The `/reviews` route renders the collaboration dashboard.

## Schema Overview
- **projects**: Studio projects with status tracking, storage allocation (10TB default), and immutable archive logging.
- **project_members**: Associates users with projects using hierarchical roles (owner → manager → lead → contributor → reviewer → viewer).
- **project_storage_snapshots**: Records asset counts and storage consumption to inform scaling.
- **assets**: Core table for asset metadata scoped to projects (id: UUID, name, type, metadata: JSONB).
- **asset_versions**: Tracks versions with branch affinity, depot file paths, and timestamps.
- **branches**: Project streams to model mainline/integration flows with hierarchical parents.
- **workspaces**: Per-user sandboxes that reference branches for Helix-style work semantics.
- **asset_locks**: Provides binary asset locking to prevent concurrent edits.
- **shelves**: Store shelved changes pending submission/review.
- **workspace_activity**: Timeline of sync/publish events for collaboration insights.
- **asset_reviews**: Workflow table capturing review states per asset version.
- **users**: User accounts with studio-level roles (admin, editor, viewer).
- **permissions**: Maps users to projects/assets with read/write/delete flags while honoring project hierarchy.
- **tags**: Many-to-many for categorizing assets (e.g., "texture", "model").
- **audit_log**: Trigger-populated for changes.
- **project_archive_log**: Immutable record of archived project summaries for compliance.

## Usage
### Database Access with RLS
- Set the current user for a session to respect RLS: `SELECT set_app_user('<user-uuid>');`
- Query assets for a project: `SELECT id, name, metadata FROM assets WHERE project_id = '<project-uuid>';`
- Reset at the end of the transaction: `SELECT set_config('app.current_user_id', '', true);`

### Depot API Highlights
- Request token: `curl -X POST http://localhost:8000/auth/token -d '{"username":"admin_user","password":"admin123"}' -H 'Content-Type: application/json'`
- Upload new version: `curl -X POST "http://localhost:8000/assets/<asset_uuid>/versions/upload" -H "Authorization: Bearer <token>" -F "version_number=2" -F "file=@hero_texture.png"`
- View review UI: open http://localhost:8000/reviews after authenticating via an Authorization header or using the Swagger UI "Authorize" button.

### SQL Examples
- Add asset: `INSERT INTO assets (name, type, metadata, project_id, created_by) VALUES ('hero_model', '3D', '{"size": 1024, "format": "obj"}', '<project-uuid>', '<user-uuid>');`
- Capture storage telemetry: `INSERT INTO project_storage_snapshots (project_id, asset_count, total_bytes) VALUES ('<project-uuid>', 1500, 7340032000);`
- Archive a project: `UPDATE projects SET status = 'archived', archived_by = '<user-uuid>' WHERE id = '<project-uuid>';`

## Configuration
Copy `configs/postgresql.conf` and `pg_hba.conf` to your Postgres data dir for production tuning (e.g., increase work_mem).

## Backup and Restore
- Point-in-time aware backups: the `pgbackups` service performs nightly dumps in `./backups` (configurable via environment variables in `docker-compose.yml`).
- Manual backup: `./scripts/backup.sh`
- Restore: `./scripts/restore.sh <backup_file>`
- Replication & failover: see `docs/operations.md` and `scripts/create-replica.sh` for a pg_basebackup-driven replica bootstrap example.

See `docs/performance-tuning.md` for optimization tips and `docs/operations.md` for operational procedures.

## Contributing
Fork and PR improvements, e.g., adding ORM integration.

## License
MIT
