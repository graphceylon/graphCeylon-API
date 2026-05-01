#!/usr/bin/env bash
# ============================================================
# Upload data & models to Google Cloud Storage
# ============================================================
# Run from your LOCAL machine (where the files exist).
# Usage: bash upload-assets.sh <GCP_PROJECT_ID>
#
# Prerequisites:
#   gcloud auth login
#   gsutil available (comes with gcloud CLI)
# ============================================================

set -euo pipefail

PROJECT_ID="${1:?Usage: bash upload-assets.sh <GCP_PROJECT_ID>}"
BUCKET="gs://${PROJECT_ID}-graphceylon-assets"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "=== Uploading GraphCeylon assets to ${BUCKET} ==="

# ---- 1. Create bucket if it doesn't exist ----
if ! gsutil ls "$BUCKET" &>/dev/null; then
    echo ">>> Creating bucket ${BUCKET} (asia-south1, Standard)..."
    gsutil mb -l us-central1 -c standard "$BUCKET"
    # Enable versioning for rollback safety
    gsutil versioning set on "$BUCKET"
fi

# ---- 2. Upload KG service data (tourism JSONs for Neo4j import) ----
echo ">>> Uploading data/kg_service/data/ ..."
gsutil -m rsync -r -d \
    "${REPO_ROOT}/data/kg_service/data/" \
    "${BUCKET}/data/kg_service/data/"

# ---- 3. Upload recommender service clean data (CSVs) ----
echo ">>> Uploading data/recommender_service/clean/ ..."
gsutil -m rsync -r -d \
    "${REPO_ROOT}/data/recommender_service/clean/" \
    "${BUCKET}/data/recommender_service/clean/"

# ---- 4. Upload orchestrator models ----
echo ">>> Uploading models/orchestrator/intent_multilabel_final_v5/ ..."
gsutil -m rsync -r -d \
    "${REPO_ROOT}/models/orchestrator/intent_multilabel_final_v5/" \
    "${BUCKET}/models/orchestrator/intent_multilabel_final_v5/"

echo ">>> Uploading models/orchestrator/NLI/ ..."
gsutil -m rsync -r -d \
    "${REPO_ROOT}/models/orchestrator/NLI/" \
    "${BUCKET}/models/orchestrator/NLI/"

# ---- 5. Upload KG service local data & checkpoints ----
echo ">>> Uploading services/kg_service/data/ ..."
gsutil -m rsync -r -d \
    "${REPO_ROOT}/services/kg_service/data/" \
    "${BUCKET}/services/kg_service/data/"

echo ">>> Uploading services/kg_service/checkpoints/ ..."
gsutil -m rsync -r -d \
    "${REPO_ROOT}/services/kg_service/checkpoints/" \
    "${BUCKET}/services/kg_service/checkpoints/"

# ---- 6. Upload language service Sinhala TTS model ----
echo ">>> Uploading models/language_service/sinhala_tts/ ..."
gsutil -m rsync -r -d \
    "${REPO_ROOT}/services/language_service/models/sinhala_tts/" \
    "${BUCKET}/models/language_service/sinhala_tts/"

echo ""
echo "=== Upload complete! ==="
echo "Bucket: ${BUCKET}"
gsutil du -sh "$BUCKET"
