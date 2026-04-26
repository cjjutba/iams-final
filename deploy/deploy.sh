#!/bin/bash
# =============================================================================
# IAMS Deploy Script
#
# Three deploy modes after the 2026-04-22 two-app split:
#
#   vps (default — the new world):
#     VPS runs: mediamtx + coturn + nginx + thin api-gateway + postgres + dozzle.
#     The thin api-gateway serves ONLY faculty auth + schedules + rooms
#     (backend/.env.vps disables ML + every heavy router). This powers the
#     Faculty Android APK. No student data, no face embeddings, no attendance.
#
#     Uses: docker-compose.vps.yml, nginx.vps.conf, mediamtx.relay.yml,
#           backend/.env.vps, backend/scripts/seed_vps_minimal.py
#
#   relay (video-only fallback):
#     Pure public video relay (mediamtx + coturn + nginx + dozzle).
#     Use if the Faculty APK is off / not deployed yet, or for raw-video
#     thesis demos. No backend, no DB.
#
#     Uses: docker-compose.relay.yml, nginx.relay.conf, mediamtx.relay.yml
#
#   full (legacy):
#     VPS runs the old full stack (backend + DB + redis + mediamtx + nginx).
#     Pre-2026-04-21. Kept as the ultimate rollback.
#
#     Uses: docker-compose.prod.yml, nginx.conf, mediamtx.yml
#
# Usage:
#   ./deploy/deploy.sh                 # defaults to `vps`
#   ./deploy/deploy.sh vps             # explicit thin API + video
#   ./deploy/deploy.sh relay           # video-only relay (no API)
#   ./deploy/deploy.sh full            # legacy full-stack deploy
# =============================================================================

set -euo pipefail

VPS_IP="167.71.217.44"
VPS_USER="root"
VPS_DIR="/opt/iams"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Source per-machine secrets (POSTGRES_PASSWORD). See scripts/.env.local.
# Same file used by onprem-up.sh — one place for one secret.
if [ -f "${PROJECT_DIR}/scripts/.env.local" ]; then
  # shellcheck disable=SC1091
  set -a
  . "${PROJECT_DIR}/scripts/.env.local"
  set +a
fi

MODE="${1:-vps}"

case "${MODE}" in
    vps|relay|full) ;;
    *)
        echo "ERROR: Unknown mode '${MODE}'. Use 'vps', 'relay', or 'full'." >&2
        exit 2
        ;;
esac

echo "=========================================="
echo "  IAMS Deploy → ${VPS_IP} (mode: ${MODE})"
echo "=========================================="

if [ "${MODE}" = "vps" ]; then
    # ── VPS MODE: thin API (auth+schedules+rooms) + public video relay ─

    if [ ! -f "${PROJECT_DIR}/backend/.env.vps" ]; then
        echo "ERROR: backend/.env.vps is missing on this host." >&2
        echo "       Create it from the template:" >&2
        echo "         cp backend/.env.vps.example backend/.env.vps" >&2
        echo "       Then fill SECRET_KEY + POSTGRES_PASSWORD." >&2
        exit 3
    fi

    echo "[1/5] Syncing VPS stack files..."
    rsync -avz \
        "${PROJECT_DIR}/deploy/docker-compose.vps.yml" \
        "${PROJECT_DIR}/deploy/nginx.vps.conf" \
        "${PROJECT_DIR}/deploy/mediamtx.relay.yml" \
        "${VPS_USER}@${VPS_IP}:${VPS_DIR}/deploy/"

    echo "[2/5] Syncing backend code + seed scripts..."
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
        --exclude '.env' \
        --exclude '.env.production' \
        --exclude '.env.onprem' \
        "${PROJECT_DIR}/backend/" "${VPS_USER}@${VPS_IP}:${VPS_DIR}/backend/"

    # backend/.env.vps must be synced explicitly (it's excluded by the
    # pattern above for safety; secrets don't overwrite whatever's there).
    rsync -avz \
        "${PROJECT_DIR}/backend/.env.vps" \
        "${VPS_USER}@${VPS_IP}:${VPS_DIR}/backend/.env.vps"

    echo "[3/5] Switching VPS to vps-mode stack..."
    # Propagate the operator's secrets (POSTGRES_PASSWORD + VPS_SYNC_SECRET)
    # into the remote shell so docker compose's ${VPS_SYNC_SECRET:-} +
    # ${POSTGRES_PASSWORD:-...} substitutions resolve. We deliberately do
    # NOT write either secret into a file on the VPS — they only live in
    # the api-gateway container's environment for the duration of the
    # compose process group.
    ssh "${VPS_USER}@${VPS_IP}" \
        "POSTGRES_PASSWORD='${POSTGRES_PASSWORD:-}' VPS_SYNC_SECRET='${VPS_SYNC_SECRET:-}' bash -s" << 'REMOTE'
        set -e
        cd /opt/iams/deploy

        # Firewall — same ports as relay plus nothing new (api is loopback,
        # nginx fronts it on :80 which is already open).
        ufw allow 80/tcp       comment "nginx" 2>/dev/null || true
        ufw allow 443/tcp      comment "nginx ssl" 2>/dev/null || true
        ufw allow 8554/tcp     comment "mediamtx RTSP ingest from on-prem Mac" 2>/dev/null || true
        ufw allow 8887/udp     comment "mediamtx WebRTC media" 2>/dev/null || true
        ufw allow 8889/tcp     comment "mediamtx WHEP" 2>/dev/null || true
        ufw allow 3478/tcp     comment "coturn" 2>/dev/null || true
        ufw allow 3478/udp     comment "coturn" 2>/dev/null || true
        ufw allow 49152:49252/udp comment "coturn relay" 2>/dev/null || true
        ufw allow 9999/tcp     comment "dozzle" 2>/dev/null || true

        # Down any conflicting stack first.
        for alt in docker-compose.prod.yml docker-compose.relay.yml; do
            if [ -f "${alt}" ] && docker compose -f "${alt}" ps -q | grep -q .; then
                echo "  Stopping ${alt}..."
                docker compose -f "${alt}" down --remove-orphans || true
            fi
        done

        echo "  Starting vps stack..."
        # POSTGRES_PASSWORD + VPS_SYNC_SECRET are inherited from the
        # outer ssh env; docker compose substitutes them into the
        # api-gateway service's environment block.
        docker compose -f docker-compose.vps.yml up -d --build --remove-orphans

        sleep 5
        docker compose -f docker-compose.vps.yml ps
REMOTE

    echo "[4/6] Seeding VPS postgres (faculty + schedules + rooms)..."
    ssh "${VPS_USER}@${VPS_IP}" \
        'docker exec iams-api-gateway-vps python -m scripts.seed_vps_minimal' || {
        echo "  WARNING: seed failed. Run manually later via:" >&2
        echo "    ssh root@${VPS_IP} 'docker exec iams-api-gateway-vps python -m scripts.seed_vps_minimal'" >&2
    }

    # Pull the latest signed APKs from GitHub releases onto the VPS so nginx
    # (deploy/nginx.vps.conf) can serve /iams-student.apk + /iams-faculty.apk
    # out of /static. The Build & Release APKs workflow publishes both
    # assets on every push to main; this step just mirrors the latest
    # release into /opt/iams/deploy/static/. Bind-mounted into the nginx
    # container at /static, so no nginx restart is needed — new file is
    # picked up on the next request.
    echo "[5/6] Pulling latest APKs from GitHub releases onto VPS..."
    ssh "${VPS_USER}@${VPS_IP}" 'bash -s' <<'REMOTE'
        set -e
        STATIC_DIR=/opt/iams/deploy/static
        REPO_URL="https://github.com/cjjutba/iams-final/releases/latest/download"
        mkdir -p "${STATIC_DIR}"

        downloaded_any=0
        for apk in iams-student.apk iams-faculty.apk; do
            echo "  → ${apk}"
            tmp="${STATIC_DIR}/${apk}.tmp"
            if curl -fLsS --retry 3 --retry-delay 2 -o "${tmp}" "${REPO_URL}/${apk}"; then
                # Sanity: APK files start with "PK" (zip magic). If the GitHub
                # CDN ever returns an HTML 404 page with a 200 wrapper, the
                # download would silently succeed but be unservable.
                if head -c 2 "${tmp}" | grep -q "^PK"; then
                    mv "${tmp}" "${STATIC_DIR}/${apk}"
                    ls -lh "${STATIC_DIR}/${apk}"
                    downloaded_any=1
                else
                    echo "    WARNING: ${apk} did not look like a valid APK (no PK header)."
                    rm -f "${tmp}"
                fi
            else
                echo "    WARNING: failed to download ${apk} from ${REPO_URL}"
                echo "    The Build & Release APKs workflow may not have published it yet."
                rm -f "${tmp}"
            fi
        done

        # Maintain a legacy /iams.apk → faculty APK alias on disk so the
        # relay-mode nginx (which still references /static/iams.apk) keeps
        # working without config churn.
        if [ -f "${STATIC_DIR}/iams-faculty.apk" ]; then
            cp -f "${STATIC_DIR}/iams-faculty.apk" "${STATIC_DIR}/iams.apk"
        fi

        if [ "${downloaded_any}" = "1" ]; then
            echo "  APK sync complete."
        else
            echo "  WARNING: no APKs downloaded — landing-page Download buttons"
            echo "           will 404 until the Build & Release APKs workflow"
            echo "           publishes a release with iams-student.apk +"
            echo "           iams-faculty.apk attached."
        fi
REMOTE

    echo "[6/6] Verifying..."
    sleep 2
    HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "http://${VPS_IP}/api/v1/health" || echo "000")
    FACE_GONE=$(curl -s -o /dev/null -w "%{http_code}" "http://${VPS_IP}/api/v1/face/register" || echo "000")
    STUDENT_APK=$(curl -s -o /dev/null -w "%{http_code}" "http://${VPS_IP}/iams-student.apk" || echo "000")
    FACULTY_APK=$(curl -s -o /dev/null -w "%{http_code}" "http://${VPS_IP}/iams-faculty.apk" || echo "000")

    echo ""
    echo "=========================================="
    if [ "${HEALTH}" = "200" ]; then
        echo "  VPS thin-API deploy successful!"
    else
        echo "  WARNING: /api/v1/health returned ${HEALTH}"
    fi
    echo "=========================================="
    echo ""
    echo "  Health:          http://${VPS_IP}/api/v1/health              (expect 200)"
    echo "  Faculty login:   POST http://${VPS_IP}/api/v1/auth/login     (expect 200 + JWT)"
    echo "  Face endpoint:   http://${VPS_IP}/api/v1/face/register       (got ${FACE_GONE}, expect 404 — route disabled)"
    echo "  Student APK:     http://${VPS_IP}/iams-student.apk           (got ${STUDENT_APK}, expect 200)"
    echo "  Faculty APK:     http://${VPS_IP}/iams-faculty.apk           (got ${FACULTY_APK}, expect 200)"
    echo "  Public WHEP:     http://${VPS_IP}:8889/<stream>/whep"
    echo "  Logs:            http://${VPS_IP}:9999                        (Dozzle)"
    echo ""
    if [ "${STUDENT_APK}" != "200" ] || [ "${FACULTY_APK}" != "200" ]; then
        echo "  NOTE: APK URL(s) did not return 200. If the Build & Release APKs"
        echo "        workflow has not published a release yet, push to main and"
        echo "        wait for the GitHub Action to finish, then re-run this deploy."
        echo ""
    fi
    echo "  Next: ensure the on-prem Mac is running ./scripts/onprem-up.sh"
    echo "        so its mediamtx pushes to rtsp://${VPS_IP}:8554/<streamKey>."
    echo ""
    exit 0
fi

if [ "${MODE}" = "relay" ]; then
    # ── RELAY MODE: VPS is video relay only ────────────────────────────

    echo "[1/3] Syncing relay configs..."
    rsync -avz \
        "${PROJECT_DIR}/deploy/docker-compose.relay.yml" \
        "${PROJECT_DIR}/deploy/nginx.relay.conf" \
        "${PROJECT_DIR}/deploy/mediamtx.relay.yml" \
        "${VPS_USER}@${VPS_IP}:${VPS_DIR}/deploy/"

    echo "[2/3] Switching VPS to relay-only stack..."
    ssh "${VPS_USER}@${VPS_IP}" << 'REMOTE'
        cd /opt/iams/deploy

        # Firewall — needs 80, 443, 8554, 8887/udp, 8889, 3478, 49152-49252/udp.
        # Same as before, idempotent.
        ufw allow 80/tcp       comment "nginx" 2>/dev/null || true
        ufw allow 443/tcp      comment "nginx ssl" 2>/dev/null || true
        ufw allow 8554/tcp     comment "mediamtx RTSP ingest from on-prem Mac" 2>/dev/null || true
        ufw allow 8887/udp     comment "mediamtx WebRTC media" 2>/dev/null || true
        ufw allow 8889/tcp     comment "mediamtx WHEP" 2>/dev/null || true
        ufw allow 3478/tcp     comment "coturn" 2>/dev/null || true
        ufw allow 3478/udp     comment "coturn" 2>/dev/null || true
        ufw allow 49152:49252/udp comment "coturn relay" 2>/dev/null || true
        ufw allow 9999/tcp     comment "dozzle" 2>/dev/null || true

        # Stop any conflicting stack (full or vps) first. `down --remove-orphans`
        # without `-v` preserves volumes in case you need to roll back.
        for alt in docker-compose.prod.yml docker-compose.vps.yml; do
            if [ -f "${alt}" ] && docker compose -f "${alt}" ps -q | grep -q .; then
                echo "  Stopping ${alt}..."
                docker compose -f "${alt}" down --remove-orphans || true
            fi
        done

        echo "  Starting relay stack..."
        docker compose -f docker-compose.relay.yml up -d --remove-orphans

        sleep 3
        docker compose -f docker-compose.relay.yml ps
REMOTE

    echo "[3/3] Verifying relay..."
    sleep 2
    HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "http://${VPS_IP}/health" || echo "000")
    if [ "$HEALTH" = "200" ]; then
        echo ""
        echo "=========================================="
        echo "  Relay deploy successful!"
        echo "=========================================="
        echo ""
        echo "  Health: http://${VPS_IP}/health"
        echo "  APK:    http://${VPS_IP}/iams.apk"
        echo "  WHEP:   http://${VPS_IP}:8889/<streamKey>/whep"
        echo "  Logs:   http://${VPS_IP}:9999"
        echo ""
        echo "  Next: ensure the on-prem Mac is running ./scripts/onprem-up.sh"
        echo "        so its mediamtx pushes to rtsp://${VPS_IP}:8554/<streamKey>."
        echo ""
    else
        echo ""
        echo "=========================================="
        echo "  WARNING: /health returned ${HEALTH}"
        echo "  Logs: ssh ${VPS_USER}@${VPS_IP} 'docker logs iams-nginx'"
        echo "=========================================="
    fi

    exit 0
fi

# ── FULL MODE (legacy): pre-split, VPS runs everything ─────────────────

# Step 1: Sync backend code to VPS
echo "[1/5] Syncing backend code to VPS..."
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

# Step 1c: Sync student/faculty master roster (seed_data.py reads from this)
echo "[1c/5] Syncing docs/data (student master roster)..."
ssh "${VPS_USER}@${VPS_IP}" "mkdir -p ${VPS_DIR}/docs/data"
rsync -avz --delete \
    "${PROJECT_DIR}/docs/data/" "${VPS_USER}@${VPS_IP}:${VPS_DIR}/docs/data/"

# Step 2: Sync admin dashboard code to VPS
echo "[2/5] Syncing admin dashboard code to VPS..."
rsync -avz --delete \
    --exclude 'node_modules/' \
    --exclude 'dist/' \
    --exclude '.env.local' \
    --exclude '.env.development' \
    "${PROJECT_DIR}/admin/" "${VPS_USER}@${VPS_IP}:${VPS_DIR}/admin/"

# Step 3: Sync legacy deploy configs
echo "[3/5] Syncing deploy configs (legacy full stack)..."
rsync -avz \
    "${PROJECT_DIR}/deploy/docker-compose.prod.yml" \
    "${PROJECT_DIR}/deploy/nginx.conf" \
    "${PROJECT_DIR}/deploy/mediamtx.yml" \
    "${VPS_USER}@${VPS_IP}:${VPS_DIR}/deploy/"

# Step 4: Build and restart on VPS
echo "[4/5] Building and starting containers on VPS..."
ssh "${VPS_USER}@${VPS_IP}" << 'REMOTE'
    cd /opt/iams/deploy

    echo "Checking firewall rules..."
    ufw allow 8554/tcp comment "mediamtx RTSP ingest from RPi" 2>/dev/null || true
    ufw allow 8887/udp comment "mediamtx WebRTC media" 2>/dev/null || true
    ufw allow 3478/tcp comment "coturn TURN listening" 2>/dev/null || true
    ufw allow 3478/udp comment "coturn TURN listening" 2>/dev/null || true
    ufw allow 49152:49252/udp comment "coturn TURN relay range" 2>/dev/null || true
    ufw allow 9999/tcp comment "Dozzle log viewer" 2>/dev/null || true

    # Stop any conflicting stack (relay or vps) so we don't have port conflicts.
    for alt in docker-compose.relay.yml docker-compose.vps.yml; do
        if [ -f "${alt}" ] && docker compose -f "${alt}" ps -q | grep -q .; then
            echo "Stopping ${alt} before switching to full..."
            docker compose -f "${alt}" down --remove-orphans || true
        fi
    done

    echo "Building and restarting containers..."
    docker compose -f docker-compose.prod.yml up -d --build

    echo "Waiting for backend to be healthy..."
    for i in $(seq 1 30); do
        if docker compose -f docker-compose.prod.yml ps | grep -q "healthy"; then
            echo "Backend is healthy!"
            break
        fi
        echo "  Waiting... ($i/30)"
        sleep 5
    done

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
    echo "  Check logs: ssh root@${VPS_IP} 'cd /opt/iams/deploy && docker compose -f docker-compose.prod.yml logs api-gateway'"
    echo "=========================================="
fi
