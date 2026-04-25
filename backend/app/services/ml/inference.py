"""
Realtime inference backend selector.

The gateway chooses between two backends at startup, and the rest of
the realtime ML code (``RealtimeTracker``, ``SessionPipeline``) reads
the selected one via ``get_realtime_model()``. Switching is a config
flip — no caller changes — because both backends present the same
``detect()`` / ``embed_from_kps()`` surface.

Backends
--------
- ``InsightFaceModel`` (in-process, CPU-only inside Docker)
    Default. Today's behaviour. ``ML_SIDECAR_URL`` empty.

- ``RemoteInsightFaceModel`` (HTTP proxy → native macOS sidecar)
    Selected when ``ML_SIDECAR_URL`` is set AND the sidecar passes its
    boot-time health probe. Routes SCRFD + ArcFace to a native process
    that uses ``CoreMLExecutionProvider`` to delegate to the Apple
    Neural Engine + Metal GPU.

Failover
--------
If ``ML_SIDECAR_URL`` is set but the sidecar isn't reachable at gateway
boot, the lifespan logs a warning and binds the in-process backend
anyway. The system stays functional with degraded throughput rather
than refusing to start.

Per-call failures (sidecar HTTP error) are surfaced as ``RuntimeError``
to the SessionPipeline's existing per-frame ``try/except``; the loop
catches them, logs once, and proceeds — equivalent to a frame drop.
There is no per-call fallback to in-process inference: that would
silently mask a wedged sidecar.
"""

from __future__ import annotations

import logging
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


class _RealtimeModel(Protocol):
    """Structural type the realtime tracker depends on. Both
    ``InsightFaceModel`` and ``RemoteInsightFaceModel`` implement it."""

    def detect(
        self,
        frame: np.ndarray,
        input_size: tuple[int, int] | None = None,
    ) -> list[dict]: ...

    def embed_from_kps(self, frame: np.ndarray, kps: np.ndarray) -> np.ndarray: ...


_realtime_model: _RealtimeModel | None = None


def set_realtime_model(model: _RealtimeModel) -> None:
    """Bind the active backend. Called once during gateway lifespan
    after the in-process model has loaded and the sidecar has been
    health-probed. Safe to call multiple times — last write wins."""
    global _realtime_model
    _realtime_model = model
    logger.info("Realtime ML backend bound: %r", model)


def get_realtime_model() -> _RealtimeModel:
    """Return the currently-bound realtime backend.

    Used by ``SessionPipeline.start()`` when constructing a
    ``RealtimeTracker``. If lifespan never set one (e.g. unit-test
    import without going through ``app.main``), fall back to the
    in-process ``insightface_model`` so the import-time path doesn't
    crash.
    """
    if _realtime_model is None:
        # Late-import to avoid making this module pull insightface +
        # onnxruntime at module load — keeps test imports cheap when
        # the realtime path isn't exercised.
        from app.services.ml.insightface_model import insightface_model

        return insightface_model
    return _realtime_model
