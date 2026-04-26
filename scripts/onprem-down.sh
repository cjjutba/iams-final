#!/bin/bash
# Stop the IAMS ON-PREM stack (leaves volumes intact for quick restart).
#
# Usage:
#   ./scripts/onprem-down.sh           # stop containers, keep volumes
#   ./scripts/onprem-down.sh --purge   # also remove named volumes (wipes DB, FAISS, admin build)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_ROOT}"

COMPOSE_FILE="deploy/docker-compose.onprem.yml"

if [ "${1:-}" = "--purge" ]; then
  echo "Stopping and removing volumes (this wipes the onprem postgres + FAISS + admin build)…"
  docker compose -f "${COMPOSE_FILE}" down -v
else
  docker compose -f "${COMPOSE_FILE}" down
fi

# Stop the host-side ML sidecar too. Idempotent — no-op if it wasn't running.
echo ""
echo "Stopping ML sidecar..."
"${REPO_ROOT}/scripts/stop-ml-sidecar.sh" || true

echo ""
echo "IAMS on-prem stack stopped."
echo "To start again: ./scripts/onprem-up.sh"
