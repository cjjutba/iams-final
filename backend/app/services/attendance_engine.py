"""
AttendanceScanEngine — stateless frame scan with SCRFD + ArcFace.

Pure function: frame in -> scan results out.

Takes a single frame from a FrameGrabber, runs SCRFD face detection via
InsightFace, filters by detection confidence, runs ArcFace recognition
via FAISS search_with_margin for each surviving face, and returns a
ScanResult dataclass.

This module does NOT manage sessions, miss counters, or DB writes.
The caller (presence_service) handles all business logic.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RecognizedFace:
    """A face that was detected and matched to a known user."""

    user_id: str
    confidence: float
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2) from InsightFace
    det_score: float


@dataclass(frozen=True, slots=True)
class UnrecognizedFace:
    """A face that was detected but not matched (or ambiguous)."""

    bbox: tuple[int, int, int, int]
    det_score: float
    best_confidence: float


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Result of a single scan_frame() call."""

    detected_faces: int
    recognized: list[RecognizedFace]
    unrecognized: list[UnrecognizedFace]
    scan_duration_ms: float


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AttendanceScanEngine:
    """Stateless scan engine: frame in -> ScanResult out.

    Constructor args:
        frame_grabber:    Object with a ``grab() -> Optional[np.ndarray]`` method.
        insightface_model: InsightFaceModel instance (has ``app.get(frame)``).
        faiss_manager:    FAISSManager instance (has ``search_with_margin()``).
        detection_threshold:  Minimum SCRFD det_score to keep a face (default 0.5).
        recognition_threshold: Minimum cosine similarity for FAISS match (default 0.45).
        recognition_margin:   Min gap between top-1 and top-2 FAISS scores (default 0.1).
    """

    def __init__(
        self,
        *,
        frame_grabber,
        insightface_model,
        faiss_manager,
        detection_threshold: float = 0.5,
        recognition_threshold: float = 0.45,
        recognition_margin: float = 0.1,
    ) -> None:
        self._grabber = frame_grabber
        self._insight = insightface_model
        self._faiss = faiss_manager
        self._det_thresh = detection_threshold
        self._rec_thresh = recognition_threshold
        self._rec_margin = recognition_margin

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_frame(self) -> Optional[ScanResult]:
        """Grab one frame, detect faces, recognise each one.

        Returns:
            ScanResult with detection/recognition results, or None if no
            frame is available from the grabber.
        """
        t0 = time.monotonic()

        frame = self._grabber.grab()
        if frame is None:
            return None

        # Run SCRFD detection + ArcFace embedding in one InsightFace call
        raw_faces = self._insight.app.get(frame)
        if not raw_faces:
            duration_ms = (time.monotonic() - t0) * 1000.0
            return ScanResult(
                detected_faces=0,
                recognized=[],
                unrecognized=[],
                scan_duration_ms=duration_ms,
            )

        # Filter low-confidence detections
        faces = [f for f in raw_faces if f.det_score >= self._det_thresh]

        recognized: list[RecognizedFace] = []
        unrecognized: list[UnrecognizedFace] = []

        for face in faces:
            bbox = tuple(int(v) for v in face.bbox.astype(int).tolist())

            result = self._faiss.search_with_margin(
                face.normed_embedding,
                threshold=self._rec_thresh,
                margin=self._rec_margin,
            )

            user_id = result.get("user_id")
            confidence = result.get("confidence", 0.0)
            is_ambiguous = result.get("is_ambiguous", False)

            print(
                f"[FAISS] det_score={face.det_score:.2f}, sim={confidence:.4f}, "
                f"user={user_id}, ambiguous={is_ambiguous}, thresh={self._rec_thresh}"
            )

            if user_id is not None and not is_ambiguous:
                recognized.append(
                    RecognizedFace(
                        user_id=user_id,
                        confidence=confidence,
                        bbox=bbox,
                        det_score=float(face.det_score),
                    )
                )
            else:
                unrecognized.append(
                    UnrecognizedFace(
                        bbox=bbox,
                        det_score=float(face.det_score),
                        best_confidence=confidence,
                    )
                )

        duration_ms = (time.monotonic() - t0) * 1000.0

        return ScanResult(
            detected_faces=len(faces),
            recognized=recognized,
            unrecognized=unrecognized,
            scan_duration_ms=duration_ms,
        )
