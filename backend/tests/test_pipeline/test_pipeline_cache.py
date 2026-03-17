"""Tests for cache-first recognition path and identity cache integration.

Validates that VideoAnalyticsPipeline reads the attendance engine's identity
cache from Redis and uses cached identities before falling back to ArcFace.
"""

import json
import time
from unittest.mock import MagicMock

import numpy as np
import pytest
import supervision as sv

from app.pipeline.video_pipeline import VideoAnalyticsPipeline


class TestReadIdentityCache:
    """Tests for _read_identity_cache()."""

    def _make_pipeline(self, **overrides):
        cfg = {
            "room_id": "room-1",
            "session_id": "session-abc",
            "rtsp_source": "rtsp://mediamtx:8554/room-1/raw",
            "rtsp_target": "rtsp://mediamtx:8554/room-1/annotated",
            "width": 640,
            "height": 480,
            "fps": 25,
            "room_name": "Room 301",
            "det_model": "buffalo_sc",
        }
        cfg.update(overrides)
        return VideoAnalyticsPipeline(cfg)

    def test_returns_empty_when_no_redis(self):
        pipeline = self._make_pipeline()
        assert pipeline._redis is None
        assert pipeline._read_identity_cache() == {}

    def test_returns_empty_when_no_session_id(self):
        pipeline = self._make_pipeline(session_id=None)
        pipeline._redis = MagicMock()
        # Should not even call Redis when session_id is None
        assert pipeline._read_identity_cache() == {}
        pipeline._redis.hgetall.assert_not_called()

    def test_returns_empty_on_cache_miss(self):
        pipeline = self._make_pipeline()
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {}
        pipeline._redis = mock_redis

        result = pipeline._read_identity_cache()
        assert result == {}
        mock_redis.hgetall.assert_called_once_with(
            "attendance:room-1:session-abc:identities"
        )

    def test_parses_cached_identities(self):
        pipeline = self._make_pipeline()
        mock_redis = MagicMock()

        # Simulate Redis returning bytes (decode_responses=False)
        mock_redis.hgetall.return_value = {
            b"user-1": json.dumps({
                "name": "Juan",
                "confidence": 0.95,
                "bbox": [100, 100, 200, 200],
            }).encode(),
            b"user-2": json.dumps({
                "name": "Maria",
                "confidence": 0.88,
                "bbox": [300, 100, 400, 200],
            }).encode(),
        }
        pipeline._redis = mock_redis

        result = pipeline._read_identity_cache()
        assert len(result) == 2
        assert result["user-1"]["name"] == "Juan"
        assert result["user-1"]["confidence"] == 0.95
        assert result["user-2"]["name"] == "Maria"

    def test_handles_string_keys(self):
        """When Redis returns strings (decode_responses=True), parsing still works."""
        pipeline = self._make_pipeline()
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {
            "user-1": json.dumps({
                "name": "Juan",
                "confidence": 0.95,
                "bbox": [100, 100, 200, 200],
            }),
        }
        pipeline._redis = mock_redis

        result = pipeline._read_identity_cache()
        assert result["user-1"]["name"] == "Juan"

    def test_returns_empty_on_redis_error(self):
        pipeline = self._make_pipeline()
        mock_redis = MagicMock()
        mock_redis.hgetall.side_effect = ConnectionError("Redis down")
        pipeline._redis = mock_redis

        result = pipeline._read_identity_cache()
        assert result == {}


class TestMatchFromCache:
    """Tests for _match_from_cache() static method."""

    def test_returns_none_for_empty_cache(self):
        result = VideoAnalyticsPipeline._match_from_cache(
            (100, 100, 200, 200), {}
        )
        assert result is None

    def test_matches_closest_bbox_by_centroid(self):
        cached = {
            "user-far": {
                "name": "Far Person",
                "confidence": 0.90,
                "bbox": [500, 500, 600, 600],
            },
            "user-close": {
                "name": "Close Person",
                "confidence": 0.95,
                "bbox": [105, 105, 205, 205],
            },
        }
        # Track bbox at (100,100)-(200,200), centroid (150, 150)
        # user-close centroid: (155, 155) -> distance ~7.07
        # user-far centroid: (550, 550) -> distance ~565.7
        result = VideoAnalyticsPipeline._match_from_cache(
            (100, 100, 200, 200), cached
        )
        assert result is not None
        assert result["user_id"] == "user-close"
        assert result["name"] == "Close Person"
        assert result["confidence"] == 0.95

    def test_returns_none_when_all_too_far(self):
        cached = {
            "user-1": {
                "name": "Far Person",
                "confidence": 0.90,
                "bbox": [500, 500, 600, 600],
            },
        }
        # Track at (100,100)-(200,200), cache at (500,500)-(600,600)
        # Centroid distance ~ 565 px, well above 100 px threshold
        result = VideoAnalyticsPipeline._match_from_cache(
            (100, 100, 200, 200), cached
        )
        assert result is None

    def test_custom_max_distance(self):
        cached = {
            "user-1": {
                "name": "Nearby",
                "confidence": 0.85,
                "bbox": [180, 180, 280, 280],
            },
        }
        # Track centroid (150, 150), cache centroid (230, 230)
        # Distance = sqrt(80^2 + 80^2) ~ 113.1
        # Default max_distance=100 -> miss
        result = VideoAnalyticsPipeline._match_from_cache(
            (100, 100, 200, 200), cached, max_distance=100.0
        )
        assert result is None

        # With higher threshold -> hit
        result = VideoAnalyticsPipeline._match_from_cache(
            (100, 100, 200, 200), cached, max_distance=120.0
        )
        assert result is not None
        assert result["user_id"] == "user-1"

    def test_skips_entries_without_bbox(self):
        cached = {
            "user-no-bbox": {"name": "NoBbox", "confidence": 0.9},
            "user-with-bbox": {
                "name": "WithBbox",
                "confidence": 0.88,
                "bbox": [105, 105, 205, 205],
            },
        }
        result = VideoAnalyticsPipeline._match_from_cache(
            (100, 100, 200, 200), cached
        )
        assert result is not None
        assert result["user_id"] == "user-with-bbox"

    def test_returns_student_id_from_cache(self):
        cached = {
            "user-1": {
                "name": "Juan",
                "student_id": "2021-0001",
                "confidence": 0.95,
                "bbox": [100, 100, 200, 200],
            },
        }
        result = VideoAnalyticsPipeline._match_from_cache(
            (100, 100, 200, 200), cached
        )
        assert result is not None
        assert result["student_id"] == "2021-0001"


class TestRecognizeNewTracksWithCache:
    """Tests for the cache-first path in _recognize_new_tracks()."""

    def _make_pipeline(self, **overrides):
        cfg = {
            "room_id": "room-1",
            "session_id": "session-abc",
            "rtsp_source": "rtsp://mediamtx:8554/room-1/raw",
            "rtsp_target": "rtsp://mediamtx:8554/room-1/annotated",
            "width": 640,
            "height": 480,
            "fps": 25,
            "room_name": "Room 301",
            "det_model": "buffalo_sc",
        }
        cfg.update(overrides)
        return VideoAnalyticsPipeline(cfg)

    def test_cache_hit_skips_arcface(self):
        """When identity cache has a match, ArcFace should NOT be called."""
        pipeline = self._make_pipeline()

        # Set up mock Redis with cached identity near the track
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {
            b"user-1": json.dumps({
                "name": "Juan Cruz",
                "student_id": "2021-0001",
                "confidence": 0.95,
                "bbox": [102, 102, 198, 198],  # Very close to (100,100,200,200)
            }).encode(),
        }
        pipeline._redis = mock_redis

        # Mock ArcFace detector + FAISS (should NOT be called)
        mock_detector = MagicMock()
        mock_faiss = MagicMock()
        pipeline._detector = mock_detector
        pipeline._faiss = mock_faiss

        # Set up a confirmed but unidentified track
        pipeline._confirmed_track_ids = {1}
        pipeline._track_frame_counts = {1: 5}

        tracked = sv.Detections(
            xyxy=np.array([[100, 100, 200, 200]], dtype=np.float32),
            confidence=np.array([0.9]),
            tracker_id=np.array([1]),
        )
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        pipeline._recognize_new_tracks(frame, tracked)

        # Identity should be set from cache
        assert 1 in pipeline._identities
        assert pipeline._identities[1]["user_id"] == "user-1"
        assert pipeline._identities[1]["name"] == "Juan Cruz"
        assert pipeline._identities[1]["confidence"] == 0.95

        # ArcFace should NOT have been called
        mock_detector.get_embedding.assert_not_called()
        mock_faiss.search_with_margin.assert_not_called()

    def test_cache_miss_falls_back_to_arcface(self):
        """When cache has no nearby match, ArcFace should be used as fallback."""
        pipeline = self._make_pipeline()

        # Set up mock Redis with cached identity far from the track
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {
            b"user-far": json.dumps({
                "name": "Far Person",
                "confidence": 0.90,
                "bbox": [500, 500, 600, 600],  # Far from (100,100,200,200)
            }).encode(),
        }
        pipeline._redis = mock_redis

        # Mock ArcFace detector + FAISS
        mock_detector = MagicMock()
        mock_detector.get_embedding.return_value = np.random.randn(512)
        mock_faiss = MagicMock()
        mock_faiss.search_with_margin.return_value = {
            "user_id": "user-2",
            "name": "Maria Santos",
            "student_id": "2021-0002",
            "confidence": 0.88,
        }
        pipeline._detector = mock_detector
        pipeline._faiss = mock_faiss

        # Set up a confirmed but unidentified track
        pipeline._confirmed_track_ids = {1}
        pipeline._track_frame_counts = {1: 5}

        tracked = sv.Detections(
            xyxy=np.array([[100, 100, 200, 200]], dtype=np.float32),
            confidence=np.array([0.9]),
            tracker_id=np.array([1]),
        )
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        pipeline._recognize_new_tracks(frame, tracked)

        # ArcFace should have been called
        mock_detector.get_embedding.assert_called_once()
        mock_faiss.search_with_margin.assert_called_once()

        # Identity should come from ArcFace
        assert 1 in pipeline._identities
        assert pipeline._identities[1]["user_id"] == "user-2"
        assert pipeline._identities[1]["name"] == "Maria Santos"

    def test_no_redis_falls_back_to_arcface(self):
        """When Redis is unavailable, ArcFace should be used directly."""
        pipeline = self._make_pipeline()
        pipeline._redis = None  # No Redis

        mock_detector = MagicMock()
        mock_detector.get_embedding.return_value = np.random.randn(512)
        mock_faiss = MagicMock()
        mock_faiss.search_with_margin.return_value = {
            "user_id": "user-3",
            "name": "Pedro Reyes",
            "student_id": "2021-0003",
            "confidence": 0.91,
        }
        pipeline._detector = mock_detector
        pipeline._faiss = mock_faiss

        pipeline._confirmed_track_ids = {1}
        pipeline._track_frame_counts = {1: 5}

        tracked = sv.Detections(
            xyxy=np.array([[100, 100, 200, 200]], dtype=np.float32),
            confidence=np.array([0.9]),
            tracker_id=np.array([1]),
        )
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        pipeline._recognize_new_tracks(frame, tracked)

        mock_detector.get_embedding.assert_called_once()
        assert pipeline._identities[1]["name"] == "Pedro Reyes"

    def test_skips_already_identified_tracks(self):
        """Tracks that already have an identity should be skipped entirely."""
        pipeline = self._make_pipeline()

        mock_redis = MagicMock()
        pipeline._redis = mock_redis

        # Track 1 already identified
        pipeline._identities = {
            1: {"user_id": "u1", "name": "Already Known", "confidence": 0.99}
        }
        pipeline._confirmed_track_ids = {1}

        tracked = sv.Detections(
            xyxy=np.array([[100, 100, 200, 200]], dtype=np.float32),
            confidence=np.array([0.9]),
            tracker_id=np.array([1]),
        )
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        pipeline._recognize_new_tracks(frame, tracked)

        # Redis should still be read (for other potential tracks), but identity unchanged
        assert pipeline._identities[1]["name"] == "Already Known"

    def test_skips_unconfirmed_tracks(self):
        """Unconfirmed tracks (< 3 frames) should not be processed."""
        pipeline = self._make_pipeline()

        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {
            b"user-1": json.dumps({
                "name": "Juan",
                "confidence": 0.95,
                "bbox": [100, 100, 200, 200],
            }).encode(),
        }
        pipeline._redis = mock_redis

        # Track NOT in confirmed set
        pipeline._confirmed_track_ids = set()
        pipeline._track_frame_counts = {1: 1}

        tracked = sv.Detections(
            xyxy=np.array([[100, 100, 200, 200]], dtype=np.float32),
            confidence=np.array([0.9]),
            tracker_id=np.array([1]),
        )
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        pipeline._recognize_new_tracks(frame, tracked)

        # Track should not be identified
        assert 1 not in pipeline._identities

    def test_empty_cache_falls_back_to_arcface(self):
        """When Redis returns empty hash, ArcFace should be used."""
        pipeline = self._make_pipeline()

        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {}
        pipeline._redis = mock_redis

        mock_detector = MagicMock()
        mock_detector.get_embedding.return_value = np.random.randn(512)
        mock_faiss = MagicMock()
        mock_faiss.search_with_margin.return_value = {
            "user_id": "user-4",
            "name": "Ana Lim",
            "student_id": "2021-0004",
            "confidence": 0.87,
        }
        pipeline._detector = mock_detector
        pipeline._faiss = mock_faiss

        pipeline._confirmed_track_ids = {1}
        pipeline._track_frame_counts = {1: 5}

        tracked = sv.Detections(
            xyxy=np.array([[100, 100, 200, 200]], dtype=np.float32),
            confidence=np.array([0.9]),
            tracker_id=np.array([1]),
        )
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        pipeline._recognize_new_tracks(frame, tracked)

        mock_detector.get_embedding.assert_called_once()
        assert pipeline._identities[1]["name"] == "Ana Lim"

    def test_no_detector_no_faiss_still_uses_cache(self):
        """Even without ML models loaded, cache should work."""
        pipeline = self._make_pipeline()
        pipeline._detector = None
        pipeline._faiss = None

        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {
            b"user-1": json.dumps({
                "name": "Juan",
                "confidence": 0.95,
                "bbox": [105, 105, 195, 195],
            }).encode(),
        }
        pipeline._redis = mock_redis

        pipeline._confirmed_track_ids = {1}
        pipeline._track_frame_counts = {1: 5}

        tracked = sv.Detections(
            xyxy=np.array([[100, 100, 200, 200]], dtype=np.float32),
            confidence=np.array([0.9]),
            tracker_id=np.array([1]),
        )
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        pipeline._recognize_new_tracks(frame, tracked)

        assert 1 in pipeline._identities
        assert pipeline._identities[1]["name"] == "Juan"


class TestPublishStateKeyRename:
    """Verify the Redis key was renamed from :state to :status."""

    def _make_pipeline(self):
        cfg = {
            "room_id": "room-1",
            "session_id": "session-abc",
            "rtsp_source": "rtsp://mediamtx:8554/room-1/raw",
            "rtsp_target": "rtsp://mediamtx:8554/room-1/annotated",
            "width": 640,
            "height": 480,
            "fps": 25,
            "room_name": "Room 301",
            "det_model": "buffalo_sc",
        }
        return VideoAnalyticsPipeline(cfg)

    def test_publishes_to_status_key(self):
        pipeline = self._make_pipeline()
        mock_redis = MagicMock()
        pipeline._redis = mock_redis

        pipeline._publish_state_to_redis([])

        # Should use :status, NOT :state
        calls = mock_redis.set.call_args_list
        keys_written = [call[0][0] for call in calls]
        assert "pipeline:room-1:status" in keys_written
        assert "pipeline:room-1:state" not in keys_written
        assert "pipeline:room-1:heartbeat" in keys_written


class TestSessionIdFromConfig:
    """Verify session_id is extracted from config."""

    def test_session_id_set(self):
        cfg = {
            "room_id": "room-1",
            "session_id": "sess-xyz",
            "rtsp_source": "rtsp://x",
            "rtsp_target": "rtsp://x",
            "width": 640,
            "height": 480,
            "fps": 25,
            "room_name": "R1",
            "det_model": "m",
        }
        pipeline = VideoAnalyticsPipeline(cfg)
        assert pipeline._session_id == "sess-xyz"

    def test_session_id_defaults_to_none(self):
        cfg = {
            "room_id": "room-1",
            "rtsp_source": "rtsp://x",
            "rtsp_target": "rtsp://x",
            "width": 640,
            "height": 480,
            "fps": 25,
            "room_name": "R1",
            "det_model": "m",
        }
        pipeline = VideoAnalyticsPipeline(cfg)
        assert pipeline._session_id is None
