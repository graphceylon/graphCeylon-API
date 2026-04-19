#!/usr/bin/env bash
# ============================================================
# GraphCeylon API — GCE VM Setup Script
# ============================================================
# Run this on a fresh Ubuntu 22.04+ GCE instance.
# Usage: sudo bash setup-vm.sh
# ============================================================

set -euo pipefail

echo "=== GraphCeylon API — VM Setup ==="

# ---- 1. System Updates ----
echo ">>> Updating system packages..."
apt-get update && apt-get upgrade -y

# ---- 2. Install Docker Engine ----
echo ">>> Installing Docker..."
apt-get install -y ca-certificates curl gnupg lsb-release

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# ---- 3. Create app user ----
echo ">>> Creating app user..."
if ! id "graphceylon" &>/dev/null; then
    useradd -m -s /bin/bash -G docker graphceylon
fi

# ---- 4. Create app directory ----
echo ">>> Setting up app directory..."
APP_DIR="/opt/graphceylon"
mkdir -p "$APP_DIR"/{data,models,logs}
chown -R graphceylon:graphceylon "$APP_DIR"

# ---- 5. Install Google Cloud Ops Agent (monitoring + logging) ----
echo ">>> Installing Google Cloud Ops Agent..."
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
bash add-google-cloud-ops-agent-repo.sh --also-install
rm -f add-google-cloud-ops-agent-repo.sh

# ---- 6. Configure Docker logging to Google Cloud Logging ----
echo ">>> Configuring Docker logging driver..."
cat > /etc/docker/daemon.json <<'DAEMON_JSON'
{
  "log-driver": "gcplogs",
  "log-opts": {
    "gcp-meta-name": "graphceylon-api"
  },
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 65536,
      "Soft": 65536
    }
  }
}
DAEMON_JSON

systemctl restart docker

# ---- 7. Install Certbot for SSL ----
echo ">>> Installing Certbot..."
apt-get install -y certbot

# ---- 8. Authenticate to Artifact Registry ----
echo ">>> Configuring Docker auth for Artifact Registry..."
apt-get install -y google-cloud-cli
# The VM's service account handles auth automatically
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet 2>/dev/null || true

# ---- 9. Set up firewall reminder ----
echo ""
echo "============================================================"
echo "VM setup complete!"
echo ""
echo "NEXT STEPS:"
echo "  1. Set up GCP firewall rules:"
echo "     gcloud compute firewall-rules create graphceylon-http \\"
echo "       --allow tcp:80,tcp:443 --target-tags=graphceylon-api"
echo ""
echo "     gcloud compute firewall-rules create graphceylon-ssh \\"
echo "       --allow tcp:22 --source-ranges=YOUR_IP/32 --target-tags=graphceylon-api"
echo ""
echo "  2. Copy .env.production to $APP_DIR/.env"
echo "  3. Clone the repo or copy data/models to $APP_DIR/"
echo "  4. Run: cd $APP_DIR && bash deploy.sh"
echo "============================================================"
