# Game Asset Management Database (Postgres)

This repository provides a PostgreSQL-based database setup for managing game assets in a media/entertainment IT environment. It's tailored for games industry workflows, supporting asset metadata storage, versioning, and access controls to facilitate title releases. Use this to demonstrate expertise in database administration, schema design, and performance optimization.

## Features
- **Schema Design**: Tables for assets, versions, users, permissions, and tags.
- **Security**: Row-level security (RLS) and triggers for auditing.
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
- **assets**: Core table for asset metadata (id: UUID, name, type, metadata: JSONB).
- **asset_versions**: Tracks versions with file paths (e.g., S3 links) and timestamps.
- **users**: User accounts with roles (admin, editor, viewer).
- **permissions**: Maps users to assets with read/write/delete flags.
- **tags**: Many-to-many for categorizing assets (e.g., "texture", "model").
- **audit_log**: Trigger-populated for changes.

## Usage
- Query assets: `SELECT * FROM assets WHERE tags @> ARRAY['texture'];`
- Add asset: `INSERT INTO assets (name, type, metadata) VALUES ('hero_model', '3D', '{"size": 1024, "format": "obj"}');`
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
