#!/bin/bash
# Stop the IAMS ML sidecar started by scripts/start-ml-sidecar.sh.
# Mirrors stop-cam-relay's two-phase SIGTERM → SIGKILL pattern.

set -euo pipefail

PID_FILE="${HOME}/Library/Application Support/iams/ml-sidecar.pid"
PORT="${ML_SIDECAR_PORT:-8001}"

# Stop supervisor via PID file if available.
if [ -f "${PID_FILE}" ]; then
  pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
    echo "Sending SIGTERM to ML sidecar supervisor pid ${pid}..."
    kill -TERM "${pid}" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "${pid}" 2>/dev/null; then
      echo "Supervisor didn't exit — sending SIGKILL"
      kill -KILL "${pid}" 2>/dev/null || true
    fi
  fi
  rm -f "${PID_FILE}"
else
  echo "No PID file at ${PID_FILE} — falling through to pattern scan."
fi

# Belt-and-braces: catch the supervisor + any orphan uvicorn workers.
pkill -TERM -f "iams-ml-sidecar.sh" 2>/dev/null || true
pkill -TERM -f "uvicorn main:app.*--port[ =]${PORT}" 2>/dev/null || true
sleep 2
pkill -KILL -f "iams-ml-sidecar.sh" 2>/dev/null || true
pkill -KILL -f "uvicorn main:app.*--port[ =]${PORT}" 2>/dev/null || true

remaining=$(pgrep -fc "iams-ml-sidecar.sh|uvicorn main:app.*--port[ =]${PORT}" 2>/dev/null || echo 0)
if [ "${remaining}" = "0" ] || [ -z "${remaining}" ]; then
  echo ""
  echo "IAMS ML sidecar stopped."
else
  echo ""
  echo "WARN: ${remaining} related processes still running after SIGKILL." >&2
  ps -A -o pid,comm,args 2>/dev/null | grep -E "iams-ml-sidecar|uvicorn main:app.*${PORT}" | grep -v grep >&2
  exit 1
fi
