#!/bin/bash
# =============================================================================
# Deploy IAMS FFmpeg Relay on Raspberry Pi
#
# Replaces the old Python/MediaPipe edge service with a pure FFmpeg relay.
# The RPi just copies the Reolink RTSP stream to the VPS mediamtx — no
# face detection, no Python, minimal CPU/memory.
#
# Run from your MacBook:
#   bash edge/scripts/deploy-relay.sh
# =============================================================================

set -euo pipefail

RPI_HOST="pi@192.168.1.19"
RPI_PASS='@Iams2026THESIS!'
PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# Camera: Reolink main stream (1080p+, more keyframes, better for distant faces)
CAMERA_RTSP_URL="rtsp://admin:Iams2026THESIS@192.168.1.100:554/h264Preview_01_main"

# VPS mediamtx RTSP ingest
VPS_RTSP_URL="rtsp://167.71.217.44:8554"

# Room ID (must match the schedule's room in the database)
ROOM_ID="36168673-34de-4c64-8ace-c6b72cbaba3f"

echo "=========================================="
echo "  IAMS Relay Deploy → RPi"
echo "=========================================="

# Step 1: Stop old edge service (if running)
echo "[1/5] Stopping old iams-edge service..."
sshpass -p "${RPI_PASS}" ssh -o StrictHostKeyChecking=no "${RPI_HOST}" \
    "sudo systemctl stop iams-edge 2>/dev/null || true; \
     sudo systemctl disable iams-edge 2>/dev/null || true" \
    2>/dev/null || true

# Step 2: Ensure FFmpeg is installed
echo "[2/5] Ensuring FFmpeg is installed..."
sshpass -p "${RPI_PASS}" ssh -o StrictHostKeyChecking=no "${RPI_HOST}" \
    "which ffmpeg >/dev/null 2>&1 || sudo apt-get install -y ffmpeg"

# Step 3: Create environment file
echo "[3/5] Creating relay environment file..."
sshpass -p "${RPI_PASS}" ssh -o StrictHostKeyChecking=no "${RPI_HOST}" \
    "cat > /home/pi/iams-relay.env << 'EOF'
CAMERA_RTSP_URL=${CAMERA_RTSP_URL}
VPS_RTSP_URL=${VPS_RTSP_URL}
ROOM_ID=${ROOM_ID}
EOF"

# Step 4: Deploy systemd service
echo "[4/5] Installing systemd service..."
sshpass -p "${RPI_PASS}" scp -o StrictHostKeyChecking=no \
    "${PROJECT_DIR}/edge/iams-relay.service" \
    "${RPI_HOST}:/tmp/iams-relay.service"

sshpass -p "${RPI_PASS}" ssh -o StrictHostKeyChecking=no "${RPI_HOST}" \
    "sudo cp /tmp/iams-relay.service /etc/systemd/system/iams-relay.service && \
     sudo systemctl daemon-reload && \
     sudo systemctl enable iams-relay && \
     sudo systemctl restart iams-relay"

# Step 5: Verify
echo "[5/5] Verifying relay..."
sleep 3
sshpass -p "${RPI_PASS}" ssh -o StrictHostKeyChecking=no "${RPI_HOST}" \
    "systemctl is-active iams-relay && echo 'Relay is running!' || echo 'WARNING: Relay failed to start'; \
     echo ''; \
     echo '--- Last 10 log lines ---'; \
     tail -10 /home/pi/iams-relay.log 2>/dev/null || echo 'No logs yet'"

echo ""
echo "=========================================="
echo "  Relay deployed!"
echo "  Stream: ${CAMERA_RTSP_URL}"
echo "     → ${VPS_RTSP_URL}/${ROOM_ID}"
echo "=========================================="
