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

# Static-shape ONNX re-export for the CoreML execution provider (live-feed
# plan 2026-04-25 Step 2b). Idempotent — the script exits 0 without doing
# work when a matching export already exists in
# ~/.insightface/models/buffalo_l_static. We run it under appuser so the
# output files are owned correctly. ``ENABLE_ML=false`` (VPS thin profile)
# skips this entirely because there is no ML dir to write to and no
# model loader to verify the work.
if [ "${ENABLE_ML:-true}" != "false" ]; then
    # DETECTOR_ONNX_FILENAME (Phase 4a): set to scrfd_34g.onnx to swap
    # in the heavier SCRFD detector. Defaults to det_10g.onnx (the
    # buffalo_l pack's stock detector). When swapping, drop the
    # downloaded scrfd_34g.onnx into ~/.insightface/models/buffalo_l/
    # first — the export script raises a clear error if it's missing.
    INSIGHTFACE_DET_SIZE="${INSIGHTFACE_DET_SIZE:-640}" \
    INSIGHTFACE_STATIC_PACK_NAME="${INSIGHTFACE_STATIC_PACK_NAME:-buffalo_l_static}" \
    DETECTOR_ONNX_FILENAME="${DETECTOR_ONNX_FILENAME:-det_10g.onnx}" \
    gosu appuser python -m scripts.export_static_models \
        || echo "[entrypoint] static-shape ONNX export failed; will run on CPU EP fallback" >&2
fi

exec gosu appuser uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips "*" \
    --log-level info
