"""
RemoteInsightFaceModel — HTTP proxy for the realtime ML path.

Wraps the gateway-side caller so that ``RealtimeTracker`` can keep
calling ``model.detect(frame)`` and ``model.embed_from_kps(frame, kps)``
unchanged while the actual SCRFD + ArcFace work happens in a native
macOS sidecar process (see ``backend/ml-sidecar/``). The sidecar is the
only way to reach ``CoreMLExecutionProvider`` because Docker's Linux
build of ONNX Runtime cannot see the Apple Neural Engine.

Boundary
--------
Only the realtime path proxies. Registration calls (``get_embedding`` /
``get_face_with_quality`` / ``get_embeddings_batch``) stay in-process
because they're rare (once per student) and don't justify the extra
hop. This class deliberately does NOT implement those methods — if
something tries to call them it'll surface as ``AttributeError`` rather
than silently work-with-degraded-perf.

Failure policy
--------------
A request-level failure raises ``RuntimeError``; the SessionPipeline's
existing per-frame ``try/except`` catches it and the loop survives.
Aggregate failure is detected at startup via the ``healthcheck()``
probe — see ``app.main`` lifespan; the gateway falls back to
``insightface_model`` (in-process CPU) when the sidecar isn't
reachable, so a downed sidecar degrades to "no overlays" rather than
a hard outage.
"""

from __future__ import annotations

import base64
import logging
import time

import cv2
import httpx
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


class RemoteInsightFaceModel:
    """HTTP-proxy implementation of the realtime ``InsightFaceModel`` API.

    Public methods mirror ``InsightFaceModel.detect()`` and
    ``InsightFaceModel.embed_from_kps()`` exactly so the tracker can
    swap implementations without seeing a difference.

    Args:
        base_url: Sidecar root URL, e.g. ``http://host.docker.internal:8001``.
        timeout: Per-request HTTP timeout (seconds). Surfaces as a
            request-level failure that the pipeline catches.
        jpeg_quality: 1-100. 85 is visually lossless on face crops and
            ~30% smaller than 95 over the wire.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float | None = None,
        jpeg_quality: int | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout or settings.ML_SIDECAR_TIMEOUT_SECONDS
        self._jpeg_quality = jpeg_quality or settings.ML_SIDECAR_JPEG_QUALITY
        # Single httpx.Client reused across calls — preserves the
        # underlying TCP connection to the sidecar instead of paying TCP
        # handshake + sslcontext setup on every frame.
        self._client = httpx.Client(timeout=self._timeout)
        # ``RealtimeTracker`` guards its detect() call with
        # ``if self._insight.app else []`` to handle "model not loaded yet"
        # on the in-process model. The proxy is always "loaded" once
        # bound (the lifespan only binds it after a successful health
        # probe), so set a non-None sentinel that satisfies the truthy
        # check without exposing a real FaceAnalysis instance.
        self.app = True

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def healthcheck(self) -> dict | None:
        """Probe ``/health``; return parsed body or None on failure.

        Used by the gateway lifespan once at startup to decide whether to
        route through the sidecar or fall back to in-process inference.
        Doesn't raise — failure is the signal.
        """
        try:
            resp = self._client.get(f"{self._base_url}/health", timeout=3.0)
            if resp.status_code != 200:
                logger.warning(
                    "ML sidecar /health returned %d: %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return None
            return resp.json()
        except Exception as exc:
            logger.warning("ML sidecar /health unreachable: %s", exc)
            return None

    def close(self) -> None:
        """Close the underlying HTTP client. Idempotent."""
        try:
            self._client.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Realtime API (mirror InsightFaceModel)
    # ------------------------------------------------------------------

    def detect(
        self,
        frame: np.ndarray,
        input_size: tuple[int, int] | None = None,  # noqa: ARG002 — sidecar uses prepared det_size
    ) -> list[dict]:
        """Run SCRFD on ``frame`` via the sidecar.

        ``input_size`` is accepted for signature parity with
        ``InsightFaceModel.detect`` but is ignored — the sidecar's model
        is prepared with a single ``det_size`` at startup and changing
        it per-call would defeat the static-shape CoreML delegation.
        """
        jpeg = self._encode_jpeg(frame)
        if jpeg is None:
            return []

        try:
            resp = self._client.post(
                f"{self._base_url}/detect",
                content=jpeg,
                headers={"Content-Type": "application/octet-stream"},
            )
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:
            logger.warning("Sidecar /detect failed: %s", exc)
            raise RuntimeError(f"sidecar /detect failed: {exc}") from exc

        out: list[dict] = []
        for det in body.get("detections", []):
            kps_raw = det.get("kps")
            kps = (
                np.asarray(kps_raw, dtype=np.float32) if kps_raw is not None else None
            )
            out.append(
                {
                    "bbox": np.asarray(det["bbox"], dtype=np.float32),
                    "det_score": float(det["det_score"]),
                    "kps": kps,
                }
            )
        return out

    def embed_from_kps(self, frame: np.ndarray, kps: np.ndarray) -> np.ndarray:
        """Run ArcFace via the sidecar for one face's 5-point landmarks.

        Single-face wrapper around the sidecar's batch ``/embed``
        endpoint. The realtime tracker calls this once per face that
        needs embedding, so we re-encode + send the frame each time.
        Per-call overhead is ~7-10 ms (JPEG encode + loopback HTTP); a
        future optimisation could batch when multiple faces hit the
        same frame, but at typical N=1-3 the delta is small.
        """
        jpeg = self._encode_jpeg(frame)
        if jpeg is None:
            raise RuntimeError("could not JPEG-encode frame for /embed")

        kps_list = np.asarray(kps, dtype=np.float32).tolist()

        payload = {
            "jpeg_b64": base64.b64encode(jpeg).decode("ascii"),
            "kps": [kps_list],
        }
        try:
            resp = self._client.post(f"{self._base_url}/embed", json=payload)
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:
            logger.warning("Sidecar /embed failed: %s", exc)
            raise RuntimeError(f"sidecar /embed failed: {exc}") from exc

        emb_list = body.get("embeddings") or []
        if not emb_list:
            raise RuntimeError("sidecar /embed returned no embeddings")
        return np.asarray(emb_list[0], dtype=np.float32)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _encode_jpeg(self, frame: np.ndarray) -> bytes | None:
        """Encode a BGR ndarray to JPEG bytes."""
        try:
            ok, buf = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), int(self._jpeg_quality)],
            )
            if not ok:
                return None
            return buf.tobytes()
        except Exception:
            logger.debug("JPEG encode failed", exc_info=True)
            return None

    # Cosmetic: surface the sidecar URL in repr so log lines like
    # "RealtimeTracker bound to <RemoteInsightFaceModel ...>" identify
    # the routing without a separate field.
    def __repr__(self) -> str:  # pragma: no cover — repr only
        return f"<RemoteInsightFaceModel url={self._base_url}>"


# Sidecar-side timing breakdown (det_ms / embed_ms returned in the
# response bodies) is intentionally NOT surfaced upward — the existing
# RealtimeTracker measures wall-clock per stage, which already captures
# both sidecar inference time AND HTTP round-trip. Adding sidecar-side
# numbers as separate fields would just make it easier to over-credit
# the sidecar when latency is actually network-bound.
