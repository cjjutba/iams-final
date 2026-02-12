"""
Tests for Tracking Service

Tests the DeepSORT-based tracking implementation including:
- Track creation and lifecycle
- Detection-to-track association
- IoU calculation
- Track aging and cleanup
- Identity persistence
"""

import pytest
from datetime import datetime, timedelta
from app.services.tracking_service import TrackingService, Detection, Track


class TestTrackingService:
    """Test suite for TrackingService"""

    def test_track_creation(self):
        """Test that new detections create tracks"""
        service = TrackingService(max_age=180, min_hits=1, iou_threshold=0.3)
        session_id = "test-session-1"

        service.start_session(session_id)

        # Create detection
        detection = Detection(
            bbox=[100, 100, 200, 200],
            confidence=0.9,
            user_id="user-123",
            recognition_confidence=0.85
        )

        # Update tracker
        tracks = service.update(session_id, [detection])

        # Verify track created
        assert len(tracks) == 1
        track = tracks[0]
        assert track.user_id == "user-123"
        assert track.recognition_confidence == 0.85
        assert track.detection_count == 1
        assert track.is_confirmed is True  # min_hits=1

    def test_track_association(self):
        """Test that similar detections are associated with existing tracks"""
        service = TrackingService(max_age=180, min_hits=1, iou_threshold=0.3)
        session_id = "test-session-2"

        service.start_session(session_id)

        # First detection
        detection1 = Detection(
            bbox=[100, 100, 200, 200],
            confidence=0.9,
            user_id="user-123",
            recognition_confidence=0.85
        )

        tracks1 = service.update(session_id, [detection1])
        track_id = tracks1[0].track_id

        # Second detection (similar location)
        detection2 = Detection(
            bbox=[105, 105, 205, 205],  # Slight movement
            confidence=0.9,
            user_id="user-123",
            recognition_confidence=0.88
        )

        tracks2 = service.update(session_id, [detection2])

        # Should update same track (not create new one)
        assert len(tracks2) == 1
        assert tracks2[0].track_id == track_id
        assert tracks2[0].detection_count == 2

    def test_track_aging(self):
        """Test that old tracks are removed after max_age"""
        service = TrackingService(max_age=1, min_hits=1, iou_threshold=0.3)  # 1 second max age
        session_id = "test-session-3"

        service.start_session(session_id)

        # Create track
        detection = Detection(
            bbox=[100, 100, 200, 200],
            confidence=0.9,
            user_id="user-123"
        )

        tracks1 = service.update(session_id, [detection])
        assert len(tracks1) == 1

        # Wait for track to age
        import time
        time.sleep(1.5)

        # Update without new detections
        tracks2 = service.update(session_id, [])

        # Track should be removed
        assert len(tracks2) == 0

    def test_multiple_tracks(self):
        """Test tracking multiple people simultaneously"""
        service = TrackingService(max_age=180, min_hits=1, iou_threshold=0.3)
        session_id = "test-session-4"

        service.start_session(session_id)

        # Create multiple detections
        detections = [
            Detection(bbox=[100, 100, 200, 200], confidence=0.9, user_id="user-1"),
            Detection(bbox=[300, 100, 400, 200], confidence=0.9, user_id="user-2"),
            Detection(bbox=[100, 300, 200, 400], confidence=0.9, user_id="user-3"),
        ]

        tracks = service.update(session_id, detections)

        # Should create 3 separate tracks
        assert len(tracks) == 3

        # Verify each has different user_id
        user_ids = {t.user_id for t in tracks}
        assert user_ids == {"user-1", "user-2", "user-3"}

    def test_iou_threshold(self):
        """Test that detections below IoU threshold create new tracks"""
        service = TrackingService(max_age=180, min_hits=1, iou_threshold=0.5)
        session_id = "test-session-5"

        service.start_session(session_id)

        # First detection
        detection1 = Detection(
            bbox=[100, 100, 200, 200],
            confidence=0.9,
            user_id="user-123"
        )

        tracks1 = service.update(session_id, [detection1])
        assert len(tracks1) == 1

        # Second detection (far away, low IoU)
        detection2 = Detection(
            bbox=[500, 500, 600, 600],
            confidence=0.9,
            user_id="user-456"
        )

        service.update(session_id, [detection2])

        # Should create new track (IoU too low) - check all active tracks
        all_tracks = service.get_active_tracks(session_id)
        assert len(all_tracks) == 2

    def test_identity_consistency_bonus(self):
        """Test that same user_id gets preference in matching"""
        service = TrackingService(max_age=180, min_hits=1, iou_threshold=0.3)
        session_id = "test-session-6"

        service.start_session(session_id)

        # Create initial track
        detection1 = Detection(
            bbox=[100, 100, 200, 200],
            confidence=0.9,
            user_id="user-123"
        )

        tracks1 = service.update(session_id, [detection1])
        track_id = tracks1[0].track_id

        # New detection with same user_id but slight movement
        detection2 = Detection(
            bbox=[110, 110, 210, 210],
            confidence=0.9,
            user_id="user-123"
        )

        tracks2 = service.update(session_id, [detection2])

        # Should match to same track
        assert len(tracks2) == 1
        assert tracks2[0].track_id == track_id

    def test_get_identified_users(self):
        """Test getting map of identified users"""
        service = TrackingService(max_age=180, min_hits=1, iou_threshold=0.3)
        session_id = "test-session-7"

        service.start_session(session_id)

        # Create multiple detections
        detections = [
            Detection(bbox=[100, 100, 200, 200], confidence=0.9, user_id="user-1", recognition_confidence=0.85),
            Detection(bbox=[300, 100, 400, 200], confidence=0.9, user_id="user-2", recognition_confidence=0.90),
            Detection(bbox=[100, 300, 200, 400], confidence=0.9, user_id=None),  # Unidentified
        ]

        service.update(session_id, detections)

        # Get identified users
        identified = service.get_identified_users(session_id)

        # Should have 2 identified users (not the unidentified one)
        assert len(identified) == 2
        assert "user-1" in identified
        assert "user-2" in identified

    def test_session_isolation(self):
        """Test that tracks are isolated per session"""
        service = TrackingService(max_age=180, min_hits=1, iou_threshold=0.3)

        session1 = "session-1"
        session2 = "session-2"

        service.start_session(session1)
        service.start_session(session2)

        # Create detection in session 1
        detection1 = Detection(
            bbox=[100, 100, 200, 200],
            confidence=0.9,
            user_id="user-1"
        )

        service.update(session1, [detection1])

        # Create detection in session 2
        detection2 = Detection(
            bbox=[100, 100, 200, 200],
            confidence=0.9,
            user_id="user-2"
        )

        service.update(session2, [detection2])

        # Verify isolation
        tracks1 = service.get_active_tracks(session1)
        tracks2 = service.get_active_tracks(session2)

        assert len(tracks1) == 1
        assert len(tracks2) == 1
        assert tracks1[0].user_id == "user-1"
        assert tracks2[0].user_id == "user-2"

    def test_session_cleanup(self):
        """Test that ending session removes all tracks"""
        service = TrackingService(max_age=180, min_hits=1, iou_threshold=0.3)
        session_id = "test-session-8"

        service.start_session(session_id)

        # Create tracks
        detections = [
            Detection(bbox=[100, 100, 200, 200], confidence=0.9, user_id="user-1"),
            Detection(bbox=[300, 100, 400, 200], confidence=0.9, user_id="user-2"),
        ]

        service.update(session_id, detections)
        assert len(service.get_active_tracks(session_id)) == 2

        # End session
        service.end_session(session_id)

        # Tracks should be gone
        assert len(service.get_active_tracks(session_id)) == 0

    def test_track_confidence_update(self):
        """Test that track confidence is updated with better detections"""
        service = TrackingService(max_age=180, min_hits=1, iou_threshold=0.3)
        session_id = "test-session-9"

        service.start_session(session_id)

        # First detection (low confidence)
        detection1 = Detection(
            bbox=[100, 100, 200, 200],
            confidence=0.9,
            user_id="user-123",
            recognition_confidence=0.70
        )

        tracks1 = service.update(session_id, [detection1])
        assert tracks1[0].recognition_confidence == 0.70

        # Second detection (higher confidence)
        detection2 = Detection(
            bbox=[105, 105, 205, 205],
            confidence=0.9,
            user_id="user-123",
            recognition_confidence=0.90
        )

        tracks2 = service.update(session_id, [detection2])

        # Confidence should be updated
        assert tracks2[0].recognition_confidence == 0.90

    def test_iou_computation(self):
        """Test IoU calculation accuracy"""
        service = TrackingService()

        # Perfect overlap (IoU = 1.0)
        bbox1 = [100, 100, 200, 200]
        bbox2 = [100, 100, 200, 200]
        iou = service._compute_iou(bbox1, bbox2)
        assert abs(iou - 1.0) < 0.01

        # No overlap (IoU = 0.0)
        bbox1 = [100, 100, 200, 200]
        bbox2 = [300, 300, 400, 400]
        iou = service._compute_iou(bbox1, bbox2)
        assert abs(iou - 0.0) < 0.01

        # Partial overlap (IoU ~ 0.14)
        bbox1 = [100, 100, 200, 200]
        bbox2 = [150, 150, 250, 250]
        iou = service._compute_iou(bbox1, bbox2)
        assert 0.13 < iou < 0.15

    def test_min_hits_confirmation(self):
        """Test that tracks require min_hits detections to confirm"""
        service = TrackingService(max_age=180, min_hits=3, iou_threshold=0.3)
        session_id = "test-session-10"

        service.start_session(session_id)

        detection = Detection(
            bbox=[100, 100, 200, 200],
            confidence=0.9,
            user_id="user-123"
        )

        # First detection
        tracks1 = service.update(session_id, [detection])
        assert tracks1[0].is_confirmed is False

        # Second detection
        detection.bbox = [105, 105, 205, 205]
        tracks2 = service.update(session_id, [detection])
        assert tracks2[0].is_confirmed is False

        # Third detection (reaches min_hits=3)
        detection.bbox = [110, 110, 210, 210]
        tracks3 = service.update(session_id, [detection])
        assert tracks3[0].is_confirmed is True

    def test_get_session_stats(self):
        """Test session statistics reporting"""
        service = TrackingService(max_age=180, min_hits=1, iou_threshold=0.3)
        session_id = "test-session-11"

        service.start_session(session_id)

        # Create mix of identified and unidentified detections
        detections = [
            Detection(bbox=[100, 100, 200, 200], confidence=0.9, user_id="user-1"),
            Detection(bbox=[300, 100, 400, 200], confidence=0.9, user_id="user-2"),
            Detection(bbox=[100, 300, 200, 400], confidence=0.9, user_id=None),
            Detection(bbox=[300, 300, 400, 400], confidence=0.9, user_id=None),
        ]

        service.update(session_id, detections)

        stats = service.get_session_stats(session_id)

        assert stats["total_tracks"] == 4
        assert stats["confirmed_tracks"] == 4  # min_hits=1
        assert stats["identified_tracks"] == 2
        assert stats["unidentified_tracks"] == 2


class TestDetection:
    """Test Detection dataclass methods"""

    def test_detection_to_ltwh(self):
        """Test bbox conversion to left-top-width-height format"""
        detection = Detection(
            bbox=[100, 150, 300, 450],  # [x1, y1, x2, y2]
            confidence=0.9
        )

        ltwh = detection.to_ltwh()

        assert ltwh == [100, 150, 200, 300]  # [left, top, width, height]

    def test_detection_to_tlbr(self):
        """Test bbox conversion to top-left-bottom-right format"""
        detection = Detection(
            bbox=[100, 150, 300, 450],  # [x1, y1, x2, y2]
            confidence=0.9
        )

        tlbr = detection.to_tlbr()

        assert tlbr == [150, 100, 450, 300]  # [top, left, bottom, right]
