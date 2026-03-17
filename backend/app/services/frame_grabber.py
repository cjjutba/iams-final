"""
FrameGrabber — persistent RTSP frame source for the attendance engine.

Maintains a long-lived cv2.VideoCapture connection to an RTSP camera and
continuously drains frames in a daemon thread, keeping only the latest.
The caller retrieves the most recent frame via grab(), which returns
instantly without any network overhead.

Why a drain loop?
  - Avoids 500ms-1s connection overhead of spawning FFmpeg per grab
  - Prevents RTSP buffer backlog (stale frames accumulate if not read)
  - Makes grab() O(1) — just a lock-protected copy

Staleness detection:
  If no new frame arrives within `stale_timeout` seconds, grab() returns
  None and the drain thread automatically reconnects the RTSP stream.
"""

import logging
import threading
import time
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class FrameGrabber:
    """Thread-safe, persistent RTSP frame source.

    Args:
        rtsp_url:      Full RTSP URL (e.g. ``rtsp://host:8554/cam1``).
        stale_timeout: Seconds after which a frame is considered stale.
                       Triggers automatic reconnect.  Default 30 s.
    """

    def __init__(self, rtsp_url: str, stale_timeout: float = 30.0) -> None:
        self._url = rtsp_url
        self._stale_timeout = stale_timeout

        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_time: float = 0.0  # monotonic timestamp of last frame

        self._stop_event = threading.Event()
        self._cap: Optional[cv2.VideoCapture] = None

        # Open initial connection and start drain thread
        self._cap = self._open_capture()
        self._thread = threading.Thread(
            target=self._drain_loop, daemon=True, name="frame-grabber"
        )
        self._thread.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def grab(self) -> Optional[np.ndarray]:
        """Return a *copy* of the latest frame, or None if unavailable.

        Returns None in two cases:
          1. No frame has been received yet.
          2. The latest frame is older than ``stale_timeout`` — a reconnect
             is triggered automatically.
        """
        with self._lock:
            if self._latest_frame is None:
                return None

            age = time.monotonic() - self._frame_time
            if age > self._stale_timeout:
                logger.warning(
                    "Frame stale (%.1fs > %.1fs), triggering reconnect",
                    age,
                    self._stale_timeout,
                )
                self._latest_frame = None
                self._reconnect()
                return None

            return self._latest_frame.copy()

    def is_alive(self) -> bool:
        """Return True if the drain thread is running."""
        return self._thread.is_alive() and not self._stop_event.is_set()

    def stop(self) -> None:
        """Signal the drain thread to exit and release the capture."""
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        self._thread.join(timeout=3.0)
        self._release_capture()
        logger.info("FrameGrabber stopped for %s", self._url)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _open_capture(self) -> cv2.VideoCapture:
        """Create a new VideoCapture for the RTSP URL."""
        logger.info("Opening RTSP connection: %s", self._url)
        cap = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
        return cap

    def _release_capture(self) -> None:
        """Release the current VideoCapture if any."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def _reconnect(self) -> None:
        """Close the current capture and open a fresh one.

        Called from grab() (under lock) when a stale frame is detected,
        and from the drain loop on read failures.
        """
        logger.info("Reconnecting RTSP: %s", self._url)
        self._release_capture()
        self._cap = self._open_capture()

    def _drain_loop(self) -> None:
        """Continuously read frames, keeping only the latest.

        Runs in a daemon thread until stop() sets the stop event.
        """
        while not self._stop_event.is_set():
            cap = self._cap
            if cap is None or not cap.isOpened():
                # Wait briefly before retry to avoid busy-spin
                self._stop_event.wait(0.5)
                with self._lock:
                    if not self._stop_event.is_set():
                        self._reconnect()
                continue

            ret, frame = cap.read()

            if not ret or frame is None:
                # Read failed — brief back-off then retry
                self._stop_event.wait(0.1)
                continue

            with self._lock:
                self._latest_frame = frame
                self._frame_time = time.monotonic()
