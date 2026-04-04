"""
Stream Relay -- FFmpeg RTSP relay to VPS mediamtx.

Supports two modes:
  - "copy":      Remux only (no transcode), minimal CPU. Best for cameras
                 that produce clean, predictable H.264 streams (e.g. P340).
  - "transcode": Re-encode to a normalized H.264 Baseline stream. Needed for
                 cameras like the CX810 that produce bursty/problematic output.
"""
import logging
import subprocess
import threading
import time

logger = logging.getLogger(__name__)


class StreamRelay:
    """Relay an RTSP source stream to a target RTSP URL via FFmpeg."""

    def __init__(
        self,
        source_url: str,
        target_url: str,
        mode: str = "copy",
        resolution: str = "1280x720",
        bitrate: str = "2500k",
        max_bitrate: str = "3000k",
        fps: str = "20",
    ):
        self.source_url = source_url
        self.target_url = target_url
        self.mode = mode
        self.resolution = resolution
        self.bitrate = bitrate
        self.max_bitrate = max_bitrate
        self.fps = fps
        self.process = None
        self._thread = None
        self._stop_event = threading.Event()

    def _build_cmd(self) -> list[str]:
        """Build the FFmpeg command based on relay mode."""
        # Common input flags for low-latency RTSP ingestion
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-probesize", "500000",
            "-analyzeduration", "500000",
            "-rtsp_transport", "tcp",
            "-i", self.source_url,
        ]

        if self.mode == "transcode":
            # Re-encode to a clean, predictable H.264 Baseline stream.
            # ultrafast preset keeps RPi CPU usage reasonable (~40-60% on Pi 4).
            cmd += [
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-profile:v", "baseline",
                "-b:v", self.bitrate,
                "-maxrate", self.max_bitrate,
                "-bufsize", "1500k",
                "-s", self.resolution,
                "-r", self.fps,
                "-g", str(int(self.fps) * 2),  # Keyframe every 2 seconds
                "-an",  # Drop audio
            ]
        else:
            # Copy mode: passthrough, no transcoding
            cmd += [
                "-c", "copy",
                "-an",
            ]

        # Common output flags
        cmd += [
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            "-muxdelay", "0",
            self.target_url,
        ]
        return cmd

    def start(self):
        """Start FFmpeg RTSP relay in a background thread."""
        self._stop_event.clear()
        cmd = self._build_cmd()
        logger.info(
            f"Starting RTSP relay ({self.mode} mode): "
            f"{self.source_url} -> {self.target_url}"
        )
        if self.mode == "transcode":
            logger.info(
                f"Transcode settings: {self.resolution} @ {self.bitrate} "
                f"(max {self.max_bitrate}), {self.fps}fps"
            )
        self._thread = threading.Thread(target=self._run, args=(cmd,), daemon=True)
        self._thread.start()

    def _run(self, cmd):
        while not self._stop_event.is_set():
            try:
                self.process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                logger.info("FFmpeg relay started")
                self.process.wait()
                if self._stop_event.is_set():
                    break
                logger.warning("FFmpeg relay exited, restarting in 5s...")
            except Exception as e:
                logger.error(f"FFmpeg relay error: {e}")
            time.sleep(5)

    def stop(self):
        """Stop the relay process and background thread."""
        self._stop_event.set()
        if self.process:
            self.process.terminate()
            self.process = None

    def is_alive(self) -> bool:
        """Check if the relay thread is still running."""
        return self._thread is not None and self._thread.is_alive()
