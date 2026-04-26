"""
Tile-based face detection helpers — distant-face plan 2026-04-26 Phase 3.

Imported by both the api-gateway (when it pre-computes tile rectangles
to send to the sidecar) and the ML sidecar (when it runs SCRFD on each
tile and merges the per-tile detections back into a single global list).
Pure-numpy / cv2; no FastAPI / DB dependencies.

Algorithm overview
------------------

A "tile" is a rectangular crop of the source frame, optionally
letterboxed to a fixed square so it matches the sidecar's
static-shape ANE-bound model input. SCRFD runs on each tile
independently, returning bboxes + 5-point landmarks in tile-local
coordinates. We then:

  1. Remap each tile's detections back to the original frame's
     pixel space (additive offset + letterbox-pad subtraction).
  2. Optionally include a coarse global-frame detection so close-up
     faces don't regress when their bbox spans a tile seam.
  3. Merge the combined detections with **IOS-NMM** (Greedy
     Non-Maximum Merging using Intersection-over-Smaller) — the
     SAHI paper's default for sliced inference. Vanilla IoU-NMS
     tends to *delete* legitimate seam-clipped detections because
     two halves of the same face have IoU ≈ 0.3; IOS detects "this
     small box is mostly inside that big box" and merges instead.

The classroom geometry sweet spot is N×1 horizontal tiles (students
roughly line up horizontally on benches), each padded to a square
matching the static export's ``det_size``. Overlap of 160 px guards
against split-detection failures for typical 50-70 px close-up faces.

References:
  - SAHI paper: https://arxiv.org/abs/2202.06934
  - SAHI postprocess source: github.com/obss/sahi/blob/main/sahi/postprocess/combine.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TileRect:
    """One tile's geometry inside the source frame.

    Coordinates are pixels in the original frame. ``x0/y0`` is the
    top-left corner of the tile crop; ``x1/y1`` is the exclusive
    bottom-right (so ``frame[y0:y1, x0:x1]`` produces the tile).
    """

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0


def compute_tile_rects(
    frame_w: int,
    frame_h: int,
    cols: int,
    rows: int,
    overlap_px: int,
) -> list[TileRect]:
    """Lay out ``cols × rows`` overlapping tiles over a ``frame_w × frame_h`` frame.

    Each tile is the same size and tiles share ``overlap_px`` on each
    interior edge. The first tile is left/top-anchored, the last is
    right/bottom-anchored, and intermediate tiles are evenly spaced.

    Edge cases:
      * cols=1, rows=1 → returns a single tile covering the full frame
        (equivalent to non-tiled detection; useful so the caller can
        always go through the same merge-path).
      * cols × rows > 1 but overlap_px ≥ tile_w/h → tiles would not
        meaningfully tile; we clamp overlap to half the tile size and
        log a warning.
    """
    if cols < 1 or rows < 1:
        raise ValueError(f"cols/rows must be >= 1; got cols={cols} rows={rows}")
    if frame_w <= 0 or frame_h <= 0:
        raise ValueError(f"frame must have positive dims; got {frame_w}x{frame_h}")

    if cols == 1 and rows == 1:
        return [TileRect(0, 0, frame_w, frame_h)]

    # Tile size given overlap and target counts. With N tiles spanning
    # ``frame_w`` total and overlap ``o`` between adjacent tiles, we
    # solve N*tile_w - (N-1)*o = frame_w → tile_w = (frame_w + (N-1)*o) / N.
    # Use ceil-division so integer rounding never produces less overlap
    # than the caller asked for (the alternative — floor — produced
    # 159px overlap for a 160px request, which let small faces fall
    # through tile seams).
    def _tile_dim(total: int, n: int, ov: int) -> int:
        if n == 1:
            return total
        # Clamp overlap so the tile is at least 2× overlap (otherwise
        # adjacent tiles invert and the tiling math breaks).
        max_ov = total // (n + 1)
        if ov > max_ov:
            logger.warning(
                "compute_tile_rects: overlap_px=%d > %d for %d tiles in dim=%d; "
                "clamping",
                ov,
                max_ov,
                n,
                total,
            )
            ov = max_ov
        # Ceil division: (a + b - 1) // b
        size = (total + (n - 1) * ov + n - 1) // n
        return max(size, ov + 1)

    tile_w = _tile_dim(frame_w, cols, overlap_px)
    tile_h = _tile_dim(frame_h, rows, overlap_px)

    # Stride between tile starts. For the first/last tile to stay
    # anchored on the frame edges, we use total - tile_size as the
    # "remaining travel" and split evenly across (n-1) gaps.
    def _stride(total: int, tile_size: int, n: int) -> int:
        if n == 1:
            return tile_size
        return max(1, (total - tile_size) // (n - 1))

    stride_x = _stride(frame_w, tile_w, cols)
    stride_y = _stride(frame_h, tile_h, rows)

    out: list[TileRect] = []
    for r in range(rows):
        for c in range(cols):
            # Anchor the last col/row to the right/bottom edge to
            # cover any rounding remainder.
            x0 = c * stride_x if c < cols - 1 else max(0, frame_w - tile_w)
            y0 = r * stride_y if r < rows - 1 else max(0, frame_h - tile_h)
            x1 = min(frame_w, x0 + tile_w)
            y1 = min(frame_h, y0 + tile_h)
            out.append(TileRect(x0=x0, y0=y0, x1=x1, y1=y1))
    return out


def letterbox_to_square(
    tile: np.ndarray,
    target_size: int,
    pad_value: int = 0,
) -> tuple[np.ndarray, float, int, int]:
    """Pad/resize a tile to a fixed square. Returns (img, scale, pad_x, pad_y).

    Scales the tile so its longest edge fits ``target_size``, then pads
    the short edge symmetrically with ``pad_value`` so the result is
    exactly ``target_size × target_size``. The static-shape ANE-bound
    SCRFD requires this exact shape — letterboxing preserves aspect
    ratio so the model's anchor priors still align with face geometry.

    Returned ``scale`` is the resize factor (target = original × scale)
    and ``pad_x/pad_y`` are the left/top pad widths in pixels — needed
    to map coordinates back to the original tile after detection.
    """
    h, w = tile.shape[:2]
    long_edge = max(h, w)
    if long_edge <= 0:
        raise ValueError("empty tile in letterbox_to_square")
    scale = float(target_size) / long_edge
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(tile, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    pad_x = (target_size - new_w) // 2
    pad_y = (target_size - new_h) // 2
    canvas = np.full((target_size, target_size, 3), pad_value, dtype=np.uint8)
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
    return canvas, scale, pad_x, pad_y


def remap_detection(
    bbox: np.ndarray,
    kps: np.ndarray | None,
    tile: TileRect,
    scale: float,
    pad_x: int,
    pad_y: int,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Map a tile-local detection back to original-frame pixel coords.

    Inverse of letterbox_to_square + tile crop:
      1. Subtract the letterbox pad (so coords are in resized-tile space).
      2. Divide by the resize scale (so coords are in original-tile space).
      3. Add the tile origin (so coords are in original-frame space).

    Operates on a SCRFD bbox ``[x1,y1,x2,y2]`` and optional 5-point
    landmark array of shape ``[5,2]``. Both come back in float32.
    """
    if scale <= 0:
        raise ValueError("scale must be > 0 in remap_detection")
    inv_scale = 1.0 / scale
    bbox_remapped = bbox.astype(np.float32, copy=True)
    bbox_remapped[0] = (bbox[0] - pad_x) * inv_scale + tile.x0
    bbox_remapped[1] = (bbox[1] - pad_y) * inv_scale + tile.y0
    bbox_remapped[2] = (bbox[2] - pad_x) * inv_scale + tile.x0
    bbox_remapped[3] = (bbox[3] - pad_y) * inv_scale + tile.y0

    if kps is None:
        return bbox_remapped, None
    kps_remapped = kps.astype(np.float32, copy=True)
    kps_remapped[:, 0] = (kps[:, 0] - pad_x) * inv_scale + tile.x0
    kps_remapped[:, 1] = (kps[:, 1] - pad_y) * inv_scale + tile.y0
    return bbox_remapped, kps_remapped


def _intersection_area(a: np.ndarray, b: np.ndarray) -> float:
    """Pixel-space intersection of two ``[x1,y1,x2,y2]`` boxes."""
    x1 = max(float(a[0]), float(b[0]))
    y1 = max(float(a[1]), float(b[1]))
    x2 = min(float(a[2]), float(b[2]))
    y2 = min(float(a[3]), float(b[3]))
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return (x2 - x1) * (y2 - y1)


def _box_area(b: np.ndarray) -> float:
    return max(0.0, float(b[2]) - float(b[0])) * max(0.0, float(b[3]) - float(b[1]))


def greedy_nmm_ios(
    detections: list[dict],
    ios_threshold: float = 0.5,
) -> list[dict]:
    """Greedy Non-Maximum Merging using Intersection-over-Smaller (IOS).

    Replacement for vanilla IoU-NMS in tile-merge contexts. SAHI's
    canonical default for sliced inference. Algorithm:

      Sort detections by descending det_score.
      For each survivor S:
        For every queued detection D:
          If IOS(S, D) >= threshold (i.e. D is mostly inside S):
            Merge D into S — keep S's bbox+kps, drop D.
          Else: D survives independently.

    Inputs each ``dict`` with keys:
      - ``bbox`` (np.ndarray, shape [4]): [x1,y1,x2,y2] float
      - ``det_score`` (float)
      - ``kps`` (np.ndarray, shape [5,2]) or None

    Output: same shape, with merged duplicates removed. The retained
    entry preserves the higher-confidence box's landmarks (which are
    more likely to come from a tile that fully contained the face).

    IoS is asymmetric: ``IOS(big, small) = intersection / area(small)``.
    A small detection contained inside a big one merges; two roughly
    equal boxes only merge when their overlap is large.
    """
    # Validate threshold first so callers get a clean failure even for
    # empty inputs (catching config errors before they hit the hot path).
    if ios_threshold <= 0.0 or ios_threshold > 1.0:
        raise ValueError(
            f"ios_threshold must be in (0, 1]; got {ios_threshold}"
        )
    if not detections:
        return []

    # Defensive copy + score-descending sort. We don't mutate the input.
    ordered = sorted(detections, key=lambda d: -float(d.get("det_score", 0.0)))
    survivors: list[dict] = []
    for cand in ordered:
        cand_box = np.asarray(cand["bbox"], dtype=np.float32)
        merged = False
        for kept in survivors:
            kept_box = np.asarray(kept["bbox"], dtype=np.float32)
            inter = _intersection_area(kept_box, cand_box)
            if inter <= 0.0:
                continue
            small_area = min(_box_area(kept_box), _box_area(cand_box))
            if small_area <= 0.0:
                continue
            ios = inter / small_area
            if ios >= ios_threshold:
                # Merge: kept retains its box+kps (it has higher score
                # by sort invariant). The candidate is absorbed.
                merged = True
                break
        if not merged:
            survivors.append(cand)
    return survivors


def compute_motion_mask(
    frame: np.ndarray,
    bg_subtractor,
    downscale_dim: int,
    dilation_px: int,
) -> np.ndarray:
    """Compute a binary motion mask at a downscaled resolution.

    Returns a uint8 mask in the *downscaled* coord space (so the caller
    can quickly intersect tile rectangles in normalised coords without
    paying full-resolution cv2 calls). MOG2's ``apply()`` builds up a
    background model over the first few frames; callers should expect
    "all motion" output for the first ~10 frames after the first
    activation, which is fine — that's what we want anyway when the
    pipeline is just starting up.

    Args:
        frame: BGR ndarray, original-resolution.
        bg_subtractor: cv2.BackgroundSubtractorMOG2 instance, mutated
            in place. Caller is responsible for keeping one instance
            per logical camera so the bg model doesn't reset on every
            frame.
        downscale_dim: long-edge target for the downscaled motion mask.
            320 px is a solid default — MOG2 cost is ~quadratic in
            input size so this keeps motion-gating well under 1 ms
            per frame.
        dilation_px: kernel radius (in mask-space pixels) for the
            morphological dilation pass. Bigger = more permissive
            (tiles light up on smaller motion blobs).

    Returns:
        uint8 mask, shape ``(mask_h, mask_w)``, where pixels with
        recent motion are 255 and static pixels are 0. The mask's
        coord space is downscaled — to test whether a tile rectangle
        intersects motion, scale tile coords by ``mask_w/frame_w`` and
        ``mask_h/frame_h``.
    """
    h, w = frame.shape[:2]
    if h <= 0 or w <= 0:
        return np.zeros((1, 1), dtype=np.uint8)
    long_edge = max(h, w)
    if long_edge <= downscale_dim:
        small = frame
    else:
        scale = float(downscale_dim) / long_edge
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        small = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
    fg_mask = bg_subtractor.apply(small)
    # MOG2 emits gray "shadow" at value 127; threshold to a clean
    # binary mask so dilation produces clean blobs.
    _, fg_bin = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
    if dilation_px > 0:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (2 * dilation_px + 1, 2 * dilation_px + 1)
        )
        fg_bin = cv2.dilate(fg_bin, kernel, iterations=1)
    return fg_bin


def tile_intersects_mask(
    tile: TileRect,
    mask: np.ndarray,
    frame_w: int,
    frame_h: int,
    min_motion_ratio: float = 0.001,
) -> bool:
    """Return True if a tile rectangle intersects any motion in the mask.

    ``mask`` is in downscaled coord space (see ``compute_motion_mask``).
    We scale the tile coords into mask-space, sum the mask, and check
    against ``min_motion_ratio`` of the tile's pixel count to filter
    isolated noise pixels. 0.1 % of the tile being "motion" = real
    motion event; below that is camera noise / compression artifact.
    """
    mh, mw = mask.shape[:2]
    if mh <= 0 or mw <= 0 or frame_w <= 0 or frame_h <= 0:
        return True  # mask unavailable — fail open
    sx = mw / float(frame_w)
    sy = mh / float(frame_h)
    mx0 = max(0, int(tile.x0 * sx))
    my0 = max(0, int(tile.y0 * sy))
    mx1 = min(mw, int(tile.x1 * sx))
    my1 = min(mh, int(tile.y1 * sy))
    if mx1 <= mx0 or my1 <= my0:
        return False
    sub = mask[my0:my1, mx0:mx1]
    motion_px = int((sub > 0).sum())
    total_px = sub.size
    if total_px <= 0:
        return False
    return (motion_px / total_px) >= min_motion_ratio
