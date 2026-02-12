"""
Image Processing and Face Cropping

Handles face image preprocessing, cropping, and JPEG encoding for backend transmission.

Features:
- Face region extraction with padding
- Resize to standard dimensions (112x112)
- JPEG compression with configurable quality
- Base64 encoding for HTTP transmission
- Batch processing support
"""

import cv2
import numpy as np
import base64
from typing import List, Optional, Tuple
from io import BytesIO
from PIL import Image

from app.config import config, logger
from app.detector import FaceBox


class FaceData:
    """
    Processed face data ready for transmission.

    Attributes:
        image_base64: Base64-encoded JPEG image
        bbox: Original bounding box [x, y, width, height]
        confidence: Detection confidence
    """

    def __init__(self, image_base64: str, bbox: List[int], confidence: float):
        self.image_base64 = image_base64
        self.bbox = bbox
        self.confidence = confidence

    def to_dict(self) -> dict:
        """Convert to API request format"""
        return {
            "image": self.image_base64,
            "bbox": self.bbox
        }


class FaceProcessor:
    """
    Processes detected faces for backend transmission.

    Extracts face regions, resizes to standard dimensions, compresses to JPEG,
    and encodes to Base64 for HTTP transmission.
    """

    def __init__(self):
        self.crop_size = config.FACE_CROP_SIZE
        self.jpeg_quality = config.JPEG_QUALITY

    def crop_face(
        self,
        frame: np.ndarray,
        face_box: FaceBox,
        padding: float = 0.2
    ) -> Optional[np.ndarray]:
        """
        Crop face region from frame with optional padding.

        Args:
            frame: Source BGR image (H, W, 3)
            face_box: Face bounding box
            padding: Padding ratio (e.g., 0.2 = 20% padding on each side)

        Returns:
            Cropped face image or None if invalid

        Notes:
            - Adds padding to include more context around face
            - Clamps to frame boundaries
            - Returns None if resulting crop is too small
        """
        try:
            frame_height, frame_width = frame.shape[:2]

            # Calculate padded bounding box
            pad_w = int(face_box.width * padding)
            pad_h = int(face_box.height * padding)

            x1 = max(0, face_box.x - pad_w)
            y1 = max(0, face_box.y - pad_h)
            x2 = min(frame_width, face_box.x + face_box.width + pad_w)
            y2 = min(frame_height, face_box.y + face_box.height + pad_h)

            # Validate crop dimensions
            crop_width = x2 - x1
            crop_height = y2 - y1

            if crop_width < 10 or crop_height < 10:
                logger.warning(f"Crop too small: {crop_width}x{crop_height}")
                return None

            # Extract crop
            cropped = frame[y1:y2, x1:x2].copy()

            return cropped

        except Exception as e:
            logger.error(f"Face crop error: {e}")
            return None

    def resize_face(self, face_img: np.ndarray) -> Optional[np.ndarray]:
        """
        Resize face image to standard dimensions.

        Args:
            face_img: Face image to resize

        Returns:
            Resized face image (crop_size x crop_size)
        """
        try:
            resized = cv2.resize(
                face_img,
                (self.crop_size, self.crop_size),
                interpolation=cv2.INTER_AREA
            )
            return resized

        except Exception as e:
            logger.error(f"Face resize error: {e}")
            return None

    def encode_jpeg(self, face_img: np.ndarray) -> Optional[bytes]:
        """
        Encode face image to JPEG bytes.

        Args:
            face_img: BGR face image

        Returns:
            JPEG bytes or None if encoding failed
        """
        try:
            # Encode to JPEG using OpenCV
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            success, buffer = cv2.imencode('.jpg', face_img, encode_params)

            if not success:
                logger.error("JPEG encoding failed")
                return None

            return buffer.tobytes()

        except Exception as e:
            logger.error(f"JPEG encoding error: {e}")
            return None

    def encode_base64(self, jpeg_bytes: bytes) -> str:
        """
        Encode JPEG bytes to Base64 string.

        Args:
            jpeg_bytes: JPEG image bytes

        Returns:
            Base64-encoded string
        """
        return base64.b64encode(jpeg_bytes).decode('utf-8')

    def process_face(
        self,
        frame: np.ndarray,
        face_box: FaceBox
    ) -> Optional[FaceData]:
        """
        Process a single detected face for transmission.

        Pipeline:
        1. Crop face region with padding
        2. Resize to standard dimensions
        3. Encode to JPEG
        4. Encode to Base64

        Args:
            frame: Source BGR frame
            face_box: Detected face bounding box

        Returns:
            FaceData object ready for transmission, or None if processing failed
        """
        try:
            # Crop face
            cropped = self.crop_face(frame, face_box)
            if cropped is None:
                return None

            # Resize
            resized = self.resize_face(cropped)
            if resized is None:
                return None

            # Encode to JPEG
            jpeg_bytes = self.encode_jpeg(resized)
            if jpeg_bytes is None:
                return None

            # Encode to Base64
            base64_str = self.encode_base64(jpeg_bytes)

            # Create FaceData
            face_data = FaceData(
                image_base64=base64_str,
                bbox=face_box.to_list(),
                confidence=face_box.confidence
            )

            return face_data

        except Exception as e:
            logger.error(f"Face processing error: {e}")
            return None

    def process_batch(
        self,
        frame: np.ndarray,
        face_boxes: List[FaceBox]
    ) -> List[FaceData]:
        """
        Process multiple detected faces.

        Args:
            frame: Source BGR frame
            face_boxes: List of detected face bounding boxes

        Returns:
            List of FaceData objects (may be shorter than input if processing fails)
        """
        face_data_list = []

        for i, face_box in enumerate(face_boxes):
            face_data = self.process_face(frame, face_box)

            if face_data:
                face_data_list.append(face_data)
            else:
                logger.warning(f"Failed to process face {i+1}/{len(face_boxes)}")

        logger.debug(f"Processed {len(face_data_list)}/{len(face_boxes)} faces")
        return face_data_list

    def save_debug_image(self, face_img: np.ndarray, filename: str) -> bool:
        """
        Save face image for debugging.

        Args:
            face_img: Face image to save
            filename: Output filename

        Returns:
            True if saved successfully
        """
        try:
            cv2.imwrite(filename, face_img)
            logger.debug(f"Saved debug image: {filename}")
            return True

        except Exception as e:
            logger.error(f"Failed to save debug image: {e}")
            return False

    def get_status(self) -> dict:
        """
        Get processor status information.

        Returns:
            Dictionary with processor configuration
        """
        return {
            "crop_size": self.crop_size,
            "jpeg_quality": self.jpeg_quality
        }
