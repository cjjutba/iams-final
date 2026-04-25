#!/bin/bash
# IAMS ML Sidecar — supervisor for the native macOS InsightFace process.
#
# Why this exists
# ---------------
# The api-gateway runs in a Linux Docker container; ONNX Runtime there
# only ships with `CPUExecutionProvider`, so the M5's Apple Neural Engine
# + Metal GPU can't be reached. This supervisor launches a thin FastAPI
# process (backend/ml-sidecar/main.py) directly on macOS where ONNX
# Runtime's `CoreMLExecutionProvider` is available and delegates SCRFD
# + ArcFace to the ANE / GPU. The gateway proxies its realtime ML calls
# here via host.docker.internal:8001.
#
# Same lifecycle pattern as scripts/iams-cam-relay.sh:
#   - Loop forever: launch uvicorn → wait for exit → restart in 3 s.
#   - Trap SIGTERM/SIGINT to teardown cleanly so onprem-down.sh /
#     stop-ml-sidecar.sh leave no orphans.
# We deliberately do NOT use launchd: macOS 26 TCC silently sandboxes
# unsigned binaries spawned by launchd in ways that don't apply to
# Terminal-spawned processes. The same reasoning as cam-relay.

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SIDECAR_DIR="${REPO_ROOT}/backend/ml-sidecar"
VENV_PYTHON="${REPO_ROOT}/backend/venv/bin/python"
HOST="${ML_SIDECAR_HOST:-127.0.0.1}"
PORT="${ML_SIDECAR_PORT:-8001}"

if [ ! -x "${VENV_PYTHON}" ]; then
  echo "FATAL: ${VENV_PYTHON} not found. Set up the macOS-native venv first:" >&2
  echo "  python3 -m venv backend/venv" >&2
  echo "  backend/venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi
if [ ! -f "${SIDECAR_DIR}/main.py" ]; then
  echo "FATAL: ${SIDECAR_DIR}/main.py not found." >&2
  exit 1
fi

# Track the running uvicorn PID for the cleanup trap. Re-set per loop
# iteration so SIGTERM during a restart-sleep doesn't try to kill a stale PID.
CHILD_PID=0

cleanup() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') [ml-sidecar] caught signal — stopping uvicorn pid=${CHILD_PID}"
  if [ "${CHILD_PID}" != "0" ]; then
    # SIGTERM the process group so any worker subprocesses die too.
    kill -TERM -"${CHILD_PID}" 2>/dev/null || kill -TERM "${CHILD_PID}" 2>/dev/null || true
    # Give uvicorn a moment to drain its accept queue + flush logs.
    for _ in 1 2 3 4 5; do
      kill -0 "${CHILD_PID}" 2>/dev/null || break
      sleep 1
    done
    kill -KILL "${CHILD_PID}" 2>/dev/null || true
  fi
  exit 0
}
trap cleanup SIGTERM SIGINT SIGHUP

echo "$(date '+%Y-%m-%d %H:%M:%S') [ml-sidecar] supervisor starting on ${HOST}:${PORT}"

# The sidecar lives at backend/ml-sidecar/main.py. uvicorn needs to import
# it as `main:app`, so we cd into the sidecar dir and put `backend/` on
# PYTHONPATH so `from app.services.ml.insightface_model import ...` works.
cd "${SIDECAR_DIR}"
export PYTHONPATH="${REPO_ROOT}/backend"

# Pin model config via env. Matches backend/.env.onprem so behaviour is
# identical to the in-process model when the sidecar is healthy.
# INSIGHTFACE_DET_SIZE / INSIGHTFACE_DET_THRESH / INSIGHTFACE_STATIC_PACK_NAME
# can be overridden by the launcher if the operator wants to test alternate
# values without touching .env.onprem.
export INSIGHTFACE_MODEL="${INSIGHTFACE_MODEL:-buffalo_l}"
export INSIGHTFACE_STATIC_PACK_NAME="${INSIGHTFACE_STATIC_PACK_NAME:-buffalo_l_static}"
export INSIGHTFACE_DET_SIZE="${INSIGHTFACE_DET_SIZE:-960}"
export INSIGHTFACE_DET_THRESH="${INSIGHTFACE_DET_THRESH:-0.3}"
# `app.config.Settings` requires DATABASE_URL even though the sidecar
# never touches it. main.py also sets a sentinel default, but doing it
# here keeps the env explicit when someone tails the supervisor log.
export DATABASE_URL="${DATABASE_URL:-sqlite:///ml-sidecar-not-used.db}"
# Disable everything the gateway uses but the sidecar shouldn't.
export ENABLE_REDIS="false"
export ENABLE_BACKGROUND_JOBS="false"
export ENABLE_RECOGNITION_EVIDENCE="false"
export ENABLE_RECOGNITION_EVIDENCE_RETENTION="false"

while true; do
  echo "$(date '+%Y-%m-%d %H:%M:%S') [ml-sidecar] launching uvicorn (model=${INSIGHTFACE_MODEL}/${INSIGHTFACE_STATIC_PACK_NAME}, det_size=${INSIGHTFACE_DET_SIZE})"

  # Use `setsid`-like behaviour by spawning in a fresh process group so
  # the trap can SIGTERM the whole group cleanly. macOS doesn't ship
  # setsid; `setpgrp` via Python is simpler and portable.
  "${VENV_PYTHON}" -c "
import os
os.setpgrp()
os.execvp('${VENV_PYTHON}', [
    '${VENV_PYTHON}',
    '-m', 'uvicorn',
    'main:app',
    '--host', '${HOST}',
    '--port', '${PORT}',
    '--log-level', 'info',
    '--no-access-log',
])
" &
  CHILD_PID=$!
  echo "$(date '+%Y-%m-%d %H:%M:%S') [ml-sidecar] uvicorn pid=${CHILD_PID}"

  # Wait for it to exit (it shouldn't unless something crashes).
  wait "${CHILD_PID}"
  rc=$?
  CHILD_PID=0
  echo "$(date '+%Y-%m-%d %H:%M:%S') [ml-sidecar] uvicorn exited rc=${rc} — restart in 3 s"
  sleep 3
done
