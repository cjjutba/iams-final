#!/bin/bash
# Double-click this file in Finder to start the IAMS camera relay.
# macOS treats `.command` files as Terminal executables — the script runs
# in a brand-new Terminal window, which has full Local Network permissions
# (unlike launchd-spawned processes on macOS 26+).
#
# To make this run automatically on login:
#   1. Open System Settings → General → Login Items & Extensions
#   2. Click the `+` under "Open at Login"
#   3. Navigate to <repo>/scripts/ and pick this `.command` file
#   4. (Optional) check "Hide" so Terminal opens minimised
#
# When the Mac boots, macOS will open Terminal and run this script, which
# in turn calls start-cam-relay.sh to background the supervisor. The
# Terminal window can be closed safely — the supervisor is `nohup`+`disown`
# so it survives terminal exit.

# Resolve the repo path from this file's location. Works whether the
# .command lives in the repo (via symlink) or was copied elsewhere — the
# script follows the symlink before resolving.
SCRIPT_SOURCE="${BASH_SOURCE[0]}"
while [ -h "${SCRIPT_SOURCE}" ]; do
  SCRIPT_DIR="$(cd -P "$(dirname "${SCRIPT_SOURCE}")" && pwd)"
  SCRIPT_SOURCE="$(readlink "${SCRIPT_SOURCE}")"
  [[ ${SCRIPT_SOURCE} != /* ]] && SCRIPT_SOURCE="${SCRIPT_DIR}/${SCRIPT_SOURCE}"
done
SCRIPT_DIR="$(cd -P "$(dirname "${SCRIPT_SOURCE}")" && pwd)"
REPO_SCRIPTS_DIR="${SCRIPT_DIR}"

cd "${REPO_SCRIPTS_DIR}"
echo "Starting IAMS camera relay from: ${REPO_SCRIPTS_DIR}"
echo ""

./start-cam-relay.sh

echo ""
echo "Press Cmd+W to close this Terminal window. The relay runs in the background."
