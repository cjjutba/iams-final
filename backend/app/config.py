"""
IAMS Backend Configuration

Central configuration file using Pydantic Settings for all environment variables.
Includes JWT, Face Recognition, and Presence Tracking settings.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "IAMS"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str  # PostgreSQL connection string

    # JWT Settings
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rate Limiting
    RATE_LIMIT_AUTH: str = "10/minute"  # Auth endpoint rate limit
    RATE_LIMIT_ENABLED: bool = True

    # CORS
    CORS_ORIGINS: list[str] = []  # Must be explicitly set per environment

    # ONNX Runtime (thread control for multi-worker CPU efficiency)
    ONNX_INTRA_OP_THREADS: int = 4  # threads within a single op (1 worker × 4 = 4 vCPUs)
    ONNX_INTER_OP_THREADS: int = 2  # threads between ops (allows pipelining det + rec)

    # Face Recognition
    INSIGHTFACE_MODEL: str = "buffalo_l"
    INSIGHTFACE_DET_SIZE: int = 640  # 640 for best accuracy with main stream (480 for sub-stream)
    INSIGHTFACE_DET_THRESH: float = 0.3  # Detection confidence minimum (lowered for distant CCTV faces)
    FAISS_INDEX_PATH: str = "data/faiss/faces.index"
    RECOGNITION_THRESHOLD: float = (
        0.45  # Cosine similarity threshold (CCTV-sim + adaptive enrollment pushes scores to 0.6-0.9)
    )
    RECOGNITION_MARGIN: float = 0.10  # Min gap between top-1 and top-2 scores
    RECOGNITION_TOP_K: int = 3  # Number of neighbors to search in FAISS
    USE_GPU: bool = True  # Use GPU if available, fallback to CPU
    MIN_FACE_IMAGES: int = 3  # Minimum images for registration
    MAX_FACE_IMAGES: int = 5  # Maximum images for registration

    # Face Quality Gating
    QUALITY_GATE_ENABLED: bool = True
    QUALITY_BLUR_THRESHOLD: float = 100.0  # Laplacian variance minimum (CCTV)
    QUALITY_BLUR_THRESHOLD_MOBILE: float = 10.0  # Laplacian variance minimum (mobile CameraX bitmap capture)
    QUALITY_BRIGHTNESS_MIN: float = 40.0  # Mean pixel intensity minimum
    QUALITY_BRIGHTNESS_MAX: float = 220.0  # Mean pixel intensity maximum
    QUALITY_MIN_FACE_SIZE_RATIO: float = 0.05  # Face area / image area minimum
    QUALITY_MIN_DET_SCORE: float = 0.5  # SCRFD detection confidence minimum

    # Anti-Spoofing / Liveness Detection
    ANTISPOOF_ENABLED: bool = True
    ANTISPOOF_REGISTRATION_STRICT: bool = True  # Block registration if spoof detected
    ANTISPOOF_RECOGNITION_LOG_ONLY: bool = True  # Only log during CCTV (no blocking)
    ANTISPOOF_EMBEDDING_VARIANCE_MIN: float = 0.1  # Min embedding cosine distance variance across angles
    ANTISPOOF_LBP_THRESHOLD: float = 0.15  # LBP texture uniformity threshold (lowered for mobile selfie)
    ANTISPOOF_FFT_THRESHOLD: float = 0.20  # FFT high-freq energy threshold (lowered for mobile selfie)

    # Adaptive Per-Session Enrollment
    # When a student is recognized with high confidence from CCTV, store that
    # real CCTV embedding in FAISS (RAM only, volatile) to boost future matches.
    ADAPTIVE_ENROLL_ENABLED: bool = True
    ADAPTIVE_ENROLL_MIN_CONFIDENCE: float = 0.55  # Only enroll very confident matches
    ADAPTIVE_ENROLL_MAX_PER_USER: int = 3  # Max session embeddings per user
    ADAPTIVE_ENROLL_COOLDOWN: float = 30.0  # Seconds between adaptive enrollments per user

    # Presence Tracking (legacy scan-based — kept for backward compatibility)
    SCAN_INTERVAL_SECONDS: int = 15  # How often to run presence scans
    EARLY_LEAVE_THRESHOLD: int = 3  # Consecutive misses to flag early leave
    GRACE_PERIOD_MINUTES: int = 15  # Late grace period after class starts
    SESSION_BUFFER_MINUTES: int = 5  # Buffer before/after class for session

    # Real-Time Pipeline
    PROCESSING_FPS: float = 10.0  # Frames/sec for realtime tracker loop (10fps = 100ms budget for 1280x720)
    WS_BROADCAST_FPS: float = 10.0  # WebSocket broadcast rate

    # ByteTrack / Track Lifecycle
    TRACK_LOST_TIMEOUT: float = 0.5  # Seconds before removing lost track (coasting period)
    REVERIFY_INTERVAL: float = 5.0  # Re-run ArcFace on existing tracks (seconds)
    TRACK_CONFIRM_FRAMES: int = 1  # Recognize immediately on first detection

    # Track-Based Presence
    EARLY_LEAVE_TIMEOUT: float = 300.0  # Fallback: 5 min absent before early-leave alert (per-schedule override in DB)
    PRESENCE_FLUSH_INTERVAL: float = 10.0  # Seconds between DB presence flushes

    # Frame Grabber
    FRAME_GRABBER_FPS: float = 10.0  # FFmpeg output frame rate (10fps for 1280x720 CPU budget)
    FRAME_GRABBER_WIDTH: int = 1280  # 720p — gives ~50-80px faces even on wide-angle lenses
    FRAME_GRABBER_HEIGHT: int = 720  # Consistent across all cameras

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PRESENCE_PREFIX: str = "presence"
    REDIS_WS_CHANNEL: str = "ws_broadcast"

    # RTSP
    DEFAULT_RTSP_URL: str = ""  # Fallback RTSP URL (set via env var)

    # WebRTC Streaming (mediamtx + WHEP — replaces HLS for <300ms latency)
    USE_WEBRTC_STREAMING: bool = True  # True=WebRTC, False=fall back to HLS/legacy
    MEDIAMTX_EXTERNAL: bool = False  # True = mediamtx runs as separate container (skip subprocess)
    MEDIAMTX_API_URL: str = "http://localhost:9997"  # mediamtx REST API (internal only)
    MEDIAMTX_WEBRTC_URL: str = "http://localhost:8889"  # mediamtx WHEP endpoint (internal only)
    MEDIAMTX_RTSP_URL: str = "rtsp://localhost:8554"  # mediamtx RTSP endpoint (for recognition in push mode)
    WEBRTC_STUN_URLS: str = "stun:stun.l.google.com:19302"  # Comma-separated STUN URLs (free Google STUN)
    WEBRTC_TURN_URL: str = ""  # Optional: "turn:your-server:3478"
    WEBRTC_TURN_USERNAME: str = ""  # TURN username (empty = no TURN)
    WEBRTC_TURN_CREDENTIAL: str = ""  # TURN credential

    # mediamtx subprocess settings
    MEDIAMTX_BIN_PATH: str = "bin/mediamtx"  # Path to mediamtx binary (relative to backend/)
    MEDIAMTX_CONFIG_PATH: str = "mediamtx.yml"  # Path to mediamtx config (relative to backend/)

    # Recognition
    RECOGNITION_FPS: float = 10.0  # Frames/sec for attendance engine recognition loop
    RECOGNITION_MAX_BATCH_SIZE: int = 50  # Max faces per batch forward pass
    RECOGNITION_MAX_DIM: int = 1280  # Cap frame dimension for detection (balances accuracy vs speed)

    # Service Role (determines which components start)
    # "api-gateway" | "all" (dev)
    SERVICE_ROLE: str = "all"

    # Edge Gateway
    EDGE_API_KEY: str = "edge-secret-key-change-in-production"  # RPi auth

    # Re-enrollment Monitoring
    REENROLL_CHECK_ENABLED: bool = True
    REENROLL_SIMILARITY_THRESHOLD: float = 0.55  # Mean similarity below this triggers re-enroll prompt
    REENROLL_WINDOW_SIZE: int = 20  # Rolling window of recent similarity scores

    # File Storage
    UPLOAD_DIR: str = "data/uploads/faces"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Email (Resend)
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "IAMS <noreply@iams.jrmsu.edu.ph>"
    EMAIL_ENABLED: bool = False  # Master kill switch — set True when Resend API key is configured

    # Notification Jobs
    DAILY_DIGEST_HOUR: int = 18  # Hour (0-23) to send daily digest
    WEEKLY_DIGEST_HOUR: int = 19  # Hour (0-23) to send weekly digest (Sundays)
    NOTIFICATION_RETENTION_DAYS: int = 90  # Days to keep read notifications
    LOW_ATTENDANCE_CHECK_WINDOW_DAYS: int = 30  # Rolling window for low attendance check
    LOW_ATTENDANCE_RENOTIFY_DAYS: int = 7  # Min days between re-notification for low attendance

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    LOG_MAX_BYTES: int = 10485760  # 10MB
    LOG_BACKUP_COUNT: int = 5

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# Initialize settings
settings = Settings()

# --- Startup validation: catch dangerous defaults in production ---
# Only enforce in explicit production mode (DEBUG=False AND not in test runner)
_is_testing = "pytest" in sys.modules or os.getenv("TESTING", "").lower() in ("1", "true")
if not settings.DEBUG and not _is_testing:
    if settings.SECRET_KEY == "dev-secret-key-change-in-production":
        raise RuntimeError("SECRET_KEY must be changed in production")
    if settings.EDGE_API_KEY == "edge-secret-key-change-in-production":
        raise RuntimeError("EDGE_API_KEY must be changed in production")


class _HLSAccessFilter(logging.Filter):
    """
    Drop uvicorn access-log records for routine HLS media delivery.

    The mobile player polls playlist.m3u8 several times per second and
    fetches a new .m4s segment every ~0.5 s.  None of these lines carry
    actionable information during normal operation and they drown out
    everything else in the terminal.
    """

    _HLS_NOISE = ("playlist.m3u8", ".m4s", "init.mp4")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "/hls/" not in msg:
            return True
        return not any(token in msg for token in self._HLS_NOISE)


def setup_logging() -> logging.Logger:
    """
    Setup structured logging with file rotation

    Returns:
        Configured logger instance
    """
    # Suppress noisy HLS media delivery from uvicorn's access log
    logging.getLogger("uvicorn.access").addFilter(_HLSAccessFilter())

    # SQLAlchemy echoes every BEGIN/COMMIT/query at INFO when echo=True.
    # Silence it here regardless of the engine echo setting so it doesn't
    # drown out application logs.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logger = logging.getLogger("iams")

    # Set level based on debug mode
    if settings.DEBUG:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Create logs directory if it doesn't exist
    log_path = Path(settings.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        settings.LOG_FILE, maxBytes=settings.LOG_MAX_BYTES, backupCount=settings.LOG_BACKUP_COUNT
    )

    # Console handler
    console_handler = logging.StreamHandler()

    # Format: [timestamp] [level] [module] message
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers if not already added
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


# Initialize logger
logger = setup_logging()
