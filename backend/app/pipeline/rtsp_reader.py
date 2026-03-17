"""Threaded RTSP reader with latest-frame semantics.

Continuously reads from an RTSP source in a background thread.
The main thread always gets the most recent frame -- stale frames are dropped.
This prevents the OpenCV internal buffer from accumulating latency.
"""

import os
import threading
import time

import cv2
import numpy as np

from app.config import logger


class RTSPReader:
    """Thread-safe RTSP reader that always returns the latest frame.

    Spawns a daemon thread that continuously calls ``cv2.VideoCapture.read()``.
    Each successful read overwrites the previous frame so that the consumer
    always gets the most recent image without buffering delay.

    Args:
        url: RTSP stream URL (e.g. ``rtsp://mediamtx:8554/room-1/raw``).
        target_fps: Desired capture rate -- used by callers for pacing; the
            reader thread itself runs as fast as the source provides frames.
    """

    # Number of frames to discard on connect to let the H.264 decoder
    # receive a keyframe and stabilise (avoids green/smeared artifacts).
    WARMUP_FRAMES = 60

    def __init__(self, url: str, target_fps: int = 25) -> None:
        self.url = url
        self.target_fps = target_fps
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._stopped = False
        self._thread: threading.Thread | None = None
        self._cap: cv2.VideoCapture | None = None

    def start(self) -> "RTSPReader":
        """Open the RTSP source and start the background reader thread.

        Returns:
            ``self`` so callers can chain: ``reader = RTSPReader(url).start()``.
        """
        os.environ.setdefault(
            "OPENCV_FFMPEG_CAPTURE_OPTIONS",
            "rtsp_transport;tcp"
            "|fflags;nobuffer+discardcorrupt"
            "|flags;low_delay"
            "|probesize;500000"
            "|analyzeduration;500000",
        )
        self._cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._stopped = False
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()
        return self

    def _reader_loop(self) -> None:
        """Continuously read frames, keeping only the latest.

        On first connect, discards ``WARMUP_FRAMES`` frames to let the
        H.264 decoder synchronise to a keyframe before exposing frames
        to the consumer.
        """
        warmup_remaining = self.WARMUP_FRAMES
        while not self._stopped:
            if self._cap is None or not self._cap.isOpened():
                time.sleep(0.1)
                continue
            ret, frame = self._cap.read()
            if ret and frame is not None:
                # Discard initial frames until decoder has a clean keyframe
                if warmup_remaining > 0:
                    warmup_remaining -= 1
                    continue
                with self._lock:
                    self._frame = frame
            else:
                time.sleep(0.01)

    def read(self) -> np.ndarray | None:
        """Return the latest frame (or ``None`` if no frame available yet).

        The returned array is a *copy* so the caller can mutate it without
        affecting the reader thread.
        """
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def stop(self) -> None:
        """Stop the reader thread and release the capture device."""
        self._stopped = True
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def is_alive(self) -> bool:
        """Return ``True`` if the reader thread is still running."""
        return self._thread is not None and self._thread.is_alive()
