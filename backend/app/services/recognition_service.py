"""
Recognition Service

Samples RTSP frames at a configurable FPS (default 2.0), runs InsightFace
(SCRFD detection + ArcFace embedding) on each frame, then performs FAISS
nearest-neighbor search to identify detected faces.

This runs independently from the HLS video layer, producing lightweight
detection metadata that is pushed to mobile clients via WebSocket.
"""

import asyncio
import contextlib
import threading
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from app.config import logger, settings



@dataclass
class Detection:
    """Single face detection/recognition result."""

    x: int
    y: int
    width: int
    height: int
    confidence: float
    user_id: str | None = None
    student_id: str | None = None
    name: str | None = None
    similarity: float | None = None

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
class RecognitionState:
    """Mutable state for a single room's recognition pipeline."""

    room_id: str
    rtsp_url: str
    capture: cv2.VideoCapture | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    viewers: set[str] = field(default_factory=set)
    last_detections: list[Detection] = field(default_factory=list)
    last_detections_dicts: list[dict] = field(default_factory=list)
    last_timestamp: float = 0.0
    update_seq: int = 0
    frame_width: int = 0
    frame_height: int = 0
    reconnect_backoff: float = 0.0  # seconds to sleep before next reconnect (exponential)
    frame_provider: object | None = None  # callable returning np.ndarray | None


class RecognitionService:
    """
    Decoupled face recognition pipeline.

    Samples frames from RTSP at RECOGNITION_FPS, runs detection + recognition,
    and stores latest results for the WebSocket push loop to read.
    """

    _active: dict[str, RecognitionState] = {}
    _lock = threading.Lock()
    _BACKOFF_BASE: float = 2.0
    _BACKOFF_MAX: float = 30.0

    def __init__(self):
        self._insight = None
        self._faiss = None
        self._ml_available = False
        self._ml_checked = False

    # ------------------------------------------------------------------
    # Lazy initializers
    # ------------------------------------------------------------------

    def _ensure_ml(self):
        if not self._ml_checked:
            try:
                from app.services.ml.faiss_manager import faiss_manager
                from app.services.ml.insightface_model import insightface_model

                if insightface_model.app is not None and faiss_manager.index is not None:
                    self._insight = insightface_model
                    self._faiss = faiss_manager
                    self._ml_available = True
                    logger.info(
                        "Recognition: InsightFace + FAISS available "
                        "(index=%d vectors, user_map=%d entries)",
                        faiss_manager.index.ntotal,
                        len(faiss_manager.user_map),
                    )
                else:
                    logger.warning("Recognition: InsightFace/FAISS not loaded")
            except Exception as exc:
                logger.warning(f"Recognition: ML import failed: {exc}")
            self._ml_checked = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self, room_id: str, rtsp_url: str, viewer_id: str) -> bool:
        """Start (or join) the recognition pipeline for a room."""
        with self._lock:
            if room_id in self._active:
                state = self._active[room_id]
                state.viewers.add(viewer_id)
                logger.info(f"Recognition: viewer {viewer_id} joined room {room_id} ({len(state.viewers)} viewers)")
                return True

            state = RecognitionState(room_id=room_id, rtsp_url=rtsp_url)
            state.viewers.add(viewer_id)
            self._active[room_id] = state

        # Ensure lazy components are initialized
        self._ensure_ml()

        # Open capture in executor (skip if frame provider is set)
        if state.frame_provider is None:
            loop = asyncio.get_event_loop()
            opened = await loop.run_in_executor(None, self._open_capture, state)
            if not opened:
                with self._lock:
                    self._active.pop(room_id, None)
                return False

        # Start recognition loop
        asyncio.ensure_future(self._recognition_loop(state))
        # Mask password in log
        masked_url = rtsp_url.split("@")[-1] if "@" in rtsp_url else rtsp_url
        logger.info(
            f"Recognition: started for room {room_id} at {settings.RECOGNITION_FPS} FPS (stream: ...@{masked_url})"
        )
        return True

    async def stop(self, room_id: str, viewer_id: str | None = None) -> None:
        """Remove a viewer. If none remain, stop the recognition pipeline."""
        with self._lock:
            state = self._active.get(room_id)
            if state is None:
                return

            if viewer_id is not None:
                state.viewers.discard(viewer_id)
                logger.info(f"Recognition: viewer {viewer_id} left room {room_id} ({len(state.viewers)} remaining)")
                if state.viewers:
                    return

            state.stop_event.set()
            self._active.pop(room_id, None)

        logger.info(f"Recognition: stopped for room {room_id}")

    def get_latest_detections(self, room_id: str) -> tuple | None:
        """
        Return (detections_dicts, update_seq, frame_width, frame_height) or None.
        """
        state = self._active.get(room_id)
        if state is None:
            return None
        return state.last_detections_dicts, state.update_seq, state.frame_width, state.frame_height

    def get_detections_objects(self, room_id: str) -> list[Detection]:
        """Return the raw Detection objects (for name enrichment)."""
        state = self._active.get(room_id)
        return state.last_detections if state else []

    async def cleanup_all(self) -> None:
        """Stop all recognition pipelines (app shutdown)."""
        for room_id in list(self._active.keys()):
            await self.stop(room_id)
        logger.info("Recognition: all pipelines stopped")

    # ------------------------------------------------------------------
    # Internal: capture + recognition loop
    # ------------------------------------------------------------------

    def _open_capture(self, state: RecognitionState) -> bool:
        """Open a separate RTSP capture for recognition sampling."""
        try:
            import os

            # Suppress non-fatal h264 decode warnings (cabac errors, MB decode
            # failures) that flood the console but don't affect pipeline health.
            os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "error"

            # Reduce RTSP connect timeout from default 30s to 5s.
            # The stream may not be available yet (RPi still starting),
            # and the recognition loop will retry with backoff anyway.
            prev = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS", "")
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                "rtsp_transport;tcp|stimeout;5000000"
                "|err_detect;ignore_err"
                "|fflags;discardcorrupt"
            )
            cap = cv2.VideoCapture(state.rtsp_url, cv2.CAP_FFMPEG)
            # Restore previous env var
            if prev:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = prev
            else:
                os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)

            if not cap.isOpened():
                logger.error(f"Recognition: failed to open RTSP: {state.rtsp_url}")
                return False
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            state.capture = cap
            return True
        except Exception as exc:
            logger.error(f"Recognition: capture open error: {exc}")
            return False

    async def _recognition_loop(self, state: RecognitionState) -> None:
        """
        Continuously sample frames and run detection + recognition.
        """
        loop = asyncio.get_event_loop()
        target_interval = 1.0 / settings.RECOGNITION_FPS
        first_frame = True

        try:
            while not state.stop_event.is_set():
                frame_start = time.monotonic()

                # Read freshest frame
                success, frame = await loop.run_in_executor(None, self._read_frame, state)

                if success and first_frame and frame is not None:
                    h, w = frame.shape[:2]
                    logger.info(f"Recognition: first frame from RTSP is {w}x{h} (room={state.room_id})")
                    first_frame = False

                if not success:
                    # Try reconnecting
                    reconnected = await loop.run_in_executor(None, self._reconnect, state)
                    if not reconnected:
                        logger.error(f"Recognition: stream lost for room {state.room_id}")
                        break
                    continue

                # Skip corrupted / unusable frames (stream is alive but frame is bad)
                if frame is None:
                    await asyncio.sleep(target_interval * 0.5)
                    continue

                # Process frame (detect + recognize)
                detections, fw, fh = await loop.run_in_executor(None, self._process_frame, frame)

                # Store results
                state.last_detections = detections
                state.last_detections_dicts = [d.to_dict() for d in detections]
                state.frame_width = fw
                state.frame_height = fh
                state.last_timestamp = time.monotonic()
                state.update_seq += 1

                # Identity push is handled by the video pipeline (which enriches
                # names via DB cache before compositing). No duplicate push here.

                # Throttle to target FPS
                elapsed = time.monotonic() - frame_start
                sleep_time = target_interval - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info(f"Recognition: loop cancelled for room {state.room_id}")
        except Exception as exc:
            logger.exception(f"Recognition: loop error for room {state.room_id}: {exc}")
        finally:
            if state.capture is not None:
                with contextlib.suppress(Exception):
                    state.capture.release()
                state.capture = None
            with self._lock:
                self._active.pop(state.room_id, None)
            logger.info(f"Recognition: loop ended for room {state.room_id}")

    def _read_frame(self, state: RecognitionState):
        """Read the freshest frame (from provider or RTSP capture)."""
        # Try frame provider first (local camera mode)
        if state.frame_provider is not None:
            frame = state.frame_provider()
            if frame is not None:
                return True, frame
            return True, None  # Provider exists but no frame yet

        # Original RTSP capture logic follows...
        if state.capture is None or not state.capture.isOpened():
            return False, None
        try:
            # Drain buffer — grab without decode to reach the latest frame
            for _ in range(4):
                if not state.capture.grab():
                    break
            ret, frame = state.capture.read()
            if not ret or frame is None:
                return False, None
            # Quick corruption check: if frame is nearly all black or all
            # one colour it's likely a decode artefact — skip it.
            mean_val = frame.mean()
            if mean_val < 3.0 or mean_val > 252.0:
                return True, None  # signal success (stream alive) but no usable frame
            return True, frame
        except Exception as exc:
            logger.error(f"Recognition: frame read error: {exc}")
            return False, None

    def _reconnect(self, state: RecognitionState) -> bool:
        """Attempt to reconnect using exponential backoff."""
        if state.capture is not None:
            with contextlib.suppress(Exception):
                state.capture.release()
            state.capture = None

        # Determine delay for this attempt
        delay = state.reconnect_backoff if state.reconnect_backoff > 0 else self._BACKOFF_BASE
        delay = min(delay, self._BACKOFF_MAX)

        logger.warning(f"Recognition: reconnecting for room {state.room_id} (backoff={delay:.1f}s)")
        time.sleep(delay)

        success = self._open_capture(state)
        if success:
            state.reconnect_backoff = 0.0
            logger.info(f"Recognition: reconnected for room {state.room_id}")
        else:
            # Double backoff for next attempt, capped at max
            next_backoff = delay * 2.0 if state.reconnect_backoff > 0 else delay
            state.reconnect_backoff = min(next_backoff, self._BACKOFF_MAX)
        return success

    def _process_frame(self, frame: np.ndarray) -> tuple:
        """
        Full recognition pipeline:
        1. Optionally downscale large frames (cap at RECOGNITION_MAX_DIM)
        2+3. InsightFace detect + ArcFace embed + FAISS search in one call

        Returns (detections, frame_width, frame_height).
        """
        return self._process_frame_ml(frame)

    # ------------------------------------------------------------------
    # Face deduplication (IoU-based NMS)
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_iou(a, b) -> float:
        """Compute Intersection over Union between two DetectedFace objects."""
        ax1, ay1 = a.x, a.y
        ax2, ay2 = a.x + a.width, a.y + a.height
        bx1, by1 = b.x, b.y
        bx2, by2 = b.x + b.width, b.y + b.height

        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)

        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        if inter == 0:
            return 0.0

        area_a = a.width * a.height
        area_b = b.width * b.height
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    @classmethod
    def _deduplicate_faces(cls, faces, iou_threshold: float = 0.3):
        """
        Remove overlapping face detections using Non-Maximum Suppression.

        When two faces overlap with IoU > threshold, keep the one with
        higher detection confidence. This prevents the same person from
        being detected multiple times by SCRFD's multi-scale anchors.
        """
        if len(faces) <= 1:
            return faces

        # Sort by confidence descending — higher confidence faces are kept first
        sorted_faces = sorted(faces, key=lambda f: f.confidence, reverse=True)
        keep = []

        for face in sorted_faces:
            is_duplicate = False
            for kept in keep:
                if cls._compute_iou(face, kept) > iou_threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                keep.append(face)

        if len(keep) < len(faces):
            logger.debug(
                f"Recognition: deduplicated {len(faces)} -> {len(keep)} faces "
                f"(removed {len(faces) - len(keep)} overlapping)"
            )

        return keep

    def _process_frame_ml(self, frame: np.ndarray) -> tuple:
        """
        Run InsightFace detection + recognition on one frame.
        Returns (detections, frame_width, frame_height).
        """
        h, w = frame.shape[:2]
        max_dim = max(h, w)
        cap = settings.RECOGNITION_MAX_DIM

        if max_dim > cap:
            scale = cap / max_dim
            new_w, new_h = int(w * scale), int(h * scale)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

        frame_h, frame_w = int(frame.shape[0]), int(frame.shape[1])

        if not self._ml_available:
            return [], frame_w, frame_h

        try:
            insight_faces = self._insight.get_faces(frame)
            if not insight_faces:
                return [], frame_w, frame_h

            # Deduplicate overlapping detections from SCRFD multi-scale anchors
            insight_faces = self._deduplicate_faces(insight_faces)

            # Filter low-confidence detections (SCRFD false positives at
            # CCTV angles/distances). 0.5 is the InsightFace default but
            # CCTV views produce many sub-0.5 false positives on edges,
            # watermarks, and high-contrast objects.
            insight_faces = [f for f in insight_faces if f.confidence >= 0.5]

            detections = []
            for face in insight_faces:
                user_id, similarity = None, None
                if self._faiss is not None:
                    result = self._faiss.search_with_margin(face.embedding)
                    logger.info(
                        "FAISS search: user=%s conf=%.3f ambiguous=%s det_conf=%.2f bbox=[%d,%d,%d,%d]",
                        result.get("user_id", "None"),
                        result.get("confidence", 0),
                        result.get("is_ambiguous"),
                        face.confidence,
                        face.x, face.y, face.width, face.height,
                    )
                    if result["user_id"] is not None and not result["is_ambiguous"]:
                        user_id = result["user_id"]
                        similarity = result["confidence"]

                # Record similarity for re-enrollment monitoring
                if user_id and similarity is not None and settings.REENROLL_CHECK_ENABLED:
                    try:
                        from app.services.reenrollment_service import reenrollment_monitor

                        needs_reenroll = reenrollment_monitor.record_similarity(user_id, similarity)
                        if needs_reenroll:
                            self._queue_reenroll_notification(user_id)
                    except Exception:
                        pass  # Non-critical

                detections.append(
                    Detection(
                        x=face.x,
                        y=face.y,
                        width=face.width,
                        height=face.height,
                        confidence=face.confidence,
                        user_id=user_id,
                        similarity=similarity,
                    )
                )
            return detections, frame_w, frame_h

        except Exception as exc:
            logger.error(f"Recognition: InsightFace error: {exc}")
            return [], frame_w, frame_h

    # ------------------------------------------------------------------
    # Re-enrollment notification helper
    # ------------------------------------------------------------------

    def _queue_reenroll_notification(self, user_id: str) -> None:
        """Create a re-enrollment notification for a user (fire-and-forget)."""
        try:
            from app.database import SessionLocal
            from app.routers.websocket import manager as ws_manager
            from app.services.notification_service import NotificationService

            db = SessionLocal()
            try:
                svc = NotificationService(ws_manager, db)
                svc.create_persisted_notification(
                    user_id=user_id,
                    title="Face Re-registration Recommended",
                    message=(
                        "Your face recognition accuracy has decreased. "
                        "Please re-register your face for better attendance tracking."
                    ),
                    notification_type="reenrollment",
                    data={"action": "reenroll"},
                )
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Failed to create re-enrollment notification: {e}")

    # ------------------------------------------------------------------
    # Enrichment helper (requires DB session — called from router layer)
    # ------------------------------------------------------------------

    @staticmethod
    def enrich_detections(detections: list[Detection], db) -> None:
        """Populate name/student_id on detections that have a user_id."""
        from app.repositories.user_repository import UserRepository

        user_repo = UserRepository(db)
        ids_to_resolve = {d.user_id for d in detections if d.user_id and not d.name}

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
recognition_service = RecognitionService()
