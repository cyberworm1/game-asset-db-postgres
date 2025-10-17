#!/bin/bash
# Backup Script for Postgres Asset DB
# Author: [Your Name]
# Description: Dumps the database to a timestamped file. Run periodically via cron for data protection in production.

set -euo pipefail

DB_NAME="asset_db"
DB_USER="postgres"
DB_HOST="localhost"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

mkdir -p "$BACKUP_DIR"

PGPASSWORD=${PGPASSWORD:-password} pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -F c -b -v -f "$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.backup"

echo "Backup created: ${DB_NAME}_${TIMESTAMP}.backup"
