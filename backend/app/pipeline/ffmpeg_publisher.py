"""FFmpeg subprocess publisher -- encodes raw frames to H.264 and pushes to RTSP.

Accepts raw BGR24 numpy arrays via ``write_frame()``, pipes them to an FFmpeg
subprocess that encodes H.264 ultrafast/zerolatency and publishes to mediamtx.

Platform-aware:
- **macOS (Darwin):** Uses ``h264_videotoolbox`` for hardware-accelerated encoding.
- **Linux:** Uses ``libx264`` with ``ultrafast`` preset and ``zerolatency`` tune.

Critical: ``-bf 0`` (no B-frames) is always set for WebRTC compatibility.
"""

import os
import platform
import subprocess
import threading

import numpy as np

from app.config import logger


class FFmpegPublisher:
    """Encode raw BGR frames via FFmpeg and publish as an RTSP stream.

    Args:
        rtsp_url: Target RTSP URL (e.g. ``rtsp://mediamtx:8554/room-1/annotated``).
        width: Frame width in pixels.
        height: Frame height in pixels.
        fps: Target frame rate for the output stream.
    """

    # Maximum seconds to wait for a single write before declaring pipe dead
    WRITE_TIMEOUT = 2.0

    def __init__(self, rtsp_url: str, width: int, height: int, fps: int) -> None:
        self.rtsp_url = rtsp_url
        self.width = width
        self.height = height
        self.fps = fps
        self._process: subprocess.Popen | None = None

    def _build_ffmpeg_cmd(self) -> list[str]:
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{self.width}x{self.height}",
            "-r", str(self.fps),
            "-i", "pipe:0",
        ]

        if platform.system() == "Darwin":
            cmd += ["-c:v", "h264_videotoolbox", "-realtime", "1", "-allow_sw", "1"]
        else:
            cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency"]

        cmd += [
            "-pix_fmt", "yuv420p",
            "-bf", "0",
            "-g", str(self.fps),
            "-b:v", "1200k",
            "-maxrate", "1500k",
            "-bufsize", "300k",
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            self.rtsp_url,
        ]
        return cmd

    def start(self) -> None:
        """Launch the FFmpeg subprocess and open the stdin pipe."""
        cmd = self._build_ffmpeg_cmd()
        logger.info(f"Starting FFmpeg publisher -> {self.rtsp_url}")
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            bufsize=self.width * self.height * 3 * 2,
        )
        # Make stdin non-blocking on Unix to prevent write() from hanging
        if hasattr(os, "set_blocking") and self._process.stdin:
            try:
                os.set_blocking(self._process.stdin.fileno(), False)
            except Exception:
                pass  # fall back to blocking mode

    def write_frame(self, frame: np.ndarray) -> bool:
        """Write a single BGR frame to FFmpeg stdin with timeout protection.

        Returns ``True`` on success, ``False`` if the pipe is broken,
        process exited, or write timed out.
        """
        if self._process is None or self._process.poll() is not None:
            return False

        data = frame.tobytes()
        result = [False]

        def _do_write():
            try:
                self._process.stdin.write(data)
                self._process.stdin.flush()
                result[0] = True
            except (BrokenPipeError, OSError):
                result[0] = False
            except Exception:
                result[0] = False

        # Use a thread with timeout to prevent blocking forever
        t = threading.Thread(target=_do_write, daemon=True)
        t.start()
        t.join(timeout=self.WRITE_TIMEOUT)

        if t.is_alive():
            # Write timed out — pipe is blocked (FFmpeg output buffer full)
            logger.warning("FFmpeg publisher write timed out (pipe blocked)")
            return False

        return result[0]

    def stop(self) -> None:
        """Stop the FFmpeg subprocess gracefully."""
        if self._process is not None:
            try:
                self._process.stdin.close()
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
        """Return ``True`` if the FFmpeg process is still running."""
        return self._process is not None and self._process.poll() is None
