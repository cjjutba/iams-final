#!/bin/bash
# IAMS Backend - Stop Production Server
# This script gracefully stops the backend service

set -e

echo "========================================"
echo "IAMS Backend - Stopping Production Server"
echo "========================================"
echo ""

# Check if running via systemd
if systemctl is-active --quiet iams-backend.service 2>/dev/null; then
    echo "Stopping systemd service..."
    sudo systemctl stop iams-backend.service
    echo "✓ Service stopped"
else
    # Find and kill uvicorn processes
    echo "Looking for running uvicorn processes..."
    pids=$(pgrep -f "uvicorn.*app.main:app" || true)

    if [ -z "$pids" ]; then
        echo "No running processes found"
    else
        echo "Found processes: $pids"
        echo "Sending SIGTERM (graceful shutdown)..."
        kill -TERM $pids

        # Wait for graceful shutdown
        sleep 2

        # Check if still running
        pids=$(pgrep -f "uvicorn.*app.main:app" || true)
        if [ ! -z "$pids" ]; then
            echo "Processes still running. Sending SIGKILL..."
            kill -KILL $pids
        fi

        echo "✓ Processes stopped"
    fi
fi

echo ""
echo "========================================"
echo "Backend stopped successfully"
echo "========================================"
