"""
Unit tests for AttendanceScanEngine — stateless frame scan with SCRFD + ArcFace.

All external dependencies (FrameGrabber, InsightFace, FAISS) are mocked.
No real ML models or RTSP connections are needed.
"""

import numpy as np
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_frame(value: int = 128) -> np.ndarray:
    """Return a small 480x640 BGR frame filled with *value*."""
    return np.full((480, 640, 3), value, dtype=np.uint8)


def _make_detected_face(*, bbox, det_score, embedding=None):
    """Create a mock InsightFace DetectedFace-like object."""
    face = MagicMock()
    face.bbox = np.array(bbox, dtype=np.float32)
    face.det_score = det_score
    if embedding is None:
        embedding = np.random.randn(512).astype(np.float32)
        embedding /= np.linalg.norm(embedding)
    face.normed_embedding = embedding
    return face


def _build_engine(
    *,
    frame=None,
    insight_faces=None,
    faiss_results=None,
    detection_threshold=0.5,
    recognition_threshold=0.45,
    recognition_margin=0.1,
):
    """
    Construct an AttendanceScanEngine with mocked dependencies.

    Args:
        frame: What frame_grabber.grab() returns (None = no frame).
        insight_faces: List of mock faces from insightface app.get().
        faiss_results: List of dicts from faiss_manager.search_with_margin(),
                       one per face. If shorter than insight_faces, remaining
                       faces get no-match results.
    """
    from app.services.attendance_engine import AttendanceScanEngine

    frame_grabber = MagicMock()
    frame_grabber.grab.return_value = frame

    insightface_model = MagicMock()
    insightface_model.app = MagicMock()
    insightface_model.app.get.return_value = insight_faces or []

    faiss_manager = MagicMock()
    if faiss_results is not None:
        faiss_manager.search_with_margin.side_effect = list(faiss_results)
    else:
        faiss_manager.search_with_margin.return_value = {
            "user_id": None,
            "confidence": 0.0,
            "is_ambiguous": False,
        }

    engine = AttendanceScanEngine(
        frame_grabber=frame_grabber,
        insightface_model=insightface_model,
        faiss_manager=faiss_manager,
        detection_threshold=detection_threshold,
        recognition_threshold=recognition_threshold,
        recognition_margin=recognition_margin,
    )

    return engine, frame_grabber, insightface_model, faiss_manager


# ---------------------------------------------------------------------------
# Test: scan_frame detects and recognizes faces
# ---------------------------------------------------------------------------

class TestScanFrameDetectsAndRecognizes:
    """Mock insightface to return 2 faces, mock FAISS to match 1."""

    def test_two_faces_one_recognized(self):
        face_a = _make_detected_face(
            bbox=[10, 20, 110, 120], det_score=0.85,
        )
        face_b = _make_detected_face(
            bbox=[200, 50, 300, 150], det_score=0.72,
        )

        faiss_results = [
            {"user_id": "user-abc-123", "confidence": 0.78, "is_ambiguous": False},
            {"user_id": None, "confidence": 0.30, "is_ambiguous": False},
        ]

        engine, _, _, _ = _build_engine(
            frame=_make_frame(),
            insight_faces=[face_a, face_b],
            faiss_results=faiss_results,
        )

        result = engine.scan_frame()

        assert result is not None
        assert result.detected_faces == 2
        assert len(result.recognized) == 1
        assert len(result.unrecognized) == 1
        assert result.scan_duration_ms >= 0

        rec = result.recognized[0]
        assert rec.user_id == "user-abc-123"
        assert rec.confidence == 0.78
        assert rec.det_score == 0.85
        assert rec.bbox == (10, 20, 110, 120)

        unrec = result.unrecognized[0]
        assert unrec.det_score == 0.72
        assert unrec.best_confidence == 0.30
        assert unrec.bbox == (200, 50, 300, 150)

    def test_all_faces_recognized(self):
        face_a = _make_detected_face(bbox=[0, 0, 50, 50], det_score=0.90)
        face_b = _make_detected_face(bbox=[100, 100, 200, 200], det_score=0.88)

        faiss_results = [
            {"user_id": "user-1", "confidence": 0.82, "is_ambiguous": False},
            {"user_id": "user-2", "confidence": 0.76, "is_ambiguous": False},
        ]

        engine, _, _, _ = _build_engine(
            frame=_make_frame(),
            insight_faces=[face_a, face_b],
            faiss_results=faiss_results,
        )

        result = engine.scan_frame()

        assert result is not None
        assert result.detected_faces == 2
        assert len(result.recognized) == 2
        assert len(result.unrecognized) == 0

    def test_ambiguous_match_is_treated_as_unrecognized(self):
        """When FAISS returns is_ambiguous=True, the face should be unrecognized."""
        face = _make_detected_face(bbox=[10, 10, 60, 60], det_score=0.80)

        faiss_results = [
            {"user_id": "user-x", "confidence": 0.55, "is_ambiguous": True},
        ]

        engine, _, _, _ = _build_engine(
            frame=_make_frame(),
            insight_faces=[face],
            faiss_results=faiss_results,
        )

        result = engine.scan_frame()

        assert result is not None
        assert len(result.recognized) == 0
        assert len(result.unrecognized) == 1
        assert result.unrecognized[0].best_confidence == 0.55


# ---------------------------------------------------------------------------
# Test: scan_frame returns None when no frame available
# ---------------------------------------------------------------------------

class TestScanFrameNoFrame:
    def test_returns_none_when_grabber_returns_none(self):
        engine, _, _, _ = _build_engine(frame=None)

        result = engine.scan_frame()

        assert result is None

    def test_insightface_not_called_when_no_frame(self):
        engine, _, insightface_model, _ = _build_engine(frame=None)

        engine.scan_frame()

        insightface_model.app.get.assert_not_called()


# ---------------------------------------------------------------------------
# Test: scan_frame handles no faces detected
# ---------------------------------------------------------------------------

class TestScanFrameNoFaces:
    def test_returns_empty_scan_result(self):
        engine, _, _, _ = _build_engine(
            frame=_make_frame(),
            insight_faces=[],
        )

        result = engine.scan_frame()

        assert result is not None
        assert result.detected_faces == 0
        assert len(result.recognized) == 0
        assert len(result.unrecognized) == 0
        assert result.scan_duration_ms >= 0

    def test_faiss_not_called_when_no_faces(self):
        engine, _, _, faiss_manager = _build_engine(
            frame=_make_frame(),
            insight_faces=[],
        )

        engine.scan_frame()

        faiss_manager.search_with_margin.assert_not_called()


# ---------------------------------------------------------------------------
# Test: scan_frame filters low-confidence detections
# ---------------------------------------------------------------------------

class TestScanFrameFiltersLowConfidence:
    def test_filters_below_default_threshold(self):
        """Faces with det_score < 0.5 (default) should be discarded."""
        high_conf = _make_detected_face(bbox=[10, 10, 60, 60], det_score=0.85)
        low_conf = _make_detected_face(bbox=[100, 100, 200, 200], det_score=0.30)

        faiss_results = [
            {"user_id": "user-1", "confidence": 0.70, "is_ambiguous": False},
        ]

        engine, _, _, faiss_manager = _build_engine(
            frame=_make_frame(),
            insight_faces=[high_conf, low_conf],
            faiss_results=faiss_results,
        )

        result = engine.scan_frame()

        assert result is not None
        # Only the high-confidence face should survive filtering
        assert result.detected_faces == 1
        assert len(result.recognized) == 1
        assert result.recognized[0].det_score == 0.85
        # FAISS should only be called once (for the surviving face)
        assert faiss_manager.search_with_margin.call_count == 1

    def test_filters_with_custom_threshold(self):
        """Custom detection_threshold should be respected."""
        face_a = _make_detected_face(bbox=[10, 10, 60, 60], det_score=0.70)
        face_b = _make_detected_face(bbox=[100, 100, 200, 200], det_score=0.55)

        engine, _, _, faiss_manager = _build_engine(
            frame=_make_frame(),
            insight_faces=[face_a, face_b],
            detection_threshold=0.75,
        )

        result = engine.scan_frame()

        assert result is not None
        # Both should be filtered at threshold=0.75 (0.70 < 0.75, 0.55 < 0.75)
        assert result.detected_faces == 0
        assert faiss_manager.search_with_margin.call_count == 0

    def test_exactly_at_threshold_is_included(self):
        """A face with det_score exactly equal to threshold should pass."""
        face = _make_detected_face(bbox=[10, 10, 60, 60], det_score=0.50)

        faiss_results = [
            {"user_id": None, "confidence": 0.20, "is_ambiguous": False},
        ]

        engine, _, _, _ = _build_engine(
            frame=_make_frame(),
            insight_faces=[face],
            faiss_results=faiss_results,
            detection_threshold=0.50,
        )

        result = engine.scan_frame()

        assert result is not None
        assert result.detected_faces == 1


# ---------------------------------------------------------------------------
# Test: configurable thresholds
# ---------------------------------------------------------------------------

class TestConfigurableThresholds:
    def test_recognition_threshold_passed_to_faiss(self):
        """recognition_threshold should be forwarded to FAISS search_with_margin."""
        face = _make_detected_face(bbox=[10, 10, 60, 60], det_score=0.90)

        engine, _, _, faiss_manager = _build_engine(
            frame=_make_frame(),
            insight_faces=[face],
            recognition_threshold=0.55,
            recognition_margin=0.15,
        )
        faiss_manager.search_with_margin.return_value = {
            "user_id": None,
            "confidence": 0.0,
            "is_ambiguous": False,
        }

        engine.scan_frame()

        call_kwargs = faiss_manager.search_with_margin.call_args
        assert call_kwargs[1]["threshold"] == 0.55
        assert call_kwargs[1]["margin"] == 0.15


# ---------------------------------------------------------------------------
# Test: ScanResult dataclass fields
# ---------------------------------------------------------------------------

class TestScanResultDataclass:
    def test_scan_duration_is_positive(self):
        engine, _, _, _ = _build_engine(
            frame=_make_frame(),
            insight_faces=[],
        )

        result = engine.scan_frame()

        assert result.scan_duration_ms >= 0
        assert isinstance(result.scan_duration_ms, float)
