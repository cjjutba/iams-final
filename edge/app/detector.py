"""
Face Detection with MediaPipe

Implements face detection using MediaPipe Face Detection model optimized for Raspberry Pi.

Features:
- TFLite runtime for efficient ARM execution
- Short-range model optimized for indoor classroom scenarios
- Configurable confidence threshold
- Bounding box extraction
- Handles multiple faces per frame
"""

import numpy as np
import cv2
from typing import List, Tuple, Optional
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from app.config import config, logger


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

    def to_list(self) -> List[int]:
        """Convert to [x, y, width, height] format for API"""
        return [self.x, self.y, self.width, self.height]

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "confidence": self.confidence
        }

    def __repr__(self) -> str:
        return f"FaceBox(x={self.x}, y={self.y}, w={self.width}, h={self.height}, conf={self.confidence:.2f})"


class FaceDetector:
    """
    MediaPipe-based face detector optimized for Raspberry Pi.

    Uses MediaPipe Face Detection with TFLite runtime for efficient execution on ARM.
    Configured for short-range detection suitable for indoor classroom monitoring.
    """

    def __init__(self):
        self.detector: Optional[vision.FaceDetector] = None
        self.is_initialized = False

    def initialize(self) -> bool:
        """
        Initialize MediaPipe Face Detection model.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing MediaPipe Face Detector...")

            # Create face detector options
            base_options = python.BaseOptions(
                model_asset_path=None  # Uses default model bundled with MediaPipe
            )

            options = vision.FaceDetectorOptions(
                base_options=base_options,
                min_detection_confidence=config.DETECTION_CONFIDENCE,
                # model_selection: 0 = short-range (up to 2m), 1 = full-range (up to 5m)
                # Short-range is faster and more accurate for classroom scenarios
            )

            self.detector = vision.FaceDetector.create_from_options(options)
            self.is_initialized = True

            logger.info(
                f"MediaPipe Face Detector initialized - "
                f"confidence={config.DETECTION_CONFIDENCE}, "
                f"model={'short-range' if config.DETECTION_MODEL == 0 else 'full-range'}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Face Detector: {e}")
            self.detector = None
            self.is_initialized = False
            return False

    def detect(self, frame: np.ndarray) -> List[FaceBox]:
        """
        Detect faces in a frame.

        Args:
            frame: BGR image as numpy array (H, W, 3)

        Returns:
            List of FaceBox objects for detected faces

        Notes:
            - Returns empty list if no faces detected
            - Filters by confidence threshold automatically
            - Converts coordinates to absolute pixel values
        """
        if not self.is_initialized or self.detector is None:
            logger.error("Detector not initialized - call initialize() first")
            return []

        try:
            # Convert BGR to RGB for MediaPipe
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Create MediaPipe Image
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

            # Detect faces
            detection_result = self.detector.detect(mp_image)

            if not detection_result.detections:
                return []

            # Extract bounding boxes
            face_boxes = []
            frame_height, frame_width = frame.shape[:2]

            for detection in detection_result.detections:
                # Get bounding box (normalized coordinates 0.0-1.0)
                bbox = detection.bounding_box

                # Convert to absolute pixel coordinates
                x = int(bbox.origin_x)
                y = int(bbox.origin_y)
                width = int(bbox.width)
                height = int(bbox.height)

                # Get confidence score
                confidence = detection.categories[0].score if detection.categories else 0.0

                # Create FaceBox
                face_box = FaceBox(x, y, width, height, confidence)
                face_boxes.append(face_box)

            logger.debug(f"Detected {len(face_boxes)} faces in frame")
            return face_boxes

        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return []

    def detect_and_visualize(self, frame: np.ndarray, draw_boxes: bool = True) -> Tuple[List[FaceBox], np.ndarray]:
        """
        Detect faces and optionally draw bounding boxes.

        Args:
            frame: BGR image as numpy array
            draw_boxes: Whether to draw bounding boxes on frame

        Returns:
            Tuple of (face_boxes, annotated_frame)

        Notes:
            Useful for debugging and visualization
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
                2
            )

            # Draw confidence score
            label = f"{face_box.confidence:.2f}"
            cv2.putText(
                annotated_frame,
                label,
                (face_box.x, face_box.y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
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
            "model_type": "short-range" if config.DETECTION_MODEL == 0 else "full-range"
        }
