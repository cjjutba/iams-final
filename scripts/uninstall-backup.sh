#!/bin/bash
# IAMS — remove the nightly backup launchd agent.
#
# Safe to run repeatedly. Existing dumps in ${IAMS_BACKUP_DIR:-~/iams-backups}
# are NOT deleted — only the launchd registration + plist file are removed.
set -euo pipefail

PLIST_PATH="${HOME}/Library/LaunchAgents/com.iams.backup.plist"

if launchctl list 2>/dev/null | awk '{print $3}' | grep -q '^com\.iams\.backup$'; then
  launchctl bootout "gui/$(id -u)/com.iams.backup" 2>/dev/null || true
  echo "Unloaded com.iams.backup."
else
  echo "com.iams.backup is not loaded — nothing to bootout."
fi

if [ -f "${PLIST_PATH}" ]; then
  rm -f "${PLIST_PATH}"
  echo "Removed ${PLIST_PATH}."
else
  echo "Plist already absent — nothing to remove."
fi

echo
echo "Existing backups in ~/iams-backups (or \$IAMS_BACKUP_DIR) are kept."
echo "Delete them manually if you want to free disk space."
