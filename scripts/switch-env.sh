#!/bin/bash
# IAMS environment toggle: flip all client configs between local Docker and VPS production.
#
# Usage:
#   ./scripts/switch-env.sh local         # Point Android + admin at local Docker stack
#   ./scripts/switch-env.sh production    # Point Android + admin at VPS (167.71.217.44)
#   ./scripts/switch-env.sh status        # Show current mode
#
# This script is idempotent and only edits config files. It does NOT start/stop
# Docker, rebuild the APK, or launch npm. Those are orchestrated by Claude via
# the "Switch Protocol" section in CLAUDE.md, or by the user manually.

set -euo pipefail

# ---------------- constants ----------------

VPS_IP="167.71.217.44"
VPS_PORT="80"
LOCAL_PORT="8000"
MEDIAMTX_PORT="8554"
MEDIAMTX_WEBRTC_PORT="8889"

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

current_host() {
  awk -F= '/^IAMS_BACKEND_HOST=/ {print $2; exit}' "${GRADLE_PROPS}" | tr -d ' \r\n'
}

warn_local_overrides() {
  # If android/local.properties has uncommented IAMS_* overrides, Gradle will
  # prefer them over our gradle.properties edit. Warn the user.
  if [ -f "${LOCAL_PROPS}" ]; then
    if grep -E '^[[:space:]]*IAMS_(BACKEND_HOST|BACKEND_PORT|MEDIAMTX_PORT|MEDIAMTX_WEBRTC_PORT)=' "${LOCAL_PROPS}" >/dev/null 2>&1; then
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
  local host
  host="$(current_host)"
  if [ -z "${host}" ]; then
    echo "UNKNOWN (no IAMS_BACKEND_HOST in ${GRADLE_PROPS})"
    exit 1
  fi
  if [ "${host}" = "${VPS_IP}" ]; then
    echo "PRODUCTION (VPS: ${VPS_IP}:${VPS_PORT})"
  else
    echo "LOCAL (Mac LAN IP: ${host}:${LOCAL_PORT})"
  fi
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

  # 1. android/gradle.properties — host + port. Mediamtx ports unchanged (same locally).
  replace_kv "${GRADLE_PROPS}" "IAMS_BACKEND_HOST" "${lan_ip}"
  replace_kv "${GRADLE_PROPS}" "IAMS_BACKEND_PORT" "${LOCAL_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_MEDIAMTX_PORT" "${MEDIAMTX_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_MEDIAMTX_WEBRTC_PORT" "${MEDIAMTX_WEBRTC_PORT}"

  # 2. admin/.env.production — only VITE_API_URL + VITE_WS_URL. Supabase keys preserved.
  replace_env_line "${ADMIN_ENV_PROD}" "VITE_API_URL" "http://localhost:${LOCAL_PORT}/api/v1"
  replace_env_line "${ADMIN_ENV_PROD}" "VITE_WS_URL" "ws://localhost:${LOCAL_PORT}"

  # 3. admin/vite.config.ts — swap proxy targets. Both directions supported so this is idempotent.
  replace_vite_target "http://${VPS_IP}" "http://localhost:${LOCAL_PORT}"
  replace_vite_target "ws://${VPS_IP}"   "ws://localhost:${LOCAL_PORT}"

  echo "Switched to LOCAL."
  echo ""
  echo "Files updated:"
  echo "  - android/gradle.properties          (host → ${lan_ip}:${LOCAL_PORT})"
  echo "  - admin/.env.production              (VITE_* → localhost:${LOCAL_PORT})"
  echo "  - admin/vite.config.ts               (proxy → localhost:${LOCAL_PORT})"
  echo ""
  echo "Next steps:"
  echo "  1. Start local Docker stack:  ./scripts/dev-up.sh"
  echo "  2. Rebuild Android APK:        cd android && ./gradlew installDebug"
  echo "  3. Run admin dev server:       cd admin && npm run dev"
  echo "  4. Ensure physical Android device is on the same WiFi as this Mac (${lan_ip%.*}.x)."

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
  replace_kv "${GRADLE_PROPS}" "IAMS_MEDIAMTX_PORT" "${MEDIAMTX_PORT}"
  replace_kv "${GRADLE_PROPS}" "IAMS_MEDIAMTX_WEBRTC_PORT" "${MEDIAMTX_WEBRTC_PORT}"

  # 2. admin/.env.production
  replace_env_line "${ADMIN_ENV_PROD}" "VITE_API_URL" "/api/v1"
  replace_env_line "${ADMIN_ENV_PROD}" "VITE_WS_URL" "ws://${VPS_IP}"

  # 3. admin/vite.config.ts — swap localhost:PORT back to VPS.
  replace_vite_target "http://localhost:${LOCAL_PORT}" "http://${VPS_IP}"
  replace_vite_target "ws://localhost:${LOCAL_PORT}"   "ws://${VPS_IP}"

  echo "Switched to PRODUCTION (VPS: ${VPS_IP})."
  echo ""
  echo "Files updated:"
  echo "  - android/gradle.properties          (host → ${VPS_IP}:${VPS_PORT})"
  echo "  - admin/.env.production              (VITE_* → ${VPS_IP})"
  echo "  - admin/vite.config.ts               (proxy → ${VPS_IP})"
  echo ""
  echo "Next steps:"
  echo "  1. (Optional) Stop local Docker:  ./scripts/dev-down.sh"
  echo "  2. Rebuild Android APK:            cd android && ./gradlew installDebug"
  echo "  3. Admin is live at:               https://iams-thesis.vercel.app"
  echo "  4. Verify API:                     curl http://${VPS_IP}/api/v1/health"

  warn_local_overrides
}

# ---------------- entry point ----------------

main() {
  local cmd="${1:-}"
  case "${cmd}" in
    local)      cmd_local ;;
    production) cmd_production ;;
    status)     cmd_status ;;
    ""|-h|--help|help)
      cat <<EOF
IAMS environment toggle.

Usage:
  ./scripts/switch-env.sh local         Point Android + admin at local Docker stack
                                        (auto-detects Mac LAN IP for physical device access)
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
      die "Unknown command: '${cmd}'. Try: local | production | status"
      ;;
  esac
}

main "$@"
