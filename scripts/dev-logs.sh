#!/bin/bash
# Tail IAMS container logs
# Usage: ./scripts/dev-logs.sh                    # all services
#        ./scripts/dev-logs.sh api-gateway         # single service
#        ./scripts/dev-logs.sh detection-worker     # single service
cd "$(dirname "$0")/.."
docker compose logs -f "$@"
