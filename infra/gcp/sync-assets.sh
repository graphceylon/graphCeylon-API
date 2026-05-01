#!/usr/bin/env bash
# ============================================================
# Download data & models from GCS to the VM
# ============================================================
# Run on the GCE VM before starting services.
# Usage: bash sync-assets.sh
#
# Reads GCP_PROJECT_ID from /opt/graphceylon/.env
# ============================================================

set -euo pipefail

APP_DIR="/opt/graphceylon"
ENV_FILE="$APP_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found."
    exit 1
fi

# Load GCP_PROJECT_ID from env
GCP_PROJECT_ID=$(grep -E '^GCP_PROJECT_ID=' "$ENV_FILE" | cut -d= -f2)
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "ERROR: GCP_PROJECT_ID not set in $ENV_FILE"
    exit 1
fi

BUCKET="gs://${GCP_PROJECT_ID}-graphceylon-assets"

echo "=== Syncing assets from ${BUCKET} ==="

# ---- 1. KG service data (for Neo4j import volume) ----
echo ">>> Syncing data/kg_service/data/ ..."
mkdir -p "$APP_DIR/data/kg_service/data"
gsutil -m rsync -c -r \
    "${BUCKET}/data/kg_service/data/" \
    "$APP_DIR/data/kg_service/data/"

# ---- 2. Recommender service clean data ----
echo ">>> Syncing data/recommender_service/clean/ ..."
mkdir -p "$APP_DIR/data/recommender_service/clean"
gsutil -m rsync -c -r \
    "${BUCKET}/data/recommender_service/clean/" \
    "$APP_DIR/data/recommender_service/clean/"

# ---- 3. Orchestrator ML models ----
echo ">>> Syncing models/orchestrator/intent_multilabel_final_v5/ ..."
mkdir -p "$APP_DIR/models/orchestrator/intent_multilabel_final_v5"
gsutil -m rsync -c -r \
    "${BUCKET}/models/orchestrator/intent_multilabel_final_v5/" \
    "$APP_DIR/models/orchestrator/intent_multilabel_final_v5/"

echo ">>> Syncing models/orchestrator/NLI/ ..."
mkdir -p "$APP_DIR/models/orchestrator/NLI"
gsutil -m rsync -c -r \
    "${BUCKET}/models/orchestrator/NLI/" \
    "$APP_DIR/models/orchestrator/NLI/"

# ---- 4. KG service data & checkpoints ----
echo ">>> Syncing services/kg_service/data/ ..."
mkdir -p "$APP_DIR/services/kg_service/data"
gsutil -m rsync -c -r \
    "${BUCKET}/services/kg_service/data/" \
    "$APP_DIR/services/kg_service/data/"

echo ">>> Syncing services/kg_service/checkpoints/ ..."
mkdir -p "$APP_DIR/services/kg_service/checkpoints"
gsutil -m rsync -c -r \
    "${BUCKET}/services/kg_service/checkpoints/" \
    "$APP_DIR/services/kg_service/checkpoints/"

echo ""
echo "=== Asset sync complete! ==="

# ---- Fix permissions so container app users can read all synced files ----
echo ">>> Fixing file permissions on synced assets..."
chmod -R a+rX "$APP_DIR"
echo ">>> Permissions fixed."

