#!/bin/bash
# Stop the IAMS camera relay started by scripts/start-cam-relay.sh.
#
# Handles three messy real-world states:
#   - Normal case: PID file points to a live supervisor
#   - Crashed supervisor: PID file gone, ffmpeg orphans still running
#   - Double-started: multiple supervisors (user ran start twice quickly)
# The pkill pass at the end is the safety net for the last two.

set -euo pipefail

PID_FILE="${HOME}/Library/Application Support/iams/cam-relay.pid"

# Kill supervisor via pid file if we have it.
if [ -f "${PID_FILE}" ]; then
  pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
    echo "Sending SIGTERM to supervisor pid ${pid}..."
    kill -TERM "${pid}" 2>/dev/null || true
    sleep 2
    if kill -0 "${pid}" 2>/dev/null; then
      echo "Supervisor didn't exit — sending SIGKILL"
      kill -KILL "${pid}" 2>/dev/null || true
    fi
  fi
  rm -f "${PID_FILE}"
else
  echo "No PID file at ${PID_FILE} — falling through to pattern scan."
fi

# Belt-and-braces: kill any Reolink ffmpeg pushers AND loop wrappers that
# might have been orphaned from the supervisor (duplicate starts, crashed
# PID files, or an old supervisor whose pid file already got overwritten).
# Patterns are narrow — won't hit unrelated ffmpeg jobs.
#
# Two-pass SIGTERM → wait → SIGKILL so ffmpeg has a chance to flush its
# mux before we force-kill. Without the wait, the next start-cam-relay
# can race with dying ffmpegs still bound to the RTSP port.
pkill -TERM -f "iams-cam-relay.sh" 2>/dev/null || true
pkill -TERM -f "rtsp://admin:%40Iams2026THESIS%21@192.168.88" 2>/dev/null || true
sleep 2
# Anything still alive after 2 s — escalate.
pkill -KILL -f "iams-cam-relay.sh" 2>/dev/null || true
pkill -KILL -f "rtsp://admin:%40Iams2026THESIS%21@192.168.88" 2>/dev/null || true

# Verify nothing's left so the user sees a definitive state.
remaining=$(pgrep -fc "iams-cam-relay.sh|rtsp://admin:%40Iams2026THESIS%21@192.168.88" 2>/dev/null || echo 0)
if [ "${remaining}" = "0" ] || [ -z "${remaining}" ]; then
  echo ""
  echo "IAMS camera relay stopped."
else
  echo ""
  echo "WARN: ${remaining} related processes still running after SIGKILL." >&2
  ps -A -o pid,comm,args 2>/dev/null | grep -E "iams-cam-relay|rtsp://admin:%40Iams2026" | grep -v grep >&2
  exit 1
fi
