#!/bin/bash
# IAMS environment toggle: flip all client configs between local Docker, VPS
# production, and on-prem Mac on IAMS-Net.
#
# Usage:
#   ./scripts/switch-env.sh local         Point Android + admin at local dev stack (Mac LAN IP : 8000)
#   ./scripts/switch-env.sh onprem        Point Android + admin at on-prem Mac stack (Mac LAN IP : 80 via nginx)
#   ./scripts/switch-env.sh production    Point Android + admin at VPS (167.71.217.44)
#   ./scripts/switch-env.sh status        Show current mode
#
# Modes:
#   local     = dev iteration; docker-compose.yml; admin via `npm run dev`.
#   onprem    = production on Mac on IAMS-Net; deploy/docker-compose.onprem.yml;
#               admin served by local nginx. Mobile video still comes from VPS.
#   production= VPS runs everything (legacy full-stack) OR VPS is relay-only
#               (post-split) — mobile hits VPS for all non-video too.
#
# This script is idempotent and only edits config files. It does NOT start/stop
# Docker, rebuild the APK, or launch npm. Those are orchestrated by Claude via
# the "Switch Protocol" section in CLAUDE.md, or by the user manually.

set -euo pipefail

# ---------------- constants ----------------

VPS_IP="167.71.217.44"
VPS_PORT="80"
LOCAL_PORT="8000"
ONPREM_PORT="80"
MEDIAMTX_PORT="8554"
MEDIAMTX_WEBRTC_PORT="8889"

# Mediamtx WHEP target — always localhost:8889 because the admin portal's
# live-feed proxy always talks to the Mac's local mediamtx, regardless of
# which backend mode we're in. The sweep below preserves this target.
MEDIAMTX_WHEP_TARGET="http://localhost:${MEDIAMTX_WEBRTC_PORT}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

GRADLE_PROPS="${REPO_ROOT}/android/gradle.properties"
LOCAL_PROPS="${REPO_ROOT}/android/local.properties"
ADMIN_ENV_PROD="${REPO_ROOT}/admin/.env.production"
VITE_CONFIG="${REPO_ROOT}/admin/vite.config.ts"

# ---------------- helpers ----------------

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_darwin() {
  [ "$(uname -s)" = "Darwin" ] || die "switch-env.sh only supports macOS (detected: $(uname -s))."
}

require_file() {
  [ -f "$1" ] || die "Expected file not found: $1"
}

detect_lan_ip() {
  local ip
  ip="$(ipconfig getifaddr en0 2>/dev/null || true)"
  if [ -z "${ip}" ]; then
    ip="$(ipconfig getifaddr en1 2>/dev/null || true)"
  fi
  [ -n "${ip}" ] || die "Could not detect Mac LAN IP on en0 or en1. Are you connected to WiFi?"
  echo "${ip}"
}

# Rewrite `key=...` → `key=<value>` in-place, BSD-sed safe.
replace_kv() {
  local file="$1" key="$2" value="$3"
  require_file "${file}"
  # Escape for sed: backslashes and pipes.
  local esc
  esc="$(printf '%s' "${value}" | sed -e 's/[\\|]/\\&/g')"
  sed -i.bak -E "s|^${key}=.*$|${key}=${esc}|" "${file}"
  rm -f "${file}.bak"
}

# Replace the VALUE of `VITE_WS_URL=` even when value is empty — needs a
# slightly different regex than replace_kv (which requires a trailing pattern).
# Also tolerant of trailing whitespace.
replace_env_line() {
  local file="$1" key="$2" value="$3"
  require_file "${file}"
  local esc
  esc="$(printf '%s' "${value}" | sed -e 's/[\\|]/\\&/g')"
  sed -i.bak -E "s|^${key}=.*|${key}=${esc}|" "${file}"
  rm -f "${file}.bak"
}

# Replace a TS string literal in vite.config.ts:
#   target: 'ws://OLD' → target: 'ws://NEW'
#   target: 'http://OLD' → target: 'http://NEW'
# We target by full old URL to avoid touching anything else in the file.
replace_vite_target() {
  local old_url="$1" new_url="$2"
  require_file "${VITE_CONFIG}"
  local esc_old esc_new
  esc_old="$(printf '%s' "${old_url}" | sed -e 's/[\\|/.]/\\&/g')"
  esc_new="$(printf '%s' "${new_url}" | sed -e 's/[\\|/]/\\&/g')"
  sed -i.bak -E "s|target: '${esc_old}'|target: '${esc_new}'|g" "${VITE_CONFIG}"
  rm -f "${VITE_CONFIG}.bak"
}

# Rewrite ALL API/WS proxy targets in vite.config.ts, regardless of current
# value. The mediamtx target (${MEDIAMTX_WHEP_TARGET}) is preserved as-is.
#
# This is the robust path — it handles stale LAN IPs from previous network
# joins (home WiFi DHCP leases, IAMS-Net, etc.) without needing to enumerate
# known predecessor states. Called by each mode command as its last vite edit.
sweep_vite_proxy_targets() {
  local new_http="$1" new_ws="$2"
  require_file "${VITE_CONFIG}"
  local esc_http esc_ws esc_mediamtx
  esc_http="$(printf '%s' "${new_http}" | sed -e 's/[\\|]/\\&/g')"
  esc_ws="$(printf '%s' "${new_ws}" | sed -e 's/[\\|]/\\&/g')"
  esc_mediamtx="$(printf '%s' "${MEDIAMTX_WHEP_TARGET}" | sed -e 's/[\\|/.:]/\\&/g')"
  # Replace every `target: 'http://...'` except the mediamtx one.
  sed -i.bak -E "/target: '${esc_mediamtx}'/!s|target: 'http://[^']*'|target: '${esc_http}'|" "${VITE_CONFIG}"
  # Only one `target: 'ws://...'` line exists; replace it.
  sed -i.bak -E "s|target: 'ws://[^']*'|target: '${esc_ws}'|" "${VITE_CONFIG}"
  rm -f "${VITE_CONFIG}.bak"
}

current_host() {
  # Prefer the post-2026-04-22 student key; fall back to the legacy
  # IAMS_BACKEND_HOST so a half-migrated tree still reports correctly.
  local host
  host="$(awk -F= '/^IAMS_STUDENT_BACKEND_HOST=/ {print $2; exit}' "${GRADLE_PROPS}" | tr -d ' \r\n')"
  if [ -z "${host}" ]; then
    host="$(awk -F= '/^IAMS_BACKEND_HOST=/ {print $2; exit}' "${GRADLE_PROPS}" | tr -d ' \r\n')"
  fi
  echo "${host}"
}

current_port() {
  local port
  port="$(awk -F= '/^IAMS_STUDENT_BACKEND_PORT=/ {print $2; exit}' "${GRADLE_PROPS}" | tr -d ' \r\n')"
  if [ -z "${port}" ]; then
    port="$(awk -F= '/^IAMS_BACKEND_PORT=/ {print $2; exit}' "${GRADLE_PROPS}" | tr -d ' \r\n')"
  fi
  echo "${port}"
}

warn_local_overrides() {
  # If android/local.properties has uncommented IAMS_* overrides, Gradle will
  # prefer them over our gradle.properties edit. Warn the user.
  if [ -f "${LOCAL_PROPS}" ]; then
    if grep -E '^[[:space:]]*IAMS_(STUDENT_BACKEND_HOST|STUDENT_BACKEND_PORT|FACULTY_API_HOST|FACULTY_API_PORT|FACULTY_STREAM_HOST|FACULTY_STREAM_WEBRTC_PORT|BACKEND_HOST|BACKEND_PORT|MEDIAMTX_PORT|MEDIAMTX_WEBRTC_PORT|STREAM_HOST|STREAM_WEBRTC_PORT)=' "${LOCAL_PROPS}" >/dev/null 2>&1; then
      echo ""
      echo "⚠️  WARNING: android/local.properties has uncommented IAMS_* overrides."
      echo "   local.properties takes precedence over gradle.properties."
      echo "   Your Android build will use local.properties values, not the switched ones."
      echo "   Comment out those lines in android/local.properties to make the switch take effect."
      echo ""
    fi
  fi
}

# ---------------- subcommands ----------------

cmd_status() {
  require_file "${GRADLE_PROPS}"
  local host port
  host="$(current_host)"
  port="$(current_port)"
  if [ -z "${host}" ]; then
    echo "UNKNOWN (no IAMS_STUDENT_BACKEND_HOST or IAMS_BACKEND_HOST in ${GRADLE_PROPS})"
    exit 1
  fi
  local mode
  if [ "${host}" = "${VPS_IP}" ]; then
    mode="PRODUCTION (Student app → VPS: ${VPS_IP}:${VPS_PORT})"
  elif [ "${port}" = "${ONPREM_PORT}" ]; then
    mode="ONPREM (Student app → Mac LAN IP: ${host}:${ONPREM_PORT} via nginx)"
  else
    mode="LOCAL (Student app → Mac LAN IP: ${host}:${LOCAL_PORT})"
  fi
  echo "${mode}"
  # Faculty app is always pointed at the VPS — surface that explicitly so the
  # user knows they can't accidentally toggle it.
  echo "Faculty app → VPS: 167.71.217.44:80 (fixed; not toggled by switch-env)"
}

cmd_local() {
  require_darwin
  require_file "${GRADLE_PROPS}"
  require_file "${ADMIN_ENV_PROD}"
  require_file "${VITE_CONFIG}"

  local lan_ip
  lan_ip="$(detect_lan_ip)"

  echo "Detected Mac LAN IP: ${lan_ip}"
  echo ""

  # 1. android/gradle.properties — student app keys ONLY. After the
  #    2026-04-22 two-app split, the faculty app has its own IAMS_FACULTY_*
  #    keys that ALWAYS point at the VPS — switch-env.sh must NOT touch them.
  #    The legacy IAMS_BACKEND_* keys are kept in sync as a fallback for any
  #    pre-split CI / local.properties overrides.
  replace_kv "${GRADLE_PROPS}" "IAMS_STUDENT_BACKEND_HOST" "${lan_ip}"
  replace_kv "${GRADLE_PROPS}" "IAMS_STUDENT_BACKEND_PORT" "${LOCAL_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_BACKEND_HOST" "${lan_ip}"
  replace_kv "${GRADLE_PROPS}" "IAMS_BACKEND_PORT" "${LOCAL_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_MEDIAMTX_PORT" "${MEDIAMTX_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_MEDIAMTX_WEBRTC_PORT" "${MEDIAMTX_WEBRTC_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_STREAM_HOST" "${lan_ip}"
  replace_kv "${GRADLE_PROPS}" "IAMS_STREAM_WEBRTC_PORT" "${MEDIAMTX_WEBRTC_PORT}"

  # 2. admin/.env.production — only VITE_API_URL + VITE_WS_URL + VITE_STREAM_WEBRTC_URL.
  #    Supabase keys preserved.
  replace_env_line "${ADMIN_ENV_PROD}" "VITE_API_URL" "http://localhost:${LOCAL_PORT}/api/v1"
  replace_env_line "${ADMIN_ENV_PROD}" "VITE_WS_URL" "ws://localhost:${LOCAL_PORT}"
  replace_env_line "${ADMIN_ENV_PROD}" "VITE_STREAM_WEBRTC_URL" "/whep"

  # 3. admin/vite.config.ts — rewrite all API/WS proxy targets. Regex sweep
  #    handles stale onprem/production/older-localhost targets uniformly.
  sweep_vite_proxy_targets "http://localhost:${LOCAL_PORT}" "ws://localhost:${LOCAL_PORT}"

  echo "Switched to LOCAL."
  echo ""
  echo "Files updated:"
  echo "  - android/gradle.properties          (host → ${lan_ip}:${LOCAL_PORT}, stream → ${lan_ip})"
  echo "  - admin/.env.production              (VITE_* → localhost:${LOCAL_PORT})"
  echo "  - admin/vite.config.ts               (proxy → localhost:${LOCAL_PORT})"
  echo ""
  echo "Next steps:"
  echo "  1. Start local Docker stack:  ./scripts/dev-up.sh"
  echo "  2. Rebuild Android APK:        cd android && ./gradlew clean installDebug"
  echo "     (use 'clean' — plain installDebug can reuse stale BuildConfig, see CLAUDE.md)"
  echo "  3. Run admin dev server:       cd admin && npm run dev"
  echo "     → Open http://localhost:5173 (NOT https://iams-thesis.vercel.app — Vercel always hits VPS)"
  echo "  4. Ensure physical Android device is on the same WiFi as this Mac (${lan_ip%.*}.x)."

  warn_local_overrides
}

cmd_onprem() {
  require_darwin
  require_file "${GRADLE_PROPS}"
  require_file "${ADMIN_ENV_PROD}"
  require_file "${VITE_CONFIG}"

  local lan_ip
  lan_ip="$(detect_lan_ip)"

  echo "Detected Mac LAN IP: ${lan_ip}"
  echo ""
  echo "Configuring ONPREM mode:"
  echo "  - Android REST + WebSocket → http://${lan_ip}:${ONPREM_PORT} (Mac nginx)"
  echo "  - Android mobile live-feed → http://${VPS_IP}:${MEDIAMTX_WEBRTC_PORT} (VPS public relay)"
  echo "  - Admin portal             → served by Mac nginx at http://${lan_ip}"
  echo ""

  # 1. android/gradle.properties — student app keys ONLY. The faculty app's
  #    IAMS_FACULTY_* keys are intentionally untouched (faculty always
  #    points at the VPS). The legacy IAMS_BACKEND_* keys are mirrored for
  #    pre-split CI / local.properties fallbacks.
  replace_kv "${GRADLE_PROPS}" "IAMS_STUDENT_BACKEND_HOST" "${lan_ip}"
  replace_kv "${GRADLE_PROPS}" "IAMS_STUDENT_BACKEND_PORT" "${ONPREM_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_BACKEND_HOST" "${lan_ip}"
  replace_kv "${GRADLE_PROPS}" "IAMS_BACKEND_PORT" "${ONPREM_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_MEDIAMTX_PORT" "${MEDIAMTX_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_MEDIAMTX_WEBRTC_PORT" "${MEDIAMTX_WEBRTC_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_STREAM_HOST" "${VPS_IP}"
  replace_kv "${GRADLE_PROPS}" "IAMS_STREAM_WEBRTC_PORT" "${MEDIAMTX_WEBRTC_PORT}"

  # 2. admin/.env.production — relative URLs. Empty VITE_WS_URL falls back to
  #    window.location.host in use-websocket.ts. Supabase keys preserved.
  replace_env_line "${ADMIN_ENV_PROD}" "VITE_API_URL" "/api/v1"
  replace_env_line "${ADMIN_ENV_PROD}" "VITE_WS_URL" ""
  replace_env_line "${ADMIN_ENV_PROD}" "VITE_STREAM_WEBRTC_URL" "/whep"

  # 3. admin/vite.config.ts — proxy targets the Mac's own nginx port 80.
  #    Supports `npm run dev` iteration against the running onprem stack.
  # Rewrite all API/WS proxy targets to the current LAN IP. Regex sweep
  #    handles any stale IP (VPS, localhost, prior LAN IPs from home WiFi or
  #    IAMS-Net) without an enumerated list.
  sweep_vite_proxy_targets "http://${lan_ip}" "ws://${lan_ip}"

  echo "Switched to ONPREM."
  echo ""
  echo "Files updated:"
  echo "  - android/gradle.properties          (backend → ${lan_ip}:${ONPREM_PORT}, stream → ${VPS_IP})"
  echo "  - admin/.env.production              (VITE_API_URL=/api/v1, VITE_WS_URL empty)"
  echo "  - admin/vite.config.ts               (proxy → ${lan_ip})"
  echo ""
  echo "Next steps:"
  echo "  1. Start on-prem Mac stack:    ./scripts/onprem-up.sh      # (added in Phase 7)"
  echo "  2. Rebuild Android APK:        cd android && ./gradlew clean installDebug"
  echo "     (use 'clean' — plain installDebug can reuse stale BuildConfig, see CLAUDE.md)"
  echo "  3. Verify API via nginx:       curl http://${lan_ip}/api/v1/health"
  echo "  4. Open admin portal:          http://${lan_ip}/    (from any LAN browser on IAMS-Net)"
  echo "  5. Ensure Android + faculty browsers are on IAMS-Net (${lan_ip%.*}.x)."

  warn_local_overrides
}

cmd_production() {
  require_darwin
  require_file "${GRADLE_PROPS}"
  require_file "${ADMIN_ENV_PROD}"
  require_file "${VITE_CONFIG}"

  # 1. android/gradle.properties
  replace_kv "${GRADLE_PROPS}" "IAMS_BACKEND_HOST" "${VPS_IP}"
  replace_kv "${GRADLE_PROPS}" "IAMS_BACKEND_PORT" "${VPS_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_STUDENT_BACKEND_HOST" "${VPS_IP}"
  replace_kv "${GRADLE_PROPS}" "IAMS_STUDENT_BACKEND_PORT" "${VPS_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_MEDIAMTX_PORT" "${MEDIAMTX_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_MEDIAMTX_WEBRTC_PORT" "${MEDIAMTX_WEBRTC_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_STREAM_HOST" "${VPS_IP}"
  replace_kv "${GRADLE_PROPS}" "IAMS_STREAM_WEBRTC_PORT" "${MEDIAMTX_WEBRTC_PORT}"

  # 2. admin/.env.production
  replace_env_line "${ADMIN_ENV_PROD}" "VITE_API_URL" "/api/v1"
  replace_env_line "${ADMIN_ENV_PROD}" "VITE_WS_URL" "ws://${VPS_IP}"
  replace_env_line "${ADMIN_ENV_PROD}" "VITE_STREAM_WEBRTC_URL" "/whep"

  # 3. admin/vite.config.ts — rewrite all API/WS proxy targets to VPS.
  #    Regex sweep handles any stale IP from prior local/onprem/home-WiFi runs.
  sweep_vite_proxy_targets "http://${VPS_IP}" "ws://${VPS_IP}"

  echo "Switched to PRODUCTION (VPS: ${VPS_IP})."
  echo ""
  echo "Files updated:"
  echo "  - android/gradle.properties          (host → ${VPS_IP}:${VPS_PORT})"
  echo "  - admin/.env.production              (VITE_* → ${VPS_IP})"
  echo "  - admin/vite.config.ts               (proxy → ${VPS_IP})"
  echo ""
  echo "Next steps:"
  echo "  1. (Optional) Stop local Docker:  ./scripts/dev-down.sh"
  echo "  2. Rebuild Android APK:            cd android && ./gradlew clean installDebug"
  echo "     (use 'clean' — plain installDebug can reuse stale BuildConfig, see CLAUDE.md)"
  echo "  3. Admin is live at:               https://iams-thesis.vercel.app"
  echo "  4. Verify API:                     curl http://${VPS_IP}/api/v1/health"

  warn_local_overrides
}

# ---------------- entry point ----------------

main() {
  local cmd="${1:-}"
  case "${cmd}" in
    local)      cmd_local ;;
    onprem)     cmd_onprem ;;
    production) cmd_production ;;
    status)     cmd_status ;;
    ""|-h|--help|help)
      cat <<EOF
IAMS environment toggle.

Usage:
  ./scripts/switch-env.sh local         Point Android + admin at local dev stack
                                        (Mac LAN IP : ${LOCAL_PORT}, docker-compose.yml)
  ./scripts/switch-env.sh onprem        Point Android + admin at on-prem Mac stack
                                        (Mac LAN IP : ${ONPREM_PORT} via nginx,
                                         deploy/docker-compose.onprem.yml;
                                         mobile live-feed still hits VPS)
  ./scripts/switch-env.sh production    Point Android + admin at VPS (${VPS_IP})
  ./scripts/switch-env.sh status        Show current mode

Files touched:
  - android/gradle.properties
  - admin/.env.production  (Supabase keys preserved)
  - admin/vite.config.ts

Not touched: backend/.env*, android/local.properties, docker-compose.yml.
EOF
      ;;
    *)
      die "Unknown command: '${cmd}'. Try: local | onprem | production | status"
      ;;
  esac
}

main "$@"
