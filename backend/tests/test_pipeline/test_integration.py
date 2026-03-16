"""Integration tests for the video analytics pipeline.

These tests verify the pipeline components work together correctly.
Mark with @pytest.mark.integration for tests requiring Docker (mediamtx + Redis).
Unit-level integration tests run without external services.
"""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import supervision as sv


class TestPipelineIntegrationUnit:
    """Unit-level integration: verify components connect correctly without external services."""

    def test_full_pipeline_flow_mocked(self):
        """Verify the full flow: detect → track → recognize → annotate → publish."""
        from app.pipeline.frame_annotator import FrameAnnotator
        from app.pipeline.video_pipeline import VideoAnalyticsPipeline

        config = {
            "room_id": "test-room",
            "rtsp_source": "rtsp://fake:8554/test/raw",
            "rtsp_target": "rtsp://fake:8554/test/annotated",
            "width": 640,
            "height": 480,
            "fps": 25,
            "room_name": "Test Room",
            "subject": "CS101",
            "professor": "Prof. Test",
            "total_enrolled": 30,
            "det_model": "buffalo_sc",
        }

        pipeline = VideoAnalyticsPipeline(config)

        # Simulate: detector returns faces, tracker assigns IDs
        pipeline._tracker = sv.ByteTrack(
            track_activation_threshold=0.20,
            lost_track_buffer=90,
            minimum_matching_threshold=0.7,
            frame_rate=25,
            minimum_consecutive_frames=1,  # confirm immediately for test
        )
        pipeline._annotator = FrameAnnotator(640, 480)

        # Mock detector to return 2 faces (DetectedFace uses x, y, width, height)
        mock_detector = MagicMock()
        face1 = MagicMock()
        face1.x, face1.y, face1.width, face1.height = 100, 100, 100, 100
        face1.confidence = 0.95
        face2 = MagicMock()
        face2.x, face2.y, face2.width, face2.height = 300, 100, 100, 100
        face2.confidence = 0.7
        mock_detector.get_faces.return_value = [face1, face2]
        pipeline._detector = mock_detector

        # Run detection
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = pipeline._detect_faces(frame)
        assert len(detections) == 2

        # Run tracking
        tracked = pipeline._tracker.update_with_detections(detections)
        assert tracked.tracker_id is not None
        assert len(tracked.tracker_id) >= 1

        # Build detection list (no identities yet)
        det_list = pipeline._build_detection_list(tracked)
        assert len(det_list) >= 1
        for det in det_list:
            assert "bbox" in det
            assert "track_state" in det
            assert "track_id" in det

        # Annotate frame
        hud = {
            "room_name": "Test Room",
            "timestamp": "2026-03-17 08:15:00",
            "subject": "CS101",
            "professor": "Prof. Test",
            "present_count": 0,
            "total_count": 30,
        }
        annotated = pipeline._annotator.annotate(frame, det_list, hud)
        assert annotated.shape == (480, 640, 3)
        # Frame should have been modified (non-zero pixels from HUD + boxes)
        assert annotated.sum() > 0

    def test_identity_persistence_across_frames(self):
        """Once a track is identified, identity persists across frames."""
        from app.pipeline.video_pipeline import VideoAnalyticsPipeline

        config = {
            "room_id": "test",
            "rtsp_source": "x",
            "rtsp_target": "x",
            "width": 640,
            "height": 480,
            "fps": 25,
            "room_name": "R",
            "det_model": "buffalo_sc",
        }
        pipeline = VideoAnalyticsPipeline(config)

        # Simulate identified track
        pipeline._identities[5] = {
            "user_id": "u1",
            "name": "Juan Dela Cruz",
            "student_id": "2021-0001",
            "confidence": 0.95,
        }
        pipeline._track_start_times[5] = time.time() - 120
        pipeline._confirmed_track_ids.add(5)
        pipeline._track_frame_counts[5] = 10

        # Build detection list with that track
        tracked = sv.Detections(
            xyxy=np.array([[100, 100, 200, 200]], dtype=np.float32),
            confidence=np.array([0.9]),
            tracker_id=np.array([5]),
        )
        det_list = pipeline._build_detection_list(tracked)

        assert len(det_list) == 1
        assert det_list[0]["name"] == "Juan Dela Cruz"
        assert det_list[0]["student_id"] == "2021-0001"
        assert det_list[0]["track_state"] == "confirmed"
        assert det_list[0]["duration_sec"] >= 119

    def test_stale_track_cleanup(self):
        """Tracks not in current frame get cleaned up."""
        from app.pipeline.video_pipeline import VideoAnalyticsPipeline

        config = {
            "room_id": "test",
            "rtsp_source": "x",
            "rtsp_target": "x",
            "width": 640,
            "height": 480,
            "fps": 25,
            "room_name": "R",
            "det_model": "buffalo_sc",
        }
        pipeline = VideoAnalyticsPipeline(config)

        # Add identities for tracks 1, 2, 3
        for tid in [1, 2, 3]:
            pipeline._identities[tid] = {"user_id": f"u{tid}", "name": f"Student {tid}",
                                          "student_id": f"S{tid}", "confidence": 0.9}
            pipeline._track_start_times[tid] = time.time()
            pipeline._confirmed_track_ids.add(tid)
            pipeline._track_frame_counts[tid] = 5

        # Only track 2 is still active
        tracked = sv.Detections(
            xyxy=np.array([[200, 100, 300, 200]], dtype=np.float32),
            confidence=np.array([0.9]),
            tracker_id=np.array([2]),
        )
        pipeline._cleanup_stale_tracks(tracked)

        assert 1 not in pipeline._identities
        assert 2 in pipeline._identities
        assert 3 not in pipeline._identities
        assert 1 not in pipeline._track_start_times
        assert 2 in pipeline._track_start_times

    def test_pipeline_manager_lifecycle(self):
        """PipelineManager can start and stop pipelines."""
        from app.pipeline.pipeline_manager import PipelineManager

        with patch("app.pipeline.pipeline_manager.multiprocessing") as mock_mp:
            mock_proc = MagicMock()
            mock_proc.is_alive.return_value = True
            mock_proc.pid = 12345
            mock_mp.Process.return_value = mock_proc

            mgr = PipelineManager()

            # Start
            mgr.start_pipeline({
                "room_id": "room-1",
                "rtsp_source": "rtsp://mediamtx:8554/room-1/raw",
                "rtsp_target": "rtsp://mediamtx:8554/room-1/annotated",
                "width": 640, "height": 480, "fps": 25,
                "room_name": "Room 301", "det_model": "buffalo_sc",
            })
            assert len(mgr.get_status()) == 1
            assert mgr.get_status()[0]["alive"] is True

            # Stop
            mgr.stop_pipeline("room-1")
            assert len(mgr.get_status()) == 0
            mock_proc.terminate.assert_called_once()

    def test_annotator_handles_50_faces(self):
        """FrameAnnotator performs well with 50 detections."""
        from app.pipeline.frame_annotator import FrameAnnotator

        annotator = FrameAnnotator(640, 480)
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        detections = []
        for i in range(50):
            x = (i % 10) * 60 + 10
            y = (i // 10) * 90 + 40
            detections.append({
                "bbox": (x, y, x + 50, y + 70),
                "name": f"Student {i}" if i % 2 == 0 else None,
                "student_id": f"2021-{i:04d}" if i % 2 == 0 else None,
                "confidence": 0.85 + (i % 10) * 0.01,
                "track_state": "confirmed" if i % 2 == 0 else "unknown",
                "track_id": i,
                "duration_sec": float(i * 10),
            })

        hud = {
            "room_name": "Room 301 - CS Lab",
            "timestamp": "2026-03-17 08:15:00 MON",
            "subject": "CS101 - Intro to Programming",
            "professor": "Prof. Santos",
            "present_count": 25,
            "total_count": 50,
        }

        start = time.time()
        result = annotator.annotate(frame, detections, hud)
        elapsed_ms = (time.time() - start) * 1000

        assert result.shape == (480, 640, 3)
        # Should complete within 50ms (generous budget; typical is 3-5ms)
        assert elapsed_ms < 50, f"Annotation took {elapsed_ms:.1f}ms for 50 faces"


@pytest.mark.integration
class TestPipelineIntegrationDocker:
    """Tests requiring Docker services (mediamtx + Redis). Skip if not available."""

    def test_pipeline_manager_starts_real_process(self):
        """Verify PipelineManager spawns a real process (no mocking)."""
        from app.pipeline.pipeline_manager import PipelineManager

        mgr = PipelineManager(redis_url="redis://localhost:6379/0")
        config = {
            "room_id": "integration-test",
            "rtsp_source": "rtsp://localhost:8554/test/raw",
            "rtsp_target": "rtsp://localhost:8554/test/annotated",
            "width": 640,
            "height": 480,
            "fps": 15,
            "room_name": "Integration Test Room",
            "det_model": "buffalo_sc",
            "subject": "Test",
            "professor": "Prof. Test",
            "total_enrolled": 10,
        }
        mgr.start_pipeline(config)
        time.sleep(2)

        status = mgr.get_status()
        assert len(status) == 1
        assert status[0]["room_id"] == "integration-test"

        mgr.stop_pipeline("integration-test")
        assert len(mgr.get_status()) == 0
