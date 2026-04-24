#!/bin/bash
# Start the IAMS ON-PREM stack on the Mac (Docker Desktop, IAMS-Net).
#
# This is the production-grade variant of dev-up.sh:
# - Uses deploy/docker-compose.onprem.yml (nginx + admin static + prod env).
# - Patches deploy/mediamtx.onprem.yml with the Mac's LAN IP.
# - Runs the admin-build sidecar which populates the admin_dist_onprem volume.
# - Serves admin portal + API at http://<MAC_LAN_IP>/ on the school LAN.
#
# Usage: ./scripts/onprem-up.sh
#
# Prereqs (first-time only — see docs/plans/2026-04-21-local-compute-split/RUNBOOK.md):
#   1. Copy backend/.env.onprem.example → backend/.env.onprem and fill secrets.
#   2. MikroTik DHCP reservation pinning this Mac's LAN IP.
#   3. `./scripts/switch-env.sh onprem` so the Android APK + admin build target
#      the Mac's LAN IP (baked into gradle.properties + admin/.env.production).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_ROOT}"

# ─ Source per-machine secrets if present ─────────────────────────────────
# scripts/.env.local holds POSTGRES_PASSWORD (plus any other per-operator
# env) so docker-compose's `${POSTGRES_PASSWORD:-iams_onprem_password}`
# substitution matches the value baked into the postgres volume. Without
# this, running `onprem-up.sh` on a fresh shell uses the default password,
# api-gateway can't authenticate to postgres, and the whole stack falls
# over with "password authentication failed for user iams".
#
# File is gitignored; see scripts/.env.local.example for the template.
if [ -f "scripts/.env.local" ]; then
  # shellcheck disable=SC1091
  set -a  # export everything we source
  . scripts/.env.local
  set +a
fi

COMPOSE_FILE="deploy/docker-compose.onprem.yml"
MEDIAMTX_TEMPLATE="deploy/mediamtx.onprem.yml"
MEDIAMTX_GENERATED="deploy/mediamtx.onprem.generated.yml"
BACKEND_ENV="backend/.env.onprem"

# ─ Preflight ─────────────────────────────────────────────────────────────

if [ "$(uname -s)" != "Darwin" ]; then
  echo "ERROR: onprem-up.sh assumes macOS (Docker Desktop / OrbStack on Apple Silicon)." >&2
  echo "       If you're porting to Linux, patch the ipconfig line below." >&2
  exit 1
fi

if [ ! -f "${BACKEND_ENV}" ]; then
  echo "ERROR: ${BACKEND_ENV} is missing." >&2
  echo "       Create it from the template:" >&2
  echo "         cp backend/.env.onprem.example ${BACKEND_ENV}" >&2
  echo "       Then fill SECRET_KEY, POSTGRES_PASSWORD, and (optionally) RESEND_API_KEY." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker CLI not found. Is Docker Desktop running?" >&2
  exit 1
fi

# ─ Detect Mac LAN IP ─────────────────────────────────────────────────────

HOST_IP=$(ipconfig getifaddr en0 2>/dev/null || true)
if [ -z "${HOST_IP}" ]; then
  HOST_IP=$(ipconfig getifaddr en1 2>/dev/null || true)
fi
if [ -z "${HOST_IP}" ]; then
  echo "ERROR: Could not detect Mac LAN IP on en0 or en1. Are you connected to IAMS-Net?" >&2
  exit 1
fi

echo "========================================"
echo "  IAMS On-Prem Stack (Mac on IAMS-Net)"
echo "  Host IP: ${HOST_IP}"
echo "========================================"

# ─ Generate mediamtx config from template with current LAN IP ───────────
# The committed `deploy/mediamtx.onprem.yml` is a TEMPLATE with a placeholder
# in `webrtcAdditionalHosts`. We copy it to a gitignored `.generated.yml`
# and patch the placeholder, so the committed file never drifts with the
# user's LAN IP (which used to leak into git on every boot).

cp "${MEDIAMTX_TEMPLATE}" "${MEDIAMTX_GENERATED}"
sed -i '' "/^webrtcAdditionalHosts:/,/^[^ ]/{s/^  - .*/  - ${HOST_IP}/;}" "${MEDIAMTX_GENERATED}"

# ─ Build + start the stack ───────────────────────────────────────────────
# HOST_IP is exported so docker-compose.onprem.yml can inject it into the
# api-gateway's ADMIN_URL and CORS_ORIGINS env vars (see that file's
# `environment:` block). This avoids mutating the user's .env.onprem at boot
# and keeps secrets untouched across runs.

export HOST_IP

echo ""
echo "Building and starting containers…"
docker compose -f "${COMPOSE_FILE}" up --build -d

# ─ Wait for api-gateway health ───────────────────────────────────────────

echo ""
echo "Waiting for api-gateway to report healthy…"
for i in $(seq 1 30); do
  if curl -sf "http://localhost:8000/api/v1/health" >/dev/null 2>&1; then
    echo "api-gateway healthy!"
    break
  fi
  # fall through if admin-build is still running — it blocks nginx start
  if [ "$i" = "30" ]; then
    echo "WARNING: api-gateway not healthy after 150 s."
    echo "  Check: docker compose -f ${COMPOSE_FILE} logs api-gateway | tail -50"
  else
    printf '.'
    sleep 5
  fi
done
echo ""

# ─ Verify via nginx (served on :80) ──────────────────────────────────────
NGINX_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost/api/v1/health" || echo "000")

echo ""
echo "========================================"
if [ "${NGINX_STATUS}" = "200" ]; then
  echo "  Stack is up. Admin portal + API live on IAMS-Net."
else
  echo "  WARNING: http://localhost/api/v1/health returned ${NGINX_STATUS}"
  echo "  admin-build may still be running; wait 1-2 min and retry the curl."
fi
echo "========================================"
echo ""
echo "  Admin portal:   http://${HOST_IP}/    (open from any LAN browser on IAMS-Net)"
echo "  Admin (local):  http://localhost/"
echo "  API:            http://${HOST_IP}/api/v1"
echo "  WebSocket:      ws://${HOST_IP}/api/v1/ws/…"
echo "  WHEP proxy:     http://${HOST_IP}/whep/<streamKey>/whep"
echo ""
echo "  mediamtx RTSP:  rtsp://${HOST_IP}:8554/<streamKey>  (RPi pushes here)"
echo "  mediamtx WHEP:  http://${HOST_IP}:8889/<streamKey>/whep (direct)"
echo "  mediamtx API:   http://localhost:9997/v3/paths/list   (loopback)"
echo ""
echo "  Logs:           docker compose -f ${COMPOSE_FILE} logs -f api-gateway"
echo "  Dozzle:         http://localhost:9998/"
echo ""
echo "  Next:"
echo "    1. RPi .env → RELAY_HOST=${HOST_IP}  (Phase 8 updates edge code)"
echo "    2. Android APK: cd android && ./gradlew clean installDebug"
echo "    3. Seed DB (first boot only):"
echo "         docker exec iams-api-gateway-onprem python -m scripts.seed_data"
echo "========================================"
