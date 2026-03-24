#!/bin/bash
# Wipe all user data and reseed with JRMSU school data
#
# Usage: ./scripts/db-reset.sh
#        ./scripts/db-reset.sh --no-sim   # Skip simulation data

set -e

echo "Wiping user data..."
docker compose exec -T api-gateway python -m scripts.wipe_user_data --confirm

echo ""
echo "Seeding JRMSU school data..."
docker compose exec -T api-gateway python -m scripts.seed_all "$@"

echo ""
echo "Done. Database reset and reseeded with JRMSU data."
