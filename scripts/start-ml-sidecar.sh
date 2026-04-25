#!/bin/bash
# Start the IAMS ML sidecar in the background, detached from the current TTY.
# Mirrors scripts/start-cam-relay.sh's pattern (nohup + disown + PID file).
#
# Usage:
#   ./scripts/start-ml-sidecar.sh        # start (or restart)
#   ./scripts/stop-ml-sidecar.sh         # stop
#
# Logs: ~/Library/Logs/iams-ml-sidecar.log
# Lifecycle: survives terminal close. Dies on Mac sleep with networking
# down, manual kill, or reboot.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SUPERVISOR="${REPO_ROOT}/scripts/iams-ml-sidecar.sh"
LOG_FILE="${HOME}/Library/Logs/iams-ml-sidecar.log"
PID_FILE="${HOME}/Library/Application Support/iams/ml-sidecar.pid"
HEALTH_URL="http://127.0.0.1:${ML_SIDECAR_PORT:-8001}/health"

mkdir -p "$(dirname "${LOG_FILE}")"
mkdir -p "$(dirname "${PID_FILE}")"

# Idempotent restart: stop any existing supervisor first.
if [ -f "${PID_FILE}" ]; then
  existing="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [ -n "${existing}" ] && kill -0 "${existing}" 2>/dev/null; then
    echo "Existing ML sidecar supervisor (pid ${existing}) — stopping first"
    kill -TERM "${existing}" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      kill -0 "${existing}" 2>/dev/null || break
      sleep 1
    done
    kill -KILL "${existing}" 2>/dev/null || true
  fi
fi
# Belt-and-braces: kill any orphan uvicorn matching our sidecar path.
# Narrow pattern: matches main:app launched from backend/ml-sidecar.
pkill -TERM -f "uvicorn main:app.*--port[ =]${ML_SIDECAR_PORT:-8001}" 2>/dev/null || true
sleep 1
pkill -KILL -f "uvicorn main:app.*--port[ =]${ML_SIDECAR_PORT:-8001}" 2>/dev/null || true

if [ ! -x "${SUPERVISOR}" ]; then
  chmod +x "${SUPERVISOR}"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') === ml-sidecar started by start-ml-sidecar.sh ===" >> "${LOG_FILE}"
nohup "${SUPERVISOR}" >> "${LOG_FILE}" 2>&1 < /dev/null &
SUP_PID=$!
disown "${SUP_PID}"
echo "${SUP_PID}" > "${PID_FILE}"

# Wait up to ~30 s for /health to come back ready. Model load is ~8s
# cold, plus FastAPI startup ~1-2 s. 30s gives margin for slower disk.
echo "Waiting for ML sidecar /health..."
ready=0
for i in $(seq 1 30); do
  if curl -sf "${HEALTH_URL}" > /dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done

if [ "${ready}" = "1" ]; then
  echo ""
  echo "=========================================="
  echo "  IAMS ML sidecar started"
  echo "=========================================="
  echo ""
  echo "  Supervisor pid:   ${SUP_PID}"
  echo "  Listening on:     ${HEALTH_URL}"
  echo "  Log file:         ${LOG_FILE}"
  echo "  PID file:         ${PID_FILE}"
  echo ""
  echo "  Tail the logs:    tail -f ${LOG_FILE}"
  echo "  Stop the sidecar: ./scripts/stop-ml-sidecar.sh"
  echo ""
  # Show the provider summary so the operator confirms CoreML delegated.
  echo "  Provider report:"
  curl -sf "${HEALTH_URL}" 2>/dev/null \
    | python3 -c "import sys, json; r = json.load(sys.stdin); [print('    %s → %s' % (p['task'], ', '.join(p['providers']))) for p in r.get('providers', [])]" \
    || echo "    (could not parse /health body)"
  echo ""
else
  echo "" >&2
  echo "ERROR: ML sidecar /health didn't come up within 30 s" >&2
  echo "  Check ${LOG_FILE} for startup errors." >&2
  if kill -0 "${SUP_PID}" 2>/dev/null; then
    echo "  Supervisor pid ${SUP_PID} is still alive — leaving it running so you can investigate." >&2
  fi
  exit 1
fi
