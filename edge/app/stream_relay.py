"""
Stream Relay -- FFmpeg RTSP sub-stream relay to VPS mediamtx.
Remux only (no transcode), minimal CPU usage.
"""
import logging
import subprocess
import threading
import time

from app.config import ROOM_ID, RTSP_SUB, VPS_RTSP_URL

logger = logging.getLogger(__name__)


class StreamRelay:
    """Relay Reolink sub-stream to VPS mediamtx via FFmpeg."""

    def __init__(self):
        self.process = None
        self._thread = None

    def start(self):
        """Start FFmpeg RTSP relay in a background thread."""
        target_url = f"{VPS_RTSP_URL}/{ROOM_ID}"
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-rtsp_transport", "tcp",
            "-i", RTSP_SUB,
            "-c", "copy",
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            target_url,
        ]
        logger.info(f"Starting RTSP relay: {RTSP_SUB} -> {target_url}")
        self._thread = threading.Thread(target=self._run, args=(cmd,), daemon=True)
        self._thread.start()

    def _run(self, cmd):
        while True:
            try:
                self.process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                logger.info("FFmpeg relay started")
                self.process.wait()
                logger.warning("FFmpeg relay exited, restarting in 5s...")
            except Exception as e:
                logger.error(f"FFmpeg relay error: {e}")
            time.sleep(5)

    def stop(self):
        if self.process:
            self.process.terminate()
