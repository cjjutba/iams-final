"""
Recognition Service

Decoupled face recognition pipeline that samples frames from an RTSP stream
at a configurable low FPS (default 1.5), runs MediaPipe face detection, then
batch FaceNet + FAISS recognition on all detected faces.

This runs independently from the HLS video layer, producing lightweight
detection metadata that is pushed to mobile clients via WebSocket.
"""

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import cv2
import numpy as np

from app.config import settings, logger


@dataclass
class Detection:
    """Single face detection/recognition result."""
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
class RecognitionState:
    """Mutable state for a single room's recognition pipeline."""
    room_id: str
    rtsp_url: str
    capture: Optional[cv2.VideoCapture] = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    viewers: Set[str] = field(default_factory=set)
    last_detections: List[Detection] = field(default_factory=list)
    last_detections_dicts: List[dict] = field(default_factory=list)
    last_timestamp: float = 0.0
    update_seq: int = 0
    frame_width: int = 0
    frame_height: int = 0


class RecognitionService:
    """
    Decoupled face recognition pipeline.

    Samples frames from RTSP at RECOGNITION_FPS, runs detection + recognition,
    and stores latest results for the WebSocket push loop to read.
    """

    _active: Dict[str, RecognitionState] = {}
    _lock = threading.Lock()

    def __init__(self):
        self._face_detector = None
        self._detector_initialized = False
        self._facenet = None
        self._faiss = None
        self._ml_available = False
        self._ml_checked = False

    # ------------------------------------------------------------------
    # Lazy initializers (same pattern as live_stream_service)
    # ------------------------------------------------------------------

    def _ensure_detector(self):
        if not self._detector_initialized:
            try:
                from app.services.live_stream_service import _create_face_detector
                self._face_detector = _create_face_detector()
                if self._face_detector is not None:
                    logger.info("Recognition: MediaPipe face detector initialized OK")
                else:
                    logger.error("Recognition: MediaPipe face detector returned None")
            except Exception as exc:
                logger.warning(f"Recognition: MediaPipe init failed: {exc}")
            self._detector_initialized = True

    def _ensure_ml(self):
        if not self._ml_checked:
            try:
                from app.services.ml.face_recognition import facenet_model
                from app.services.ml.faiss_manager import faiss_manager

                if facenet_model.model is not None and faiss_manager.index is not None:
                    self._facenet = facenet_model
                    self._faiss = faiss_manager
                    self._ml_available = True
                    logger.info("Recognition: FaceNet + FAISS available")
                else:
                    logger.warning("Recognition: FaceNet/FAISS not loaded")
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
                logger.info(
                    f"Recognition: viewer {viewer_id} joined room {room_id} "
                    f"({len(state.viewers)} viewers)"
                )
                return True

            state = RecognitionState(room_id=room_id, rtsp_url=rtsp_url)
            state.viewers.add(viewer_id)
            self._active[room_id] = state

        # Open capture in executor
        loop = asyncio.get_event_loop()
        opened = await loop.run_in_executor(None, self._open_capture, state)
        if not opened:
            with self._lock:
                self._active.pop(room_id, None)
            return False

        # Ensure lazy components are initialized
        self._ensure_detector()
        self._ensure_ml()

        # Start recognition loop
        asyncio.ensure_future(self._recognition_loop(state))
        # Mask password in log
        masked_url = rtsp_url.split("@")[-1] if "@" in rtsp_url else rtsp_url
        logger.info(
            f"Recognition: started for room {room_id} at {settings.RECOGNITION_FPS} FPS "
            f"(stream: ...@{masked_url})"
        )
        return True

    async def stop(self, room_id: str, viewer_id: Optional[str] = None) -> None:
        """Remove a viewer. If none remain, stop the recognition pipeline."""
        with self._lock:
            state = self._active.get(room_id)
            if state is None:
                return

            if viewer_id is not None:
                state.viewers.discard(viewer_id)
                logger.info(
                    f"Recognition: viewer {viewer_id} left room {room_id} "
                    f"({len(state.viewers)} remaining)"
                )
                if state.viewers:
                    return

            state.stop_event.set()
            self._active.pop(room_id, None)

        logger.info(f"Recognition: stopped for room {room_id}")

    def get_latest_detections(self, room_id: str) -> Optional[tuple]:
        """
        Return (detections_dicts, update_seq, frame_width, frame_height) or None.
        """
        state = self._active.get(room_id)
        if state is None:
            return None
        return state.last_detections_dicts, state.update_seq, state.frame_width, state.frame_height

    def get_detections_objects(self, room_id: str) -> List[Detection]:
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
            cap = cv2.VideoCapture(state.rtsp_url)
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
                success, frame = await loop.run_in_executor(
                    None, self._read_frame, state
                )

                if success and first_frame and frame is not None:
                    h, w = frame.shape[:2]
                    logger.info(
                        f"Recognition: first frame from RTSP is {w}x{h} "
                        f"(room={state.room_id})"
                    )
                    first_frame = False

                if not success:
                    # Try reconnecting
                    reconnected = await loop.run_in_executor(
                        None, self._reconnect, state
                    )
                    if not reconnected:
                        logger.error(f"Recognition: stream lost for room {state.room_id}")
                        break
                    continue

                # Process frame (detect + recognize)
                detections, fw, fh = await loop.run_in_executor(
                    None, self._process_frame, frame
                )

                # Store results
                state.last_detections = detections
                state.last_detections_dicts = [d.to_dict() for d in detections]
                state.frame_width = fw
                state.frame_height = fh
                state.last_timestamp = time.monotonic()
                state.update_seq += 1

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
                try:
                    state.capture.release()
                except Exception:
                    pass
                state.capture = None
            with self._lock:
                self._active.pop(state.room_id, None)
            logger.info(f"Recognition: loop ended for room {state.room_id}")

    def _read_frame(self, state: RecognitionState):
        """Read the freshest frame (drain buffer first)."""
        if state.capture is None or not state.capture.isOpened():
            return False, None
        try:
            # Drain buffer
            for _ in range(4):
                if not state.capture.grab():
                    break
            ret, frame = state.capture.read()
            return ret, frame if ret else None
        except Exception as exc:
            logger.error(f"Recognition: frame read error: {exc}")
            return False, None

    def _reconnect(self, state: RecognitionState) -> bool:
        """Attempt to reconnect to the RTSP stream."""
        if state.capture is not None:
            try:
                state.capture.release()
            except Exception:
                pass
            state.capture = None

        logger.warning(f"Recognition: reconnecting for room {state.room_id}")
        time.sleep(2.0)
        return self._open_capture(state)

    def _process_frame(self, frame: np.ndarray) -> tuple:
        """
        Full recognition pipeline:
        1. Optionally downscale large frames (cap at RECOGNITION_MAX_DIM)
        2. Detect faces with MediaPipe
        3. Crop faces → batch FaceNet embeddings → batch FAISS search

        Returns (detections, frame_width, frame_height).
        """
        h, w = frame.shape[:2]
        max_dim = max(h, w)
        cap = settings.RECOGNITION_MAX_DIM  # default 1280

        # Only downscale if larger than cap — never upscale
        if max_dim > cap:
            scale = cap / max_dim
            new_w, new_h = int(w * scale), int(h * scale)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            logger.debug(f"Recognition: downscaled {w}x{h} → {new_w}x{new_h}")

        frame_h, frame_w = frame.shape[:2]

        # Detect
        detections = self._detect_faces(frame)
        if not detections:
            return [], frame_w, frame_h

        logger.info(f"Recognition: detected {len(detections)} face(s) in {frame_w}x{frame_h} frame")

        # Recognize (batch)
        if self._ml_available:
            self._recognise_faces_batch(frame, detections)

        return detections, frame_w, frame_h

    _detect_log_counter: int = 0

    def _detect_faces(self, frame: np.ndarray) -> List[Detection]:
        """Run MediaPipe face detection on a BGR frame."""
        if self._face_detector is None:
            self._detect_log_counter += 1
            if self._detect_log_counter <= 3:
                logger.warning("Recognition: face detector is None — skipping detection")
            return []

        try:
            import mediapipe as mp

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = self._face_detector.detect(mp_image)

            detections: List[Detection] = []
            if result.detections:
                for det in result.detections:
                    bbox = det.bounding_box
                    conf = det.categories[0].score if det.categories else 0.0
                    detections.append(
                        Detection(
                            x=max(0, bbox.origin_x),
                            y=max(0, bbox.origin_y),
                            width=max(1, bbox.width),
                            height=max(1, bbox.height),
                            confidence=conf,
                        )
                    )
            return detections
        except Exception as exc:
            logger.error(f"Recognition: detection error: {exc}")
            return []

    def _recognise_faces_batch(
        self,
        frame: np.ndarray,
        detections: List[Detection],
    ) -> None:
        """
        Batch recognition: crop all faces, generate embeddings in a single
        forward pass, then batch FAISS search. Mutates detections in place.
        """
        if self._facenet is None or self._faiss is None:
            return

        h, w = frame.shape[:2]
        face_crops = []
        crop_indices = []  # maps back to detection index

        for i, det in enumerate(detections):
            x1 = max(0, det.x)
            y1 = max(0, det.y)
            x2 = min(w, det.x + det.width)
            y2 = min(h, det.y + det.height)

            if x2 - x1 < 10 or y2 - y1 < 10:
                continue

            face_crop = frame[y1:y2, x1:x2]
            face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
            face_crops.append(face_rgb)
            crop_indices.append(i)

        if not face_crops:
            return

        try:
            # Limit batch size
            max_batch = settings.RECOGNITION_MAX_BATCH_SIZE
            face_crops = face_crops[:max_batch]
            crop_indices = crop_indices[:max_batch]

            # Batch FaceNet embedding (single forward pass)
            embeddings = self._facenet.generate_embeddings_batch(face_crops)

            # Batch FAISS search
            batch_results = self._faiss.search_batch(embeddings, k=1)

            # Map results back to detections
            for idx, results in zip(crop_indices, batch_results):
                if results:
                    user_id, similarity = results[0]
                    detections[idx].user_id = user_id
                    detections[idx].similarity = similarity

        except Exception as exc:
            logger.error(f"Recognition: batch recognition error: {exc}")

    # ------------------------------------------------------------------
    # Enrichment helper (requires DB session — called from router layer)
    # ------------------------------------------------------------------

    @staticmethod
    def enrich_detections(detections: List[Detection], db) -> None:
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
