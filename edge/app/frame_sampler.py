"""
Frame Sampler -- Captures frames from Reolink main stream, encodes as JPEG,
sends to VPS via WebSocket. Ultra-lightweight, no ML.
"""
import base64
import logging
import os
import time
from collections import deque
from datetime import datetime

import cv2

from app.config import (
    JPEG_QUALITY,
    QUEUE_MAXLEN,
    QUEUE_TTL_SECONDS,
    ROOM_ID,
    RTSP_SUB,
    SAMPLE_FPS,
)

logger = logging.getLogger(__name__)


class FrameSampler:
    """Samples frames from Reolink main stream at configured FPS."""

    def __init__(self):
        self.cap = None
        self.running = False
        self.offline_queue = deque(maxlen=QUEUE_MAXLEN)
        self._frame_interval = 1.0 / SAMPLE_FPS

    def start(self):
        """Open RTSP connection to Reolink sub stream (H.264)."""
        logger.info(f"Opening RTSP sub stream: {RTSP_SUB}")
        # Use sub-stream (H.264) because main stream is HEVC which
        # opencv-python-headless on ARM can't decode reliably
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        self.cap = cv2.VideoCapture(RTSP_SUB, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open RTSP: {RTSP_SUB}")
        self.running = True
        logger.info("Sub stream opened successfully")

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()

    def sample_frame(self) -> dict | None:
        """Capture one frame, encode as JPEG, return as message dict."""
        if not self.cap or not self.cap.isOpened():
            return None

        ret, frame = self.cap.read()
        if not ret:
            logger.warning("Failed to read frame from main stream")
            return None

        h, w = frame.shape[:2]

        encode_params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        _, jpeg_bytes = cv2.imencode(".jpg", frame, encode_params)
        frame_b64 = base64.b64encode(jpeg_bytes.tobytes()).decode("ascii")

        return {
            "type": "frame",
            "room_id": ROOM_ID,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "frame_b64": frame_b64,
            "frame_width": w,
            "frame_height": h,
            "source": "reolink_p340",
        }

    def queue_frame(self, frame_msg: dict):
        """Add frame to offline queue (drops oldest if full)."""
        frame_msg["queued_at"] = time.time()
        self.offline_queue.append(frame_msg)

    def drain_queue(self) -> list[dict]:
        """Get all queued frames that haven't expired."""
        now = time.time()
        valid = []
        while self.offline_queue:
            msg = self.offline_queue.popleft()
            if now - msg.get("queued_at", 0) < QUEUE_TTL_SECONDS:
                valid.append(msg)
        return valid
