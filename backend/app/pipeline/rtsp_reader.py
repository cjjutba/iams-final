"""Threaded RTSP reader using FFmpeg subprocess.

Uses a dedicated FFmpeg process to decode the RTSP stream, outputting raw
BGR24 frames on stdout. A background thread reads these frames and keeps
only the latest one for the consumer.
"""

import subprocess
import threading
import time

import numpy as np

from app.config import logger


class RTSPReader:
    """Thread-safe RTSP reader backed by an FFmpeg subprocess.

    FFmpeg handles RTSP demuxing, H.264 decoding, rescaling, and outputs
    raw BGR24 frames on stdout. The reader thread continuously reads these
    frames and overwrites a shared buffer so the consumer always gets the
    most recent image.

    Args:
        url: RTSP stream URL.
        target_fps: Output frame rate (FFmpeg ``-r`` flag).
        width: Output frame width (FFmpeg ``-s`` flag).
        height: Output frame height (FFmpeg ``-s`` flag).
    """

    WARMUP_FRAMES = 50

    def __init__(
        self,
        url: str,
        target_fps: int = 10,
        width: int = 640,
        height: int = 480,
    ) -> None:
        self.url = url
        self.target_fps = target_fps
        self.width = width
        self.height = height
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._stopped = False
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen | None = None

    def start(self) -> "RTSPReader":
        """Launch FFmpeg subprocess and start the background reader thread."""
        cmd = [
            "ffmpeg",
            "-fflags", "+genpts+discardcorrupt",
            "-rtsp_transport", "tcp",
            "-i", self.url,
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{self.width}x{self.height}",
            "-r", str(self.target_fps),
            "-an",
            "pipe:1",
        ]
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        self._stopped = False
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()
        logger.info(f"RTSPReader started: {self.url} → {self.width}x{self.height}@{self.target_fps}fps")
        return self

    def _read_exactly(self, n: int) -> bytes:
        """Read exactly n bytes from stdout, looping until complete."""
        data = b""
        while len(data) < n:
            remaining = n - len(data)
            chunk = self._process.stdout.read(remaining)
            if not chunk:
                return data  # EOF
            data += chunk
        return data

    def _reader_loop(self) -> None:
        """Continuously read raw frames from FFmpeg stdout."""
        frame_bytes = self.width * self.height * 3
        warmup = self.WARMUP_FRAMES
        while not self._stopped:
            if self._process is None or self._process.poll() is not None:
                time.sleep(0.1)
                continue
            try:
                raw = self._read_exactly(frame_bytes)
                if len(raw) != frame_bytes:
                    time.sleep(0.1)
                    continue
                if warmup > 0:
                    warmup -= 1
                    continue
                frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                    (self.height, self.width, 3)
                )
                with self._lock:
                    self._frame = frame
            except Exception:
                time.sleep(0.01)

    def read(self) -> np.ndarray | None:
        """Return the latest frame (or ``None`` if no frame available yet)."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def stop(self) -> None:
        """Stop the reader thread and kill the FFmpeg process."""
        self._stopped = True
        if self._thread is not None:
            self._thread.join(timeout=3.0)
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

    @property
    def is_alive(self) -> bool:
        """Return ``True`` if the reader thread is still running."""
        return self._thread is not None and self._thread.is_alive()
