#!/bin/bash
# Run scripts.export_static_models on the host so the ML sidecar can find a
# matching static-shape ONNX pack on first boot.
#
# Why this exists
# ---------------
# `backend/entrypoint.sh` already runs the exporter inside the api-gateway
# container. That works fine for the gateway's in-process model fallback,
# but the **sidecar** (backend/ml-sidecar/main.py) runs natively on the
# host and reads `~/.insightface/models/` directly. After bumping
# INSIGHTFACE_DET_SIZE in .env.onprem, the container will re-export on its
# next boot and write to the host-mounted volume; the sidecar then sees
# the new pack on the next sidecar restart. But if the sidecar boots
# BEFORE the container (which scripts/onprem-up.sh does — see the ML
# sidecar start as step one), it'll find a stale pack with the old shape
# and load InsightFace with that. SCRFD then runs at the OLD det_size,
# losing the recall improvement Phase 1 was meant to deliver.
#
# This script is the host-side companion that produces the new pack
# *before* the sidecar reads it. It is idempotent: if the on-disk sidecar
# JSON marker matches the requested shape, the underlying exporter exits
# 0 without doing work.
#
# Usage
# -----
#     INSIGHTFACE_DET_SIZE=1280 ./scripts/export-static-models.sh
#
# Honours the same env vars as backend/scripts/export_static_models.py:
#   INSIGHTFACE_DET_SIZE          (default 640)
#   INSIGHTFACE_STATIC_PACK_NAME  (default buffalo_l_static)
#   INSIGHTFACE_HOME              (default ~/.insightface)
#
# Sourced by scripts/start-ml-sidecar.sh before the supervisor launches,
# so an operator who runs `./scripts/start-ml-sidecar.sh` after editing
# .env.onprem doesn't have to remember a separate re-export step.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
VENV_PYTHON="${BACKEND_DIR}/venv/bin/python"

# Read .env.onprem so the operator-facing source of truth (the same file
# that drives the Docker container) is also the source of truth here.
# Only the relevant vars are extracted — we don't want POSTGRES_PASSWORD
# etc. leaking into this shell.
ENV_FILE="${BACKEND_DIR}/.env.onprem"
if [ -f "${ENV_FILE}" ]; then
  while IFS='=' read -r key value; do
    case "${key}" in
      INSIGHTFACE_DET_SIZE|INSIGHTFACE_STATIC_PACK_NAME|INSIGHTFACE_MODEL|DETECTOR_ONNX_FILENAME)
        # Trim surrounding whitespace + quotes if any.
        value="${value%\"}"
        value="${value#\"}"
        export "${key}=${value}"
        ;;
    esac
  done < <(grep -E '^(INSIGHTFACE_DET_SIZE|INSIGHTFACE_STATIC_PACK_NAME|INSIGHTFACE_MODEL|DETECTOR_ONNX_FILENAME)=' "${ENV_FILE}" || true)
fi

# Apply documented defaults if .env.onprem doesn't set them.
export INSIGHTFACE_DET_SIZE="${INSIGHTFACE_DET_SIZE:-1280}"
export INSIGHTFACE_STATIC_PACK_NAME="${INSIGHTFACE_STATIC_PACK_NAME:-buffalo_l_static}"
export INSIGHTFACE_MODEL="${INSIGHTFACE_MODEL:-buffalo_l}"
# Phase 4a: detector swap. det_10g.onnx (default) = SCRFD-10G,
# scrfd_34g.onnx = SCRFD-34G. The 34G ONNX must be downloaded
# separately and dropped into ~/.insightface/models/buffalo_l/.
export DETECTOR_ONNX_FILENAME="${DETECTOR_ONNX_FILENAME:-det_10g.onnx}"

if [ ! -x "${VENV_PYTHON}" ]; then
  echo "FATAL: ${VENV_PYTHON} not found. Set up the macOS-native venv first:" >&2
  echo "  python3 -m venv backend/venv" >&2
  echo "  backend/venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

# `app.config` validates a Settings model that requires DATABASE_URL.
# The exporter only needs the InsightFace path resolution + ONNX tooling;
# satisfy the validator with a sentinel like the sidecar does.
export DATABASE_URL="${DATABASE_URL:-sqlite:///export-static-models-not-used.db}"
export ENABLE_REDIS="${ENABLE_REDIS:-false}"
export ENABLE_BACKGROUND_JOBS="${ENABLE_BACKGROUND_JOBS:-false}"

echo "$(date '+%Y-%m-%d %H:%M:%S') [export-static-models] det_size=${INSIGHTFACE_DET_SIZE} pack=${INSIGHTFACE_STATIC_PACK_NAME}"

# Run from backend/ so the package import path resolves; the script
# itself prints the resulting pack directory on stdout.
cd "${BACKEND_DIR}"
"${VENV_PYTHON}" -m scripts.export_static_models
