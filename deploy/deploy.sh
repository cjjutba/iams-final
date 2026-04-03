#!/bin/bash
# =============================================================================
# IAMS Deploy Script
# Run from your MacBook to deploy/update the backend on the VPS
# Usage: ./deploy/deploy.sh
# =============================================================================

set -euo pipefail

VPS_IP="167.71.217.44"
VPS_USER="root"
VPS_DIR="/opt/iams"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=========================================="
echo "  IAMS Deploy → ${VPS_IP}"
echo "=========================================="

# Step 1: Sync backend code to VPS
echo "[1/4] Syncing backend code to VPS..."
rsync -avz --delete \
    --exclude 'venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.pytest_cache/' \
    --exclude 'data/faiss/' \
    --exclude 'data/uploads/' \
    --exclude 'data/hls/' \
    --exclude 'data/.models/' \
    --exclude 'logs/' \
    --exclude 'bin/ffmpeg.exe' \
    --exclude 'bin/mediamtx' \
    --exclude 'test.db' \
    --exclude 'nul' \
    --exclude '.env' \
    --exclude '.env.production' \
    "${PROJECT_DIR}/backend/" "${VPS_USER}@${VPS_IP}:${VPS_DIR}/backend/"

# Step 1b: Sync database init scripts
echo "[1b/5] Syncing database init scripts..."
rsync -avz \
    "${PROJECT_DIR}/backend/db/" "${VPS_USER}@${VPS_IP}:${VPS_DIR}/backend/db/"

# Step 2: Sync admin dashboard code to VPS
echo "[2/5] Syncing admin dashboard code to VPS..."
rsync -avz --delete \
    --exclude 'node_modules/' \
    --exclude 'dist/' \
    --exclude '.env.local' \
    --exclude '.env.development' \
    "${PROJECT_DIR}/admin/" "${VPS_USER}@${VPS_IP}:${VPS_DIR}/admin/"

# Step 3: Sync deploy configs
echo "[3/5] Syncing deploy configs..."
rsync -avz \
    "${PROJECT_DIR}/deploy/docker-compose.prod.yml" \
    "${PROJECT_DIR}/deploy/nginx.conf" \
    "${PROJECT_DIR}/deploy/mediamtx.yml" \
    "${VPS_USER}@${VPS_IP}:${VPS_DIR}/deploy/"

# Step 4: Build and restart on VPS
echo "[4/5] Building and starting containers on VPS..."
ssh "${VPS_USER}@${VPS_IP}" << 'REMOTE'
    cd /opt/iams/deploy

    # Open ports for mediamtx + coturn (if not already open)
    echo "Checking firewall rules..."
    ufw allow 8554/tcp comment "mediamtx RTSP ingest from RPi" 2>/dev/null || true
    ufw allow 8887/udp comment "mediamtx WebRTC media" 2>/dev/null || true
    ufw allow 3478/tcp comment "coturn TURN listening" 2>/dev/null || true
    ufw allow 3478/udp comment "coturn TURN listening" 2>/dev/null || true
    ufw allow 49152:49252/udp comment "coturn TURN relay range" 2>/dev/null || true
    ufw allow 9999/tcp comment "Dozzle log viewer" 2>/dev/null || true

    # Build and rolling restart (zero-downtime)
    echo "Building and restarting containers..."
    docker compose -f docker-compose.prod.yml up -d --build

    # Wait for health check
    echo "Waiting for backend to be healthy..."
    for i in $(seq 1 30); do
        if docker compose -f docker-compose.prod.yml ps | grep -q "healthy"; then
            echo "Backend is healthy!"
            break
        fi
        echo "  Waiting... ($i/30)"
        sleep 5
    done

    # Show status
    echo ""
    docker compose -f docker-compose.prod.yml ps
REMOTE

# Step 5: Verify
echo ""
echo "[5/5] Verifying deployment..."
sleep 3
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "http://${VPS_IP}/api/v1/health" || echo "000")

if [ "$HEALTH" = "200" ]; then
    echo ""
    echo "=========================================="
    echo "  Deployment successful!"
    echo "=========================================="
    echo ""
    echo "  Admin:   http://${VPS_IP}/admin"
    echo "  API:     http://${VPS_IP}/api/v1"
    echo "  Docs:    http://${VPS_IP}/api/v1/docs"
    echo "  Health:  http://${VPS_IP}/api/v1/health"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "  WARNING: Health check returned ${HEALTH}"
    echo "  Check logs: ssh root@${VPS_IP} 'cd /opt/iams/deploy && docker compose -f docker-compose.prod.yml logs backend'"
    echo "=========================================="
fi
