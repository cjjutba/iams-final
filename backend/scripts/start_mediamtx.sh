#!/usr/bin/env bash
# backend/scripts/start_mediamtx.sh
# Run mediamtx alongside FastAPI for local development.
# Usage: ./scripts/start_mediamtx.sh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BINARY="$SCRIPT_DIR/bin/mediamtx"
CONFIG="$SCRIPT_DIR/mediamtx.yml"

if [ ! -f "$BINARY" ]; then
  echo "ERROR: mediamtx binary not found at $BINARY"
  echo "Download from https://github.com/bluenviron/mediamtx/releases"
  exit 1
fi

echo "Starting mediamtx..."
exec "$BINARY" "$CONFIG"
