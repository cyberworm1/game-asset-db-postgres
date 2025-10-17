# Game Asset Management Database (Postgres)

This repository provides a PostgreSQL-based database setup for managing game assets in a media/entertainment IT environment. It's tailored for games industry workflows across multi-project studios with 15-50 users, supporting asset metadata storage, versioning, hierarchical access, and immutable archiving to facilitate title releases. Use this to demonstrate expertise in database administration, schema design, and performance optimization.

## Features
- **Schema Design**: Tables for projects, assets, versions, users, permissions, tags, and review workflows.
- **Security**: Role hierarchies with project membership, row-level security (RLS), and triggers for auditing.
- **Storage Planning**: Project storage snapshots to plan for the default 10TB allocation with room to scale.
- **Setup**: Docker Compose for quick local deployment.
- **Operations**: Backup/restore scripts.
- **Tuning**: Guide for performance in high-load scenarios (e.g., during asset uploads for game builds).
- **Sample Data**: Pre-populated with demo assets for testing.

## Prerequisites
- Docker and Docker Compose installed.
- PostgreSQL client (e.g., psql) for querying.

## Setup Instructions
1. Clone the repo: `git clone https://github.com/yourusername/game-asset-db-postgres.git`
2. Navigate to the directory: `cd game-asset-db-postgres`
3. Start the database: `docker-compose up -d`
4. Connect to the DB: `psql -h localhost -U postgres -d asset_db` (password: `password`)
5. Init schema: The `init-db` scripts are automatically run via Docker volume mounting.
6. Insert sample data: Run `psql -h localhost -U postgres -d asset_db -f init-db/04-sample-data.sql` if needed.

## Schema Overview
- **projects**: Studio projects with status tracking, storage allocation (10TB default), and immutable archive logging.
- **project_members**: Associates users with projects using hierarchical roles (owner → manager → lead → contributor → reviewer → viewer).
- **project_storage_snapshots**: Records asset counts and storage consumption to inform scaling.
- **assets**: Core table for asset metadata scoped to projects (id: UUID, name, type, metadata: JSONB).
- **asset_versions**: Tracks versions with file paths (e.g., S3 links) and timestamps; automatically created via triggers.
- **asset_reviews**: Workflow table capturing review states per asset version.
- **users**: User accounts with studio-level roles (admin, editor, viewer).
- **permissions**: Maps users to projects/assets with read/write/delete flags while honoring project hierarchy.
- **tags**: Many-to-many for categorizing assets (e.g., "texture", "model").
- **audit_log**: Trigger-populated for changes.
- **project_archive_log**: Immutable record of archived project summaries for compliance.

## Usage
- Query assets: `SELECT * FROM assets WHERE tags @> ARRAY['texture'];`
- Add asset: `INSERT INTO assets (name, type, metadata, project_id) VALUES ('hero_model', '3D', '{"size": 1024, "format": "obj"}', '<project-uuid>');`
- Capture storage telemetry: `INSERT INTO project_storage_snapshots (project_id, asset_count, total_bytes) VALUES ('<project-uuid>', 1500, 7340032000);`
- Archive a project: `UPDATE projects SET status = 'archived', archived_by = '<user-uuid>' WHERE id = '<project-uuid>';`
- For integration in game releases: Use this DB in CI/CD to validate asset versions before builds.

## Configuration
Copy `configs/postgresql.conf` and `pg_hba.conf` to your Postgres data dir for production tuning (e.g., increase work_mem).

## Backup and Restore
- Backup: `./scripts/backup.sh`
- Restore: `./scripts/restore.sh <backup_file>`

See `docs/performance-tuning.md` for optimization tips.

## Contributing
Fork and PR improvements, e.g., adding ORM integration.

## License
MIT
