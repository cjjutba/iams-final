"""
Live Stream Service

Manages RTSP camera connections and real-time annotated frame streaming
to mobile clients via WebSocket.  One RTSP capture per room is shared
across all viewers.

Frame pipeline:
    1. cv2.VideoCapture(rtsp_url)
    2. Read frame at target FPS (configurable, default 8)
    3. Resize to stream resolution (640x360)
    4. Face detection + recognition only every Nth frame (configurable) — cache results
    5. InsightFace unified detect+embed+search per frame
    6. Draw bounding boxes with name, student_id, confidence (every frame)
    7. Encode as JPEG (quality 50)
    8. Pre-compute base64 (once, shared across viewers)
"""

import asyncio
import base64
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

import cv2
import numpy as np

from app.config import settings, logger


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Detection:
    """Single face detection result."""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    user_id: Optional[str] = None
    student_id: Optional[str] = None
    name: Optional[str] = None
    similarity: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "bbox": {"x": self.x, "y": self.y, "width": self.width, "height": self.height},
            "confidence": round(self.confidence, 3),
            "user_id": self.user_id,
            "student_id": self.student_id,
            "name": self.name,
            "similarity": round(self.similarity, 3) if self.similarity is not None else None,
        }


@dataclass
class StreamState:
    """Mutable state for a single room's RTSP stream."""
    room_id: str
    rtsp_url: str
    capture: Optional[cv2.VideoCapture] = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    viewers: Set[str] = field(default_factory=set)  # websocket ids
    # Frame data (written by capture loop, read by push loops)
    last_jpeg: Optional[bytes] = None
    last_b64: Optional[str] = None  # pre-computed base64
    last_detections: List[Detection] = field(default_factory=list)
    last_detections_dicts: List[dict] = field(default_factory=list)
    last_frame_time: float = 0.0
    frame_seq: int = 0  # monotonically increasing, viewers compare to avoid dups
    # Capture state
    frame_count: int = 0
    reconnect_attempts: int = 0
    max_reconnect_attempts: int = 10
    reconnect_delay_seconds: float = 2.0


# ---------------------------------------------------------------------------
# LiveStreamService
# ---------------------------------------------------------------------------

class LiveStreamService:
    """
    Manages RTSP connections and streams annotated frames to WebSocket
    clients.  One RTSP VideoCapture per room is shared across viewers.
    """

    # Class-level active streams (shared across service instances)
    _active_streams: Dict[str, StreamState] = {}
    _lock = threading.Lock()

    # Run face detection only every Nth frame (reduces CPU load dramatically).
    # Cached detections are drawn on every frame for smooth overlays.
    DETECT_EVERY_N: int = 5

    def __init__(self):
        # Lazy-initialized per-instance references (avoid import at module level
        # because ML models are loaded during FastAPI startup).
        self._insight = None
        self._faiss = None
        self._ml_available = False
        self._ml_checked = False

    # ------------------------------------------------------------------
    # Lazy initializers
    # ------------------------------------------------------------------

    def _ensure_ml(self):
        """Lazy-init InsightFace + FAISS (first call only)."""
        if not self._ml_checked:
            try:
                from app.services.ml.insightface_model import insightface_model
                from app.services.ml.faiss_manager import faiss_manager

                if insightface_model.app is not None and faiss_manager.index is not None:
                    self._insight = insightface_model
                    self._faiss = faiss_manager
                    self._ml_available = True
                    logger.info("Live stream: InsightFace + FAISS ready for recognition.")
                else:
                    logger.warning(
                        "Live stream: InsightFace/FAISS not loaded — recognition disabled."
                    )
            except Exception as exc:
                logger.warning(f"Live stream: ML import failed — recognition disabled: {exc}")
            self._ml_checked = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_stream(
        self,
        room_id: str,
        rtsp_url: str,
        viewer_id: str,
    ) -> bool:
        """
        Start (or join) a stream for *room_id*.

        If a capture loop is already running for this room the caller is
        simply added to the viewer set.
        """
        with self._lock:
            if room_id in self._active_streams:
                state = self._active_streams[room_id]
                state.viewers.add(viewer_id)
                logger.info(
                    f"Viewer {viewer_id} joined existing stream for room {room_id} "
                    f"({len(state.viewers)} viewers)"
                )
                return True

            # Create new stream state
            state = StreamState(room_id=room_id, rtsp_url=rtsp_url)
            state.viewers.add(viewer_id)
            self._active_streams[room_id] = state

        logger.info(f"Starting new stream for room {room_id}")

        # Open RTSP capture in a background thread (blocking I/O)
        loop = asyncio.get_event_loop()
        opened = await loop.run_in_executor(None, self._open_capture, state)
        if not opened:
            with self._lock:
                self._active_streams.pop(room_id, None)
            return False

        # Kick off the capture loop as a background asyncio task
        asyncio.ensure_future(self._capture_loop(state))
        return True

    async def stop_stream(self, room_id: str, viewer_id: Optional[str] = None) -> None:
        """
        Remove a viewer.  If no viewers remain, stop the RTSP capture.
        """
        with self._lock:
            state = self._active_streams.get(room_id)
            if state is None:
                return

            if viewer_id is not None:
                state.viewers.discard(viewer_id)
                logger.info(
                    f"Viewer {viewer_id} left stream for room {room_id} "
                    f"({len(state.viewers)} remaining)"
                )
                if state.viewers:
                    return  # other viewers still watching

            # No viewers left -- signal the capture loop to stop
            state.stop_event.set()
            self._active_streams.pop(room_id, None)

        logger.info(f"Stopping stream for room {room_id}")

    def get_latest(self, room_id: str) -> Optional[Tuple[str, List[dict], str, int]]:
        """
        Return the latest pre-computed frame data for *room_id*.

        Returns:
            Tuple of (base64_jpeg, detections_dicts, iso_timestamp, frame_seq)
            or None if no frame available.
        """
        state = self._active_streams.get(room_id)
        if state is None or state.last_b64 is None:
            return None

        ts = datetime.now(timezone.utc).isoformat()
        return state.last_b64, state.last_detections_dicts, ts, state.frame_seq

    def get_active_rooms(self) -> List[str]:
        """Return list of room_ids with active streams."""
        return list(self._active_streams.keys())

    def get_viewer_count(self, room_id: str) -> int:
        """Return number of viewers for a room stream."""
        state = self._active_streams.get(room_id)
        return len(state.viewers) if state else 0

    # ------------------------------------------------------------------
    # Internal: capture loop
    # ------------------------------------------------------------------

    def _open_capture(self, state: StreamState) -> bool:
        """Open cv2.VideoCapture (blocking -- run in executor)."""
        try:
            cap = cv2.VideoCapture(state.rtsp_url)
            if not cap.isOpened():
                logger.error(f"Failed to open RTSP stream: {state.rtsp_url}")
                return False
            # Minimise internal buffer to reduce latency for RTSP
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            state.capture = cap
            state.reconnect_attempts = 0
            logger.info(f"RTSP stream opened: {state.rtsp_url}")
            return True
        except Exception as exc:
            logger.error(f"Error opening RTSP stream {state.rtsp_url}: {exc}")
            return False

    def _reconnect(self, state: StreamState) -> bool:
        """Attempt to reconnect to the RTSP stream (blocking)."""
        if state.capture is not None:
            try:
                state.capture.release()
            except Exception:
                pass
            state.capture = None

        state.reconnect_attempts += 1
        if state.reconnect_attempts > state.max_reconnect_attempts:
            logger.error(
                f"Max reconnect attempts ({state.max_reconnect_attempts}) reached "
                f"for room {state.room_id}"
            )
            return False

        delay = state.reconnect_delay_seconds * state.reconnect_attempts
        logger.warning(
            f"Reconnecting to RTSP stream for room {state.room_id} "
            f"(attempt {state.reconnect_attempts}, delay {delay:.1f}s)"
        )
        time.sleep(delay)
        return self._open_capture(state)

    async def _capture_loop(self, state: StreamState) -> None:
        """
        Continuously read frames from the RTSP capture, process them,
        and store the latest result in ``state``.

        Runs until ``state.stop_event`` is set or max reconnect attempts
        are exhausted.
        """
        loop = asyncio.get_event_loop()
        target_interval = 1.0 / settings.STREAM_FPS

        # Ensure lazy components are initialized
        self._ensure_ml()

        logger.info(
            f"Capture loop started for room {state.room_id} "
            f"(target {settings.STREAM_FPS} FPS, detect every {self.DETECT_EVERY_N} frames)"
        )

        try:
            while not state.stop_event.is_set():
                frame_start = time.monotonic()

                # Read frame in executor (blocking cv2 call).
                # _read_frame drains the RTSP buffer to get the freshest frame.
                success, frame = await loop.run_in_executor(
                    None, self._read_frame, state
                )

                if not success:
                    # Try to reconnect
                    reconnected = await loop.run_in_executor(
                        None, self._reconnect, state
                    )
                    if not reconnected:
                        logger.error(f"Stream ended for room {state.room_id} -- reconnect failed")
                        break
                    continue

                # Process frame in executor.
                # Detection only runs every Nth frame; cached results are drawn
                # on every frame for smooth bounding-box overlays.
                run_detection = (state.frame_count % self.DETECT_EVERY_N == 0)
                jpeg_bytes, detections, b64_str = await loop.run_in_executor(
                    None,
                    self._process_frame,
                    frame,
                    run_detection,
                    state.last_detections,
                )

                # Store result (atomic-ish assignment; readers get a consistent snapshot)
                state.last_jpeg = jpeg_bytes
                state.last_b64 = b64_str
                if run_detection:
                    state.last_detections = detections
                    state.last_detections_dicts = [d.to_dict() for d in detections]
                state.last_frame_time = time.monotonic()
                state.frame_count += 1
                state.frame_seq += 1

                # Throttle to target FPS
                elapsed = time.monotonic() - frame_start
                sleep_time = target_interval - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info(f"Capture loop cancelled for room {state.room_id}")
        except Exception as exc:
            logger.exception(f"Capture loop error for room {state.room_id}: {exc}")
        finally:
            # Release resources
            if state.capture is not None:
                try:
                    state.capture.release()
                except Exception:
                    pass
                state.capture = None
            with self._lock:
                self._active_streams.pop(state.room_id, None)
            logger.info(f"Capture loop ended for room {state.room_id}")

    # ------------------------------------------------------------------
    # Internal: frame-level operations (all synchronous / blocking)
    # ------------------------------------------------------------------

    def _read_frame(self, state: StreamState) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read the freshest frame from the capture device.

        For RTSP streams, grab (discard) buffered frames first so
        we always get the most recent frame, reducing latency.
        """
        if state.capture is None or not state.capture.isOpened():
            return False, None
        try:
            # Drain the RTSP buffer — grab() is fast (no decode).
            # This prevents reading stale buffered frames.
            for _ in range(4):
                if not state.capture.grab():
                    break

            ret, frame = state.capture.read()
            return ret, frame if ret else None
        except Exception as exc:
            logger.error(f"Frame read error for room {state.room_id}: {exc}")
            return False, None

    def _process_frame(
        self,
        frame: np.ndarray,
        run_detection: bool,
        cached_detections: List[Detection],
    ) -> Tuple[bytes, List[Detection], str]:
        """
        Full frame pipeline (synchronous, meant to run in executor):
            1. Resize to stream resolution
            2+3. Optionally detect+recognise faces with InsightFace (only every Nth frame)
            4. Annotate frame with bounding boxes / labels
            5. JPEG-encode
            6. Base64-encode (pre-computed, shared across all viewers)

        Args:
            frame: Raw BGR frame from cv2.VideoCapture
            run_detection: True to run face detection on this frame
            cached_detections: Previous detection results to draw if skipping

        Returns:
            (jpeg_bytes, detections, base64_string)
        """
        # 1. Resize
        frame = cv2.resize(
            frame,
            (settings.STREAM_WIDTH, settings.STREAM_HEIGHT),
            interpolation=cv2.INTER_AREA,
        )

        # 2 & 3. Detect + recognise in one InsightFace call
        if run_detection:
            detections = self._detect_and_recognise(frame) if self._ml_available else []
        else:
            detections = cached_detections

        # 4. Annotate with current (or cached) detections
        annotated = self._annotate_frame(frame, detections)

        # 5. JPEG encode
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, settings.STREAM_QUALITY]
        _, jpeg_buf = cv2.imencode(".jpg", annotated, encode_params)
        jpeg_bytes = jpeg_buf.tobytes()

        # 6. Base64 encode (once — shared across all viewers)
        b64_str = base64.b64encode(jpeg_bytes).decode("ascii")

        return jpeg_bytes, detections, b64_str

    def _detect_and_recognise(self, frame: np.ndarray) -> List[Detection]:
        """
        Run InsightFace detection + ArcFace embedding + FAISS search on one frame.
        Returns Detection list (user_id/similarity populated for matched faces).
        """
        try:
            insight_faces = self._insight.get_faces(frame)
            detections = []
            for face in insight_faces:
                user_id, similarity = None, None
                if self._faiss is not None:
                    matches = self._faiss.search(face.embedding, k=1)
                    if matches:
                        user_id, similarity = matches[0]

                detections.append(Detection(
                    x=face.x,
                    y=face.y,
                    width=face.width,
                    height=face.height,
                    confidence=face.confidence,
                    user_id=user_id,
                    similarity=similarity,
                ))
            return detections
        except Exception as exc:
            logger.error(f"Live stream detect+recognise error: {exc}")
            return []

    def _annotate_frame(
        self,
        frame: np.ndarray,
        detections: List[Detection],
    ) -> np.ndarray:
        """
        Draw bounding boxes and labels onto the frame.

        Returns a copy so the original stays clean for future crops.
        """
        if not detections:
            return frame

        annotated = frame.copy()

        for det in detections:
            # Choose colour: green if recognised, yellow otherwise
            if det.user_id:
                color = (0, 200, 0)  # green (BGR)
            else:
                color = (0, 200, 255)  # yellow (BGR)

            # Bounding box
            cv2.rectangle(
                annotated,
                (det.x, det.y),
                (det.x + det.width, det.y + det.height),
                color,
                2,
            )

            # Label
            parts: List[str] = []
            if det.name:
                parts.append(det.name)
            elif det.student_id:
                parts.append(det.student_id)
            elif det.user_id:
                parts.append(det.user_id[:8])

            if det.similarity is not None:
                parts.append(f"{det.similarity:.2f}")

            if not parts:
                parts.append(f"{det.confidence:.2f}")

            label = " | ".join(parts)
            label_y = max(det.y - 8, 16)

            # Background rectangle for text readability
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(
                annotated,
                (det.x, label_y - th - 4),
                (det.x + tw + 4, label_y + 4),
                color,
                cv2.FILLED,
            )
            cv2.putText(
                annotated,
                label,
                (det.x + 2, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),  # black text on coloured background
                1,
                cv2.LINE_AA,
            )

        return annotated

    # ------------------------------------------------------------------
    # Enrichment helper (requires DB session -- called from router layer)
    # ------------------------------------------------------------------

    @staticmethod
    def enrich_detections(
        detections: List[Detection],
        db,
    ) -> None:
        """
        Populate ``name`` and ``student_id`` on detections that have a
        ``user_id`` but no name yet, by querying the database.
        """
        from app.repositories.user_repository import UserRepository

        user_repo = UserRepository(db)
        # Collect unique user_ids that need resolution
        ids_to_resolve = {
            d.user_id for d in detections
            if d.user_id and not d.name
        }
        if not ids_to_resolve:
            return

        for uid in ids_to_resolve:
            user = user_repo.get_by_id(uid)
            if user is None:
                continue
            for d in detections:
                if d.user_id == uid:
                    d.name = user.full_name
                    d.student_id = user.student_id


# Global singleton
live_stream_service = LiveStreamService()
