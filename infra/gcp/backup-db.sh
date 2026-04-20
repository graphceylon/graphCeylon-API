#!/usr/bin/env bash
# ============================================================
# Backup all databases (Postgres, Neo4j, Redis) to GCS
# Usage: bash backup-db.sh
# ============================================================

set -euo pipefail

APP_DIR="/opt/graphceylon"
ENV_FILE="$APP_DIR/.env"
BACKUP_DIR="$APP_DIR/backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Load GCP_PROJECT_ID from env
GCP_PROJECT_ID=$(grep -E '^GCP_PROJECT_ID=' "$ENV_FILE" | cut -d= -f2)
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "ERROR: GCP_PROJECT_ID not set in $ENV_FILE"
    exit 1
fi
BUCKET="gs://${GCP_PROJECT_ID}-graphceylon-backups"

# Postgres
PG_CONTAINER="graphceylon-postgres"
echo "Backing up Postgres..."
docker exec $PG_CONTAINER pg_dumpall -U postgres > "$BACKUP_DIR/postgres.sql"

# Neo4j
NEO4J_CONTAINER="graphceylon-neo4j"
echo "Backing up Neo4j..."
docker exec $NEO4J_CONTAINER tar czf - /data > "$BACKUP_DIR/neo4j-data.tar.gz"

# Redis
REDIS_CONTAINER="graphceylon-redis"
echo "Backing up Redis..."
docker exec $REDIS_CONTAINER sh -c 'redis-cli save && cat /data/dump.rdb' > "$BACKUP_DIR/redis-dump.rdb"

# Upload to GCS
echo "Uploading backups to $BUCKET ..."
gsutil -m cp -r "$BACKUP_DIR" "$BUCKET/"

echo "Backup complete: $BACKUP_DIR"
