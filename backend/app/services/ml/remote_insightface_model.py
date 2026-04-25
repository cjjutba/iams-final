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
        """Single-face convenience wrapper — delegates to the batched path.

        Kept on the API surface so callers that only have one face don't
        have to wrap+unwrap a list themselves.
        """
        out = self.embed_from_kps_batch(frame, [kps])
        if out.shape[0] == 0:
            raise RuntimeError("sidecar /embed returned no embeddings")
        return out[0]

    def embed_from_kps_batch(
        self,
        frame: np.ndarray,
        kps_list: list[np.ndarray],
    ) -> np.ndarray:
        """Run ArcFace on N faces via the sidecar in ONE round-trip.

        The realtime tracker accumulates all faces that need embedding
        on a given frame, then makes one call here. We:

          1. JPEG-encode the source frame ONCE (~5-10 ms)
          2. Base64-encode + POST ONCE (~3-5 ms loopback)
          3. Sidecar runs ONE cv2.dnn.blobFromImages + ONE ONNX
             session.run for all N faces — see ml-sidecar/main.py
          4. Receive [N, 512] in one response

        At N=4 this saves ~50 ms vs the previous sequential per-face
        path. Per-call overhead floor stays at the JPEG-encode + RTT
        (~10 ms) so single-face callers pay roughly the same as before.

        Args:
            frame: BGR ndarray — the single source frame all faces are
                in. Coordinate space of every kps must match.
            kps_list: List of [5, 2] landmark arrays. Empty list returns
                an empty [0, 512] array without making a network call.

        Returns:
            [N, 512] float32 L2-normalized embeddings, in the same order
            as ``kps_list``. Numerically identical to per-face calls.

        Raises:
            RuntimeError: JPEG encode failure, sidecar HTTP failure,
                or unexpected response shape.
        """
        if not kps_list:
            return np.zeros((0, 512), dtype=np.float32)

        jpeg = self._encode_jpeg(frame)
        if jpeg is None:
            raise RuntimeError("could not JPEG-encode frame for /embed")

        # Convert all kps to plain Python lists for JSON serialisation.
        # The sidecar validates shape on its end so we don't need to here.
        kps_payload = [
            np.asarray(k, dtype=np.float32).tolist() for k in kps_list
        ]

        payload = {
            "jpeg_b64": base64.b64encode(jpeg).decode("ascii"),
            "kps": kps_payload,
        }
        try:
            resp = self._client.post(f"{self._base_url}/embed", json=payload)
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:
            logger.warning("Sidecar /embed (batch=%d) failed: %s", len(kps_list), exc)
            raise RuntimeError(f"sidecar /embed failed: {exc}") from exc

        emb_list = body.get("embeddings") or []
        if len(emb_list) != len(kps_list):
            raise RuntimeError(
                f"sidecar /embed returned {len(emb_list)} embeddings; "
                f"requested {len(kps_list)}"
            )
        arr = np.asarray(emb_list, dtype=np.float32)
        if arr.shape != (len(kps_list), 512):
            raise RuntimeError(
                f"sidecar /embed returned shape {arr.shape}; "
                f"expected ({len(kps_list)}, 512)"
            )
        return arr

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
