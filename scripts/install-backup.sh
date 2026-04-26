#!/bin/bash
# IAMS — install the nightly backup launchd agent.
#
# Run ONCE per Mac. After this, scripts/iams-backup.sh fires every night
# at IAMS_BACKUP_HOUR:IAMS_BACKUP_MINUTE local time (default 03:00) for as
# long as the user is logged in. Survives reboots; pauses while the Mac
# is asleep and runs at next wake if a scheduled time was missed.
#
# Usage:
#   1. cp scripts/.env.local.example scripts/.env.local
#      (if you haven't already)
#   2. Set IAMS_BACKUP_GPG_PASSPHRASE in scripts/.env.local. Pick a strong
#      passphrase and SAVE IT IN A PASSWORD MANAGER. Without it, the
#      encrypted dumps are unrecoverable.
#   3. Make sure the on-prem stack is running (./scripts/onprem-up.sh) so
#      the install-time smoke test can verify it.
#   4. Run ./scripts/install-backup.sh
#
# To verify:
#   launchctl list | grep iams        # should show com.iams.backup
#   tail -f ~/Library/Logs/iams-backup.log
#
# To remove:
#   ./scripts/uninstall-backup.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_PATH="${HOME}/Library/LaunchAgents/com.iams.backup.plist"
BACKUP_SCRIPT="${PROJECT_DIR}/scripts/iams-backup.sh"
LOG_FILE="${HOME}/Library/Logs/iams-backup.log"

# Schedule defaults — overridable via env if the operator wants to shift
# the run window (e.g. to 04:30 to avoid colliding with a separate
# backup of an unrelated service).
BACKUP_HOUR="${IAMS_BACKUP_HOUR:-3}"
BACKUP_MINUTE="${IAMS_BACKUP_MINUTE:-0}"

# ── Preflight ────────────────────────────────────────────────────────
if [ ! -f "${PROJECT_DIR}/scripts/.env.local" ]; then
  echo "ERROR: scripts/.env.local missing." >&2
  echo "       cp scripts/.env.local.example scripts/.env.local" >&2
  echo "       and set IAMS_BACKUP_GPG_PASSPHRASE first." >&2
  exit 2
fi

# Source so we can sanity-check the passphrase is set without printing it.
# shellcheck disable=SC1091
set -a
. "${PROJECT_DIR}/scripts/.env.local"
set +a

if [ -z "${IAMS_BACKUP_GPG_PASSPHRASE:-}" ]; then
  echo "ERROR: IAMS_BACKUP_GPG_PASSPHRASE is empty in scripts/.env.local." >&2
  echo "       Pick a strong passphrase and add it. SAVE IT IN A PASSWORD" >&2
  echo "       MANAGER — without it, the encrypted dumps are unrecoverable." >&2
  exit 3
fi

if ! [ -x "${BACKUP_SCRIPT}" ]; then
  chmod +x "${BACKUP_SCRIPT}"
fi

mkdir -p "${HOME}/Library/LaunchAgents"
mkdir -p "$(dirname "${LOG_FILE}")"

# Bootout any existing instance before replacing the plist. Idempotent —
# a 'bootout' on a non-loaded label is a 5-line warning, not a failure.
if launchctl list 2>/dev/null | awk '{print $3}' | grep -q '^com\.iams\.backup$'; then
  echo "Stopping existing com.iams.backup before reinstall..."
  launchctl bootout "gui/$(id -u)/com.iams.backup" 2>/dev/null || true
fi

# ── Write the plist ──────────────────────────────────────────────────
cat > "${PLIST_PATH}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.iams.backup</string>

  <!-- Run the backup script verbatim — it sources its own env from
       scripts/.env.local and handles all logging itself. -->
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${BACKUP_SCRIPT}</string>
  </array>

  <!-- Daily at HH:MM local time. macOS launchd interprets
       StartCalendarInterval in the agent's wall-clock TZ. -->
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>${BACKUP_HOUR}</integer>
    <key>Minute</key>
    <integer>${BACKUP_MINUTE}</integer>
  </dict>

  <!-- Don't run on load — only on the calendar fire. The first real run
       happens the next time HH:MM rolls around. Run a one-shot now via
       ./scripts/iams-backup.sh manually if you want to verify. -->
  <key>RunAtLoad</key>
  <false/>

  <!-- launchd defaults to a minimal PATH that doesn't include
       /opt/homebrew/bin (where docker, gpg, gnupg live on Apple
       Silicon). Add it explicitly so the script's command-resolution
       finds the same tools the operator's Terminal does. -->
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>

  <key>StandardOutPath</key>
  <string>${LOG_FILE}</string>
  <key>StandardErrorPath</key>
  <string>${LOG_FILE}</string>
</dict>
</plist>
EOF

# ── Activate ─────────────────────────────────────────────────────────
launchctl bootstrap "gui/$(id -u)" "${PLIST_PATH}"

echo
echo "Installed IAMS backup launchd agent."
echo "  Plist:    ${PLIST_PATH}"
echo "  Schedule: daily at $(printf '%02d:%02d' "${BACKUP_HOUR}" "${BACKUP_MINUTE}") local time"
echo "  Logs:     ${LOG_FILE}"
echo
echo "Verify:"
echo "  launchctl list | grep iams        # should show 'com.iams.backup'"
echo "  ./scripts/iams-backup.sh           # manual one-shot test (recommended)"
echo "  tail -f ${LOG_FILE}                # watch the next scheduled run"
echo
echo "Remove with: ./scripts/uninstall-backup.sh"
