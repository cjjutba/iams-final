"""FFmpeg subprocess publisher -- encodes raw frames to H.264 and pushes to RTSP.

Accepts raw BGR24 numpy arrays via ``write_frame()``, pipes them to an FFmpeg
subprocess that encodes H.264 ultrafast/zerolatency and publishes to mediamtx.

Platform-aware:
- **macOS (Darwin):** Uses ``h264_videotoolbox`` for hardware-accelerated encoding.
- **Linux:** Uses ``libx264`` with ``ultrafast`` preset and ``zerolatency`` tune.

Critical: ``-bf 0`` (no B-frames) is always set for WebRTC compatibility.
"""

import platform
import subprocess

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

    def __init__(self, rtsp_url: str, width: int, height: int, fps: int) -> None:
        self.rtsp_url = rtsp_url
        self.width = width
        self.height = height
        self.fps = fps
        self._process: subprocess.Popen | None = None

    def _build_ffmpeg_cmd(self) -> list[str]:
        """Build the FFmpeg command line based on platform.

        Returns:
            List of command-line tokens suitable for ``subprocess.Popen``.
        """
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
            "-g", "10",
            "-b:v", "1200k",
            "-maxrate", "1500k",
            "-bufsize", "500k",
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
            stderr=subprocess.PIPE,
            bufsize=self.width * self.height * 3 * 2,
        )

    def write_frame(self, frame: np.ndarray) -> bool:
        """Write a single BGR frame to FFmpeg stdin.

        Args:
            frame: BGR numpy array of shape ``(height, width, 3)``.

        Returns:
            ``True`` on success, ``False`` if the pipe is broken or the
            process has exited.
        """
        if self._process is None or self._process.poll() is not None:
            return False
        try:
            self._process.stdin.write(frame.tobytes())
            return True
        except BrokenPipeError:
            logger.warning("FFmpeg publisher pipe broken")
            return False

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
                self._process.kill()
            self._process = None

    @property
    def is_alive(self) -> bool:
        """Return ``True`` if the FFmpeg process is still running."""
        return self._process is not None and self._process.poll() is None
