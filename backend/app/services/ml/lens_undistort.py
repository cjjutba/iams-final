"""
Lens undistortion helpers — distant-face plan 2026-04-26 Phase 4b.

Reolink wide-angle CCTV lenses (4 mm or 2.8 mm on EB226/EB227) introduce
visible barrel distortion at the frame edges. A face that's near the
left or right wall ends up "stretched" across more pixels than it
deserves geometrically, which both costs SCRFD pixel density on the
edge subjects and skews ArcFace alignment because the 5-point landmarks
no longer reflect rectilinear face geometry.

Calibrate once per physical camera using a printed checkerboard pattern
and OpenCV's ``cv2.calibrateCamera``; the resulting intrinsic matrix +
distortion coefficients can then be applied per frame to straighten the
image before SCRFD ever sees it. Math:

    K = [[fx, 0, cx], [0, fy, cy], [0, 0, 1]]
    D = (k1, k2, p1, p2, k3)

The undistorted frame has the same pixel dimensions but with edge
distortion removed. Recovered effective pixel density at corners is
typically ~30 % on a 4 mm lens, ~50 % on a 2.8 mm lens.

Wire-up:
- Settings: ``LENS_UNDISTORTION_COEFFS`` is a string of newline-or-comma-
  separated entries, each ``stream_key:fx,fy,cx,cy,k1,k2,p1,p2,k3``.
- FrameGrabber accepts an optional ``stream_key`` and pre-computes
  the undistortion remap once when constructed. ``grab_with_pts()``
  applies ``cv2.remap`` to each frame before returning. Per-frame cost
  is ~3-5 ms on the M5 for a 1920×1080 frame — negligible compared
  to the SCRFD inference budget.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LensCoeffs:
    """Calibrated intrinsics + distortion for a single camera."""

    fx: float
    fy: float
    cx: float
    cy: float
    k1: float
    k2: float
    p1: float
    p2: float
    k3: float

    def camera_matrix(self) -> np.ndarray:
        return np.array(
            [[self.fx, 0.0, self.cx], [0.0, self.fy, self.cy], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )

    def dist_coeffs(self) -> np.ndarray:
        return np.array(
            [self.k1, self.k2, self.p1, self.p2, self.k3],
            dtype=np.float64,
        )


def parse_lens_undistortion_config(raw: str | None) -> dict[str, LensCoeffs]:
    """Parse ``settings.LENS_UNDISTORTION_COEFFS`` into a stream_key → coeffs map.

    Format (newline OR comma separated entries):
      ``stream_key:fx,fy,cx,cy,k1,k2,p1,p2,k3``

    Bad entries are logged and skipped so a typo doesn't break startup.
    Empty / None / all-whitespace input → empty map (no undistortion
    applied to any camera).
    """
    if not raw:
        return {}
    out: dict[str, LensCoeffs] = {}
    # Operators may use either commas or newlines as the entry separator;
    # split on newlines first so commas inside a single entry's coefficient
    # list are preserved.
    entries: list[str] = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        # If the line has no colon, it's a continuation — skip; we expect
        # one full entry per line.
        if ":" in line:
            entries.append(line)
        else:
            logger.warning(
                "LENS_UNDISTORTION_COEFFS: skipping unparseable line %r", line
            )

    for entry in entries:
        try:
            stream_key, _, rest = entry.partition(":")
            stream_key = stream_key.strip()
            if not stream_key:
                logger.warning(
                    "LENS_UNDISTORTION_COEFFS: empty stream_key in %r", entry
                )
                continue
            parts = [p.strip() for p in rest.split(",") if p.strip()]
            if len(parts) != 9:
                logger.warning(
                    "LENS_UNDISTORTION_COEFFS: %r expected 9 numbers "
                    "(fx,fy,cx,cy,k1,k2,p1,p2,k3), got %d — skipping",
                    stream_key,
                    len(parts),
                )
                continue
            nums = [float(p) for p in parts]
            out[stream_key] = LensCoeffs(*nums)
        except ValueError as exc:
            logger.warning(
                "LENS_UNDISTORTION_COEFFS: failed to parse %r — %s",
                entry,
                exc,
            )

    return out


def build_undistort_maps(
    coeffs: LensCoeffs,
    width: int,
    height: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Pre-compute the cv2.remap inputs for a frame size.

    Built once per FrameGrabber lifetime so per-frame undistort is just
    two lookups (one for x, one for y) plus a remap call. ``cv2.remap``
    runs at ~3-5 ms for 1920×1080 BGR on the M5.

    Uses the alpha=0 form of ``getOptimalNewCameraMatrix`` so the
    output frame contains only valid (non-extrapolated) pixels —
    extrapolated black corners would feed garbage into SCRFD's
    landmark-sanity filter, defeating the purpose.
    """
    K = coeffs.camera_matrix()
    D = coeffs.dist_coeffs()
    new_K, _roi = cv2.getOptimalNewCameraMatrix(K, D, (width, height), alpha=0)
    map1, map2 = cv2.initUndistortRectifyMap(
        K,
        D,
        R=None,
        newCameraMatrix=new_K,
        size=(width, height),
        m1type=cv2.CV_16SC2,  # most efficient form for cv2.remap
    )
    return map1, map2
