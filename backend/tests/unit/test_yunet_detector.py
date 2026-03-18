"""Tests for YuNetDetector — CPU-optimized face detection."""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch
import supervision as sv


class TestYuNetDetector:
    """Unit tests for YuNetDetector using mocked cv2.FaceDetectorYN."""

    @pytest.fixture
    def detector(self):
        from app.services.ml.yunet_detector import YuNetDetector

        with patch("app.services.ml.yunet_detector.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            with patch("cv2.FaceDetectorYN") as mock_yunet_cls:
                mock_instance = MagicMock()
                mock_yunet_cls.create.return_value = mock_instance

                det = YuNetDetector("fake_model.onnx", score_threshold=0.5)
                det.load(1280, 720)
                det._detector = mock_instance
                yield det, mock_instance

    def test_detect_returns_sv_detections(self, detector):
        """Should return sv.Detections with correct xyxy and confidence."""
        det, mock = detector
        # Simulate 2 detected faces: [x, y, w, h, ..., score] (15 columns)
        faces = np.array([
            [100, 200, 50, 60, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.95],
            [300, 400, 80, 90, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.88],
        ], dtype=np.float32)
        mock.detect.return_value = (1, faces)

        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        result = det.detect(frame)

        assert isinstance(result, sv.Detections)
        assert len(result) == 2
        # xyxy = [x, y, x+w, y+h]
        np.testing.assert_array_almost_equal(result.xyxy[0], [100, 200, 150, 260])
        np.testing.assert_array_almost_equal(result.xyxy[1], [300, 400, 380, 490])
        np.testing.assert_array_almost_equal(result.confidence, [0.95, 0.88])

    def test_detect_returns_empty_when_no_faces(self, detector):
        """Should return empty sv.Detections when no faces detected."""
        det, mock = detector
        mock.detect.return_value = (0, None)

        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        result = det.detect(frame)

        assert isinstance(result, sv.Detections)
        assert len(result) == 0

    def test_detect_returns_empty_when_detector_not_loaded(self):
        """Should return empty if detect() called before load()."""
        from app.services.ml.yunet_detector import YuNetDetector

        det = YuNetDetector("fake.onnx")
        # Don't call load()
        result = det.detect(np.zeros((720, 1280, 3), dtype=np.uint8))
        assert len(result) == 0

    def test_detect_applies_scale_factor(self, detector):
        """Bboxes should be multiplied by scale."""
        det, mock = detector
        faces = np.array([
            [100, 200, 50, 60, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.9],
        ], dtype=np.float32)
        mock.detect.return_value = (1, faces)

        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        result = det.detect(frame, scale=2.0)

        # xyxy = [100, 200, 150, 260] * 2.0 = [200, 400, 300, 520]
        np.testing.assert_array_almost_equal(result.xyxy[0], [200, 400, 300, 520])

    def test_auto_adjusts_input_size(self, detector):
        """Should call setInputSize when frame dimensions change."""
        det, mock = detector
        mock.detect.return_value = (0, None)

        # First call with 720p
        det.detect(np.zeros((720, 1280, 3), dtype=np.uint8))
        # Then call with 480p — should trigger setInputSize
        det.detect(np.zeros((480, 640, 3), dtype=np.uint8))

        mock.setInputSize.assert_called_with((640, 480))

    def test_handles_detection_exception(self, detector):
        """Should return empty on exception, not crash."""
        det, mock = detector
        mock.detect.side_effect = RuntimeError("inference failed")

        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        result = det.detect(frame)

        assert isinstance(result, sv.Detections)
        assert len(result) == 0

    def test_handles_empty_faces_array(self, detector):
        """Should handle empty numpy array from detector."""
        det, mock = detector
        mock.detect.return_value = (0, np.array([]))

        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        result = det.detect(frame)

        assert len(result) == 0
