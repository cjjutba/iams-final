"""
Stream Relay — FFmpeg RTSP Push to VPS

Manages an FFmpeg subprocess that relays the camera's RTSP sub-stream
to the VPS mediamtx instance. mediamtx then serves the stream to the
mobile app via WebRTC (WHEP protocol).

Key design decisions:
- Uses -c copy (no transcoding) → ~2-3% CPU on RPi, ~500 Kbps upload
- Session-aware: starts when a session becomes active, stops when it ends
- Auto-reconnects if FFmpeg dies (configurable retry delay)
- Runs in a background thread so it doesn't block the scan loop
"""

import shutil
import subprocess
import threading
import time

from app.config import config, logger


class StreamRelay:
    """Manages FFmpeg subprocess for RTSP relay to VPS mediamtx."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._current_room_id: str | None = None

    @property
    def is_running(self) -> bool:
        """True if the relay thread is active and FFmpeg is alive."""
        with self._lock:
            proc = self._process
        return proc is not None and proc.poll() is None

    def start(self, room_id: str) -> bool:
        """
        Start relaying the camera RTSP stream to VPS mediamtx.

        Spawns a background thread that keeps FFmpeg running and
        auto-restarts it on failure.

        Args:
            room_id: Room identifier (used as mediamtx path name).

        Returns:
            True if relay was started, False if disabled or misconfigured.
        """
        if not config.STREAM_RELAY_ENABLED:
            logger.debug("Stream relay is disabled")
            return False

        if not config.RTSP_URL:
            logger.warning("Stream relay enabled but no RTSP_URL configured")
            return False

        if not config.STREAM_RELAY_URL:
            logger.warning("Stream relay enabled but no STREAM_RELAY_URL configured")
            return False

        if not shutil.which("ffmpeg"):
            logger.error("Stream relay: ffmpeg not found in PATH")
            return False

        # Stop any existing relay first
        if self._thread and self._thread.is_alive():
            self.stop()

        self._current_room_id = room_id
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run_loop,
            name="stream-relay",
            daemon=True,
        )
        self._thread.start()

        logger.info(f"Stream relay started: {config.RTSP_URL} → {config.STREAM_RELAY_URL}/{room_id}")
        return True

    def stop(self) -> None:
        """Stop the relay. Kills FFmpeg and joins the background thread."""
        self._stop_event.set()
        self._kill_ffmpeg()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

        self._thread = None
        self._current_room_id = None
        logger.info("Stream relay stopped")

    def _run_loop(self) -> None:
        """
        Background thread: keep FFmpeg running until stop() is called.

        On FFmpeg exit (crash, network error), waits STREAM_RELAY_RETRY_DELAY
        seconds then restarts. This provides automatic recovery from transient
        network failures between the RPi and VPS.
        """
        while not self._stop_event.is_set():
            try:
                self._start_ffmpeg()
            except Exception as e:
                logger.error(f"Stream relay: failed to start FFmpeg: {e}")

            # Wait for FFmpeg to exit or stop signal
            while not self._stop_event.is_set():
                with self._lock:
                    proc = self._process
                if proc is None:
                    break
                ret = proc.poll()
                if ret is not None:
                    logger.warning(f"Stream relay: FFmpeg exited (code={ret})")
                    with self._lock:
                        if self._process is proc:
                            self._process = None
                    break
                time.sleep(1)

            # If not stopped, wait before retrying
            if not self._stop_event.is_set():
                delay = config.STREAM_RELAY_RETRY_DELAY
                logger.info(f"Stream relay: restarting FFmpeg in {delay}s...")
                self._stop_event.wait(delay)

    def _start_ffmpeg(self) -> None:
        """Launch FFmpeg subprocess to push RTSP stream to VPS."""
        dest = f"{config.STREAM_RELAY_URL}/{self._current_room_id}"
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-rtsp_transport",
            config.RTSP_TRANSPORT,
            "-i",
            config.RTSP_URL,
            "-an",  # Drop audio (avoids codec issues with mediamtx)
            "-c:v",
            "copy",
            "-f",
            "rtsp",
            dest,
        ]

        logger.info(f"Stream relay: launching FFmpeg → {dest}")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with self._lock:
            self._process = proc

    def _kill_ffmpeg(self) -> None:
        """Terminate the FFmpeg process if running."""
        with self._lock:
            proc = self._process
            self._process = None
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
        except Exception as e:
            logger.warning(f"Stream relay: error killing FFmpeg: {e}")


# Module-level singleton
stream_relay = StreamRelay()
