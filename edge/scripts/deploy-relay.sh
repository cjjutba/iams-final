#!/bin/bash
# =============================================================================
# Deploy IAMS FFmpeg Relay on Raspberry Pi
#
# Supports two relay modes:
#   - copy:      Passthrough (no transcoding). For cameras with clean H.264
#                output like the Reolink P340.
#   - transcode: Re-encode to normalized H.264 Baseline on the RPi. For cameras
#                with problematic output like the Reolink CX810.
#
# Usage:
#   bash edge/scripts/deploy-relay.sh eb226    # P340 — copy mode
#   bash edge/scripts/deploy-relay.sh eb227    # CX810 — transcode mode
# =============================================================================

set -euo pipefail

ROOM="${1:-}"
PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# VPS mediamtx RTSP ingest
VPS_RTSP_URL="rtsp://167.71.217.44:8554"

# Hardware-to-room mapping is INVERTED at the camera level. Camera IP
# 192.168.88.10 is physically mounted in EB227 (the Reolink P340), and
# 192.168.88.11 is physically in EB226 (the Reolink CX810). Each RPi sits
# next to the camera/room it serves, so:
#
#   iams-eb226  (192.168.88.12, in EB226) → pulls from 192.168.88.11 (CX810)
#   iams-eb227  (192.168.88.15, in EB227) → pulls from 192.168.88.10 (P340)
#
# Stream keys (eb226, eb227) stay aligned with rooms.stream_key in the DB,
# which the faculty app uses to build its WHEP URL. So the room → camera-IP
# mapping below is intentionally inverted from a naive name match. The Mac's
# scripts/iams-cam-relay.sh handles the same inversion in its CAMERAS array
# — the two must stay in lockstep, otherwise admin (Mac) and faculty (VPS)
# show different cameras for the same schedule.

# SSH/SCP options shared by every call. Two non-obvious flags:
#   - StrictHostKeyChecking=no + UserKnownHostsFile=/dev/null    accept new
#     keys without prompting and without polluting ~/.ssh/known_hosts (RPi
#     reflashes change host keys; we don't want a stale entry to wedge the
#     next deploy with "REMOTE HOST IDENTIFICATION HAS CHANGED").
#   - PubkeyAuthentication=no                                     force
#     password auth so sshpass actually works on machines that have other
#     RPi keys cached.
SSH_OPTS=(
    -o StrictHostKeyChecking=no
    -o UserKnownHostsFile=/dev/null
    -o PubkeyAuthentication=no
    -o LogLevel=ERROR
    -o ConnectTimeout=10
)

# ---- Per-room configuration ----
case "${ROOM}" in
    eb226)
        RPI_USER="iams-eb226"
        RPI_HOST="${RPI_USER}@192.168.88.12"
        RPI_PASS='123'
        # Reolink CX810 (the camera physically mounted in EB226).
        # Main stream (2304x1296) has severe RTSP sequence errors that crash
        # both transcode and copy modes. The sub stream (640x360, 15fps) is
        # stable and well within the RPi's WiFi upload budget (~0.9 Mbps) for
        # the LAN-to-VPS push.
        CAMERA_RTSP_URL="rtsp://admin:%40Iams2026THESIS%21@192.168.88.11:554/h264Preview_01_sub"
        ROOM_ID="eb226"
        RELAY_MODE="copy"
        ;;
    eb227)
        RPI_USER="iams-eb227"
        RPI_HOST="${RPI_USER}@192.168.88.15"
        RPI_PASS='123'
        # Reolink P340 (the camera physically mounted in EB227).
        # Sub stream (896x512, ~25fps) — main stream (2304x1296) exceeds the
        # WiFi upload bandwidth and causes constant publisher reconnects.
        CAMERA_RTSP_URL="rtsp://admin:%40Iams2026THESIS%21@192.168.88.10:554/h264Preview_01_sub"
        ROOM_ID="eb227"
        RELAY_MODE="copy"
        ;;
    *)
        echo "Usage: $0 <eb226|eb227>"
        echo ""
        echo "  eb226  — Reolink P340 (copy mode, no transcode)"
        echo "  eb227  — Reolink CX810 (transcode mode, re-encode on RPi)"
        exit 1
        ;;
esac

# Derive home directory from username
RPI_HOME="/home/${RPI_USER}"

echo "=========================================="
echo "  IAMS Relay Deploy → RPi (${ROOM})"
echo "  Mode: ${RELAY_MODE}"
echo "=========================================="

# sudo on Raspberry Pi OS prompts for the user's password by default. The RPi
# accounts in this fleet share the same login password as the SSH password, so
# we feed it via `sudo -S` (read from stdin) rather than requiring a NOPASSWD
# sudoers entry per host. Defined as a string so it can be embedded into the
# heredoc'd remote commands below.
SUDO="echo '${RPI_PASS}' | sudo -S"

# Step 1: Stop old services
echo "[1/6] Stopping old services..."
sshpass -p "${RPI_PASS}" ssh "${SSH_OPTS[@]}" "${RPI_HOST}" \
    "${SUDO} systemctl stop iams-relay 2>/dev/null || true; \
     ${SUDO} systemctl stop iams-edge 2>/dev/null || true; \
     ${SUDO} systemctl disable iams-edge 2>/dev/null || true" \
    2>/dev/null || true

# Step 2: Ensure FFmpeg is installed
echo "[2/6] Ensuring FFmpeg is installed..."
sshpass -p "${RPI_PASS}" ssh "${SSH_OPTS[@]}" "${RPI_HOST}" \
    "which ffmpeg >/dev/null 2>&1 || ${SUDO} apt-get install -y ffmpeg"

# Step 3: Create environment file
echo "[3/6] Creating relay environment file..."
ENV_CONTENT="CAMERA_RTSP_URL=${CAMERA_RTSP_URL}
VPS_RTSP_URL=${VPS_RTSP_URL}
ROOM_ID=${ROOM_ID}
RELAY_MODE=${RELAY_MODE}"

if [ "${RELAY_MODE}" = "transcode" ]; then
    ENV_CONTENT="${ENV_CONTENT}
TRANSCODE_RESOLUTION=${TRANSCODE_RESOLUTION}
TRANSCODE_BITRATE=${TRANSCODE_BITRATE}
TRANSCODE_MAX_BITRATE=${TRANSCODE_MAX_BITRATE}
TRANSCODE_FPS=${TRANSCODE_FPS}"
fi

sshpass -p "${RPI_PASS}" ssh "${SSH_OPTS[@]}" "${RPI_HOST}" \
    "cat > ${RPI_HOME}/iams-relay.env << 'ENVEOF'
${ENV_CONTENT}
ENVEOF"

# Step 4: Deploy startup script
echo "[4/6] Deploying startup script..."
sshpass -p "${RPI_PASS}" scp "${SSH_OPTS[@]}" \
    "${PROJECT_DIR}/edge/iams-relay-start.sh" \
    "${RPI_HOST}:${RPI_HOME}/iams-relay-start.sh"

sshpass -p "${RPI_PASS}" ssh "${SSH_OPTS[@]}" "${RPI_HOST}" \
    "chmod +x ${RPI_HOME}/iams-relay-start.sh"

# Step 5: Deploy systemd service (templated for this user/home)
echo "[5/6] Installing systemd service..."
sshpass -p "${RPI_PASS}" ssh "${SSH_OPTS[@]}" "${RPI_HOST}" \
    "cat > /tmp/iams-relay.service << 'SVCEOF'
[Unit]
Description=IAMS RTSP Relay (Reolink → VPS mediamtx)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RPI_USER}
Group=${RPI_USER}
EnvironmentFile=${RPI_HOME}/iams-relay.env
ExecStart=${RPI_HOME}/iams-relay-start.sh

# Restart always — the script handles its own backoff internally
Restart=always
RestartSec=10
StartLimitInterval=0

# Resource limits
MemoryMax=256M
CPUQuota=80%

# Kill any leftover FFmpeg processes on stop
ExecStopPost=/usr/bin/killall -q ffmpeg || true

# Logging
StandardOutput=append:${RPI_HOME}/iams-relay.log
StandardError=append:${RPI_HOME}/iams-relay.log

[Install]
WantedBy=multi-user.target
SVCEOF
${SUDO} cp /tmp/iams-relay.service /etc/systemd/system/iams-relay.service && \
     ${SUDO} systemctl daemon-reload && \
     ${SUDO} systemctl enable iams-relay && \
     ${SUDO} systemctl restart iams-relay"

# Step 6: Verify
echo "[6/6] Verifying relay..."
sleep 3
sshpass -p "${RPI_PASS}" ssh "${SSH_OPTS[@]}" "${RPI_HOST}" \
    "systemctl is-active iams-relay && echo 'Relay is running!' || echo 'WARNING: Relay failed to start'; \
     echo ''; \
     echo '--- Last 10 log lines ---'; \
     tail -10 ${RPI_HOME}/iams-relay.log 2>/dev/null || echo 'No logs yet'"

echo ""
echo "=========================================="
echo "  Relay deployed! (${ROOM} — ${RELAY_MODE} mode)"
echo "  Stream: ${CAMERA_RTSP_URL}"
echo "     → ${VPS_RTSP_URL}/${ROOM_ID}"
echo "=========================================="
