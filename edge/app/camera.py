"""
Camera Capture Manager

Handles camera initialization, frame capture, and resource management for Raspberry Pi.

Supports:
- Raspberry Pi Camera Module (via picamera2)
- USB Webcam (via OpenCV fallback)

Features:
- Automatic camera detection and initialization
- Configurable resolution and frame rate
- Graceful error handling and retry logic
- Resource cleanup on shutdown
"""

import time
import numpy as np
from typing import Optional
from contextlib import contextmanager

from app.config import config, logger


class CameraManager:
    """
    Manages camera capture for face detection.

    Attempts to use picamera2 for Pi Camera first, falls back to OpenCV for USB cameras.
    """

    def __init__(self):
        self.camera = None
        self.camera_type: Optional[str] = None
        self.is_running = False
        self._init_attempts = 0
        self._max_init_attempts = 3

    def initialize(self) -> bool:
        """
        Initialize camera with retry logic.

        Returns:
            True if initialization successful, False otherwise
        """
        while self._init_attempts < self._max_init_attempts:
            try:
                self._init_attempts += 1
                logger.info(f"Initializing camera (attempt {self._init_attempts}/{self._max_init_attempts})...")

                # Try picamera2 first (for Raspberry Pi Camera Module)
                if self._try_picamera2():
                    return True

                # Fall back to OpenCV (for USB webcams)
                if self._try_opencv():
                    return True

                logger.warning(f"Camera initialization failed, retrying in 2 seconds...")
                time.sleep(2)

            except Exception as e:
                logger.error(f"Camera initialization error: {e}")
                time.sleep(2)

        logger.error(f"Failed to initialize camera after {self._max_init_attempts} attempts")
        return False

    def _try_picamera2(self) -> bool:
        """
        Try to initialize Raspberry Pi Camera using picamera2.

        Returns:
            True if successful, False otherwise
        """
        try:
            from picamera2 import Picamera2

            logger.info("Attempting to initialize Pi Camera (picamera2)...")

            self.camera = Picamera2()

            # Configure camera
            camera_config = self.camera.create_still_configuration(
                main={
                    "size": (config.CAMERA_WIDTH, config.CAMERA_HEIGHT),
                    "format": "RGB888"
                },
                controls={
                    "FrameRate": config.CAMERA_FPS
                }
            )

            self.camera.configure(camera_config)
            self.camera.start()

            # Wait for camera to stabilize
            time.sleep(2)

            # Test capture
            test_frame = self.camera.capture_array()
            if test_frame is None or test_frame.size == 0:
                raise RuntimeError("Test capture returned empty frame")

            self.camera_type = "picamera2"
            self.is_running = True

            logger.info(
                f"Pi Camera initialized successfully - "
                f"{config.CAMERA_WIDTH}x{config.CAMERA_HEIGHT} @ {config.CAMERA_FPS} FPS"
            )
            return True

        except ImportError:
            logger.debug("picamera2 not available, trying OpenCV fallback...")
            return False

        except Exception as e:
            logger.warning(f"Failed to initialize Pi Camera: {e}")
            if self.camera:
                try:
                    self.camera.stop()
                except:
                    pass
            self.camera = None
            return False

    def _try_opencv(self) -> bool:
        """
        Try to initialize USB camera using OpenCV.

        Returns:
            True if successful, False otherwise
        """
        try:
            import cv2

            logger.info("Attempting to initialize USB camera (OpenCV)...")

            self.camera = cv2.VideoCapture(config.CAMERA_INDEX)

            if not self.camera.isOpened():
                raise RuntimeError(f"Failed to open camera at index {config.CAMERA_INDEX}")

            # Set camera properties
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
            self.camera.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)

            # Test capture
            ret, test_frame = self.camera.read()
            if not ret or test_frame is None or test_frame.size == 0:
                raise RuntimeError("Test capture failed")

            self.camera_type = "opencv"
            self.is_running = True

            # Get actual resolution (may differ from requested)
            actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.camera.get(cv2.CAP_PROP_FPS))

            logger.info(
                f"USB camera initialized successfully - "
                f"{actual_width}x{actual_height} @ {actual_fps} FPS"
            )
            return True

        except ImportError:
            logger.error("OpenCV (cv2) not available - cannot initialize camera")
            return False

        except Exception as e:
            logger.warning(f"Failed to initialize USB camera: {e}")
            if self.camera:
                try:
                    self.camera.release()
                except:
                    pass
            self.camera = None
            return False

    def capture_frame(self) -> Optional[np.ndarray]:
        """
        Capture a single frame from the camera.

        Returns:
            BGR frame as numpy array (H, W, 3), or None if capture failed

        Notes:
            - picamera2 returns RGB, converted to BGR for consistency
            - OpenCV returns BGR directly
        """
        if not self.is_running or self.camera is None:
            logger.error("Camera not initialized - call initialize() first")
            return None

        try:
            if self.camera_type == "picamera2":
                # picamera2 returns RGB
                frame_rgb = self.camera.capture_array()

                if frame_rgb is None or frame_rgb.size == 0:
                    logger.warning("Captured empty frame from Pi Camera")
                    return None

                # Convert RGB to BGR for consistency with OpenCV
                import cv2
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                return frame_bgr

            elif self.camera_type == "opencv":
                # OpenCV returns BGR
                ret, frame_bgr = self.camera.read()

                if not ret or frame_bgr is None or frame_bgr.size == 0:
                    logger.warning("Captured empty frame from USB camera")
                    return None

                return frame_bgr

            else:
                logger.error(f"Unknown camera type: {self.camera_type}")
                return None

        except Exception as e:
            logger.error(f"Frame capture error: {e}")
            return None

    def stop(self) -> None:
        """
        Stop camera and release resources.
        """
        if not self.is_running:
            return

        logger.info("Stopping camera...")

        try:
            if self.camera_type == "picamera2":
                self.camera.stop()
                self.camera.close()

            elif self.camera_type == "opencv":
                self.camera.release()

        except Exception as e:
            logger.error(f"Error stopping camera: {e}")

        finally:
            self.camera = None
            self.camera_type = None
            self.is_running = False
            logger.info("Camera stopped")

    @contextmanager
    def capture_context(self):
        """
        Context manager for camera capture.

        Usage:
            with camera.capture_context():
                frame = camera.capture_frame()
        """
        try:
            if not self.initialize():
                raise RuntimeError("Failed to initialize camera")
            yield self
        finally:
            self.stop()

    def __enter__(self):
        """Support 'with' statement"""
        if not self.initialize():
            raise RuntimeError("Failed to initialize camera")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support 'with' statement"""
        self.stop()

    def get_status(self) -> dict:
        """
        Get camera status information.

        Returns:
            Dictionary with camera status
        """
        return {
            "is_running": self.is_running,
            "camera_type": self.camera_type,
            "resolution": f"{config.CAMERA_WIDTH}x{config.CAMERA_HEIGHT}",
            "fps": config.CAMERA_FPS,
            "init_attempts": self._init_attempts
        }
