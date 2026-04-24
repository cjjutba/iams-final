#!/bin/bash
# Start the IAMS camera relay in the background, detached from the current
# TTY. Runs until explicitly stopped or the Mac sleeps/reboots.
#
# Why not launchd/LaunchAgent?
# On macOS 15+ (Sequoia / 26 Tahoe), LaunchAgent-spawned binaries that aren't
# Apple-signed get silently blocked by Local Network TCC rules when trying
# to reach LAN endpoints like the Reolink cameras (192.168.88.x). Homebrew
# `ffmpeg` is unsigned, so the LaunchAgent approach fails with "No route to
# host" even though ping / nc / curl from the same launchd context work.
# Running the supervisor from a Terminal session inherits the shell's
# permissions and connects cleanly.
#
# Usage:
#   ./scripts/start-cam-relay.sh        # start (or restart)
#   ./scripts/stop-cam-relay.sh         # stop
#
# Logs: ~/Library/Logs/iams-cam-relay.log
# Lifecycle: survives terminal close. Dies on: Mac sleep with networking
# down, manual kill, reboot.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SUPERVISOR="${REPO_ROOT}/scripts/iams-cam-relay.sh"
LOG_FILE="${HOME}/Library/Logs/iams-cam-relay.log"
PID_FILE="${HOME}/Library/Application Support/iams/cam-relay.pid"

mkdir -p "$(dirname "${LOG_FILE}")"
mkdir -p "$(dirname "${PID_FILE}")"

# If an existing supervisor is running, stop it first (idempotent).
if [ -f "${PID_FILE}" ]; then
  existing="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [ -n "${existing}" ] && kill -0 "${existing}" 2>/dev/null; then
    echo "Existing supervisor running (pid ${existing}) — stopping first"
    kill -TERM "${existing}" 2>/dev/null || true
    sleep 2
  fi
fi
# Belt-and-braces: also nuke any stray ffmpeg from previous runs (matches the
# Reolink RTSP URL — narrow pattern won't hit unrelated ffmpeg jobs).
#
# The pattern here is slightly wider than stop-cam-relay's: if the supervisor
# crashed without cleaning up, the orphaned ffmpeg may have been reparented to
# init and would otherwise race against the fresh one we're about to spawn.
# Two-phase: SIGTERM + wait, then SIGKILL the stragglers. Without the wait
# the new ffmpeg could start while the old one is still bound to the
# mediamtx publish slot → `overridePublisher` disconnects both in rapid
# succession and neither actually establishes a stable publisher.
pkill -TERM -f "rtsp://admin:%40Iams2026THESIS%21@192.168.88" 2>/dev/null || true
for _ in 1 2 3 4 5; do
  pgrep -f "rtsp://admin:%40Iams2026THESIS%21@192.168.88" >/dev/null || break
  sleep 1
done
pkill -KILL -f "rtsp://admin:%40Iams2026THESIS%21@192.168.88" 2>/dev/null || true

if [ ! -x "${SUPERVISOR}" ]; then
  chmod +x "${SUPERVISOR}"
fi

if [ ! -x "/opt/homebrew/bin/ffmpeg" ]; then
  echo "ERROR: /opt/homebrew/bin/ffmpeg not found. Install with: brew install ffmpeg" >&2
  exit 1
fi

# Launch detached:
#   - `setsid`-like behaviour via `disown`  (macOS has no setsid by default;
#     nohup + disown is the equivalent)
#   - stdout + stderr → log file (rotates on restart; tail it to debug)
#   - stdin closed
echo "$(date '+%Y-%m-%d %H:%M:%S') === relay started by start-cam-relay.sh ===" >> "${LOG_FILE}"
nohup "${SUPERVISOR}" >> "${LOG_FILE}" 2>&1 < /dev/null &
SUP_PID=$!
disown "${SUP_PID}"
echo "${SUP_PID}" > "${PID_FILE}"

sleep 3

if kill -0 "${SUP_PID}" 2>/dev/null; then
  echo ""
  echo "=========================================="
  echo "  IAMS camera relay started"
  echo "=========================================="
  echo ""
  echo "  Supervisor pid:   ${SUP_PID}"
  echo "  Log file:         ${LOG_FILE}"
  echo "  PID file:         ${PID_FILE}"
  echo ""
  echo "  Tail the logs:    tail -f ${LOG_FILE}"
  echo "  Stop the relay:   ./scripts/stop-cam-relay.sh"
  echo ""
  # Show the last few log lines so the user sees the ffmpeg startup confirmation.
  echo "  Recent log output:"
  tail -8 "${LOG_FILE}" | sed 's/^/    /'
  echo ""
else
  echo ""
  echo "ERROR: supervisor died within 3 s. Check ${LOG_FILE}" >&2
  exit 1
fi
