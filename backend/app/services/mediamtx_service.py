"""
MediamtxService

Manages the mediamtx binary as a subprocess alongside the FastAPI process.
mediamtx bridges RTSP camera streams to WebRTC (WHEP protocol) for
sub-300ms mobile playback.

Key design decisions:
- start() is async so it can poll the mediamtx REST API with asyncio.sleep
  without blocking the FastAPI event loop during startup
- On failure, start() returns False and logs a clear error; FastAPI still
  starts and falls back to HLS automatically (existing behaviour)
- stop() is synchronous (called from shutdown_event which allows sync calls)
"""

import asyncio
import os
import signal
import subprocess
from typing import Optional

import httpx

from app.config import settings, logger


class MediamtxService:
    """Lifecycle manager for the mediamtx subprocess."""

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None

    async def start(
        self,
        bin_path: Optional[str] = None,
        config_path: Optional[str] = None,
    ) -> bool:
        """
        Launch mediamtx and wait for its REST API to become ready.

        Args:
            bin_path:    Override binary path (used in tests).
            config_path: Override config path (used in tests).

        Returns:
            True if mediamtx is running and API is ready, False otherwise.
            FastAPI startup continues regardless of the return value.
        """
        # Resolve paths relative to the backend/ directory.
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        resolved_bin = os.path.abspath(bin_path or os.path.join(base, settings.MEDIAMTX_BIN_PATH))
        resolved_cfg = os.path.abspath(config_path or os.path.join(base, settings.MEDIAMTX_CONFIG_PATH))

        if not os.path.isfile(resolved_bin):
            logger.error(
                f"mediamtx binary not found at {resolved_bin}. "
                "Run: bash backend/scripts/download_mediamtx.sh"
            )
            return False

        logger.info(f"Starting mediamtx: {resolved_bin} {resolved_cfg}")

        try:
            self._process = subprocess.Popen(
                [resolved_bin, resolved_cfg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.error(f"Failed to start mediamtx: {exc}")
            return False

        # Fast-fail: if the process exited immediately it's a bad config or port conflict.
        # Check before polling the API to avoid a 5-second wait on a dead process.
        await asyncio.sleep(0.1)
        if self._process.poll() is not None:
            logger.error(
                f"mediamtx exited immediately (rc={self._process.returncode}). "
                "Check mediamtx.yml and that ports 9997/8889/8554/8887 are free."
            )
            self._process = None
            return False

        # Wait for the mediamtx REST API to become ready (max 5 s).
        api_ready = await self._wait_for_api(timeout=5.0)

        if not api_ready:
            logger.error(
                "mediamtx started but REST API did not respond within 5 s. "
                "Falling back to HLS streaming."
            )
            self.stop()
            return False

        logger.info("mediamtx is ready (WebRTC streaming active)")
        return True

    def stop(self) -> None:
        """Terminate the mediamtx process (SIGTERM -> wait 5 s -> SIGKILL)."""
        proc = self._process
        if proc is None:
            return
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=5)
            logger.info("mediamtx stopped")
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass  # kernel will reap the zombie when FastAPI exits
            logger.info("mediamtx killed (SIGTERM timeout)")
        except Exception as exc:
            logger.warning(f"Error stopping mediamtx: {exc}")
        finally:
            self._process = None

    def is_healthy(self) -> bool:
        """Return True if the mediamtx process is still running."""
        return self._process is not None and self._process.poll() is None

    async def _wait_for_api(self, timeout: float = 5.0) -> bool:
        """Poll GET /v3/config/global/get until mediamtx responds or timeout."""
        url = f"{settings.MEDIAMTX_API_URL}/v3/config/global/get"
        elapsed = 0.0
        interval = 0.25
        async with httpx.AsyncClient(timeout=1.0) as client:
            while elapsed < timeout:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        return True
                except Exception:
                    pass
                await asyncio.sleep(interval)
                elapsed += interval
        return False


# Module-level singleton — imported by main.py
mediamtx_service = MediamtxService()
