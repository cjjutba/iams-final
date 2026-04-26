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
``GET  /health``    — readiness probe. 200 with model status + provider list.
``POST /detect``    — input: JPEG bytes (multipart). Output: list of detections
                      (bbox, score, kps).
``POST /embed``     — input: JPEG bytes + kps. Output: 512-d L2-normalized
                      ArcFace embedding.
``POST /liveness``  — input: JPEG bytes + bboxes. Output: per-face liveness
                      score (fused MiniFASNet, real-class softmax).

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
from app.services.ml.liveness_model import (  # noqa: E402
    LivenessModel,
    LivenessModelUnavailable,
)

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

# Liveness is loaded lazily and may legitimately be missing — the operator
# runs ``scripts.export_liveness_models`` to populate the on-disk pack.
# When absent, ``/liveness`` returns 503 and the gateway treats the
# absence as "skip liveness gating" instead of refusing to start.
_liveness: LivenessModel | None = None
_liveness_load_error: str | None = None
_liveness_load_seconds: float = 0.0


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
    """Load InsightFace + liveness models at startup, run JIT warmup."""
    global _model, _model_load_seconds, _provider_summary
    global _liveness, _liveness_load_error, _liveness_load_seconds

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

    # ── Liveness (MiniFASNet) ───────────────────────────────────────
    # Loading is best-effort: a missing/incomplete on-disk pack is the
    # signal the operator hasn't run scripts.export_liveness_models yet,
    # not a fatal sidecar error. /liveness will return 503 and /health
    # will report liveness_loaded=false so the gateway can degrade
    # gracefully (skip liveness gating; recognition continues unchanged).
    t1 = time.monotonic()
    try:
        liveness = LivenessModel()
        liveness.load()
        liveness.warmup()
        _liveness = liveness
        _liveness_load_seconds = time.monotonic() - t1
        info = liveness.info
        logger.info(
            "Liveness pack loaded in %.1fs from %s — submodels=%s",
            _liveness_load_seconds,
            info.get("pack_dir"),
            [sm["name"] for sm in info.get("submodels", [])],
        )
    except LivenessModelUnavailable as exc:
        _liveness_load_error = str(exc)
        logger.warning(
            "Liveness pack not loaded — /liveness will return 503. Reason: %s",
            exc,
        )
    except Exception as exc:
        _liveness_load_error = f"unexpected error: {exc}"
        logger.exception("Liveness pack load crashed unexpectedly")

    yield

    # Nothing to drain on shutdown — InsightFace + Liveness own no Python-side
    # state besides the loaded sessions.
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
                "liveness": _liveness_health_payload(),
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
            # Liveness is reported on the same /health response so the
            # gateway needs only one round-trip to decide whether to
            # bind the realtime model AND the liveness model.
            "liveness": _liveness_health_payload(),
        }
    )


def _liveness_health_payload() -> dict:
    """Self-describing block embedded in /health for the liveness layer.

    Loaded → returns the pack info (paths, providers, scales). Not loaded
    → returns the unavailability reason so the operator can act without
    tailing logs. Either way the field is always present so the gateway
    can detect the absence reliably.
    """
    if _liveness is not None and _liveness.is_loaded:
        info = _liveness.info
        return {
            "loaded": True,
            "load_seconds": round(_liveness_load_seconds, 2),
            "pack_dir": info.get("pack_dir"),
            "submodels": info.get("submodels"),
        }
    return {
        "loaded": False,
        "load_seconds": 0.0,
        "error": _liveness_load_error or "not loaded",
    }


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


@app.post("/detect_tiled")
async def detect_tiled(request: Request) -> JSONResponse:
    """Run SCRFD on N tiles of a frame, merge with IOS-NMM, return globals.

    Distant-face plan 2026-04-26 Phase 3.

    Body: JSON with shape::

        {
          "jpeg_b64": "<base64 jpeg>",
          "tiles": [{"x0":0,"y0":0,"x1":640,"y1":1080}, ...],
          "include_coarse": true,
          "ios_thresh": 0.5
        }

    The gateway pre-computes tile rectangles using
    ``app.services.ml.tile_detection.compute_tile_rects`` and
    ``compute_motion_mask`` so motion-gating decisions stay on the
    gateway side (where they have full per-camera state context).
    The sidecar's job is purely: SCRFD-on-each-tile + merge.

    Returns the merged detection list in *original-frame* pixel space,
    same shape as ``/detect``'s response. Down-stream callers
    (``RealtimeTracker``) cannot tell whether the detections came
    from a single full-frame pass or N tiles + merge.

    Returns 503 when the model isn't ready, 400 on bad input. Errors
    inside per-tile inference are caught and the offending tile is
    skipped so a single bad tile doesn't kill the frame.
    """
    if _model is None or _model.app is None:
        raise HTTPException(status_code=503, detail="model not ready")

    body = await request.json()
    jpeg_b64 = body.get("jpeg_b64")
    tiles_in = body.get("tiles")
    if not jpeg_b64 or not isinstance(tiles_in, list):
        raise HTTPException(
            status_code=400,
            detail="jpeg_b64 + tiles required",
        )
    include_coarse = bool(body.get("include_coarse", True))
    ios_thresh = float(body.get("ios_thresh", 0.5))
    if not (0.0 < ios_thresh <= 1.0):
        raise HTTPException(
            status_code=400,
            detail=f"ios_thresh must be in (0, 1]; got {ios_thresh}",
        )

    import base64

    try:
        jpeg = base64.b64decode(jpeg_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"bad jpeg_b64: {exc}") from exc
    frame = _decode_jpeg(jpeg)
    frame_h, frame_w = frame.shape[:2]

    # Lazy import to avoid pulling tile_detection (and OpenCV BG-sub
    # symbols) into the sidecar process startup path. The sidecar
    # already has cv2 + numpy resident, so import cost is just the
    # Python-level module load.
    from app.services.ml.tile_detection import (  # noqa: E402
        TileRect,
        greedy_nmm_ios,
        letterbox_to_square,
        remap_detection,
    )

    # Validate tile shapes up-front. Bad input fails fast before we
    # spend SCRFD time on it.
    tiles: list[TileRect] = []
    for entry in tiles_in:
        try:
            tile = TileRect(
                x0=int(entry["x0"]),
                y0=int(entry["y0"]),
                x1=int(entry["x1"]),
                y1=int(entry["y1"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"bad tile rect {entry!r}: {exc}",
            ) from exc
        # Clamp to frame bounds — defensive, gateway should already
        # have produced inside-the-frame rectangles.
        if (
            tile.x0 < 0
            or tile.y0 < 0
            or tile.x1 > frame_w
            or tile.y1 > frame_h
            or tile.x1 <= tile.x0
            or tile.y1 <= tile.y0
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"tile {tile!r} out of frame bounds "
                    f"({frame_w}×{frame_h})"
                ),
            )
        tiles.append(tile)

    # The sidecar's SCRFD is bound at the static export's det_size.
    # Pull that off the loaded model so we letterbox each tile to the
    # exact same shape the ANE-bound graph expects.
    target_size = int(_model._det_size[0])

    detections_global: list[dict] = []
    timing_ms: dict[str, float] = {"per_tile": [], "coarse": 0.0, "merge": 0.0}

    # Optional coarse global pass — guarantees no regression on
    # close-up faces whose bbox spans a tile seam.
    if include_coarse:
        t_coarse = time.perf_counter()
        try:
            coarse_dets = _model.detect(frame)
            detections_global.extend(coarse_dets)
        except Exception:
            logger.exception("coarse detect inside /detect_tiled failed")
        timing_ms["coarse"] = (time.perf_counter() - t_coarse) * 1000.0

    for tile in tiles:
        t0 = time.perf_counter()
        try:
            tile_img = frame[tile.y0:tile.y1, tile.x0:tile.x1]
            if tile_img.size == 0:
                continue
            padded, scale, pad_x, pad_y = letterbox_to_square(
                tile_img, target_size=target_size
            )
            local_dets = _model.detect(padded)
            for det in local_dets:
                bbox_global, kps_global = remap_detection(
                    det["bbox"],
                    det.get("kps"),
                    tile,
                    scale,
                    pad_x,
                    pad_y,
                )
                detections_global.append(
                    {
                        "bbox": bbox_global,
                        "det_score": float(det["det_score"]),
                        "kps": kps_global,
                    }
                )
        except Exception:
            logger.exception(
                "tile detection failed for %r — skipping tile", tile
            )
        finally:
            timing_ms["per_tile"].append(
                round((time.perf_counter() - t0) * 1000.0, 2)
            )

    t_merge = time.perf_counter()
    merged = greedy_nmm_ios(detections_global, ios_threshold=ios_thresh)
    timing_ms["merge"] = (time.perf_counter() - t_merge) * 1000.0

    return JSONResponse(
        content={
            "detections": [
                {
                    "bbox": d["bbox"].tolist(),
                    "det_score": d["det_score"],
                    "kps": (
                        d["kps"].tolist() if d.get("kps") is not None else None
                    ),
                }
                for d in merged
            ],
            "tile_count": len(tiles),
            "coarse_included": include_coarse,
            "ios_thresh": ios_thresh,
            "timing_ms": timing_ms,
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

    # Validate up-front — bad shapes should fail fast, before we run any
    # ArcFace work (which is the most expensive step).
    np_kps_list: list[np.ndarray] = []
    for kps in kps_list:
        kps_arr = np.asarray(kps, dtype=np.float32)
        if kps_arr.shape != (5, 2):
            raise HTTPException(
                status_code=400,
                detail=f"kps must be [5,2]; got {kps_arr.shape}",
            )
        np_kps_list.append(kps_arr)

    t0 = time.perf_counter()
    # Batched: one cv2.dnn.blobFromImages + one ONNX session.run for all
    # N faces. With N=4 on the M5 + CoreML this drops total embed time
    # from ~80 ms (4 sequential calls) to ~30 ms (one batched call).
    feats = _model.embed_from_kps_batch(frame, np_kps_list)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return JSONResponse(
        content={
            "embeddings": feats.tolist(),
            "embed_ms": round(elapsed_ms, 2),
            "count": int(feats.shape[0]),
        }
    )


@app.post("/liveness")
async def liveness(request: Request) -> JSONResponse:
    """Run MiniFASNet-fused passive liveness on N face bboxes in one frame.

    Body: JSON of the form
    ``{"jpeg_b64": "<base64 jpeg>", "bboxes": [[x1,y1,x2,y2], ...]}``
    where bboxes are pixel-space integers in the same coordinate system
    as the JPEG. Order is preserved in the response.

    Returns 503 when the on-disk pack is missing — operator runs
    ``scripts.export_liveness_models`` to enable. The gateway treats 503
    as "skip liveness gating this frame", not a hard error.
    """
    if _liveness is None or not _liveness.is_loaded:
        raise HTTPException(
            status_code=503,
            detail=f"liveness not loaded: {_liveness_load_error or 'unknown'}",
        )

    body = await request.json()
    jpeg_b64 = body.get("jpeg_b64")
    bboxes_in = body.get("bboxes", [])
    if not jpeg_b64 or not isinstance(bboxes_in, list):
        raise HTTPException(
            status_code=400,
            detail="jpeg_b64 + bboxes required",
        )

    import base64

    try:
        jpeg = base64.b64decode(jpeg_b64)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"bad jpeg_b64: {exc}",
        ) from exc
    frame = _decode_jpeg(jpeg)

    # Validate bboxes up-front; bad shapes should fail before we touch
    # the model. Each bbox must be a 4-tuple of ints/floats — we coerce
    # to int (pixel coords) inside LivenessModel._crop_for_submodel.
    parsed: list[tuple[int, int, int, int]] = []
    for entry in bboxes_in:
        if not isinstance(entry, (list, tuple)) or len(entry) != 4:
            raise HTTPException(
                status_code=400,
                detail=f"each bbox must be [x1,y1,x2,y2]; got {entry!r}",
            )
        try:
            parsed.append(tuple(int(v) for v in entry))  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"bbox {entry!r} contains non-numeric values: {exc}",
            ) from exc

    t0 = time.perf_counter()
    predictions = _liveness.predict_batch(frame, parsed)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return JSONResponse(
        content={
            "predictions": [
                {
                    "score": round(p.score, 4),
                    "label": p.label,
                    "per_model_scores": {
                        k: round(v, 4) for k, v in p.per_model_scores.items()
                    },
                }
                for p in predictions
            ],
            "liveness_ms": round(elapsed_ms, 2),
            "count": len(predictions),
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
