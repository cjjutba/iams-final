"""
IAMS Backend Configuration

Central configuration file using Pydantic Settings for all environment variables.
Includes Supabase, JWT, Face Recognition, and Presence Tracking settings.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "IAMS"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    # Supabase (optional — only needed when USE_SUPABASE_AUTH=true)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""  # Service role key for admin operations
    SUPABASE_JWT_SECRET: str = ""  # Supabase JWT secret for token verification
    SUPABASE_WEBHOOK_SECRET: str = ""  # Webhook signature verification
    SUPABASE_ACCESS_TOKEN: str = ""  # Personal access token for Management API
    DATABASE_URL: str  # PostgreSQL connection string

    # JWT Settings (Custom JWT — kept for dual-auth migration)
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Auth Feature Flags
    USE_SUPABASE_AUTH: bool = False  # Enable Supabase Auth (set True after migration)

    # Rate Limiting
    RATE_LIMIT_AUTH: str = "10/minute"  # Auth endpoint rate limit
    RATE_LIMIT_ENABLED: bool = True

    # CORS
    CORS_ORIGINS: list[str] = ["*"]  # In production, specify exact origins

    # ONNX Runtime (thread control for multi-worker CPU efficiency)
    ONNX_INTRA_OP_THREADS: int = 2  # threads within a single op (per worker)
    ONNX_INTER_OP_THREADS: int = 1  # threads between ops (per worker)

    # Face Recognition
    INSIGHTFACE_MODEL: str = "buffalo_l"
    INSIGHTFACE_DET_SIZE: int = 640
    INSIGHTFACE_DET_THRESH: float = 0.3  # Lower threshold for surveillance cameras
    FAISS_INDEX_PATH: str = "data/faiss/faces.index"
    RECOGNITION_THRESHOLD: float = 0.45  # Cosine similarity threshold (lowered for cross-camera matching)
    RECOGNITION_MARGIN: float = 0.1  # Min gap between top-1 and top-2 scores
    RECOGNITION_TOP_K: int = 3  # Number of neighbors to search in FAISS
    USE_GPU: bool = True  # Use GPU if available, fallback to CPU
    MIN_FACE_IMAGES: int = 3  # Minimum images for registration
    MAX_FACE_IMAGES: int = 5  # Maximum images for registration

    # Face Quality Gating
    QUALITY_GATE_ENABLED: bool = True
    QUALITY_BLUR_THRESHOLD: float = 100.0  # Laplacian variance minimum (CCTV)
    QUALITY_BLUR_THRESHOLD_MOBILE: float = 35.0  # Laplacian variance minimum (mobile selfie)
    QUALITY_BRIGHTNESS_MIN: float = 40.0  # Mean pixel intensity minimum
    QUALITY_BRIGHTNESS_MAX: float = 220.0  # Mean pixel intensity maximum
    QUALITY_MIN_FACE_SIZE_RATIO: float = 0.05  # Face area / image area minimum
    QUALITY_MIN_DET_SCORE: float = 0.5  # SCRFD detection confidence minimum

    # Adaptive Threshold
    ADAPTIVE_THRESHOLD_ENABLED: bool = True
    ADAPTIVE_THRESHOLD_FLOOR: float = 0.35  # Minimum allowed threshold
    ADAPTIVE_THRESHOLD_CEILING: float = 0.65  # Maximum allowed threshold
    ADAPTIVE_THRESHOLD_MIN_SAMPLES: int = 50  # Min samples before adapting
    ADAPTIVE_THRESHOLD_WINDOW: int = 500  # Rolling window size

    # Anti-Spoofing / Liveness Detection
    ANTISPOOF_ENABLED: bool = True
    ANTISPOOF_REGISTRATION_STRICT: bool = True  # Block registration if spoof detected
    ANTISPOOF_RECOGNITION_LOG_ONLY: bool = True  # Only log during CCTV (no blocking)
    ANTISPOOF_EMBEDDING_VARIANCE_MIN: float = 0.1  # Min embedding cosine distance variance across angles
    ANTISPOOF_LBP_THRESHOLD: float = 0.15  # LBP texture uniformity threshold (lowered for mobile selfie)
    ANTISPOOF_FFT_THRESHOLD: float = 0.20  # FFT high-freq energy threshold (lowered for mobile selfie)

    # Presence Tracking
    SCAN_INTERVAL_SECONDS: int = 60  # How often to run presence scans
    EARLY_LEAVE_THRESHOLD: int = 3  # Consecutive misses to flag early leave
    GRACE_PERIOD_MINUTES: int = 15  # Late grace period after class starts
    SESSION_BUFFER_MINUTES: int = 5  # Buffer before/after class for session

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_BATCH_QUEUE_PREFIX: str = "face_queue"
    REDIS_PRESENCE_PREFIX: str = "presence"
    REDIS_WS_CHANNEL: str = "ws_broadcast"
    REDIS_BATCH_LOCK_KEY: str = "batch_lock"
    REDIS_BATCH_LOCK_TIMEOUT: int = 30  # seconds
    REDIS_BATCH_INTERVAL: float = 3.0  # seconds between batch runs
    REDIS_BATCH_THRESHOLD: int = 10  # min faces to trigger immediate batch

    # Live Stream (legacy JPEG-over-WebSocket mode)
    STREAM_FPS: int = 3  # Target frames per second for live stream
    STREAM_QUALITY: int = 65  # JPEG quality (0-100) for streamed frames
    STREAM_WIDTH: int = 1280  # Stream output width in pixels
    STREAM_HEIGHT: int = 720  # Stream output height in pixels
    DEFAULT_RTSP_URL: str = ""  # Fallback RTSP URL (set via env var)

    # HLS Streaming (hardware-decoded video via FFmpeg)
    USE_HLS_STREAMING: bool = True  # Feature flag: True=HLS+WS metadata, False=legacy JPEG WS
    HLS_SEGMENT_DURATION: float = 0.2  # Seconds per HLS segment — 0.2 s forces keyframes at 0.2 s boundaries
    HLS_PLAYLIST_SIZE: int = 3  # 3 × 0.2 s = 0.6 s window; ExoPlayer targets ~0.6 s behind live edge
    HLS_TRANSCODE: bool = True  # True = libx264 ultrafast with forced keyframes; False = copy
    HLS_SEGMENT_DIR: str = "data/hls"  # Directory for .m3u8 and .ts files
    HLS_FFMPEG_PATH: str = "bin/ffmpeg.exe"  # Path to FFmpeg binary (relative to backend/)

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

    # Recognition (decoupled from video, runs at lower FPS)
    RECOGNITION_FPS: float = 10.0  # Frames/sec — match source stream FPS for near-real-time tracking
    RECOGNITION_MAX_BATCH_SIZE: int = 50  # Max faces per batch forward pass
    RECOGNITION_RTSP_URL: str = ""  # High-res RTSP URL for recognition (empty = use DEFAULT_RTSP_URL)
    RECOGNITION_MAX_DIM: int = 1280  # Cap frame dimension for detection (balances accuracy vs speed)

    # Service Role (determines which components start)
    # "api-gateway" | "detection-worker" | "recognition-worker" | "all" (dev)
    SERVICE_ROLE: str = "all"

    # Worker Settings
    DETECTION_FPS: float = 3.0  # Frames per second to process for detection
    RECOGNITION_BATCH_SIZE: int = 10  # Max faces to recognize in one batch
    TRACK_COAST_MS: int = 500  # Track coast duration before LOST (ms)
    TRACK_DELETE_MS: int = 2000  # Time in LOST before deletion (ms)
    TRACK_CONFIRM_HITS: int = 3  # Consecutive detections to confirm track
    FUSION_OUTPUT_FPS: float = 30.0  # Track fusion output rate

    # Edge Gateway
    EDGE_API_KEY: str = "edge-secret-key-change-in-production"  # RPi auth

    # Stream Consumer Groups
    DETECTION_GROUP: str = "detection-workers"
    RECOGNITION_GROUP: str = "recognition-workers"
    ATTENDANCE_GROUP: str = "attendance-writers"

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

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    LOG_MAX_BYTES: int = 10485760  # 10MB
    LOG_BACKUP_COUNT: int = 5

    class Config:
        env_file = ".env"
        case_sensitive = True


# Initialize settings
settings = Settings()


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
