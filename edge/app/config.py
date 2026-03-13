"""
Edge Device Configuration

Manages environment variables and configuration settings for the Raspberry Pi edge device.

Environment variables:
- BACKEND_URL: Backend API base URL (required)
- ROOM_ID: Room identifier (required)
- CAMERA_SOURCE: Camera source type - "picamera", "usb", "rtsp" (default: auto-detect)
- RTSP_URL: RTSP stream URL for IP cameras (e.g., rtsp://admin:pass@192.168.1.100/Preview_01_main)
- RTSP_TRANSPORT: RTSP transport protocol - "tcp" or "udp" (default: tcp)
- CAMERA_INDEX: USB camera device index (default: 0)
- CAMERA_WIDTH: Camera capture width (default: 640)
- CAMERA_HEIGHT: Camera capture height (default: 480)
- CAMERA_FPS: Camera frame rate (default: 15)
- FACE_CROP_SIZE: Face crop size in pixels (default: 160)
- JPEG_QUALITY: JPEG compression quality (default: 85)
- SCAN_INTERVAL: Interval between scans in seconds (default: 60)
- SESSION_AWARE: Enable session-aware scanning (default: True)
- SESSION_POLL_INTERVAL: How often to poll for active sessions when idle, in seconds (default: 10)
- LOG_LEVEL: Logging level (default: INFO)
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Config:
    """Edge device configuration"""

    # ===== Backend Configuration =====
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://167.71.217.44")
    ROOM_ID: str = os.getenv("ROOM_ID", "")

    # ===== Camera Configuration =====
    # Source: "auto" (try picamera→rtsp→usb), "picamera", "rtsp", "usb"
    CAMERA_SOURCE: str = os.getenv("CAMERA_SOURCE", "auto")

    # RTSP settings (for IP cameras like Reolink P340)
    RTSP_URL: str = os.getenv("RTSP_URL", "")
    RTSP_TRANSPORT: str = os.getenv("RTSP_TRANSPORT", "tcp")  # tcp or udp
    RTSP_RECONNECT_DELAY: int = int(os.getenv("RTSP_RECONNECT_DELAY", "5"))

    # USB / general camera settings
    CAMERA_INDEX: int = int(os.getenv("CAMERA_INDEX", "0"))
    CAMERA_WIDTH: int = int(os.getenv("CAMERA_WIDTH", "640"))
    CAMERA_HEIGHT: int = int(os.getenv("CAMERA_HEIGHT", "480"))
    CAMERA_FPS: int = int(os.getenv("CAMERA_FPS", "15"))

    # ===== Face Detection Configuration =====
    FACE_CROP_SIZE: int = int(os.getenv("FACE_CROP_SIZE", "160"))
    JPEG_QUALITY: int = int(os.getenv("JPEG_QUALITY", "85"))

    # MediaPipe Face Detection settings
    DETECTION_CONFIDENCE: float = float(os.getenv("DETECTION_CONFIDENCE", "0.6"))
    DETECTION_MODEL: int = int(os.getenv("DETECTION_MODEL", "0"))  # 0 = short_range, 1 = full_range

    # ===== Queue Configuration =====
    QUEUE_MAX_SIZE: int = int(os.getenv("QUEUE_MAX_SIZE", "500"))
    QUEUE_TTL_SECONDS: int = int(os.getenv("QUEUE_TTL_SECONDS", "300"))  # 5 minutes
    RETRY_INTERVAL_SECONDS: int = int(os.getenv("RETRY_INTERVAL_SECONDS", "10"))
    RETRY_MAX_ATTEMPTS: int = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))

    # ===== Image Preprocessing =====
    CLAHE_ENABLED: bool = os.getenv("CLAHE_ENABLED", "true").lower() in ("true", "1", "yes")
    CLAHE_CLIP_LIMIT: float = float(os.getenv("CLAHE_CLIP_LIMIT", "2.0"))
    CLAHE_TILE_SIZE: int = int(os.getenv("CLAHE_TILE_SIZE", "4"))
    BLUR_DETECTION_ENABLED: bool = os.getenv("BLUR_DETECTION_ENABLED", "true").lower() in ("true", "1", "yes")
    BLUR_THRESHOLD: float = float(os.getenv("BLUR_THRESHOLD", "50.0"))  # Laplacian variance min
    DYNAMIC_PADDING_ENABLED: bool = os.getenv("DYNAMIC_PADDING_ENABLED", "true").lower() in ("true", "1", "yes")

    # ===== Processing Configuration =====
    SCAN_INTERVAL: int = int(os.getenv("SCAN_INTERVAL", "60"))  # 60 seconds

    # ===== Session Awareness Configuration =====
    SESSION_AWARE: bool = os.getenv("SESSION_AWARE", "true").lower() in ("true", "1", "yes")
    SESSION_POLL_INTERVAL: int = int(os.getenv("SESSION_POLL_INTERVAL", "10"))  # seconds

    # ===== Smart Sampler Configuration =====
    SEND_INTERVAL: float = float(os.getenv("SEND_INTERVAL", "3"))
    DEDUP_WINDOW: float = float(os.getenv("DEDUP_WINDOW", "5"))
    FACE_GONE_TIMEOUT: float = float(os.getenv("FACE_GONE_TIMEOUT", "10"))
    IOU_MATCH_THRESHOLD: float = float(os.getenv("IOU_MATCH_THRESHOLD", "0.3"))
    USE_SMART_SAMPLER: bool = os.getenv("USE_SMART_SAMPLER", "true").lower() == "true"

    # ===== Stream Relay Configuration =====
    # When enabled, FFmpeg relays the camera RTSP stream to the VPS mediamtx
    # so faculty can view live video from any network via WebRTC.
    STREAM_RELAY_ENABLED: bool = os.getenv("STREAM_RELAY_ENABLED", "false").lower() in ("true", "1", "yes")
    STREAM_RELAY_URL: str = os.getenv("STREAM_RELAY_URL", "")  # e.g., rtsp://167.71.217.44:8554
    STREAM_RELAY_RETRY_DELAY: int = int(os.getenv("STREAM_RELAY_RETRY_DELAY", "5"))

    # ===== Logging Configuration =====
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE", None)

    # ===== HTTP Configuration =====
    HTTP_TIMEOUT: int = int(os.getenv("HTTP_TIMEOUT", "30"))
    HTTP_MAX_RETRIES: int = int(os.getenv("HTTP_MAX_RETRIES", "3"))

    @classmethod
    def validate(cls) -> None:
        """
        Validate critical configuration parameters.

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        errors = []

        # Backend URL is required
        if not cls.BACKEND_URL:
            errors.append("BACKEND_URL is required")

        # Room ID is required
        if not cls.ROOM_ID:
            errors.append("ROOM_ID is required")

        # Camera source validation
        if cls.CAMERA_SOURCE not in ("auto", "picamera", "rtsp", "usb"):
            errors.append(f"Invalid CAMERA_SOURCE: {cls.CAMERA_SOURCE} (must be auto/picamera/rtsp/usb)")

        # RTSP validation
        if cls.CAMERA_SOURCE == "rtsp" and not cls.RTSP_URL:
            errors.append("RTSP_URL is required when CAMERA_SOURCE=rtsp")

        if cls.RTSP_URL and not cls.RTSP_URL.startswith("rtsp://"):
            errors.append(f"RTSP_URL must start with rtsp:// (got: {cls.RTSP_URL[:30]}...)")

        if cls.RTSP_TRANSPORT not in ("tcp", "udp"):
            errors.append(f"Invalid RTSP_TRANSPORT: {cls.RTSP_TRANSPORT} (must be tcp/udp)")

        # Camera settings validation
        if cls.CAMERA_WIDTH <= 0 or cls.CAMERA_HEIGHT <= 0:
            errors.append(f"Invalid camera resolution: {cls.CAMERA_WIDTH}x{cls.CAMERA_HEIGHT}")

        if cls.CAMERA_FPS <= 0 or cls.CAMERA_FPS > 60:
            errors.append(f"Invalid camera FPS: {cls.CAMERA_FPS} (must be 1-60)")

        # Face crop size validation
        if cls.FACE_CROP_SIZE <= 0:
            errors.append(f"Invalid face crop size: {cls.FACE_CROP_SIZE}")

        # JPEG quality validation (1-100)
        if cls.JPEG_QUALITY < 1 or cls.JPEG_QUALITY > 100:
            errors.append(f"Invalid JPEG quality: {cls.JPEG_QUALITY} (must be 1-100)")

        # Queue configuration validation
        if cls.QUEUE_MAX_SIZE <= 0:
            errors.append(f"Invalid queue max size: {cls.QUEUE_MAX_SIZE}")

        if cls.QUEUE_TTL_SECONDS <= 0:
            errors.append(f"Invalid queue TTL: {cls.QUEUE_TTL_SECONDS}")

        if cls.RETRY_INTERVAL_SECONDS <= 0:
            errors.append(f"Invalid retry interval: {cls.RETRY_INTERVAL_SECONDS}")

        # Detection confidence (0.0-1.0)
        if cls.DETECTION_CONFIDENCE < 0.0 or cls.DETECTION_CONFIDENCE > 1.0:
            errors.append(f"Invalid detection confidence: {cls.DETECTION_CONFIDENCE} (must be 0.0-1.0)")

        # Detection model (0 or 1)
        if cls.DETECTION_MODEL not in [0, 1]:
            errors.append(f"Invalid detection model: {cls.DETECTION_MODEL} (must be 0 or 1)")

        # Session poll interval validation
        if cls.SESSION_POLL_INTERVAL <= 0:
            errors.append(f"Invalid session poll interval: {cls.SESSION_POLL_INTERVAL} (must be > 0)")

        # Stream relay validation
        if cls.STREAM_RELAY_ENABLED and not cls.STREAM_RELAY_URL:
            errors.append("STREAM_RELAY_URL is required when STREAM_RELAY_ENABLED=true")

        if cls.STREAM_RELAY_URL and not cls.STREAM_RELAY_URL.startswith(("rtsp://", "rtsps://")):
            errors.append(f"STREAM_RELAY_URL must start with rtsp:// or rtsps:// (got: {cls.STREAM_RELAY_URL[:30]}...)")

        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    @classmethod
    def get_api_endpoint(cls, path: str) -> str:
        """
        Get full API endpoint URL.

        Args:
            path: API path (e.g., "/api/v1/face/process")

        Returns:
            Full URL
        """
        base = cls.BACKEND_URL.rstrip("/")
        path = path.lstrip("/")
        return f"{base}/{path}"


def setup_logging() -> logging.Logger:
    """
    Configure logging for edge device.

    Returns:
        Configured logger instance
    """
    log_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)

    # Configure format
    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure handlers
    handlers = [logging.StreamHandler()]

    if Config.LOG_FILE:
        handlers.append(logging.FileHandler(Config.LOG_FILE))

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )

    return logging.getLogger("edge")


# Export config and logger
config = Config
logger = setup_logging()
