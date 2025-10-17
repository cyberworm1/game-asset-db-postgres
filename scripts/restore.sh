#!/bin/bash
# Restore Script for Postgres Asset DB
# Author: [Your Name]
# Description: Restores from a backup file. Usage: ./restore.sh <backup_file>

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

DB_NAME="asset_db"
DB_USER="postgres"
DB_HOST="localhost"
BACKUP_FILE=$1

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Backup file $BACKUP_FILE does not exist"
    exit 1
fi

PGPASSWORD=${PGPASSWORD:-password} pg_restore -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -v "$BACKUP_FILE"

echo "Restore completed from $BACKUP_FILE"
