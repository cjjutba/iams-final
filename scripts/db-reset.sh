#!/bin/bash
# Reset database and seed all IAMS data from scratch.
#
# Usage: ./scripts/db-reset.sh

set -e

echo "Resetting and seeding IAMS database..."
docker compose exec -T api-gateway python -m scripts.seed_data

echo ""
echo "Done. Database reset and seeded with JRMSU data."
