#!/bin/bash
# scripts/pull-and-restart.sh
#
# Post-pull bootstrap for the on-prem stack.
#
# Run on the deploy host (typically the TUF) AFTER `git pull` to restart
# only the services whose source files actually changed. Avoids the heavy
# `onprem-down.sh + onprem-up.sh` cycle when only one or two files moved.
#
# How it detects changes:
#   `git diff HEAD@{1} HEAD` — HEAD@{1} is the previous tip (pre-pull),
#   written automatically into the reflog by `git pull`. If HEAD@{1} doesn't
#   exist (fresh clone, never pulled) the script exits as a no-op rather
#   than rebuilding everything.
#
# Restart matrix:
#   backend/Dockerfile, backend/requirements*.txt, backend/entrypoint*.sh
#       → docker compose up -d --build api-gateway
#   backend/alembic/versions/*
#       → restart api-gateway + run `alembic upgrade head`
#   backend/app/**/*.py and other backend/* code
#       → restart api-gateway
#   admin/**/*  (any frontend code or config)
#       → re-run admin-build sidecar + restart nginx
#   scripts/iams-cam-relay.sh
#       → stop/start cam-relay supervisor
#   deploy/mediamtx*.yml
#       → restart mediamtx + cam-relay (so ffmpeg republishes)
#   deploy/docker-compose*.yml, deploy/nginx*.conf
#       → docker compose up -d  (recreates only the services whose config
#         actually diverged; cheaper than full down/up)
#
# Anything else (docs, tests, mobile app, etc.) — no action.
#
# Usage:
#   git pull
#   ./scripts/pull-and-restart.sh
#
# Or one-liner:
#   git pull && ./scripts/pull-and-restart.sh

set -euo pipefail

# ── Locate repo root regardless of where the script is invoked from ─────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_FILE="deploy/docker-compose.onprem.yml"
COMPOSE="docker compose -f $COMPOSE_FILE"
API_CONTAINER="iams-api-gateway-onprem"

# ── Source the per-operator secrets so compose has POSTGRES_PASSWORD etc. ───
# (matches the convention used by onprem-up.sh / onprem-down.sh)
if [ -f "scripts/.env.local" ]; then
  set -a
  # shellcheck source=/dev/null
  . scripts/.env.local
  set +a
fi

# ── Detect changed files since previous HEAD ────────────────────────────────
if ! git rev-parse 'HEAD@{1}' >/dev/null 2>&1; then
  echo "No previous HEAD position in reflog — nothing to compare."
  echo "Did you just clone? Run ./scripts/onprem-up.sh for a clean boot."
  exit 0
fi

CHANGED=$(git diff --name-only 'HEAD@{1}' HEAD || true)

if [ -z "$CHANGED" ]; then
  echo "No file changes between HEAD@{1} and HEAD. Nothing to restart."
  exit 0
fi

echo "Files changed since previous HEAD:"
echo "$CHANGED" | sed 's/^/  /'
echo

# ── Classify changes ────────────────────────────────────────────────────────
NEED_BACKEND_REBUILD=false
NEED_BACKEND_RESTART=false
NEED_MIGRATIONS=false
NEED_FRONTEND_REBUILD=false
NEED_RELAY=false
NEED_MEDIAMTX_RESTART=false
NEED_COMPOSE_RECREATE=false

while IFS= read -r f; do
  case "$f" in
    backend/Dockerfile|backend/requirements*.txt|backend/entrypoint*.sh)
      NEED_BACKEND_REBUILD=true ;;
    backend/alembic/versions/*)
      NEED_MIGRATIONS=true
      NEED_BACKEND_RESTART=true ;;
    backend/*)
      NEED_BACKEND_RESTART=true ;;
    admin/*)
      NEED_FRONTEND_REBUILD=true ;;
    scripts/iams-cam-relay.sh)
      NEED_RELAY=true ;;
    deploy/mediamtx*.yml)
      NEED_MEDIAMTX_RESTART=true
      NEED_RELAY=true ;;
    deploy/docker-compose*.yml|deploy/nginx*.conf)
      NEED_COMPOSE_RECREATE=true ;;
  esac
done <<< "$CHANGED"

# ── Execute (most invasive first so a single full recreate covers everything) ─
DID_SOMETHING=false

if $NEED_COMPOSE_RECREATE; then
  echo "==> Compose / nginx config changed — recreating affected services"
  $COMPOSE up -d
  DID_SOMETHING=true
  # `up -d` will pick up Dockerfile/requirements rebuilds via --build only if
  # asked. If both flags are needed, do the rebuild explicitly first.
  if $NEED_BACKEND_REBUILD; then
    echo "==> ...and rebuilding api-gateway image"
    $COMPOSE up -d --build api-gateway
  fi
elif $NEED_BACKEND_REBUILD; then
  echo "==> Backend Dockerfile / requirements changed — rebuilding api-gateway"
  $COMPOSE up -d --build api-gateway
  DID_SOMETHING=true
elif $NEED_BACKEND_RESTART; then
  echo "==> Backend code changed — restarting api-gateway"
  $COMPOSE restart api-gateway
  DID_SOMETHING=true
fi

if $NEED_MIGRATIONS; then
  echo "==> Alembic migration added — running upgrade head"
  # api-gateway must be up for this; restart above already ensures that.
  # Wait briefly for it to be ready before invoking alembic.
  sleep 3
  docker exec "$API_CONTAINER" alembic upgrade head
  DID_SOMETHING=true
fi

if $NEED_FRONTEND_REBUILD; then
  echo "==> Admin code changed — rebuilding SPA + restarting nginx"
  $COMPOSE run --rm admin-build
  $COMPOSE restart nginx
  DID_SOMETHING=true
fi

if $NEED_MEDIAMTX_RESTART; then
  echo "==> Mediamtx config changed — restarting mediamtx"
  $COMPOSE restart mediamtx
  DID_SOMETHING=true
fi

if $NEED_RELAY; then
  echo "==> Camera relay script (or mediamtx) changed — restarting supervisor"
  ./scripts/stop-cam-relay.sh || true
  ./scripts/start-cam-relay.sh
  DID_SOMETHING=true
fi

if ! $DID_SOMETHING; then
  echo "Files changed, but none required a restart (docs, tests, mobile, etc.)."
fi

echo
echo "Done."
