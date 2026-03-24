#!/bin/bash
# Wipe all data and reseed the database (Docker stays running)
#
# Usage: ./scripts/db-reset.sh

set -e

echo "Wiping all data and reseeding..."
docker compose exec -T postgres psql -U admin -d iams -f /docker-entrypoint-initdb.d/reset.sql
echo ""
echo "Done. Database has been reset and reseeded."
