"""
IAMS ML Sidecar — native macOS inference server.

Why this exists
---------------
The api-gateway runs inside a Linux Docker container. ONNX Runtime built
for Linux does NOT ship with the CoreMLExecutionProvider, so InsightFace
(SCRFD + ArcFace) gets pinned to ``CPUExecutionProvider`` even on an M5
host with a perfectly capable Apple Neural Engine + Metal GPU. The
gateway's effective throughput tops out around 1-2 fps in classroom
conditions because of this.

This sidecar is a thin FastAPI process meant to run **directly on
macOS** (no Docker), where ONNX Runtime's CoreML EP is available. It
loads the same ``buffalo_l_static`` model pack the gateway uses, exposes
two HTTP endpoints (``/detect`` and ``/embed``), and the gateway proxies
its realtime-path calls here.

Boundary
--------
- Stateless inference. No DB, no FAISS, no ByteTrack — those stay in the
  gateway. The sidecar's only job is to turn pixels into bounding boxes
  and embeddings.
- Loopback only. Listens on ``127.0.0.1`` by default. The gateway in
  Docker reaches it via ``host.docker.internal:8001``. Not reachable
  from outside the host.
- Idempotent restarts. The supervisor script restarts the process if it
  crashes; restart cost is the model load (~3-5s) plus a CoreML JIT
  warmup pass (~3-5s). The gateway tolerates the gap by falling back to
  the in-container CPU model — see ``RemoteInsightFaceModel`` in the
  gateway for the failover policy.

Endpoints
---------
``GET  /health``   — readiness probe. 200 with model status + provider list.
``POST /detect``   — input: JPEG bytes (multipart). Output: list of detections
                     (bbox, score, kps).
``POST /embed``    — input: JPEG bytes + kps. Output: 512-d L2-normalized
                     ArcFace embedding.

Run locally
-----------
::

    cd backend/ml-sidecar
    PYTHONPATH=.. ../venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001

The on-prem stack expects ``scripts/start-ml-sidecar.sh`` to bring this
up before the api-gateway boots — see ``scripts/onprem-up.sh``.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# Make the sibling ``app`` package importable so we can reuse the
# gateway's already-tuned ``InsightFaceModel`` rather than duplicating
# the SCRFD + ArcFace plumbing here. The sidecar imports it the same way
# unit tests do — ``backend/`` on the path, ``app.services.ml...`` from
# there.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ``app.config`` validates a Settings model that requires
# ``DATABASE_URL``; the sidecar doesn't touch the database, so satisfy
# the validator with a sentinel before the import. Real DB / Redis /
# secret config lives in the gateway, not here.
os.environ.setdefault("DATABASE_URL", "sqlite:///ml-sidecar-not-used.db")
# Disable everything ``InsightFaceModel`` doesn't need so the gateway's
# Settings model doesn't try to bring up Redis pool / FAISS reload
# subscribers / etc. when imported.
os.environ.setdefault("ENABLE_REDIS", "false")
os.environ.setdefault("ENABLE_BACKGROUND_JOBS", "false")
os.environ.setdefault("ENABLE_RECOGNITION_EVIDENCE", "false")
os.environ.setdefault("ENABLE_RECOGNITION_EVIDENCE_RETENTION", "false")

from app.services.ml.insightface_model import InsightFaceModel  # noqa: E402

# ----------------------------------------------------------------------
# Logging — separate channel from the gateway, written by the supervisor
# script to ``~/Library/Logs/iams-ml-sidecar.log``.
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - ml-sidecar - %(message)s",
)
logger = logging.getLogger("ml-sidecar")

# ----------------------------------------------------------------------
# Module-level model. One instance per worker — uvicorn is launched
# single-worker by the supervisor so this is also the global instance.
# ----------------------------------------------------------------------
_model: InsightFaceModel | None = None
_model_load_seconds: float = 0.0
_provider_summary: list[dict] = []


def _decode_jpeg(jpeg_bytes: bytes) -> np.ndarray:
    """Decode JPEG bytes to BGR ndarray. 400 on bad input."""
    if not jpeg_bytes:
        raise HTTPException(status_code=400, detail="empty body")
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="cannot decode image")
    return img


def _summarise_providers(model: InsightFaceModel) -> list[dict]:
    """Best-effort introspection of which EP each ONNX session picked.

    The point of the sidecar is that SCRFD lands on
    ``CoreMLExecutionProvider``; this surface lets ``/health`` confirm it
    boot-side instead of having to grep the launch log. If introspection
    fails the list comes back empty — not an error, just a missing nice-
    to-have.
    """
    out: list[dict] = []
    if model.app is None:
        return out
    try:
        for task_name, m in model.app.models.items():
            sess = getattr(m, "session", None)
            providers = sess.get_providers() if sess is not None else []
            out.append({"task": task_name, "providers": providers})
    except Exception:
        logger.debug("Provider introspection failed", exc_info=True)
    return out


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: D401 — fastapi lifespan signature
    """Load InsightFace at startup, run a JIT warmup pass."""
    global _model, _model_load_seconds, _provider_summary

    logger.info("Loading InsightFace model on macOS-native runtime...")
    t0 = time.monotonic()
    model = InsightFaceModel()
    model.load_model()
    _model = model
    _model_load_seconds = time.monotonic() - t0
    logger.info("InsightFace model loaded in %.1fs", _model_load_seconds)

    _provider_summary = _summarise_providers(model)
    for entry in _provider_summary:
        logger.info("[provider] %s → %s", entry["task"], entry["providers"])

    # JIT both SCRFD and (best-effort) ArcFace before serving traffic.
    # The gateway hits us cold on the first session-pipeline tick; without
    # this warmup that first call costs an extra 3-5s.
    try:
        model.warmup()
        logger.info("Sidecar warmup pass complete")
    except Exception:
        logger.exception("Sidecar warmup pass failed (non-fatal)")

    yield

    # Nothing to drain on shutdown — InsightFace owns no Python-side state
    # besides the loaded sessions.
    logger.info("ML sidecar shutdown complete")


app = FastAPI(
    title="IAMS ML Sidecar",
    description="Native CoreML/ANE inference server for IAMS face recognition",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------


@app.get("/health")
async def health() -> JSONResponse:
    """Readiness + per-model EP report.

    The gateway calls this once at startup; if the model isn't loaded yet
    or any model fell back to CPU when CoreML was expected, the response
    still reports 200 but ``status`` reflects the situation. The gateway
    decides whether to degrade or use the sidecar based on this body.
    """
    if _model is None or _model.app is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "loading",
                "model_loaded": False,
                "providers": [],
            },
        )
    return JSONResponse(
        content={
            "status": "ready",
            "model_loaded": True,
            "model_load_seconds": round(_model_load_seconds, 2),
            "providers": _provider_summary,
            "det_size": list(_model._det_size),
            "model_name": _model._model_name,
        }
    )


@app.post("/detect")
async def detect(request: Request) -> JSONResponse:
    """Run SCRFD on a JPEG-encoded frame and return raw bbox + kps + score.

    Body: ``application/octet-stream`` JPEG bytes. Sent as raw body so the
    gateway can ``cv2.imencode`` once and ``httpx.post(content=...)`` —
    no multipart, no base64.
    """
    if _model is None or _model.app is None:
        raise HTTPException(status_code=503, detail="model not ready")
    jpeg = await request.body()
    frame = _decode_jpeg(jpeg)

    t0 = time.perf_counter()
    detections = _model.detect(frame)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return JSONResponse(
        content={
            "detections": [
                {
                    "bbox": d["bbox"].tolist(),
                    "det_score": d["det_score"],
                    "kps": d["kps"].tolist() if d["kps"] is not None else None,
                }
                for d in detections
            ],
            "det_ms": round(elapsed_ms, 2),
        }
    )


@app.post("/embed")
async def embed(request: Request) -> JSONResponse:
    """Run ArcFace on N faces in one frame, returning N L2-normalised embeddings.

    Body: JSON of the form
    ``{"jpeg_b64": "<base64 jpeg>", "kps": [[[x,y]*5], [[x,y]*5], ...]}``
    where each kps entry is the 5-point landmark array SCRFD returned
    for that face. Caller is responsible for the alignment between
    frame and kps coordinates.

    Why one batch endpoint instead of N single-face calls: when the
    realtime tracker has 3 faces needing embeddings on the same frame,
    sending the frame 3× is wasteful. Batching is one round-trip,
    one JPEG decode on this side, N ArcFace inferences.
    """
    if _model is None or _model.app is None:
        raise HTTPException(status_code=503, detail="model not ready")

    body = await request.json()
    jpeg_b64 = body.get("jpeg_b64")
    kps_list = body.get("kps", [])
    if not jpeg_b64 or not isinstance(kps_list, list):
        raise HTTPException(status_code=400, detail="jpeg_b64 + kps required")

    import base64

    try:
        jpeg = base64.b64decode(jpeg_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"bad jpeg_b64: {exc}") from exc
    frame = _decode_jpeg(jpeg)

    embeddings: list[list[float]] = []
    t0 = time.perf_counter()
    for kps in kps_list:
        kps_arr = np.asarray(kps, dtype=np.float32)
        if kps_arr.shape != (5, 2):
            raise HTTPException(
                status_code=400,
                detail=f"kps must be [5,2]; got {kps_arr.shape}",
            )
        emb = _model.embed_from_kps(frame, kps_arr)
        embeddings.append(emb.tolist())
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return JSONResponse(
        content={
            "embeddings": embeddings,
            "embed_ms": round(elapsed_ms, 2),
            "count": len(embeddings),
        }
    )


# ----------------------------------------------------------------------
# Direct run (dev convenience). In production, use the supervisor script.
# ----------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("ML_SIDECAR_HOST", "127.0.0.1")
    port = int(os.environ.get("ML_SIDECAR_PORT", "8001"))
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )
