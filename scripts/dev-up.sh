#!/bin/bash
# Start IAMS local development stack on Docker Desktop
# Auto-detects Mac's LAN IP and patches mediamtx config
#
# Usage: ./scripts/dev-up.sh

set -euo pipefail
cd "$(dirname "$0")/.."

# Auto-detect Mac's WiFi LAN IP
HOST_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "")
if [ -z "$HOST_IP" ]; then
  HOST_IP=$(ipconfig getifaddr en1 2>/dev/null || echo "192.168.88.254")
fi

echo "========================================"
echo "  IAMS Local Dev Stack"
echo "  Host IP: ${HOST_IP}"
echo "========================================"

# Update .env with current IP
sed -i '' "s/^HOST_IP=.*/HOST_IP=${HOST_IP}/" .env

# Ensure ADMIN_URL points to the local admin portal (Vite dev server)
# Supabase email confirmation links redirect here
ADMIN_URL="http://localhost:5173"
if grep -q '^ADMIN_URL=' backend/.env 2>/dev/null; then
  sed -i '' "s|^ADMIN_URL=.*|ADMIN_URL=${ADMIN_URL}|" backend/.env
fi

# Update Supabase site_url so email confirmation links work in dev
SUPABASE_TOKEN=$(grep '^SUPABASE_ACCESS_TOKEN=' backend/.env | cut -d= -f2-)
if [ -n "$SUPABASE_TOKEN" ]; then
  echo "  Updating Supabase site_url → ${ADMIN_URL}"
  curl -s -X PATCH \
    -H "Authorization: Bearer ${SUPABASE_TOKEN}" \
    -H "Content-Type: application/json" \
    "https://api.supabase.com/v1/projects/fspnxqmewtxmuyqqwwni/config/auth" \
    -d "{\"site_url\": \"${ADMIN_URL}\"}" > /dev/null 2>&1 || echo "  ⚠ Could not update Supabase site_url (check token)"
fi

# Patch mediamtx.dev.yml webrtcAdditionalHosts with current IP
# Only replace the line after "webrtcAdditionalHosts:"
sed -i '' "/^webrtcAdditionalHosts:/,/^[^ ]/{s/^  - .*/  - ${HOST_IP}/;}" deploy/mediamtx.dev.yml

# Build and start
docker compose up --build -d

echo ""
echo "  API:        http://localhost:8000/api/v1"
echo "  Docs:       http://localhost:8000/api/v1/docs"
echo "  Health:     http://localhost:8000/api/v1/health"
echo "  Redis:      redis://localhost:6379"
echo "  RTSP:       rtsp://localhost:8554"
echo "  WebRTC:     http://localhost:8889"
echo "  mediamtx:   http://localhost:9997"
echo ""
echo "  Edge .env:  VPS_HOST=${HOST_IP}  VPS_PORT=8000"
echo "  Mobile:     USE_LOCAL_BACKEND=true (auto-detects ${HOST_IP})"
echo ""
echo "  Logs: docker compose logs -f api-gateway"
echo "========================================"
