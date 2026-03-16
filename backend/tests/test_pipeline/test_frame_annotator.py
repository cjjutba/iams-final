"""Tests for FrameAnnotator -- server-side bounding box and HUD drawing."""

import numpy as np
import pytest


class TestFrameAnnotator:
    def test_annotate_empty_detections(self):
        from app.pipeline.frame_annotator import FrameAnnotator

        annotator = FrameAnnotator(640, 480)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        hud = {
            "room_name": "Room 301",
            "timestamp": "2026-03-17 08:15",
            "subject": "CS101",
            "professor": "Prof. Santos",
            "present_count": 0,
            "total_count": 35,
        }
        result = annotator.annotate(frame, [], hud)
        assert result.shape == (480, 640, 3)
        assert result.dtype == np.uint8
        # Top bar should have been drawn (some non-zero pixels in the bar region)
        assert result[0:30, :].sum() > 0

    def test_annotate_with_detections(self):
        from app.pipeline.frame_annotator import FrameAnnotator

        annotator = FrameAnnotator(640, 480)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = [
            {
                "bbox": (100, 100, 200, 200),
                "name": "Juan Dela Cruz",
                "student_id": "2021-0145",
                "confidence": 0.95,
                "track_state": "confirmed",
                "track_id": 1,
                "duration_sec": 135.0,
            },
            {
                "bbox": (300, 100, 400, 200),
                "name": None,
                "student_id": None,
                "confidence": 0.0,
                "track_state": "new",
                "track_id": 2,
                "duration_sec": 5.0,
            },
        ]
        hud = {
            "room_name": "Room 301",
            "timestamp": "2026-03-17 08:15",
            "subject": "CS101",
            "professor": "Prof. Santos",
            "present_count": 1,
            "total_count": 35,
        }
        result = annotator.annotate(frame, detections, hud)
        assert result.shape == (480, 640, 3)
        # Green pixels near box 1 (confirmed = green)
        assert result[100, 100, 1] > 0 or result[100, 115, 1] > 0

    def test_corner_bracket_draws_lines_not_full_rect(self):
        from app.pipeline.frame_annotator import FrameAnnotator

        annotator = FrameAnnotator(640, 480)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = [
            {
                "bbox": (100, 100, 300, 300),
                "name": "Test",
                "student_id": "0001",
                "confidence": 0.9,
                "track_state": "confirmed",
                "track_id": 1,
                "duration_sec": 10.0,
            },
        ]
        hud = {
            "room_name": "R",
            "timestamp": "T",
            "subject": "S",
            "professor": "P",
            "present_count": 0,
            "total_count": 0,
        }
        result = annotator.annotate(frame, detections, hud)
        # Middle of top edge should be black (corner brackets, not full rect)
        mid_x = (100 + 300) // 2
        assert result[100, mid_x].sum() == 0

    def test_color_coding_by_state(self):
        from app.pipeline.frame_annotator import COLORS

        assert "confirmed" in COLORS
        assert "unknown" in COLORS
        assert "new" in COLORS
        assert "lost" in COLORS
        assert "alert" in COLORS
        # Green for confirmed (BGR: B=0, G>0, R=0)
        assert COLORS["confirmed"][1] > 100
