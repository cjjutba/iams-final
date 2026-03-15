"""
Tests for TrackFusionService

Tests the Kalman filter-based track fusion that merges fast edge detections
(15 FPS) with slow identity recognition (2 FPS) into smooth predicted tracks.
"""

import pytest
import time
from app.services.track_fusion_service import TrackFusionService, FusedTrack


class TestFusedTrackCreation:
    """Test track creation from edge detections."""

    def test_new_track_from_edge_detection(self):
        """Single detection creates a track."""
        service = TrackFusionService()
        detections = [
            {"track_id": 1, "bbox": [100, 100, 50, 60], "confidence": 0.9}
        ]
        service.update_from_edge("room-1", detections, 640, 480)
        tracks = service.get_tracks("room-1")

        assert len(tracks) == 1
        t = tracks[0]
        assert t["edge_track_id"] == 1
        assert t["confidence"] == 0.9
        assert t["detection_count"] == 1

    def test_track_persists_across_updates(self):
        """Same edge_track_id maps to same fused track across updates."""
        service = TrackFusionService()
        det = [{"track_id": 5, "bbox": [100, 100, 50, 60], "confidence": 0.9}]

        service.update_from_edge("room-1", det, 640, 480)
        tracks1 = service.get_tracks("room-1")
        fused_id = tracks1[0]["track_id"]

        # Second update with same edge track_id
        det2 = [{"track_id": 5, "bbox": [105, 102, 50, 60], "confidence": 0.88}]
        service.update_from_edge("room-1", det2, 640, 480)
        tracks2 = service.get_tracks("room-1")

        assert len(tracks2) == 1
        assert tracks2[0]["track_id"] == fused_id
        assert tracks2[0]["detection_count"] == 2


class TestIdentityFusion:
    """Test identity merging into existing tracks."""

    def test_identity_merges_into_track(self):
        """Identity update populates user_id and name."""
        service = TrackFusionService()
        det = [{"track_id": 1, "bbox": [100, 100, 50, 60], "confidence": 0.9}]
        service.update_from_edge("room-1", det, 640, 480)

        service.update_identity(
            "room-1",
            edge_track_id=1,
            user_id="user-abc",
            name="Juan Dela Cruz",
            student_id="2021-0001",
            similarity=0.85,
        )

        tracks = service.get_tracks("room-1")
        assert len(tracks) == 1
        assert tracks[0]["user_id"] == "user-abc"
        assert tracks[0]["name"] == "Juan Dela Cruz"
        assert tracks[0]["student_id"] == "2021-0001"
        assert tracks[0]["similarity"] == 0.85

    def test_identity_is_sticky(self):
        """Identity persists across subsequent edge updates without identity."""
        service = TrackFusionService()
        det = [{"track_id": 1, "bbox": [100, 100, 50, 60], "confidence": 0.9}]
        service.update_from_edge("room-1", det, 640, 480)

        service.update_identity(
            "room-1",
            edge_track_id=1,
            user_id="user-abc",
            name="Juan Dela Cruz",
            student_id="2021-0001",
            similarity=0.85,
        )

        # Another edge update — no identity info
        det2 = [{"track_id": 1, "bbox": [110, 105, 50, 60], "confidence": 0.88}]
        service.update_from_edge("room-1", det2, 640, 480)

        tracks = service.get_tracks("room-1")
        assert tracks[0]["user_id"] == "user-abc"
        assert tracks[0]["name"] == "Juan Dela Cruz"


class TestKalmanPrediction:
    """Test Kalman filter prediction behavior."""

    def test_predict_advances_position(self):
        """predict() moves bbox based on velocity."""
        service = TrackFusionService()

        # Several detections moving right to build velocity in the Kalman filter
        positions = [100, 120, 140, 160, 180]
        for x in positions:
            det = [{"track_id": 1, "bbox": [x, 100, 50, 60], "confidence": 0.9}]
            service.update_from_edge("room-1", det, 640, 480)
            # Small sleep to ensure nonzero dt between updates
            time.sleep(0.01)

        tracks_before = service.get_tracks("room-1")
        bbox_before = tracks_before[0]["bbox"]

        # Predict forward by 1 second
        service.predict("room-1", dt=1.0)

        tracks_after = service.get_tracks("room-1")
        bbox_after = tracks_after[0]["bbox"]

        # x position should have advanced (moving right)
        assert bbox_after[0] > bbox_before[0]

    def test_predict_with_no_tracks_is_noop(self):
        """predict() on empty room does not crash."""
        service = TrackFusionService()
        # Should not raise
        service.predict("nonexistent-room", dt=0.033)
        tracks = service.get_tracks("nonexistent-room")
        assert tracks == []


class TestTrackDeletion:
    """Test track removal after missed frames."""

    def test_track_removed_after_max_missed(self):
        """11 empty updates removes track when max_missed=10."""
        service = TrackFusionService(max_missed_frames=10)
        det = [{"track_id": 1, "bbox": [100, 100, 50, 60], "confidence": 0.9}]
        service.update_from_edge("room-1", det, 640, 480)

        assert len(service.get_tracks("room-1")) == 1

        # Send 11 empty updates
        for _ in range(11):
            service.update_from_edge("room-1", [], 640, 480)

        assert len(service.get_tracks("room-1")) == 0


class TestMultipleRooms:
    """Test room isolation."""

    def test_rooms_are_independent(self):
        """Different rooms have separate state."""
        service = TrackFusionService()

        det_a = [{"track_id": 1, "bbox": [100, 100, 50, 60], "confidence": 0.9}]
        det_b = [
            {"track_id": 1, "bbox": [200, 200, 40, 40], "confidence": 0.8},
            {"track_id": 2, "bbox": [300, 300, 40, 40], "confidence": 0.7},
        ]

        service.update_from_edge("room-A", det_a, 640, 480)
        service.update_from_edge("room-B", det_b, 1280, 720)

        assert len(service.get_tracks("room-A")) == 1
        assert len(service.get_tracks("room-B")) == 2

        dims_a = service.get_room_dimensions("room-A")
        dims_b = service.get_room_dimensions("room-B")
        assert dims_a == (640, 480)
        assert dims_b == (1280, 720)

        service.cleanup_room("room-A")
        assert len(service.get_tracks("room-A")) == 0
        assert len(service.get_tracks("room-B")) == 2
