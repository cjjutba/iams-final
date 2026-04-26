"""
Frame cropping + JPEG encoding helpers used by the Phase-3 live-crop capture
path in ``backend/app/services/realtime_pipeline.py``.

Kept separate (rather than inline in the pipeline) so that the helpers are
easy to unit-test and so that future non-pipeline callers (e.g. an ad-hoc
thumbnail endpoint) don't have to reach into private pipeline state.
"""

from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np


def crop_face_with_margin(
    frame_bgr: np.ndarray,
    bbox_norm: Sequence[float],
    margin_pct: float = 0.25,
) -> np.ndarray | None:
    """Crop a normalized face bbox out of a BGR frame with padding.

    Args:
        frame_bgr: Full frame from the pipeline (BGR, np.uint8, HxWx3).
        bbox_norm: ``[x1, y1, x2, y2]`` normalized to [0, 1].
        margin_pct: Fractional padding around the bbox width/height. 0.25
            gives a comfortable admin-review headshot without cutting off
            ears/chin on most detections.

    Returns:
        A BGR numpy array (the cropped region), or ``None`` if the crop is
        degenerate (bbox off-frame / zero-area after clipping).
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return None
    if len(bbox_norm) != 4:
        return None

    h, w = frame_bgr.shape[:2]
    x1, y1, x2, y2 = (float(v) for v in bbox_norm)
    bw = x2 - x1
    bh = y2 - y1
    if bw <= 0 or bh <= 0:
        return None

    x1 = max(0.0, x1 - margin_pct * bw)
    y1 = max(0.0, y1 - margin_pct * bh)
    x2 = min(1.0, x2 + margin_pct * bw)
    y2 = min(1.0, y2 + margin_pct * bh)

    px1 = max(0, int(x1 * w))
    py1 = max(0, int(y1 * h))
    px2 = min(w, int(x2 * w))
    py2 = min(h, int(y2 * h))

    if px2 - px1 < 2 or py2 - py1 < 2:
        return None

    crop = frame_bgr[py1:py2, px1:px2]
    return crop if crop.size > 0 else None


def encode_jpeg(
    bgr: np.ndarray | None,
    max_side: int = 320,
    quality: int = 80,
) -> bytes | None:
    """Resize (longer edge = ``max_side``) and JPEG-encode a BGR crop.

    The crop is downsized before encoding to keep Redis payloads small —
    live crops at 320px edge with JPEG 80 typically land at ~10-25 KB, which
    leaves a 2h TTL'd ring buffer of 10 entries per user well under Redis's
    256 MB budget on the onprem stack.

    Returns the JPEG bytes or ``None`` on any failure.
    """
    if bgr is None or bgr.size == 0:
        return None

    try:
        h, w = bgr.shape[:2]
        if max(h, w) > max_side:
            scale = max_side / float(max(h, w))
            new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
            bgr = cv2.resize(bgr, new_size, interpolation=cv2.INTER_AREA)

        ok, enc = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
        if not ok:
            return None
        return bytes(enc)
    except Exception:
        return None
