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

A separate selector pair (``set_liveness_model`` / ``get_liveness_model``)
binds the MiniFASNet liveness backend. Liveness is *optional*: when the
on-disk pack hasn't been generated, ``get_liveness_model()`` returns
``None`` and the realtime tracker skips liveness gating entirely. This
keeps the SCRFD/ArcFace path orthogonal to the liveness rollout.

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


class _LivenessModel(Protocol):
    """Structural type for the optional liveness backend.

    ``LivenessModel`` (in-process; sidecar-only) and ``RemoteLivenessModel``
    (HTTP proxy) both implement this. Returns of ``predict_batch`` are
    intentionally untyped (list of dicts/dataclasses) — the realtime
    tracker reads ``score`` and ``label`` keys and ignores the rest.
    """

    def predict_batch(
        self,
        frame: np.ndarray,
        bboxes: list[tuple[int, int, int, int]],
    ) -> list[dict]: ...


_realtime_model: _RealtimeModel | None = None
_liveness_model: _LivenessModel | None = None


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


def set_liveness_model(model: _LivenessModel | None) -> None:
    """Bind (or clear) the liveness backend. Called once during gateway
    lifespan AFTER the realtime model is bound — liveness depends on
    the same sidecar process. ``None`` explicitly clears the binding so
    the tracker treats liveness as disabled."""
    global _liveness_model
    _liveness_model = model
    logger.info(
        "Liveness backend bound: %r",
        model if model is not None else "<disabled>",
    )


def get_liveness_model() -> _LivenessModel | None:
    """Return the currently-bound liveness backend, or None if liveness
    isn't available in this process.

    Returning None (instead of raising) is the explicit signal the
    realtime tracker uses to skip liveness gating. Liveness is opt-in:
    a missing pack must NEVER prevent recognition from working."""
    return _liveness_model
