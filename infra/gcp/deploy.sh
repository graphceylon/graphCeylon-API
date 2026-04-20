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

echo "=== Deploying GraphCeylon API (tag: ${IMAGE_TAG:-latest}) ==="

# ---- 1. Sync data & models from GCS ----
echo ">>> Syncing assets from GCS..."
bash "$APP_DIR/infra/gcp/sync-assets.sh"

# ---- 2. Pull latest images ----
echo ">>> Pulling images..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull --ignore-buildable


# ---- 3. Start/update services ----
echo ">>> Starting services..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --remove-orphans

# ---- 3b. Restore Postgres backup if present ----
BACKUP_FILE="$APP_DIR/db-backup.sql"
POSTGRES_USER="${POSTGRES_USER:-graphceylon}"
if [ -f "$BACKUP_FILE" ]; then
    echo ">>> Restoring Postgres backup from $BACKUP_FILE ..."
    docker cp "$BACKUP_FILE" graphceylon-postgres:/db-backup.sql
    docker exec graphceylon-postgres psql -U "$POSTGRES_USER" -f /db-backup.sql
    echo ">>> Postgres restore complete."
fi

# ---- 4. Wait for services to be healthy ----
echo ">>> Waiting for services to start..."
sleep 15

# ---- 5. Health checks ----
echo ">>> Running health checks..."

SERVICES=(
    "orchestrator:8002"
    "auth_service:8004"
    "user_service:8005"
    "kg_service:8000"
    "language_service:8001"
    "recommender_service:8003"
)

FAILED=0
for svc in "${SERVICES[@]}"; do
    NAME="${svc%%:*}"
    PORT="${svc##*:}"
    # Use docker exec to check health from inside the network
    if docker exec "graphceylon-$NAME" curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1 || \
       docker exec "graphceylon-$NAME" curl -sf "http://localhost:$PORT/" > /dev/null 2>&1; then
        echo "  ✓ $NAME"
    else
        echo "  ✗ $NAME (unhealthy)"
        FAILED=$((FAILED + 1))
    fi
done

# ---- 6. Clean up old images and volumes ----
echo ">>> Pruning unused images and dangling volumes..."
docker image prune -f
docker volume prune -f

# ---- 7. Report ----
echo ""
if [ "$FAILED" -gt 0 ]; then
    echo "WARNING: $FAILED service(s) failed health checks."
    echo "Check logs: docker compose -f $COMPOSE_FILE logs <service_name>"
    exit 1
else
    echo "=== Deployment successful! All services healthy. ==="
fi
