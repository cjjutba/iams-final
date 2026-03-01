"""
HLS Service

Manages FFmpeg subprocesses that remux RTSP H.264 streams to HLS
(HTTP Live Streaming) format for hardware-decoded playback on mobile devices.

Key design decisions:
- ``-c:v copy`` remuxes without transcoding (near-zero CPU)
- One FFmpeg process per room, shared across viewers (reference counted)
- Sliding-window playlist with ``delete_segments`` for automatic cleanup
- Health monitoring via process returncode checks
"""

import asyncio
import glob
import os
import signal
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Optional, Set

from app.config import settings, logger


@dataclass
class HLSStream:
    """State for a single room's FFmpeg HLS process."""
    room_id: str
    rtsp_url: str
    process: Optional[subprocess.Popen] = None
    viewers: Set[str] = field(default_factory=set)
    segment_dir: str = ""


class HLSService:
    """
    Manages FFmpeg HLS transcoding processes per room.

    One FFmpeg process per room is shared across all viewers.
    When the last viewer disconnects, the process is killed and
    segment files are cleaned up.
    """

    _active: Dict[str, HLSStream] = {}

    def _ensure_segment_dir(self, room_id: str) -> str:
        """Create and return the segment directory for a room."""
        base = os.path.normpath(settings.HLS_SEGMENT_DIR)
        room_dir = os.path.join(base, room_id)
        os.makedirs(room_dir, exist_ok=True)
        return room_dir

    async def start_stream(
        self,
        room_id: str,
        rtsp_url: str,
        viewer_id: str,
    ) -> bool:
        """
        Start (or join) an HLS stream for *room_id*.

        If an FFmpeg process is already running for this room the
        caller is simply added to the viewer set.

        Returns True if the stream is available, False on failure.
        """
        if room_id in self._active:
            stream = self._active[room_id]
            stream.viewers.add(viewer_id)
            logger.info(
                f"HLS: viewer {viewer_id} joined room {room_id} "
                f"({len(stream.viewers)} viewers)"
            )
            return True

        # New stream — purge any stale segments from previous sessions
        segment_dir = self._ensure_segment_dir(room_id)
        self._cleanup_segments(segment_dir)
        # Re-create directory (cleanup removes it when empty)
        os.makedirs(segment_dir, exist_ok=True)

        stream = HLSStream(
            room_id=room_id,
            rtsp_url=rtsp_url,
            segment_dir=segment_dir,
        )
        stream.viewers.add(viewer_id)
        self._active[room_id] = stream

        ok = await self._launch_ffmpeg(room_id, stream)
        if not ok:
            self._active.pop(room_id, None)
            return False

        logger.info(f"HLS: stream started for room {room_id}")
        return True

    async def ensure_healthy(self, room_id: str) -> bool:
        """
        Check whether FFmpeg is still running for *room_id*.

        If the process has died, clean up stale segments and restart it.
        Returns True if the stream is healthy after the check.
        Called periodically from the WebSocket loop to self-heal.
        """
        stream = self._active.get(room_id)
        if stream is None:
            return False

        if stream.process and stream.process.poll() is None:
            return True  # Process is alive

        # Process died — log its return code and restart
        rc = stream.process.returncode if stream.process else "N/A"
        logger.warning(
            f"HLS: FFmpeg died for room {room_id} (rc={rc}), restarting..."
        )

        # Clean up the dead process handle
        if stream.process:
            try:
                stream.process.wait(timeout=1)
            except Exception:
                pass
            stream.process = None

        # Purge stale segments so the player gets a clean init.mp4
        self._cleanup_segments(stream.segment_dir)
        os.makedirs(stream.segment_dir, exist_ok=True)

        return await self._launch_ffmpeg(room_id, stream)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_ffmpeg_cmd(self, rtsp_url: str, segment_dir: str) -> list:
        """Return the FFmpeg argument list for an HLS mux of *rtsp_url*."""
        playlist_path = os.path.join(segment_dir, "playlist.m3u8")
        segment_pattern = os.path.join(segment_dir, "seg_%05d.m4s")
        ffmpeg_path = os.path.abspath(settings.HLS_FFMPEG_PATH)
        return [
            ffmpeg_path,
            # Low-latency input flags — minimize RTSP buffering
            "-fflags", "nobuffer+genpts",
            "-flags", "low_delay",
            "-probesize", "512000",        # 500KB — enough to detect codec params
            "-analyzeduration", "500000",  # 500ms — fast probe but not zero
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-c:v", "copy",   # Remux without transcoding; zero CPU overhead
            "-an",             # No audio
            "-f", "hls",
            "-hls_time", str(settings.HLS_SEGMENT_DURATION),
            "-hls_list_size", str(settings.HLS_PLAYLIST_SIZE),
            "-hls_flags", "delete_segments+append_list+split_by_time+omit_endlist",
            "-hls_segment_type", "fmp4",            # fMP4 segments (better decoder compat)
            "-hls_fmp4_init_filename", "init.mp4",  # Init segment for fMP4
            "-hls_segment_filename", segment_pattern,
            playlist_path,
        ]

    async def _launch_ffmpeg(self, room_id: str, stream: "HLSStream") -> bool:
        """
        Start an FFmpeg process for *stream* and wait for the first playlist.

        Updates ``stream.process`` in-place.  Returns True on success.
        """
        cmd = self._build_ffmpeg_cmd(stream.rtsp_url, stream.segment_dir)
        playlist_path = os.path.join(stream.segment_dir, "playlist.m3u8")

        logger.info(f"HLS: starting FFmpeg for room {room_id}")
        logger.debug(f"HLS cmd: {' '.join(cmd)}")

        try:
            process = subprocess.Popen(
                cmd,
                # DEVNULL prevents pipe buffer deadlock — FFmpeg writes verbose
                # progress to stderr which fills the 64KB pipe buffer and blocks.
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                # On Windows, CREATE_NEW_PROCESS_GROUP allows clean termination
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    if os.name == "nt"
                    else 0
                ),
            )
        except FileNotFoundError:
            logger.error(
                "HLS: FFmpeg not found. Install FFmpeg and ensure it is on PATH "
                f"(configured path: {settings.HLS_FFMPEG_PATH})"
            )
            return False
        except Exception as exc:
            logger.error(f"HLS: failed to start FFmpeg for room {room_id}: {exc}")
            return False

        stream.process = process

        # Wait for FFmpeg to write the first playlist file
        await self._wait_for_playlist(playlist_path, timeout=10.0)

        # Check that the process didn't exit immediately
        if process.poll() is not None:
            logger.error(
                f"HLS: FFmpeg exited immediately for room {room_id} "
                f"(rc={process.returncode})"
            )
            stream.process = None
            return False

        return True

    async def _wait_for_playlist(self, path: str, timeout: float = 10.0) -> bool:
        """Poll for the .m3u8 file to appear (FFmpeg creates it after the first segment)."""
        elapsed = 0.0
        interval = 0.3
        while elapsed < timeout:
            if os.path.exists(path):
                return True
            await asyncio.sleep(interval)
            elapsed += interval
        logger.warning(f"HLS: playlist did not appear within {timeout}s: {path}")
        return False

    async def stop_stream(self, room_id: str, viewer_id: Optional[str] = None) -> None:
        """
        Remove a viewer.  If no viewers remain, stop the FFmpeg process
        and clean up segment files.
        """
        stream = self._active.get(room_id)
        if stream is None:
            return

        if viewer_id is not None:
            stream.viewers.discard(viewer_id)
            logger.info(
                f"HLS: viewer {viewer_id} left room {room_id} "
                f"({len(stream.viewers)} remaining)"
            )
            if stream.viewers:
                return  # other viewers still watching

        # No viewers — terminate FFmpeg
        self._kill_process(stream)
        self._cleanup_segments(stream.segment_dir)
        self._active.pop(room_id, None)
        logger.info(f"HLS: stream stopped for room {room_id}")

    def get_segment_dir(self, room_id: str) -> str:
        """Return the segment directory for a room."""
        stream = self._active.get(room_id)
        if stream:
            return stream.segment_dir
        # Fallback: construct path even if not active
        return os.path.join(os.path.normpath(settings.HLS_SEGMENT_DIR), room_id)

    def is_active(self, room_id: str) -> bool:
        """Check if a stream is running for a room."""
        stream = self._active.get(room_id)
        if stream is None or stream.process is None:
            return False
        return stream.process.poll() is None

    def get_active_rooms(self) -> list:
        """Return list of room_ids with active HLS streams."""
        return [rid for rid in self._active if self.is_active(rid)]

    def get_viewer_count(self, room_id: str) -> int:
        stream = self._active.get(room_id)
        return len(stream.viewers) if stream else 0

    async def cleanup_all(self) -> None:
        """Stop all streams (called on application shutdown)."""
        for room_id in list(self._active.keys()):
            await self.stop_stream(room_id)
        logger.info("HLS: all streams stopped")

    @staticmethod
    def _kill_process(stream: HLSStream) -> None:
        """Terminate the FFmpeg process."""
        proc = stream.process
        if proc is None:
            return
        try:
            if os.name == "nt":
                proc.terminate()
            else:
                proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        except Exception as exc:
            logger.warning(f"HLS: error killing FFmpeg for room {stream.room_id}: {exc}")
        finally:
            stream.process = None

    @staticmethod
    def _cleanup_segments(segment_dir: str) -> None:
        """Remove .m3u8, .ts, .m4s, and init.mp4 files from the segment directory."""
        try:
            for pattern in ("*.m3u8", "*.ts", "*.m4s"):
                for f in glob.glob(os.path.join(segment_dir, pattern)):
                    os.remove(f)
            # Remove init segment if present
            init_path = os.path.join(segment_dir, "init.mp4")
            if os.path.exists(init_path):
                os.remove(init_path)
            # Remove the directory if empty
            if os.path.isdir(segment_dir) and not os.listdir(segment_dir):
                os.rmdir(segment_dir)
        except Exception as exc:
            logger.warning(f"HLS: cleanup error for {segment_dir}: {exc}")


# Global singleton
hls_service = HLSService()
