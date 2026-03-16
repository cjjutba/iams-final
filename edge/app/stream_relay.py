"""
Stream Relay -- FFmpeg RTSP sub-stream relay to VPS mediamtx.
Remux only (no transcode), minimal CPU usage.
"""
import logging
import subprocess
import threading
import time

logger = logging.getLogger(__name__)


class StreamRelay:
    """Relay an RTSP source stream to a target RTSP URL via FFmpeg."""

    def __init__(self, source_url: str, target_url: str):
        self.source_url = source_url
        self.target_url = target_url
        self.process = None
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        """Start FFmpeg RTSP relay in a background thread."""
        self._stop_event.clear()
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            # Low-latency input flags
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-probesize", "500000",
            "-analyzeduration", "500000",
            "-rtsp_transport", "tcp",
            "-i", self.source_url,
            "-c", "copy",
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            "-muxdelay", "0",
            self.target_url,
        ]
        logger.info(f"Starting RTSP relay: {self.source_url} -> {self.target_url}")
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
