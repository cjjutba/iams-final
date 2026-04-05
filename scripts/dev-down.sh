#!/bin/bash
# Stop IAMS local development stack
cd "$(dirname "$0")/.."
docker compose down
