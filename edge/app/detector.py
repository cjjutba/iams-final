"""
Face Detection with MediaPipe

Implements face detection using MediaPipe Face Detection model optimized for Raspberry Pi.

Features:
- TFLite runtime for efficient ARM execution
- Short-range model optimized for indoor classroom scenarios
- Configurable confidence threshold
- Bounding box extraction
- Handles multiple faces per frame
- Auto-recovery on graph errors (re-creates detector)
"""

import os

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from app.config import config, logger

# MediaPipe model URLs — only the short-range model is compatible with the
# Tasks API. The legacy full-range sparse model from mediapipe-assets uses
# a different anchor configuration (2304 boxes vs 896) and will fail with:
#   "RET_CHECK failure raw_box_tensor->shape().dims[1] == num_boxes_"
_MODEL_URLS = {
    0: "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite",
}

_MODEL_FILENAMES = {
    0: "blaze_face_short_range.tflite",
}


def _get_model_path(model_selection: int = 0) -> str:
    """
    Get path to MediaPipe face detection model, downloading if not cached.

    Args:
        model_selection: 0 = short-range (only supported model for Tasks API)

    Returns:
        Path to the .tflite model file
    """
    import urllib.request

    # Force short-range — the full-range sparse model is NOT compatible with
    # the MediaPipe Tasks API and will produce tensor dimension mismatches.
    if model_selection != 0:
        logger.warning(
            f"DETECTION_MODEL={model_selection} requested, but only short-range (0) "
            "is compatible with the MediaPipe Tasks API. Falling back to short-range."
        )
        model_selection = 0

    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".models")
    os.makedirs(cache_dir, exist_ok=True)

    filename = _MODEL_FILENAMES[0]
    model_path = os.path.join(cache_dir, filename)

    if not os.path.exists(model_path):
        url = _MODEL_URLS[0]
        logger.info(f"Downloading MediaPipe face detection model ({filename})...")
        urllib.request.urlretrieve(url, model_path)
        logger.info(f"Model saved to {model_path}")
    else:
        logger.debug(f"Using cached model: {model_path}")

    return model_path


class FaceBox:
    """
    Face bounding box data structure.

    Attributes:
        x: X-coordinate of top-left corner
        y: Y-coordinate of top-left corner
        width: Box width
        height: Box height
        confidence: Detection confidence (0.0-1.0)
    """

    def __init__(self, x: int, y: int, width: int, height: int, confidence: float):
        self.x = max(0, x)
        self.y = max(0, y)
        self.width = max(1, width)
        self.height = max(1, height)
        self.confidence = confidence

    def to_list(self) -> list[int]:
        """Convert to [x, y, width, height] format for API"""
        return [self.x, self.y, self.width, self.height]

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height, "confidence": self.confidence}

    def __repr__(self) -> str:
        return f"FaceBox(x={self.x}, y={self.y}, w={self.width}, h={self.height}, conf={self.confidence:.2f})"


class FaceDetector:
    """
    MediaPipe-based face detector optimized for Raspberry Pi.

    Uses MediaPipe Face Detection with TFLite runtime for efficient execution on ARM.
    Configured for short-range detection suitable for indoor classroom monitoring.

    Includes automatic error recovery: if the MediaPipe graph enters an error
    state (e.g. from tensor dimension mismatches), the detector is re-created
    transparently on the next call to detect().
    """

    def __init__(self):
        self.detector: vision.FaceDetector | None = None
        self.is_initialized = False
        self._consecutive_errors = 0
        self._max_consecutive_errors = 3

    def initialize(self) -> bool:
        """
        Initialize MediaPipe Face Detection model.

        Downloads model on first run (cached for subsequent calls).

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing MediaPipe Face Detector...")

            # Download/cache model file (always short-range for Tasks API compat)
            model_path = _get_model_path(config.DETECTION_MODEL)

            # Create face detector options
            base_options = python.BaseOptions(model_asset_path=model_path)

            options = vision.FaceDetectorOptions(
                base_options=base_options,
                min_detection_confidence=config.DETECTION_CONFIDENCE,
            )

            self.detector = vision.FaceDetector.create_from_options(options)
            self.is_initialized = True
            self._consecutive_errors = 0

            logger.info(
                f"MediaPipe Face Detector initialized - confidence={config.DETECTION_CONFIDENCE}, model=short-range"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Face Detector: {e}")
            self.detector = None
            self.is_initialized = False
            return False

    def _try_recover(self) -> bool:
        """
        Attempt to recover from a graph error by closing the current
        detector and re-creating it from scratch.

        Returns:
            True if recovery succeeded
        """
        logger.warning("Attempting to recover MediaPipe detector from error state...")
        self.close()
        return self.initialize()

    # Max dimension for MediaPipe input (avoids tensor overflow on large frames).
    # Short-range model works reliably at 1280. Higher values increase detection
    # range but risk tensor overflow on some platforms.
    MAX_DETECT_DIM = 1280

    # Minimum face bounding box size in pixels. Detections smaller than this
    # in either dimension are discarded — they produce poor-quality embeddings
    # and waste backend resources.
    MIN_FACE_PIXELS = 40

    def detect(self, frame: np.ndarray) -> list[FaceBox]:
        """
        Detect faces in a frame.

        Args:
            frame: BGR image as numpy array (H, W, 3)

        Returns:
            List of FaceBox objects for detected faces

        Notes:
            - Automatically downscales frames larger than MAX_DETECT_DIM
            - Coordinates are mapped back to original frame resolution
            - Returns empty list if no faces detected
            - Auto-recovers if the MediaPipe graph enters an error state
        """
        if not self.is_initialized or self.detector is None:
            logger.error("Detector not initialized - call initialize() first")
            return []

        try:
            frame_height, frame_width = frame.shape[:2]

            # Downscale large frames to avoid MediaPipe tensor overflow
            scale = 1.0
            detect_frame = frame
            max_dim = max(frame_width, frame_height)
            if max_dim > self.MAX_DETECT_DIM:
                scale = self.MAX_DETECT_DIM / max_dim
                new_w = int(frame_width * scale)
                new_h = int(frame_height * scale)
                detect_frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                logger.debug(f"Downscaled {frame_width}x{frame_height} -> {new_w}x{new_h} for detection")

            # Convert BGR to RGB for MediaPipe
            frame_rgb = cv2.cvtColor(detect_frame, cv2.COLOR_BGR2RGB)

            # Create MediaPipe Image
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

            # Detect faces
            detection_result = self.detector.detect(mp_image)

            # Reset error counter on success
            self._consecutive_errors = 0

            if not detection_result.detections:
                return []

            # Extract bounding boxes and map back to original resolution
            face_boxes = []
            inv_scale = 1.0 / scale

            for detection in detection_result.detections:
                bbox = detection.bounding_box

                # Scale coordinates back to original frame size
                x = int(bbox.origin_x * inv_scale)
                y = int(bbox.origin_y * inv_scale)
                width = int(bbox.width * inv_scale)
                height = int(bbox.height * inv_scale)

                # Get confidence score
                confidence = detection.categories[0].score if detection.categories else 0.0

                face_box = FaceBox(x, y, width, height, confidence)

                # Skip faces that are too small for reliable recognition
                if face_box.width < self.MIN_FACE_PIXELS or face_box.height < self.MIN_FACE_PIXELS:
                    logger.debug(f"Skipping small face: {face_box.width}x{face_box.height} < {self.MIN_FACE_PIXELS}px")
                    continue

                face_boxes.append(face_box)

            logger.debug(f"Detected {len(face_boxes)} faces in frame")
            return face_boxes

        except Exception as e:
            self._consecutive_errors += 1
            logger.error(f"Face detection error: {e}")

            # If we've had multiple consecutive errors, the graph is likely
            # in a broken state. Try to recover by re-creating the detector.
            if self._consecutive_errors >= self._max_consecutive_errors:
                logger.warning(f"{self._consecutive_errors} consecutive detection errors — attempting graph recovery")
                if self._try_recover():
                    logger.info("MediaPipe detector recovered successfully")
                else:
                    logger.error("MediaPipe detector recovery failed")

            return []

    def detect_and_visualize(self, frame: np.ndarray, draw_boxes: bool = True) -> tuple[list[FaceBox], np.ndarray]:
        """
        Detect faces and optionally draw bounding boxes.

        Args:
            frame: BGR image as numpy array
            draw_boxes: Whether to draw bounding boxes on frame

        Returns:
            Tuple of (face_boxes, annotated_frame)
        """
        face_boxes = self.detect(frame)

        if not draw_boxes or not face_boxes:
            return face_boxes, frame.copy()

        # Draw bounding boxes
        annotated_frame = frame.copy()

        for face_box in face_boxes:
            # Draw rectangle
            cv2.rectangle(
                annotated_frame,
                (face_box.x, face_box.y),
                (face_box.x + face_box.width, face_box.y + face_box.height),
                (0, 255, 0),  # Green
                2,
            )

            # Draw confidence score
            label = f"{face_box.confidence:.2f}"
            cv2.putText(
                annotated_frame, label, (face_box.x, face_box.y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2
            )

        return face_boxes, annotated_frame

    def close(self) -> None:
        """
        Release detector resources.
        """
        if self.detector:
            try:
                self.detector.close()
            except Exception as e:
                logger.error(f"Error closing detector: {e}")
            finally:
                self.detector = None
                self.is_initialized = False
                logger.info("Face detector closed")

    def __enter__(self):
        """Support 'with' statement"""
        if not self.initialize():
            raise RuntimeError("Failed to initialize face detector")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support 'with' statement"""
        self.close()

    def get_status(self) -> dict:
        """
        Get detector status information.

        Returns:
            Dictionary with detector status
        """
        return {
            "is_initialized": self.is_initialized,
            "confidence_threshold": config.DETECTION_CONFIDENCE,
            "model_type": "short-range",
            "consecutive_errors": self._consecutive_errors,
        }
