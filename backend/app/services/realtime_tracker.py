"""
RealtimeTracker — ByteTrack face tracking with cached ArcFace recognition.

Detect every frame, track always, recognize only NEW faces. Once a track ID
is associated with a name, the name sticks until the track is lost or the
re-verify interval elapses.

Performance on M5 MacBook Pro (Apple Silicon):
  SCRFD ~10ms + ByteTrack ~2ms + ArcFace ~8ms (new tracks only) ≈ 15ms/frame
  At 15fps (67ms budget), ~50ms headroom.
"""

import logging
import time
from dataclasses import dataclass, field

import numpy as np
import supervision as sv
from scipy.optimize import linear_sum_assignment

from app.config import settings
from app.services.ml.face_quality import assess_recognition_quality

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TrackIdentity:
    """Cached identity for a tracked face."""

    track_id: int
    user_id: str | None = None
    name: str | None = None
    confidence: float = 0.0
    first_seen: float = 0.0
    last_verified: float = 0.0
    last_seen: float = 0.0
    last_drift_time: float = 0.0  # When embedding drift was last detected
    recognition_status: str = "pending"  # "pending" | "recognized" | "unknown"
    frames_seen: int = 0
    last_embedding: np.ndarray | None = None  # Detect track ID swaps
    embedding_buffer: list = field(default_factory=list)  # Recent quality-passed embeddings (FIFO, max 5)


@dataclass(frozen=True, slots=True)
class TrackResult:
    """Single track in a processed frame."""

    track_id: int
    bbox: list[float]  # [x1, y1, x2, y2] normalized 0-1
    velocity: list[float]  # [vx, vy, vw, vh] normalized units/second (center+size)
    user_id: str | None
    name: str | None
    confidence: float
    status: str  # "recognized" | "unknown" | "pending"
    is_active: bool  # True if matched to a detection this frame


@dataclass(frozen=True, slots=True)
class TrackFrame:
    """Result of processing one frame through the realtime tracker."""

    tracks: list[TrackResult]
    fps: float
    processing_ms: float
    timestamp: float


# ---------------------------------------------------------------------------
# Core tracker
# ---------------------------------------------------------------------------


class RealtimeTracker:
    """ByteTrack-based face tracker with cached ArcFace recognition.

    Args:
        insightface_model: InsightFaceModel instance (has ``app.get(frame)``).
        faiss_manager: FAISSManager instance (has ``search_with_margin()``).
        enrolled_user_ids: Set of enrolled student user_ids for this session.
        name_map: Dict mapping user_id -> display name.
    """

    def __init__(
        self,
        insightface_model,
        faiss_manager,
        enrolled_user_ids: set[str] | None = None,
        name_map: dict[str, str] | None = None,
    ) -> None:
        self._insight = insightface_model
        self._faiss = faiss_manager
        self._enrolled = enrolled_user_ids or set()
        self._name_map = name_map or {}

        # ByteTrack with tuned parameters for face tracking
        self._tracker = sv.ByteTrack(
            track_activation_threshold=0.25,
            lost_track_buffer=int(settings.TRACK_LOST_TIMEOUT * settings.PROCESSING_FPS),
            minimum_matching_threshold=0.8,
            frame_rate=int(settings.PROCESSING_FPS),
        )

        # Identity cache: track_id -> TrackIdentity
        self._identity_cache: dict[int, TrackIdentity] = {}

        # Previous frame bboxes for velocity computation: track_id -> [cx, cy, w, h]
        self._prev_bboxes: dict[int, list[float]] = {}
        self._processing_fps: float = settings.PROCESSING_FPS

        # Adaptive per-session enrollment state: user_id -> {count, last_time}
        self._adaptive_state: dict[str, dict] = {}

        # Frame dimensions (set on first frame)
        self._frame_h: int = 0
        self._frame_w: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, frame: np.ndarray) -> TrackFrame:
        """Process one BGR frame: detect → track → recognize (new only).

        Args:
            frame: BGR numpy array from FrameGrabber.

        Returns:
            TrackFrame with all current tracks and timing info.
        """
        t0 = time.monotonic()
        self._frame_h, self._frame_w = frame.shape[:2]
        now = time.monotonic()

        # 1. SCRFD detection via InsightFace
        raw_faces = self._insight.app.get(frame) if self._insight.app else []
        if not raw_faces:
            self._expire_lost_tracks(now)
            duration_ms = (time.monotonic() - t0) * 1000.0
            return TrackFrame(
                tracks=[],
                fps=1000.0 / max(duration_ms, 0.1),
                processing_ms=duration_ms,
                timestamp=now,
            )

        # 2. Convert InsightFace results to supervision Detections
        bboxes = []
        confidences = []
        embeddings_list = []
        for face in raw_faces:
            x1, y1, x2, y2 = face.bbox.astype(float)
            bboxes.append([x1, y1, x2, y2])
            confidences.append(float(face.det_score))
            embeddings_list.append(face.normed_embedding.copy())

        # Apply NMS to remove duplicate face detections
        bboxes, confidences, embeddings_list = self._nms_faces(bboxes, confidences, embeddings_list)

        # Filter out faces smaller than 0.25% of frame area (noise/ghost detections)
        # 1% was too aggressive — classroom faces at 2-4m are ~1,000-2,500 px² at 896×512,
        # well below the old 4,587 px² cutoff. 0.25% = ~1,147 px² ≈ 34×34 px minimum.
        frame_area = self._frame_w * self._frame_h
        min_face_area = frame_area * 0.0025
        filtered = [
            (b, c, e)
            for b, c, e in zip(bboxes, confidences, embeddings_list)
            if (b[2] - b[0]) * (b[3] - b[1]) >= min_face_area
        ]
        if not filtered:
            self._expire_lost_tracks(now)
            duration_ms = (time.monotonic() - t0) * 1000.0
            return TrackFrame(
                tracks=[],
                fps=1000.0 / max(duration_ms, 0.1),
                processing_ms=duration_ms,
                timestamp=now,
            )
        bboxes, confidences, embeddings_list = zip(*filtered)
        bboxes = list(bboxes)
        confidences = list(confidences)
        embeddings_list = list(embeddings_list)

        det_array = np.array(bboxes, dtype=np.float32)
        conf_array = np.array(confidences, dtype=np.float32)

        detections = sv.Detections(
            xyxy=det_array,
            confidence=conf_array,
        )

        # 3. ByteTrack update → persistent track IDs
        tracked = self._tracker.update_with_detections(detections)

        # 4. Match embeddings to tracked detections by IoU
        track_embeddings = self._match_embeddings_to_tracks(det_array, embeddings_list, tracked)

        # 5. For each track: lookup cache or run ArcFace
        results: list[TrackResult] = []
        active_track_ids: set[int] = set()

        for i, track_id in enumerate(tracked.tracker_id):
            track_id = int(track_id)
            active_track_ids.add(track_id)

            bbox = tracked.xyxy[i]
            embedding = track_embeddings.get(track_id)

            identity = self._get_or_create_identity(track_id, now)
            identity.last_seen = now
            identity.frames_seen += 1

            # Quality gate: check face crop before using embedding for recognition.
            # Bad crops (too small, blurry, extreme lighting) produce noisy embeddings.
            # Skipping costs nothing — the track retries next frame (100ms at 10fps).
            quality_passed = False
            if embedding is not None:
                x1p, y1p, x2p, y2p = bbox.astype(int)
                x1p, y1p = max(0, x1p), max(0, y1p)
                x2p, y2p = min(self._frame_w, x2p), min(self._frame_h, y2p)
                crop = frame[y1p:y2p, x1p:x2p]
                if crop.size > 0:
                    quality_passed, _ = assess_recognition_quality(crop)

            # Accumulate quality-passed embeddings for temporal aggregation.
            # Averaging 3-5 frames of the same tracked face stabilizes match scores.
            if quality_passed and embedding is not None:
                identity.embedding_buffer.append(embedding)
                if len(identity.embedding_buffer) > 5:
                    identity.embedding_buffer.pop(0)

            # Detect track ID swaps: if the face embedding suddenly changes
            # (cosine similarity < 0.5 vs cached embedding), ByteTrack likely
            # swapped this track to a different person. Force re-recognition.
            embedding_drifted = False
            if (
                embedding is not None
                and identity.last_embedding is not None
                and identity.recognition_status == "recognized"
            ):
                sim = float(np.dot(embedding, identity.last_embedding))
                if sim < 0.5:
                    logger.info(
                        "Track %d embedding drift (sim=%.2f), forcing re-recognition",
                        track_id,
                        sim,
                    )
                    identity.recognition_status = "pending"
                    identity.user_id = None
                    identity.name = None
                    identity.confidence = 0.0
                    identity.last_drift_time = now
                    embedding_drifted = True
                    identity.embedding_buffer.clear()

            # Cache current embedding for drift detection
            if embedding is not None:
                identity.last_embedding = embedding

            # Recognize if: new/unknown track or re-verify interval elapsed.
            # Unknown tracks: retry every frame for first 5s (aggressive),
            # then every 2s after that (each frame is a new angle chance).
            if identity.recognition_status == "unknown":
                age = now - identity.first_seen
                retry_interval = 0.0 if age < 5.0 else 2.0
                is_unknown_retry = (now - identity.last_verified) > retry_interval
            else:
                is_unknown_retry = False

            # Use shorter re-verify interval (1s) for 3s after drift detection
            if identity.last_drift_time > 0 and (now - identity.last_drift_time) < 3.0:
                reverify_interval = 1.0
            else:
                reverify_interval = settings.REVERIFY_INTERVAL

            needs_recognition = (
                identity.recognition_status == "pending"
                or is_unknown_retry
                or embedding_drifted
                or (now - identity.last_verified) > reverify_interval
            )

            if needs_recognition and quality_passed and embedding is not None:
                self._recognize_track(identity, embedding, now)

            # Normalize bbox to 0-1
            norm_bbox = [
                float(bbox[0]) / self._frame_w,
                float(bbox[1]) / self._frame_h,
                float(bbox[2]) / self._frame_w,
                float(bbox[3]) / self._frame_h,
            ]

            # Compute velocity in center+size space (normalized units/second)
            cx = (norm_bbox[0] + norm_bbox[2]) / 2
            cy = (norm_bbox[1] + norm_bbox[3]) / 2
            w = norm_bbox[2] - norm_bbox[0]
            h = norm_bbox[3] - norm_bbox[1]
            prev = self._prev_bboxes.get(track_id)
            if prev is not None:
                pcx, pcy, pw, ph = prev
                fps = self._processing_fps
                velocity = [
                    (cx - pcx) * fps,
                    (cy - pcy) * fps,
                    (w - pw) * fps,
                    (h - ph) * fps,
                ]
            else:
                velocity = [0.0, 0.0, 0.0, 0.0]
            self._prev_bboxes[track_id] = [cx, cy, w, h]

            results.append(
                TrackResult(
                    track_id=track_id,
                    bbox=norm_bbox,
                    velocity=velocity,
                    user_id=identity.user_id,
                    name=identity.name,
                    confidence=identity.confidence,
                    status=identity.recognition_status,
                    is_active=True,
                )
            )

        # 6. Deduplicate by user_id — keep highest confidence per user
        seen_users: dict[str, int] = {}
        deduped_results: list[TrackResult] = []
        for r in results:
            if r.user_id and r.user_id in seen_users:
                existing_idx = seen_users[r.user_id]
                if r.confidence > deduped_results[existing_idx].confidence:
                    deduped_results[existing_idx] = r
                continue
            if r.user_id:
                seen_users[r.user_id] = len(deduped_results)
            deduped_results.append(r)
        results = deduped_results

        # 6b. Deduplicate unknown tracks by bbox IoU — same face can get
        # multiple track IDs from ByteTrack when detection is noisy.
        unknown_tracks = [r for r in results if r.user_id is None]
        known_tracks = [r for r in results if r.user_id is not None]
        deduped_unknown: list[TrackResult] = []
        for track in unknown_tracks:
            is_dup = False
            for j, existing in enumerate(deduped_unknown):
                iou = self._compute_iou_norm(track.bbox, existing.bbox)
                if iou > 0.3:
                    if track.confidence > existing.confidence:
                        deduped_unknown[j] = track
                    is_dup = True
                    break
            if not is_dup:
                deduped_unknown.append(track)
        results = known_tracks + deduped_unknown

        # 7. Expire lost tracks
        self._expire_lost_tracks(now, active_track_ids)

        duration_ms = (time.monotonic() - t0) * 1000.0

        return TrackFrame(
            tracks=results,
            fps=1000.0 / max(duration_ms, 0.1),
            processing_ms=duration_ms,
            timestamp=now,
        )

    def get_recognized_user_ids(self) -> set[str]:
        """Return set of currently recognized user_ids across all active tracks."""
        return {identity.user_id for identity in self._identity_cache.values() if identity.user_id is not None}

    def reset(self) -> None:
        """Clear all tracking state."""
        self._tracker.reset()
        self._identity_cache.clear()
        self._prev_bboxes.clear()
        self._adaptive_state.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_or_create_identity(self, track_id: int, now: float) -> TrackIdentity:
        """Get existing identity or create a new pending one."""
        if track_id not in self._identity_cache:
            self._identity_cache[track_id] = TrackIdentity(
                track_id=track_id,
                first_seen=now,
                last_seen=now,
            )
        return self._identity_cache[track_id]

    def _resolve_name(self, user_id: str) -> str:
        """Resolve display name for a user_id, with DB fallback for new registrations."""
        name = self._name_map.get(user_id)
        if name:
            return name

        # User registered during active session — not in static name_map.
        # Look up from DB and cache for future frames.
        try:
            from app.database import SessionLocal
            from app.models.user import User

            db = SessionLocal()
            try:
                user = db.query(User.first_name).filter(User.id == user_id).first()
                if user:
                    self._name_map[user_id] = user.first_name
                    return user.first_name
            finally:
                db.close()
        except Exception:
            logger.debug("DB lookup failed for user %s", user_id)

        return "Unknown"

    def _recognize_track(self, identity: TrackIdentity, embedding: np.ndarray, now: float) -> None:
        """Run ArcFace + FAISS search for a track and cache the result.

        Uses temporal embedding aggregation when 3+ quality-passed embeddings
        are available in the buffer. Averaging across frames produces a more
        stable embedding, boosting match scores by ~0.05-0.10.
        """
        if len(identity.embedding_buffer) >= 3:
            avg = np.mean(identity.embedding_buffer, axis=0)
            avg = avg / np.linalg.norm(avg)
            search_embedding = avg
        else:
            search_embedding = embedding

        result = self._faiss.search_with_margin(search_embedding)

        user_id = result.get("user_id")
        confidence = result.get("confidence", 0.0)
        is_ambiguous = result.get("is_ambiguous", False)

        logger.info(
            "[TRACK-SCORE] track=%d user=%s confidence=%.4f ambiguous=%s status=%s",
            identity.track_id,
            user_id[:8] if user_id else "NONE",
            confidence, is_ambiguous,
            "ACCEPT" if (user_id and not is_ambiguous) else "REJECT",
        )

        if user_id is not None and not is_ambiguous:
            identity.user_id = user_id
            identity.confidence = confidence
            identity.name = self._resolve_name(user_id)
            identity.recognition_status = "recognized"
            logger.info(
                "Track %d recognized: %s (%.3f)",
                identity.track_id,
                identity.name,
                confidence,
            )
            # Adaptive per-session enrollment: store high-confidence CCTV
            # embeddings in FAISS (RAM only) to boost future matches.
            if (
                settings.ADAPTIVE_ENROLL_ENABLED
                and confidence >= settings.ADAPTIVE_ENROLL_MIN_CONFIDENCE
            ):
                self._try_adaptive_enroll(user_id, embedding, now)
        elif identity.recognition_status == "recognized":
            # Already recognized — don't downgrade on a single bad frame.
            # Only log the failed re-verify; keep the existing identity.
            logger.debug(
                "Track %d re-verify missed (score=%.3f), keeping %s",
                identity.track_id,
                confidence,
                identity.name,
            )
        else:
            identity.recognition_status = "unknown"
            identity.confidence = confidence
            logger.debug(
                "Track %d unknown (score=%.3f, user=%s, ambiguous=%s)",
                identity.track_id,
                confidence,
                user_id,
                is_ambiguous,
            )

        identity.last_verified = now

    def _try_adaptive_enroll(self, user_id: str, embedding: np.ndarray, now: float) -> None:
        """Store a high-confidence CCTV embedding in FAISS (volatile, RAM only).

        Closes the phone→CCTV domain gap within the current session by adding
        real camera embeddings for students who are confidently recognized.
        Limited to ADAPTIVE_ENROLL_MAX_PER_USER per user with a cooldown.
        """
        state = self._adaptive_state.get(user_id, {"count": 0, "last_time": 0.0})
        if state["count"] >= settings.ADAPTIVE_ENROLL_MAX_PER_USER:
            return
        if (now - state["last_time"]) < settings.ADAPTIVE_ENROLL_COOLDOWN:
            return

        emb = embedding / np.linalg.norm(embedding)
        self._faiss.add_adaptive(emb.astype(np.float32), user_id)
        state["count"] += 1
        state["last_time"] = now
        self._adaptive_state[user_id] = state
        logger.info(
            "Adaptive enroll: user=%s count=%d",
            user_id[:8], state["count"],
        )

    def _match_embeddings_to_tracks(
        self,
        det_bboxes: np.ndarray,
        embeddings: list[np.ndarray],
        tracked: sv.Detections,
    ) -> dict[int, np.ndarray]:
        """Match InsightFace embeddings to ByteTrack tracks by IoU.

        Uses the Hungarian algorithm for optimal exclusive 1:1 assignment.
        This prevents two tracks from claiming the same embedding, which
        was a root cause of name swaps at scale.

        Returns:
            Dict mapping track_id -> embedding for matched tracks.
        """
        if len(tracked) == 0 or len(det_bboxes) == 0:
            return {}

        n_tracks = len(tracked)
        n_dets = len(det_bboxes)

        # Build IoU cost matrix [n_tracks x n_dets]
        iou_matrix = np.zeros((n_tracks, n_dets), dtype=np.float64)
        for i in range(n_tracks):
            for j in range(n_dets):
                iou_matrix[i, j] = self._compute_iou(tracked.xyxy[i], det_bboxes[j])

        # Hungarian algorithm: minimize cost → negate IoU to maximize it
        row_indices, col_indices = linear_sum_assignment(-iou_matrix)

        result: dict[int, np.ndarray] = {}
        for row, col in zip(row_indices, col_indices):
            if iou_matrix[row, col] > 0.3:
                track_id = int(tracked.tracker_id[row])
                result[track_id] = embeddings[col]

        return result

    @staticmethod
    def _compute_iou(box_a: np.ndarray, box_b: np.ndarray) -> float:
        """Compute IoU between two [x1, y1, x2, y2] boxes."""
        x1 = max(box_a[0], box_b[0])
        y1 = max(box_a[1], box_b[1])
        x2 = min(box_a[2], box_b[2])
        y2 = min(box_a[3], box_b[3])

        inter = max(0, x2 - x1) * max(0, y2 - y1)
        if inter == 0:
            return 0.0

        area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
        area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
        union = area_a + area_b - inter

        return float(inter / union) if union > 0 else 0.0

    @staticmethod
    def _compute_iou_norm(box_a: list[float], box_b: list[float]) -> float:
        """Compute IoU between two normalized [x1, y1, x2, y2] bboxes."""
        x1 = max(box_a[0], box_b[0])
        y1 = max(box_a[1], box_b[1])
        x2 = min(box_a[2], box_b[2])
        y2 = min(box_a[3], box_b[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
        area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _nms_faces(bboxes, confidences, embeddings, iou_threshold=0.5):
        """Remove overlapping face detections (non-max suppression)."""
        if len(bboxes) <= 1:
            return bboxes, confidences, embeddings

        indices = np.argsort(confidences)[::-1]  # Sort by confidence descending
        keep = []

        while len(indices) > 0:
            i = indices[0]
            keep.append(i)
            if len(indices) == 1:
                break

            remaining = indices[1:]
            ious = np.array([RealtimeTracker._compute_iou(bboxes[i], bboxes[j]) for j in remaining])
            indices = remaining[ious <= iou_threshold]

        return (
            [bboxes[i] for i in keep],
            [confidences[i] for i in keep],
            [embeddings[i] for i in keep],
        )

    def _expire_lost_tracks(self, now: float, active_ids: set[int] | None = None) -> None:
        """Remove tracks that have been lost for > TRACK_LOST_TIMEOUT."""
        expired = []
        for track_id, identity in self._identity_cache.items():
            if active_ids is not None and track_id in active_ids:
                continue
            if (now - identity.last_seen) > settings.TRACK_LOST_TIMEOUT:
                expired.append(track_id)

        for track_id in expired:
            identity = self._identity_cache.pop(track_id)
            self._prev_bboxes.pop(track_id, None)
            if identity.recognition_status == "recognized":
                logger.debug(
                    "Track %d expired: %s (was visible %.1fs)",
                    track_id,
                    identity.name,
                    now - identity.first_seen,
                )
