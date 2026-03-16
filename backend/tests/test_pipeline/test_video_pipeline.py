"""Tests for VideoAnalyticsPipeline -- unified detect/track/recognize/annotate pipeline."""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestVideoPipeline:
    def _make_config(self, **overrides):
        """Helper to build a minimal valid pipeline config."""
        cfg = {
            "room_id": "room-1",
            "rtsp_source": "rtsp://mediamtx:8554/room-1/raw",
            "rtsp_target": "rtsp://mediamtx:8554/room-1/annotated",
            "width": 640,
            "height": 480,
            "fps": 25,
            "room_name": "Room 301",
            "det_model": "buffalo_sc",
        }
        cfg.update(overrides)
        return cfg

    def test_pipeline_creates_all_components(self):
        from app.pipeline.video_pipeline import VideoAnalyticsPipeline

        config = self._make_config()
        pipeline = VideoAnalyticsPipeline(config)
        assert pipeline.room_id == "room-1"
        assert pipeline.config["width"] == 640

    def test_pipeline_initial_state(self):
        from app.pipeline.video_pipeline import VideoAnalyticsPipeline

        config = self._make_config(room_name="Test Room", subject="CS101",
                                   professor="Prof. Santos", total_enrolled=35)
        pipeline = VideoAnalyticsPipeline(config)
        assert pipeline._hud_info["room_name"] == "Test Room"
        assert pipeline._hud_info["subject"] == "CS101"
        assert pipeline._hud_info["total_count"] == 35
        assert pipeline._running is False

    def test_build_detection_list_from_tracked(self):
        """Verify detection list format matches FrameAnnotator expectations."""
        import supervision as sv
        from app.pipeline.video_pipeline import VideoAnalyticsPipeline

        config = self._make_config(room_id="r1")
        pipeline = VideoAnalyticsPipeline(config)
        pipeline._identities = {
            1: {
                "user_id": "u1",
                "name": "Juan",
                "student_id": "2021-0001",
                "confidence": 0.95,
            },
        }
        pipeline._track_start_times = {1: time.time() - 60, 2: time.time() - 5}

        # Simulate tracked detections
        tracked = sv.Detections(
            xyxy=np.array([[100, 100, 200, 200], [300, 100, 400, 200]], dtype=np.float32),
            confidence=np.array([0.9, 0.6]),
            tracker_id=np.array([1, 2]),
        )

        det_list = pipeline._build_detection_list(tracked)
        assert len(det_list) == 2
        assert det_list[0]["name"] == "Juan"
        assert det_list[0]["track_state"] == "confirmed"
        assert det_list[1]["name"] is None
        assert det_list[1]["track_state"] == "new"

    def test_build_detection_list_empty_tracker(self):
        """Empty tracker should produce empty list."""
        import supervision as sv
        from app.pipeline.video_pipeline import VideoAnalyticsPipeline

        config = self._make_config()
        pipeline = VideoAnalyticsPipeline(config)
        empty = sv.Detections.empty()
        det_list = pipeline._build_detection_list(empty)
        assert det_list == []

    def test_cleanup_stale_tracks(self):
        """Stale tracks should be removed from all state dicts."""
        import supervision as sv
        from app.pipeline.video_pipeline import VideoAnalyticsPipeline

        config = self._make_config()
        pipeline = VideoAnalyticsPipeline(config)

        # Set up state for tracks 1, 2, 3
        pipeline._track_start_times = {1: 100.0, 2: 200.0, 3: 300.0}
        pipeline._identities = {1: {"user_id": "u1", "name": "A", "confidence": 0.9}}
        pipeline._track_frame_counts = {1: 10, 2: 5, 3: 2}
        pipeline._confirmed_track_ids = {1, 2}

        # Only track 2 is still active
        tracked = sv.Detections(
            xyxy=np.array([[50, 50, 100, 100]], dtype=np.float32),
            confidence=np.array([0.8]),
            tracker_id=np.array([2]),
        )
        pipeline._cleanup_stale_tracks(tracked)

        assert 1 not in pipeline._track_start_times
        assert 3 not in pipeline._track_start_times
        assert 2 in pipeline._track_start_times
        assert 1 not in pipeline._identities
        assert 1 not in pipeline._confirmed_track_ids

    def test_update_hud(self):
        from app.pipeline.video_pipeline import VideoAnalyticsPipeline

        config = self._make_config()
        pipeline = VideoAnalyticsPipeline(config)
        pipeline.update_hud(subject="Math 101", professor="Dr. Reyes")
        assert pipeline._hud_info["subject"] == "Math 101"
        assert pipeline._hud_info["professor"] == "Dr. Reyes"

    def test_detect_faces_returns_empty_without_detector(self):
        """Without a loaded detector, _detect_faces returns empty Detections."""
        import supervision as sv
        from app.pipeline.video_pipeline import VideoAnalyticsPipeline

        config = self._make_config()
        pipeline = VideoAnalyticsPipeline(config)
        assert pipeline._detector is None

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = pipeline._detect_faces(frame)
        assert len(result) == 0

    def test_detect_faces_converts_to_xyxy(self):
        """Detections from InsightFace should be converted to xyxy format."""
        from app.pipeline.video_pipeline import VideoAnalyticsPipeline

        config = self._make_config()
        pipeline = VideoAnalyticsPipeline(config)

        # Mock the detector
        mock_face = MagicMock()
        mock_face.x = 100
        mock_face.y = 50
        mock_face.width = 80
        mock_face.height = 100
        mock_face.confidence = 0.92

        mock_detector = MagicMock()
        mock_detector.get_faces.return_value = [mock_face]
        pipeline._detector = mock_detector

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = pipeline._detect_faces(frame)
        assert len(result) == 1
        # xyxy should be [100, 50, 180, 150]
        np.testing.assert_array_almost_equal(
            result.xyxy[0], [100, 50, 180, 150]
        )
        assert abs(result.confidence[0] - 0.92) < 0.01

    def test_stop_sets_running_false(self):
        from app.pipeline.video_pipeline import VideoAnalyticsPipeline

        config = self._make_config()
        pipeline = VideoAnalyticsPipeline(config)
        pipeline._running = True
        pipeline._reader = MagicMock()
        pipeline._publisher = MagicMock()

        pipeline.stop()
        assert pipeline._running is False
        pipeline._reader.stop.assert_called_once()
        pipeline._publisher.stop.assert_called_once()
