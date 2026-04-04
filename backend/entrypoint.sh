#!/bin/sh
# Fix ownership of Docker-mounted volumes (they mount as root).
# The app runs as appuser but needs write access to data/ and logs/.
chown -R appuser:appuser /app/data /app/logs 2>/dev/null || true

exec gosu appuser uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips "*" \
    --log-level info
