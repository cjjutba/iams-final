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

RTP timestamp capture (live-feed plan 2026-04-25 Step 3a):
  When ``capture_rtp_pts=True``, FFmpeg is invoked with ``-vf showinfo`` so
  the showinfo filter prints the source-stream PTS to stderr per frame.
  ``_drain_stderr`` parses those lines into a bounded queue, and
  ``grab_with_pts()`` returns the next-available PTS alongside its frame.
  This lets the admin live page align WS bbox draws to the same RTP
  timestamp the browser sees on the WHEP video via
  ``requestVideoFrameCallback().rtpTimestamp``.
"""

import collections
import logging
import re
import subprocess
import threading
import time

import numpy as np

from app.config import settings


# showinfo emits ``[Parsed_showinfo_0 @ 0xADDR] n: 0 pts: 90000 pts_time: 1.000``
# per frame. We grab the integer PTS — that's already in the input
# stream's timebase, which for H.264 RTSP/RTP is the canonical 90 kHz
# clock that ``requestVideoFrameCallback().rtpTimestamp`` reports
# browser-side. Hence: the same number on both sides of the wire,
# modulo the ~13-hour wraparound at 32 bits.
_PTS_REGEX = re.compile(r"\bpts:\s*(\d+)\b")

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

    # Reconnect backoff when FFmpeg keeps failing to open the stream
    # (e.g. mediamtx returns 404 because no publisher is pushing).
    # Index by consecutive-failure count; last entry is the cap.
    _BACKOFF_SCHEDULE: tuple[float, ...] = (2.0, 5.0, 10.0, 20.0, 30.0)

    # Stderr patterns produced by FFmpeg when the RTSP endpoint has no
    # active publisher. Each FFmpeg spawn prints all four — we collapse
    # the whole cluster into a single "publisher offline" warning.
    _OFFLINE_STDERR_PATTERNS: tuple[str, ...] = (
        "404 Not Found",
        "method DESCRIBE failed",
        "Error opening input",
    )

    def __init__(
        self,
        rtsp_url: str,
        stale_timeout: float = 30.0,
        width: int | None = None,
        height: int | None = None,
        fps: float | None = None,
        capture_rtp_pts: bool = True,
    ) -> None:
        self._url = rtsp_url
        self._stale_timeout = stale_timeout
        self._width = width or settings.FRAME_GRABBER_WIDTH
        self._height = height or settings.FRAME_GRABBER_HEIGHT
        self._fps = fps or settings.FRAME_GRABBER_FPS
        self._frame_bytes = self._width * self._height * 3  # BGR24
        # When True, FFmpeg is launched with -vf showinfo + -copyts so the
        # input PTS is parseable from stderr. Live-feed plan Step 3a.
        # Disable for unit tests that mock the FFmpeg binary — they don't
        # produce a showinfo stream so the PTS queue would stay empty.
        self._capture_rtp_pts = capture_rtp_pts

        self._lock = threading.Lock()
        self._latest_frame: np.ndarray | None = None
        self._frame_time: float = 0.0
        # PTS of the most recent frame returned to the consumer. Captured
        # under the same lock as ``_latest_frame`` so ``grab_with_pts()``
        # is atomic. ``None`` means "no PTS observed yet" (filter not on,
        # or stderr drained slower than stdout for the first few frames).
        self._latest_pts: int | None = None
        # FIFO of pending PTS values from ``-vf showinfo``. The stderr and
        # stdout drains run on separate threads, so we must buffer here.
        # Bounded: in steady state the stderr thread emits one PTS per
        # frame the stdout thread reads, so the queue holds 0–1 values.
        # During reconnect glitches (e.g. stderr drained slower than the
        # warmup-frame discard) the queue may briefly grow; the maxlen
        # caps it so a runaway producer can't OOM us.
        self._pts_queue: collections.deque[int] = collections.deque(maxlen=64)
        self._pts_lock = threading.Lock()

        # Failure tracking for backoff + deduped offline logging.
        # Shared across reconnects (each reconnect spawns a new stderr thread).
        self._consecutive_failures: int = 0
        self._publisher_offline_logged: bool = False

        self._stop_event = threading.Event()
        self._process: subprocess.Popen | None = None

        self._process = self._start_ffmpeg()
        self._thread = threading.Thread(target=self._drain_loop, daemon=True, name="frame-grabber")
        self._thread.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def grab(self) -> np.ndarray | None:
        """Return a *copy* of the latest frame, or None if unavailable.

        Backwards-compatible accessor — used by face.py, calibrate scripts,
        and the test suite. The realtime pipeline uses ``grab_with_pts()``
        to also receive the upstream RTP PTS.
        """
        result = self.grab_with_pts()
        return None if result is None else result[0]

    def grab_with_pts(self) -> tuple[np.ndarray, int | None] | None:
        """Return ``(frame, rtp_pts_90k)`` for the latest frame, or None.

        ``rtp_pts_90k`` is the source-stream PTS (in the input timebase,
        which for H.264 RTSP is the canonical 90 kHz RTP clock). It is
        ``None`` when ``capture_rtp_pts=False`` or when showinfo has not
        yet emitted a PTS for this frame (rare, but possible during
        warmup or a stderr-thread restart).

        Stale-frame handling matches ``grab()``: a frame older than
        ``stale_timeout`` triggers a reconnect and returns None.
        """
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
                self._latest_pts = None
                self._reconnect()
                return None

            return self._latest_frame, self._latest_pts

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
        # Showinfo emits one ``pts: N pts_time: T`` line per frame to stderr.
        # We pipe it through scale (so the resize still happens) and parse
        # the PTS from stderr in ``_drain_stderr``. ``-copyts`` keeps the
        # input timestamps untouched so showinfo reports the source RTSP
        # PTS (i.e. the 90 kHz RTP clock). Note: showinfo runs at the
        # filter level, BEFORE ``-r`` re-rates output, so the PTS we get
        # is per *source* frame; we discard surplus PTS values when the
        # output rate is lower than source.
        vf_chain = (
            f"showinfo,scale={self._width}:{self._height}"
            if self._capture_rtp_pts
            else f"scale={self._width}:{self._height}"
        )
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
        ]
        if self._capture_rtp_pts:
            # Preserve source PTS through the filter chain so showinfo
            # reports the upstream 90 kHz RTP clock, not a re-stamped
            # value. Without this the filter graph would assign new PTS
            # starting from 0, which the browser-side WHEP RTP timestamp
            # would not match.
            cmd.extend(["-copyts"])
        cmd.extend([
            "-i",
            self._url,
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-vf",
            vf_chain,
            "-r",
            str(int(self._fps)),
            "-an",  # no audio
            # showinfo writes to stderr at the ``info`` log level. Other
            # warnings still surface — ``_drain_stderr`` distinguishes
            # showinfo lines from real warnings via the ``pts:`` regex.
            "-v",
            "info" if self._capture_rtp_pts else "warning",
            "-threads",
            "1",  # single thread decode — lower latency than multi-threaded
            "pipe:1",
        ])
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=self._frame_bytes,  # buffer exactly 1 frame — minimizes latency
            )
            # Keep the "started" log at debug during reconnect storms so a
            # camera-offline condition doesn't spam this line every backoff cycle.
            if self._consecutive_failures == 0:
                logger.info("FFmpeg started for %s (pid=%d)", self._url, proc.pid)
            else:
                logger.debug("FFmpeg retry spawn for %s (pid=%d, attempt=%d)",
                             self._url, proc.pid, self._consecutive_failures + 1)
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
        """Read FFmpeg stderr and log warnings/errors.

        Errors that indicate "no RTSP publisher" (mediamtx 404) are collapsed
        into a single ``publisher offline`` warning per outage — otherwise the
        4 error lines FFmpeg prints per failed DESCRIBE would be emitted every
        backoff cycle and drown the rest of the log.

        When ``capture_rtp_pts`` is True, every showinfo line is parsed for
        its ``pts:`` value and pushed onto the per-instance PTS queue. The
        line itself is NOT logged at info level (would drown the log at
        10–20 fps); errors that aren't showinfo lines are still surfaced
        as warnings.
        """
        try:
            for line in proc.stderr:
                msg = line.decode("utf-8", errors="replace").strip()
                if not msg:
                    continue

                # Showinfo per-frame line: extract PTS for the pairing
                # logic in ``_drain_loop`` and skip the rest of the
                # logging so we don't spam at video FPS.
                if self._capture_rtp_pts and "Parsed_showinfo" in msg:
                    m = _PTS_REGEX.search(msg)
                    if m is not None:
                        try:
                            with self._pts_lock:
                                self._pts_queue.append(int(m.group(1)))
                        except Exception:
                            pass
                    continue

                is_offline_noise = any(p in msg for p in self._OFFLINE_STDERR_PATTERNS)
                if is_offline_noise:
                    if not self._publisher_offline_logged:
                        logger.warning(
                            "Publisher offline for %s (mediamtx returned 404 — "
                            "no active RTSP publisher). Suppressing further "
                            "FFmpeg noise until frames resume.",
                            self._url,
                        )
                        self._publisher_offline_logged = True
                    continue
                logger.warning("FFmpeg [%s]: %s", self._url, msg)
        except Exception:
            pass  # process died, nothing to drain

    def _reconnect(self) -> None:
        """Kill current FFmpeg and start a fresh one."""
        # Keep the "reconnecting" log at debug during a publisher-offline storm;
        # we already logged the offline condition once in _drain_stderr.
        if self._consecutive_failures == 0:
            logger.info("Reconnecting FFmpeg for %s", self._url)
        else:
            logger.debug("Reconnecting FFmpeg for %s (attempt=%d)",
                         self._url, self._consecutive_failures + 1)
        # Drop any pending PTS values from the previous FFmpeg session —
        # the upstream stream's PTS clock has no continuity across a
        # reconnect, so pairing old PTS with new frames would mislabel
        # them on the WHEP-aligned overlay.
        with self._pts_lock:
            self._pts_queue.clear()
        self._kill_ffmpeg()
        self._process = self._start_ffmpeg()

    def _backoff_delay(self) -> float:
        """Delay before the next reconnect attempt based on consecutive failures."""
        idx = min(self._consecutive_failures, len(self._BACKOFF_SCHEDULE) - 1)
        return self._BACKOFF_SCHEDULE[idx]

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
                # FFmpeg exited (or never started). Back off before retrying
                # so a 404-returning mediamtx doesn't burn CPU + spam logs.
                delay = self._backoff_delay()
                self._consecutive_failures += 1
                self._stop_event.wait(delay)
                if not self._stop_event.is_set():
                    with self._lock:
                        self._reconnect()
                continue

            data = self._read_exactly(self._frame_bytes)
            if data is None or len(data) < self._frame_bytes:
                # EOF or short read — FFmpeg died. Apply backoff here too,
                # same reasoning as above.
                delay = self._backoff_delay()
                self._consecutive_failures += 1
                self._stop_event.wait(delay)
                if not self._stop_event.is_set():
                    with self._lock:
                        self._reconnect()
                continue

            frames_read += 1
            if frames_read <= warmup_frames:
                continue

            # Successful read — reset failure state and announce recovery
            # if we were previously in an offline state.
            if self._consecutive_failures > 0 or self._publisher_offline_logged:
                logger.info(
                    "Publisher online for %s (recovered after %d failed attempts)",
                    self._url,
                    self._consecutive_failures,
                )
            self._consecutive_failures = 0
            self._publisher_offline_logged = False

            frame = np.frombuffer(data, dtype=np.uint8).reshape((self._height, self._width, 3))

            # Pair this frame with the next-available PTS from showinfo.
            # The stderr-side queue is populated by ``_drain_stderr``; in
            # steady state it has 0–1 entries when we read here. If the
            # queue is empty the stderr drain is briefly behind — fall
            # through with ``None`` rather than block, so the pipeline
            # never stalls waiting on a metadata line.
            pts: int | None = None
            if self._capture_rtp_pts:
                with self._pts_lock:
                    if self._pts_queue:
                        pts = self._pts_queue.popleft()

            with self._lock:
                self._latest_frame = frame
                self._latest_pts = pts
                self._frame_time = time.monotonic()
