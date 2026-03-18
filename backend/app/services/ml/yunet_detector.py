"""
YuNet Face Detector — ultra-lightweight CPU-optimized face detection.

Wraps OpenCV's built-in cv2.FaceDetectorYN (available since OpenCV 4.5.4).
Returns sv.Detections compatible with ByteTrack for the live feed pipeline.

Performance: ~2-5ms per frame on CPU (vs ~100-200ms for SCRFD).
Model size: ~228KB ONNX (vs ~30MB+ for InsightFace buffalo_l).
No embeddings — detection only (bboxes + confidence + 5-point landmarks).
"""

import logging
from pathlib import Path

import cv2
import numpy as np
import supervision as sv

logger = logging.getLogger(__name__)


class YuNetDetector:
    """CPU-optimized face detector using OpenCV's YuNet DNN model.

    Args:
        model_path:      Path to the YuNet ONNX model file.
        score_threshold: Minimum confidence to keep a detection (0-1).
        nms_threshold:   Non-maximum suppression IoU threshold.
        top_k:           Maximum detections before NMS.
    """

    def __init__(
        self,
        model_path: str,
        score_threshold: float = 0.5,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
    ) -> None:
        self._model_path = model_path
        self._score_threshold = score_threshold
        self._nms_threshold = nms_threshold
        self._top_k = top_k
        self._detector: cv2.FaceDetectorYN | None = None
        self._current_size: tuple[int, int] = (0, 0)

    def load(self, width: int, height: int) -> None:
        """Initialize the detector for a given frame size.

        Must be called before detect(). Can be called again if frame
        size changes (e.g., resolution switch).
        """
        model_file = Path(self._model_path)
        if not model_file.exists():
            raise FileNotFoundError(
                f"YuNet model not found at {self._model_path}. "
                f"Download from https://github.com/opencv/opencv_zoo"
            )

        self._detector = cv2.FaceDetectorYN.create(
            str(model_file),
            "",  # no config file for ONNX
            (width, height),
            self._score_threshold,
            self._nms_threshold,
            self._top_k,
            cv2.dnn.DNN_BACKEND_OPENCV,
            cv2.dnn.DNN_TARGET_CPU,
        )
        self._current_size = (width, height)
        logger.info(
            "YuNet detector loaded: %s (%dx%d, threshold=%.2f)",
            model_file.name,
            width,
            height,
            self._score_threshold,
        )

    def detect(self, frame: np.ndarray, scale: float = 1.0) -> sv.Detections:
        """Run face detection on a BGR frame.

        Args:
            frame: BGR numpy array.
            scale: Factor to multiply bboxes by (for resolution mapping).

        Returns:
            sv.Detections with xyxy bounding boxes and confidence scores.
            Empty detections if no faces found or detector not loaded.
        """
        if self._detector is None:
            return sv.Detections.empty()

        h, w = frame.shape[:2]

        # Auto-adjust input size if frame dimensions changed
        if (w, h) != self._current_size:
            self._detector.setInputSize((w, h))
            self._current_size = (w, h)

        try:
            _, faces = self._detector.detect(frame)
        except Exception as e:
            logger.error("YuNet detection error: %s", e)
            return sv.Detections.empty()

        if faces is None or len(faces) == 0:
            return sv.Detections.empty()

        # YuNet output: [N, 15]
        # Columns: x, y, w, h, kp_rx, kp_ry, kp_lx, kp_ly, kp_nx, kp_ny,
        #          kp_rmx, kp_rmy, kp_lmx, kp_lmy, score
        x = faces[:, 0]
        y = faces[:, 1]
        fw = faces[:, 2]
        fh = faces[:, 3]
        confidence = faces[:, 14]

        xyxy = np.stack([x, y, x + fw, y + fh], axis=1).astype(np.float32)

        if scale != 1.0:
            xyxy *= scale

        return sv.Detections(xyxy=xyxy, confidence=confidence.astype(np.float32))
