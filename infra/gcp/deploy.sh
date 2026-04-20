#!/usr/bin/env bash
# ============================================================
# GraphCeylon API — Deployment Script
# ============================================================
# Pulls latest images and restarts services with zero-downtime.
# Usage: bash deploy.sh [IMAGE_TAG]
# ============================================================

set -euo pipefail

APP_DIR="/opt/graphceylon"
COMPOSE_FILE="$APP_DIR/infra/docker-compose.prod.yaml"
ENV_FILE="$APP_DIR/.env"

# Load env vars for image references
set -a
source "$ENV_FILE"
set +a

# CLI argument overrides IMAGE_TAG from .env
if [ -n "${1:-}" ]; then
    export IMAGE_TAG="$1"
fi

# Optional: Only restore DB if RESTORE_DB=1 or --restore-db is passed
RESTORE_DB="${RESTORE_DB:-0}"
for arg in "$@"; do
    if [ "$arg" = "--restore-db" ]; then
        RESTORE_DB=1
    fi
done

echo "=== Deploying GraphCeylon API (tag: ${IMAGE_TAG:-latest}) ==="

# ---- 1. Sync data & models from GCS ----
echo ">>> Syncing assets from GCS..."
bash "$APP_DIR/infra/gcp/sync-assets.sh"

# ---- 2. Pull latest images ----
echo ">>> Pulling images..."
docker compose -f "$COMPOSE_FILE" pull --ignore-buildable

# ---- 3. Start/update services ----
echo ">>> Starting services..."
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

# ---- 3b. Restore Postgres backup if present ----
BACKUP_FILE="$APP_DIR/db-backup.sql"
POSTGRES_USER="${POSTGRES_USER:-graphceylon}"
POSTGRES_DB="${POSTGRES_DB:-graphceylon_users}"
if [ "$RESTORE_DB" = "1" ] && [ -f "$BACKUP_FILE" ]; then
    echo ">>> Restoring Postgres backup from $BACKUP_FILE ..."
    # Stop services that use the DB (optional, but safer)
    docker compose -f "$COMPOSE_FILE" stop user_service auth_service orchestrator kg_service language_service recommender_service || true

    # Drop and recreate the database from the 'postgres' database
    docker exec -i graphceylon-postgres psql -U "$POSTGRES_USER" -d postgres <<EOF
DROP DATABASE IF EXISTS "$POSTGRES_DB";
CREATE DATABASE "$POSTGRES_DB";
EOF

    # Restore the backup (using psql since it's a plain text .sql file)
    docker cp "$BACKUP_FILE" graphceylon-postgres:/db-backup.sql
    docker exec graphceylon-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /db-backup.sql
    echo ">>> Postgres restore complete."
else
    echo ">>> Skipping Postgres restore. Set RESTORE_DB=1 or pass --restore-db to enable."
fi

# ---- 4. Wait for services to be healthy ----
echo ">>> Waiting for all services to become healthy (timeout 120s)..."

SERVICES=(
    "orchestrator:8002"
    "auth_service:8004"
    "user_service:8005"
    "kg_service:8000"
    "language_service:8001"
    "recommender_service:8003"
)

FAILED=0
# 24 iterations * 5 seconds = 120 seconds max wait
for i in {1..24}; do
    ALL_UP=1
    FAILED_SERVICES=""
    for svc in "${SERVICES[@]}"; do
        NAME="${svc%%:*}"
        PORT="${svc##*:}"
        
        # Test health natively from the VM network (ports are exposed to localhost)
        # We do not use 'docker exec' because some containers (like Node/Alpine) don't have curl
        if ! curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1 && ! curl -sf "http://localhost:$PORT/" > /dev/null 2>&1; then
            ALL_UP=0
            FAILED_SERVICES="$FAILED_SERVICES $NAME"
        fi
    done
    
    if [ "$ALL_UP" = "1" ]; then
        break
    fi
    echo "  [${i}/24] Waiting for services to boot ($FAILED_SERVICES )..."
    sleep 5
done

echo ">>> Running Final health checks..."
FAILED=0
for svc in "${SERVICES[@]}"; do
    NAME="${svc%%:*}"
    PORT="${svc##*:}"
    if curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1 || curl -sf "http://localhost:$PORT/" > /dev/null 2>&1; then
        echo "  ✓ $NAME"
    else
        echo "  ✗ $NAME (unhealthy)"
        FAILED=$((FAILED + 1))
    fi
done

# ---- 5. Clean up old images and volumes ----
echo ">>> Pruning unused images and dangling volumes..."
docker image prune -f
docker volume prune -f

# ---- 6. Report ----
echo ""
if [ "$FAILED" -gt 0 ]; then
    echo "WARNING: $FAILED service(s) failed health checks after 120s."
    echo "Check logs: docker compose -f $COMPOSE_FILE logs <service_name>"
    exit 1
else
    echo "=== Deployment successful! All services healthy. ==="
fi
