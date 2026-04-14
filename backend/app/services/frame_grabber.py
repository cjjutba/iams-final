"""
FrameGrabber — persistent RTSP frame source for the attendance engine.

Uses an FFmpeg subprocess to decode the RTSP stream (handles H.264/H.265)
and continuously drains frames in a daemon thread, keeping only the latest.
The caller retrieves the most recent frame via grab(), which returns
instantly without any network overhead.

Why FFmpeg subprocess instead of cv2.VideoCapture?
  - cv2.VideoCapture(RTSP) requires OpenCV built with RTSP support
  - Docker images often ship headless OpenCV without GStreamer/RTSP
  - FFmpeg subprocess works universally and handles H.265 (HEVC) natively

Staleness detection:
  If no new frame arrives within `stale_timeout` seconds, grab() returns
  None and the drain thread automatically reconnects the RTSP stream.
"""

import logging
import subprocess
import threading
import time

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


class FrameGrabber:
    """Thread-safe, persistent RTSP frame source using FFmpeg subprocess.

    Args:
        rtsp_url:      Full RTSP URL (e.g. ``rtsp://host:8554/cam1``).
        stale_timeout: Seconds after which a frame is considered stale.
                       Triggers automatic reconnect.  Default 30 s.
        width:         Output frame width (FFmpeg rescales). Default from settings.
        height:        Output frame height (FFmpeg rescales). Default from settings.
        fps:           FFmpeg output frame rate. Default from settings.
    """

    def __init__(
        self,
        rtsp_url: str,
        stale_timeout: float = 30.0,
        width: int | None = None,
        height: int | None = None,
        fps: float | None = None,
    ) -> None:
        self._url = rtsp_url
        self._stale_timeout = stale_timeout
        self._width = width or settings.FRAME_GRABBER_WIDTH
        self._height = height or settings.FRAME_GRABBER_HEIGHT
        self._fps = fps or settings.FRAME_GRABBER_FPS
        self._frame_bytes = self._width * self._height * 3  # BGR24

        self._lock = threading.Lock()
        self._latest_frame: np.ndarray | None = None
        self._frame_time: float = 0.0

        self._stop_event = threading.Event()
        self._process: subprocess.Popen | None = None

        self._process = self._start_ffmpeg()
        self._thread = threading.Thread(target=self._drain_loop, daemon=True, name="frame-grabber")
        self._thread.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def grab(self) -> np.ndarray | None:
        """Return a *copy* of the latest frame, or None if unavailable."""
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
        """Signal the drain thread to exit and release FFmpeg."""
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        self._thread.join(timeout=3.0)
        self._kill_ffmpeg()
        logger.info("FrameGrabber stopped for %s", self._url)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _start_ffmpeg(self) -> subprocess.Popen | None:
        """Start FFmpeg subprocess that decodes RTSP → raw BGR24 on stdout."""
        cmd = [
            "ffmpeg",
            # Low-latency RTSP input flags — reduces buffering from ~1s to <50ms
            "-fflags",
            "+genpts+discardcorrupt+nobuffer",
            "-flags",
            "low_delay",
            "-rtsp_transport",
            "tcp",
            "-analyzeduration",
            "500000",  # 500ms (default 5s) — faster stream analysis
            "-probesize",
            "500000",  # 500KB (default 5MB) — faster format detection
            "-max_delay",
            "0",  # no demuxer buffering
            "-reorder_queue_size",
            "0",  # no packet reordering buffer
            "-i",
            self._url,
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{self._width}x{self._height}",
            "-r",
            str(int(self._fps)),
            "-an",  # no audio
            "-v",
            "warning",
            "-threads",
            "1",  # single thread decode — lower latency than multi-threaded
            "pipe:1",
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=self._frame_bytes,  # buffer exactly 1 frame — minimizes latency
            )
            logger.info("FFmpeg started for %s (pid=%d)", self._url, proc.pid)
            # Drain stderr in a background thread so we can log FFmpeg errors
            threading.Thread(target=self._drain_stderr, args=(proc,), daemon=True, name="ffmpeg-stderr").start()
            return proc
        except Exception:
            logger.exception("Failed to start FFmpeg for %s", self._url)
            return None

    def _kill_ffmpeg(self) -> None:
        """Kill the FFmpeg subprocess."""
        if self._process is not None:
            try:
                self._process.stdout.close()
            except Exception:
                pass
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

    def _drain_stderr(self, proc: subprocess.Popen) -> None:
        """Read FFmpeg stderr and log warnings/errors."""
        try:
            for line in proc.stderr:
                msg = line.decode("utf-8", errors="replace").strip()
                if msg:
                    logger.warning("FFmpeg [%s]: %s", self._url, msg)
        except Exception:
            pass  # process died, nothing to drain

    def _reconnect(self) -> None:
        """Kill current FFmpeg and start a fresh one."""
        logger.info("Reconnecting FFmpeg for %s", self._url)
        self._kill_ffmpeg()
        self._process = self._start_ffmpeg()

    def _read_exactly(self, n: int) -> bytes | None:
        """Read exactly n bytes from FFmpeg stdout, or None on EOF."""
        if self._process is None or self._process.stdout is None:
            return None
        buf = b""
        while len(buf) < n:
            chunk = self._process.stdout.read(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _drain_loop(self) -> None:
        """Continuously read frames from FFmpeg, keeping only the latest."""
        warmup_frames = 3  # discard first few frames (may be corrupt)
        frames_read = 0

        while not self._stop_event.is_set():
            if self._process is None or self._process.poll() is not None:
                # FFmpeg not running — wait and reconnect
                self._stop_event.wait(2.0)
                if not self._stop_event.is_set():
                    with self._lock:
                        self._reconnect()
                continue

            data = self._read_exactly(self._frame_bytes)
            if data is None or len(data) < self._frame_bytes:
                # EOF or short read — FFmpeg died
                self._stop_event.wait(1.0)
                if not self._stop_event.is_set():
                    with self._lock:
                        self._reconnect()
                continue

            frames_read += 1
            if frames_read <= warmup_frames:
                continue

            frame = np.frombuffer(data, dtype=np.uint8).reshape((self._height, self._width, 3))

            with self._lock:
                self._latest_frame = frame
                self._frame_time = time.monotonic()
