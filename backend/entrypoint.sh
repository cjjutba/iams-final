#!/bin/sh
# Fix ownership of Docker-mounted volumes (they mount as root).
# The app runs as appuser but needs write access to several paths:
#   /app/data  — FAISS index, face uploads, HLS segments
#   /app/logs  — rotating file handler
#   /home/appuser/.insightface  — first-run model downloads (buffalo_s.zip etc.)
#                                 Forgetting this path leaves insightface unable
#                                 to persist its downloaded weights, which
#                                 silently breaks the whole detection pipeline
#                                 (PermissionError → "Failed to initialize face
#                                 recognition" — documented 2026-04-22).
#   /var/lib/iams/crops  — recognition-evidence JPEG pairs (Phase 1 of the
#                          recognition-evidence plan, 2026-04-24).
mkdir -p /var/lib/iams/crops 2>/dev/null || true
chown -R appuser:appuser /app/data /app/logs /home/appuser/.insightface /var/lib/iams/crops 2>/dev/null || true

exec gosu appuser uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips "*" \
    --log-level info
