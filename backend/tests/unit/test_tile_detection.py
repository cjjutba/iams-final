"""Unit tests for distant-face detection helpers.

Covers tile geometry, letterbox + remap round-trip, IOS-NMM merge, and
the lens-undistortion + back-row-streams config parsers. These are the
pure-function pieces of the distant-face plan 2026-04-26 — the ML
sidecar's HTTP path and the realtime tracker's motion-gating loop are
exercised separately via integration tests because they need a real
SCRFD-bound model.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.services.backrow_streams import BackrowStream, parse_backrow_config
from app.services.ml.lens_undistort import (
    LensCoeffs,
    parse_lens_undistortion_config,
)
from app.services.ml.tile_detection import (
    TileRect,
    compute_tile_rects,
    greedy_nmm_ios,
    letterbox_to_square,
    remap_detection,
    tile_intersects_mask,
)


# ─── Tile geometry ────────────────────────────────────────────────────


class TestComputeTileRects:
    def test_single_tile_full_frame(self):
        rects = compute_tile_rects(1920, 1080, cols=1, rows=1, overlap_px=160)
        assert len(rects) == 1
        assert rects[0].x0 == 0
        assert rects[0].y0 == 0
        assert rects[0].x1 == 1920
        assert rects[0].y1 == 1080

    def test_three_horizontal_tiles_meet_overlap(self):
        rects = compute_tile_rects(1920, 1080, cols=3, rows=1, overlap_px=160)
        assert len(rects) == 3
        # First and last are anchored to frame edges.
        assert rects[0].x0 == 0
        assert rects[-1].x1 == 1920
        # Each adjacent pair satisfies the requested overlap.
        for i in range(len(rects) - 1):
            overlap = rects[i].x1 - rects[i + 1].x0
            assert overlap >= 160, (
                f"tile {i}/{i+1} overlap {overlap} < 160 (rects={rects})"
            )

    def test_two_tile_split(self):
        rects = compute_tile_rects(1920, 1080, cols=2, rows=1, overlap_px=160)
        assert len(rects) == 2
        assert rects[0].x0 == 0
        assert rects[1].x1 == 1920
        assert (rects[0].x1 - rects[1].x0) >= 160

    def test_3x2_grid(self):
        rects = compute_tile_rects(1920, 1080, cols=3, rows=2, overlap_px=120)
        assert len(rects) == 6
        widths = {r.width for r in rects}
        heights = {r.height for r in rects}
        # All tiles same size (modulo 1px rounding allowance).
        assert len(widths) <= 1
        assert len(heights) <= 1

    def test_invalid_dims_raise(self):
        with pytest.raises(ValueError):
            compute_tile_rects(0, 1080, 3, 1, 160)
        with pytest.raises(ValueError):
            compute_tile_rects(1920, 1080, 0, 1, 160)


# ─── Letterbox + remap ────────────────────────────────────────────────


class TestLetterboxAndRemap:
    def test_letterbox_aspect_preserved(self):
        img = np.zeros((600, 800, 3), dtype=np.uint8)
        canvas, scale, pad_x, pad_y = letterbox_to_square(img, target_size=960)
        assert canvas.shape == (960, 960, 3)
        # 800 is the long edge → scale = 960/800 = 1.2
        assert abs(scale - 1.2) < 1e-3
        # 600 * 1.2 = 720 → pad_y = (960 - 720) // 2 = 120
        assert pad_y == 120
        assert pad_x == 0

    def test_round_trip_bbox(self):
        # Tile at offset (100, 200), size 800x600, letterboxed to 960x960.
        tile = TileRect(x0=100, y0=200, x1=900, y1=800)
        # In canvas-space, a bbox at (pad_x+100, pad_y+50)→(pad_x+200, pad_y+250)
        scale = 1.2
        pad_x = 0
        pad_y = 120
        bbox = np.array(
            [pad_x + 100, pad_y + 50, pad_x + 200, pad_y + 250],
            dtype=np.float32,
        )
        global_bbox, _ = remap_detection(bbox, None, tile, scale, pad_x, pad_y)
        # Tile-space (post-undo-resize): (100/1.2, 50/1.2)→(200/1.2, 250/1.2)
        # Global = tile-space + (tile.x0, tile.y0)
        expected = np.array(
            [
                100 / 1.2 + 100,
                50 / 1.2 + 200,
                200 / 1.2 + 100,
                250 / 1.2 + 200,
            ],
            dtype=np.float32,
        )
        assert np.max(np.abs(global_bbox - expected)) < 0.5

    def test_round_trip_landmarks(self):
        tile = TileRect(x0=50, y0=50, x1=850, y1=850)
        scale = 0.8  # 1000-pixel logical content scaled to 800
        pad_x = 80
        pad_y = 0
        # Five landmark points in canvas space
        kps_canvas = np.array(
            [
                [pad_x + 200, pad_y + 100],
                [pad_x + 250, pad_y + 100],
                [pad_x + 225, pad_y + 130],
                [pad_x + 210, pad_y + 160],
                [pad_x + 240, pad_y + 160],
            ],
            dtype=np.float32,
        )
        bbox = np.array([pad_x + 200, pad_y + 100, pad_x + 250, pad_y + 160], dtype=np.float32)
        _, kps_global = remap_detection(bbox, kps_canvas, tile, scale, pad_x, pad_y)
        # Right-eye x: (200 - 0)/0.8 + 50 = 300; y: (100 - 0)/0.8 + 50 = 175
        # Wait, pad_y=0 so pad-subtract on y is 0.
        assert abs(kps_global[0, 0] - (200 / 0.8 + 50)) < 0.5
        assert abs(kps_global[0, 1] - (100 / 0.8 + 50)) < 0.5

    def test_invalid_scale_raises(self):
        tile = TileRect(0, 0, 100, 100)
        bbox = np.array([0.0, 0.0, 50.0, 50.0], dtype=np.float32)
        with pytest.raises(ValueError):
            remap_detection(bbox, None, tile, 0.0, 0, 0)


# ─── IOS-NMM merge ────────────────────────────────────────────────────


class TestGreedyNmmIos:
    def test_empty_input(self):
        assert greedy_nmm_ios([], 0.5) == []

    def test_disjoint_boxes_survive(self):
        dets = [
            {
                "bbox": np.array([0, 0, 100, 100], dtype=np.float32),
                "det_score": 0.9,
                "kps": None,
            },
            {
                "bbox": np.array([200, 200, 300, 300], dtype=np.float32),
                "det_score": 0.8,
                "kps": None,
            },
        ]
        merged = greedy_nmm_ios(dets, 0.5)
        assert len(merged) == 2

    def test_contained_box_merged(self):
        # Big box + small box mostly inside it. IOS(small, big) ≈ 1.0.
        dets = [
            {
                "bbox": np.array([100, 100, 200, 200], dtype=np.float32),
                "det_score": 0.9,
                "kps": None,
            },
            {
                "bbox": np.array([110, 110, 190, 190], dtype=np.float32),
                "det_score": 0.7,
                "kps": None,
            },
        ]
        merged = greedy_nmm_ios(dets, 0.5)
        assert len(merged) == 1
        # Higher-confidence box wins.
        assert merged[0]["det_score"] == 0.9

    def test_seam_clipped_halves_merge(self):
        # Two roughly-equal halves of the same face — IOS check on the
        # smaller of the two passes when they overlap heavily.
        dets = [
            {
                "bbox": np.array([100, 100, 200, 200], dtype=np.float32),
                "det_score": 0.85,
                "kps": None,
            },
            {
                "bbox": np.array([105, 105, 205, 205], dtype=np.float32),
                "det_score": 0.8,
                "kps": None,
            },
        ]
        merged = greedy_nmm_ios(dets, 0.5)
        assert len(merged) == 1

    def test_threshold_validation(self):
        with pytest.raises(ValueError):
            greedy_nmm_ios([], 0.0)
        with pytest.raises(ValueError):
            greedy_nmm_ios([], 1.5)


# ─── Tile / motion intersection ───────────────────────────────────────


class TestTileIntersectsMask:
    def test_empty_mask_fails_open(self):
        # Defensive — if mask is unavailable, all tiles should pass
        # (so we don't silently drop detections during MOG2 warmup).
        mask = np.zeros((1, 1), dtype=np.uint8)
        tile = TileRect(0, 0, 100, 100)
        assert not tile_intersects_mask(tile, mask, 100, 100)

    def test_tile_outside_mask_returns_false(self):
        mask = np.zeros((10, 10), dtype=np.uint8)
        mask[0:5, 0:5] = 255
        tile = TileRect(60, 60, 100, 100)  # bottom-right; mask is top-left
        assert not tile_intersects_mask(tile, mask, 100, 100)

    def test_tile_intersecting_motion(self):
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 20:80] = 255  # large central blob
        tile = TileRect(0, 0, 50, 50)  # overlaps blob
        assert tile_intersects_mask(tile, mask, 100, 100)

    def test_below_min_motion_ratio(self):
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[0, 0] = 255  # single noise pixel
        tile = TileRect(0, 0, 100, 100)
        assert not tile_intersects_mask(
            tile, mask, 100, 100, min_motion_ratio=0.01
        )


# ─── Back-row streams config ──────────────────────────────────────────


class TestBackrowConfig:
    def test_empty_returns_empty_list(self):
        assert parse_backrow_config("") == []
        assert parse_backrow_config(None) == []

    def test_single_entry(self):
        out = parse_backrow_config("eb226=>eb226-back")
        assert len(out) == 1
        assert isinstance(out[0], BackrowStream)
        assert out[0].primary_stream_key == "eb226"
        assert out[0].backrow_path == "eb226-back"

    def test_multiple_entries_with_whitespace(self):
        out = parse_backrow_config(" eb226=>eb226-back , eb227=>eb227-back ")
        assert len(out) == 2
        assert out[0].primary_stream_key == "eb226"
        assert out[1].primary_stream_key == "eb227"

    def test_dedup_primary(self):
        out = parse_backrow_config("eb226=>a,eb226=>b")
        assert len(out) == 1
        assert out[0].backrow_path == "a"  # first wins

    def test_skip_malformed(self):
        out = parse_backrow_config("eb226=>eb226-back,no-arrow,=>nokey,key=>")
        assert len(out) == 1


# ─── Lens undistortion config ─────────────────────────────────────────


class TestLensUndistortionConfig:
    def test_empty_returns_empty_dict(self):
        assert parse_lens_undistortion_config("") == {}
        assert parse_lens_undistortion_config(None) == {}

    def test_single_entry(self):
        cfg = "eb226: 1500.0, 1500.0, 960.0, 540.0, -0.3, 0.1, 0.0, 0.0, 0.0"
        out = parse_lens_undistortion_config(cfg)
        assert "eb226" in out
        c = out["eb226"]
        assert isinstance(c, LensCoeffs)
        assert c.fx == 1500.0
        assert c.k1 == -0.3

    def test_multiple_entries_newline_separated(self):
        cfg = (
            "eb226:1500,1500,960,540,-0.3,0.1,0,0,0\n"
            "eb227:1480,1480,955,535,-0.28,0.09,0,0,0\n"
        )
        out = parse_lens_undistortion_config(cfg)
        assert set(out.keys()) == {"eb226", "eb227"}

    def test_skip_wrong_count(self):
        # 8 instead of 9 numbers — should skip
        cfg = "eb226:1500,1500,960,540,-0.3,0.1,0,0"
        out = parse_lens_undistortion_config(cfg)
        assert out == {}

    def test_skip_non_numeric(self):
        cfg = "eb226:1500,1500,960,540,abc,0.1,0,0,0"
        out = parse_lens_undistortion_config(cfg)
        assert out == {}

    def test_camera_matrix_shape(self):
        c = LensCoeffs(1500, 1500, 960, 540, -0.3, 0.1, 0, 0, 0)
        K = c.camera_matrix()
        assert K.shape == (3, 3)
        assert K[0, 0] == 1500
        assert K[1, 1] == 1500
        assert K[0, 2] == 960
        assert K[1, 2] == 540
        assert K[2, 2] == 1
        D = c.dist_coeffs()
        assert D.shape == (5,)
