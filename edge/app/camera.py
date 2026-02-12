"""
Camera Capture Manager

Handles camera initialization, frame capture, and resource management.

Supports:
- Raspberry Pi Camera Module (via picamera2)
- USB Webcam (via OpenCV)
- RTSP IP Camera (via OpenCV, e.g. Reolink P340)

Features:
- Automatic camera detection and initialization
- Configurable resolution and frame rate
- RTSP reconnection with backoff
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

    Priority order (when CAMERA_SOURCE="auto"):
    1. picamera2 (Raspberry Pi Camera Module)
    2. RTSP (IP cameras like Reolink P340, if RTSP_URL is set)
    3. OpenCV USB camera
    """

    def __init__(self):
        self.camera = None
        self.camera_type: Optional[str] = None
        self.is_running = False
        self._init_attempts = 0
        self._max_init_attempts = 3
        self._consecutive_failures = 0
        self._max_consecutive_failures = 10

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

                source = config.CAMERA_SOURCE

                if source == "picamera":
                    if self._try_picamera2():
                        return True
                elif source == "rtsp":
                    if self._try_rtsp():
                        return True
                elif source == "usb":
                    if self._try_opencv():
                        return True
                else:
                    # Auto-detect: try picamera → rtsp (if URL set) → usb
                    if self._try_picamera2():
                        return True
                    if config.RTSP_URL and self._try_rtsp():
                        return True
                    if self._try_opencv():
                        return True

                logger.warning("Camera initialization failed, retrying in 2 seconds...")
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
            logger.debug("picamera2 not available, trying next source...")
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

    def _try_rtsp(self) -> bool:
        """
        Try to initialize RTSP IP camera using OpenCV.

        Uses the RTSP_URL from config (e.g., Reolink P340).
        Forces TCP transport for reliability over WiFi/PoE networks.

        Returns:
            True if successful, False otherwise
        """
        try:
            import cv2

            rtsp_url = config.RTSP_URL
            if not rtsp_url:
                logger.debug("No RTSP_URL configured, skipping RTSP")
                return False

            logger.info(f"Attempting to initialize RTSP camera...")
            # Mask password in logs
            safe_url = rtsp_url
            if "@" in rtsp_url:
                prefix = rtsp_url.split("@")[0]
                if ":" in prefix.split("//")[1]:
                    safe_url = prefix.rsplit(":", 1)[0] + ":****@" + rtsp_url.split("@")[1]
            logger.info(f"RTSP URL: {safe_url}")

            # Set RTSP transport before opening
            # TCP is more reliable than UDP for PoE cameras
            transport = config.RTSP_TRANSPORT.lower()
            env_key = f"OPENCV_FFMPEG_CAPTURE_OPTIONS"

            self.camera = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

            # Set RTSP transport protocol
            if transport == "tcp":
                self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"H264"))

            # Set buffer size to 1 frame to minimize latency
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not self.camera.isOpened():
                raise RuntimeError(f"Failed to open RTSP stream")

            # Test capture (give it time to connect)
            time.sleep(2)
            ret, test_frame = self.camera.read()
            if not ret or test_frame is None or test_frame.size == 0:
                raise RuntimeError("RTSP test capture failed - check URL/credentials")

            self.camera_type = "rtsp"
            self.is_running = True

            # Get actual resolution from stream
            actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.camera.get(cv2.CAP_PROP_FPS)

            logger.info(
                f"RTSP camera initialized successfully - "
                f"{actual_width}x{actual_height} @ {actual_fps:.1f} FPS"
            )
            return True

        except ImportError:
            logger.error("OpenCV (cv2) not available - cannot initialize RTSP camera")
            return False

        except Exception as e:
            logger.warning(f"Failed to initialize RTSP camera: {e}")
            if self.camera:
                try:
                    self.camera.release()
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

    def _reconnect_rtsp(self) -> bool:
        """
        Attempt to reconnect RTSP stream after failure.

        Returns:
            True if reconnected successfully
        """
        logger.warning("Attempting RTSP reconnection...")
        try:
            if self.camera:
                self.camera.release()
            self.camera = None
            self.is_running = False

            time.sleep(config.RTSP_RECONNECT_DELAY)

            # Re-init
            self._init_attempts = 0
            return self._try_rtsp()
        except Exception as e:
            logger.error(f"RTSP reconnection failed: {e}")
            return False

    def capture_frame(self) -> Optional[np.ndarray]:
        """
        Capture a single frame from the camera.

        Returns:
            BGR frame as numpy array (H, W, 3), or None if capture failed

        Notes:
            - picamera2 returns RGB, converted to BGR for consistency
            - OpenCV/RTSP returns BGR directly
            - RTSP auto-reconnects on consecutive failures
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
                self._consecutive_failures = 0
                return frame_bgr

            elif self.camera_type in ("opencv", "rtsp"):
                # OpenCV/RTSP returns BGR
                ret, frame_bgr = self.camera.read()

                if not ret or frame_bgr is None or frame_bgr.size == 0:
                    self._consecutive_failures += 1
                    logger.warning(
                        f"Captured empty frame from {self.camera_type} camera "
                        f"(failure {self._consecutive_failures}/{self._max_consecutive_failures})"
                    )

                    # Auto-reconnect RTSP after consecutive failures
                    if (self.camera_type == "rtsp"
                            and self._consecutive_failures >= self._max_consecutive_failures):
                        logger.error("Too many consecutive RTSP failures, reconnecting...")
                        if self._reconnect_rtsp():
                            self._consecutive_failures = 0
                        else:
                            logger.error("RTSP reconnection failed")
                    return None

                self._consecutive_failures = 0
                return frame_bgr

            else:
                logger.error(f"Unknown camera type: {self.camera_type}")
                return None

        except Exception as e:
            logger.error(f"Frame capture error: {e}")
            self._consecutive_failures += 1
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

            elif self.camera_type in ("opencv", "rtsp"):
                self.camera.release()

        except Exception as e:
            logger.error(f"Error stopping camera: {e}")

        finally:
            self.camera = None
            self.camera_type = None
            self.is_running = False
            self._consecutive_failures = 0
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
        status = {
            "is_running": self.is_running,
            "camera_type": self.camera_type,
            "camera_source_config": config.CAMERA_SOURCE,
            "resolution": f"{config.CAMERA_WIDTH}x{config.CAMERA_HEIGHT}",
            "fps": config.CAMERA_FPS,
            "init_attempts": self._init_attempts,
            "consecutive_failures": self._consecutive_failures,
        }

        # Add actual resolution for RTSP/OpenCV
        if self.camera_type in ("rtsp", "opencv") and self.camera is not None:
            import cv2
            status["actual_resolution"] = (
                f"{int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
                f"{int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))}"
            )

        if self.camera_type == "rtsp":
            status["rtsp_url_configured"] = bool(config.RTSP_URL)
            status["rtsp_transport"] = config.RTSP_TRANSPORT

        return status
