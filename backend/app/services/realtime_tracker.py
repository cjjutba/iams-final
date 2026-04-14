"""
RealtimeTracker — ByteTrack face tracking with cached ArcFace recognition.

Detect every frame, track always, recognize only NEW faces. Once a track ID
is associated with a name, the name sticks until the track is lost or the
re-verify interval elapses.

Scalability features:
  - Batch FAISS search: all pending recognitions in one call
  - Staggered re-verification: max N re-verifies per frame to avoid storms
  - Static face filter: stops re-processing faces with zero movement (posters)
  - Quality gate: skips blurry/dark/tiny crops before FAISS search
  - Temporal embedding aggregation: averages 3-5 frames for stable matching

Performance on M5 MacBook Pro (Apple Silicon):
  SCRFD ~10ms + ByteTrack ~2ms + ArcFace ~8ms (new tracks only) ≈ 15ms/frame
  At 15fps (67ms budget), ~50ms headroom.
"""

import logging
import random
import time
from dataclasses import dataclass, field

import numpy as np
import supervision as sv
from scipy.optimize import linear_sum_assignment

from app.config import settings
from app.services.ml.face_quality import assess_recognition_quality

logger = logging.getLogger(__name__)

# Maximum re-verifications per frame to prevent storms with 50+ faces.
# New/pending tracks are always recognized immediately (no limit).
MAX_REVERIFIES_PER_FRAME = 5

# Static face detection: if a track's bbox center moves less than this
# (normalized units) over STATIC_WINDOW_SECONDS, treat it as a static
# image (poster, portrait) and stop re-processing it.
STATIC_MOVEMENT_THRESHOLD = 0.01  # ~1% of frame dimension
STATIC_WINDOW_SECONDS = 8.0


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
    is_static: bool = False  # True = likely a poster/portrait, skip recognition
    first_center: tuple[float, float] | None = None  # Initial bbox center (normalized)
    last_bbox: list[float] | None = None  # Last normalized bbox [x1, y1, x2, y2] for coasting


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

    # Global adaptive enrollment state shared across all tracker instances.
    # Prevents the cap from resetting when a new session creates a new tracker.
    _global_adaptive_state: dict[str, dict] = {}

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

        # 5. For each track: quality gate, embedding buffer, drift detection,
        #    and collect candidates for batch recognition.
        results: list[TrackResult] = []
        active_track_ids: set[int] = set()
        # Tracks that need recognition: [(identity, search_embedding)]
        pending_recognitions: list[tuple[TrackIdentity, np.ndarray]] = []
        reverify_count = 0

        for i, track_id in enumerate(tracked.tracker_id):
            track_id = int(track_id)
            active_track_ids.add(track_id)

            bbox = tracked.xyxy[i]
            embedding = track_embeddings.get(track_id)

            identity = self._get_or_create_identity(track_id, now)
            identity.last_seen = now
            identity.frames_seen += 1

            # Compute normalized center for static face detection
            norm_cx = (float(bbox[0]) + float(bbox[2])) / 2.0 / self._frame_w
            norm_cy = (float(bbox[1]) + float(bbox[3])) / 2.0 / self._frame_h

            # Record initial center on first frame
            if identity.first_center is None:
                identity.first_center = (norm_cx, norm_cy)

            # Static face detection: if track has barely moved from its initial
            # position after STATIC_WINDOW_SECONDS and is unrecognized, mark as
            # static (poster/portrait). Stop wasting ArcFace cycles on it.
            if (
                not identity.is_static
                and identity.recognition_status == "unknown"
                and (now - identity.first_seen) > STATIC_WINDOW_SECONDS
                and identity.first_center is not None
            ):
                dx = abs(norm_cx - identity.first_center[0])
                dy = abs(norm_cy - identity.first_center[1])
                if dx < STATIC_MOVEMENT_THRESHOLD and dy < STATIC_MOVEMENT_THRESHOLD:
                    identity.is_static = True
                    logger.info("Track %d marked as static (poster/portrait), skipping recognition", track_id)

            # Quality gate: check face crop before using embedding for recognition.
            # Bypass for pending tracks — get instant first recognition even on
            # a slightly blurry frame. Quality gate only applies to re-verifications
            # and embedding buffer accumulation.
            quality_passed = False
            is_first_recognition = identity.recognition_status == "pending"
            if embedding is not None and not identity.is_static:
                if is_first_recognition:
                    # Skip quality gate for first recognition — instant match
                    quality_passed = True
                else:
                    x1p, y1p, x2p, y2p = bbox.astype(int)
                    x1p, y1p = max(0, x1p), max(0, y1p)
                    x2p, y2p = min(self._frame_w, x2p), min(self._frame_h, y2p)
                    crop = frame[y1p:y2p, x1p:x2p]
                    if crop.size > 0:
                        quality_passed, _ = assess_recognition_quality(crop)

            # Accumulate quality-passed embeddings for temporal aggregation.
            # Only add quality-gated frames (not bypassed first-recognition frames).
            if not is_first_recognition and quality_passed and embedding is not None:
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
                    identity.is_static = False  # Reset static flag on drift

            # Cache current embedding for drift detection
            if embedding is not None:
                identity.last_embedding = embedding

            # Determine if this track needs recognition
            if identity.is_static:
                needs_recognition = False
            elif identity.recognition_status == "pending" or embedding_drifted:
                # New/pending tracks always get recognized immediately
                needs_recognition = True
            elif identity.recognition_status == "unknown":
                age = now - identity.first_seen
                retry_interval = 0.0 if age < 5.0 else 2.0
                needs_recognition = (now - identity.last_verified) > retry_interval
            else:
                # Recognized track: re-verify at interval, but stagger to avoid storms
                if identity.last_drift_time > 0 and (now - identity.last_drift_time) < 3.0:
                    reverify_interval = 1.0
                else:
                    reverify_interval = settings.REVERIFY_INTERVAL
                needs_recognition = (now - identity.last_verified) > reverify_interval

            # Stagger re-verifications: cap at MAX_REVERIFIES_PER_FRAME.
            # New/pending tracks are NOT capped (they must be recognized ASAP).
            is_reverify = needs_recognition and identity.recognition_status == "recognized"
            if is_reverify:
                if reverify_count >= MAX_REVERIFIES_PER_FRAME:
                    needs_recognition = False
                else:
                    reverify_count += 1

            # Collect for batch recognition
            if needs_recognition and quality_passed and embedding is not None:
                # Prepare search embedding (temporal average if available)
                if len(identity.embedding_buffer) >= 3:
                    avg = np.mean(identity.embedding_buffer, axis=0)
                    avg = avg / np.linalg.norm(avg)
                    search_emb = avg
                else:
                    search_emb = embedding
                pending_recognitions.append((identity, search_emb))

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

            # Store last bbox for coasting when track is briefly lost
            identity.last_bbox = norm_bbox

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

        # 5b. Add coasting tracks: recognized tracks that are not detected
        # this frame but were recently seen. This prevents bounding box blinking
        # when SCRFD misses a face for 1-2 frames (motion blur, brief occlusion).
        for tid, identity in self._identity_cache.items():
            if tid in active_track_ids:
                continue  # Already in results
            if identity.recognition_status != "recognized":
                continue  # Only coast recognized tracks
            if identity.last_bbox is None:
                continue
            age = now - identity.last_seen
            if age > settings.TRACK_LOST_TIMEOUT:
                continue  # Too old, let it expire

            results.append(
                TrackResult(
                    track_id=tid,
                    bbox=identity.last_bbox,
                    velocity=[0.0, 0.0, 0.0, 0.0],
                    user_id=identity.user_id,
                    name=identity.name,
                    confidence=identity.confidence,
                    status=identity.recognition_status,
                    is_active=False,  # Not detected this frame, coasting
                )
            )

        # 6. Batch recognition: run all pending FAISS searches
        if pending_recognitions:
            self._recognize_batch(pending_recognitions, now)

            # Update results with newly recognized identities
            results = [
                TrackResult(
                    track_id=r.track_id,
                    bbox=r.bbox,
                    velocity=r.velocity,
                    user_id=self._identity_cache[r.track_id].user_id
                    if r.track_id in self._identity_cache
                    else r.user_id,
                    name=self._identity_cache[r.track_id].name if r.track_id in self._identity_cache else r.name,
                    confidence=self._identity_cache[r.track_id].confidence
                    if r.track_id in self._identity_cache
                    else r.confidence,
                    status=self._identity_cache[r.track_id].recognition_status
                    if r.track_id in self._identity_cache
                    else r.status,
                    is_active=r.is_active,
                )
                for r in results
            ]

        # 7. Deduplicate by user_id — keep highest confidence per user
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

        # 7b. Deduplicate unknown tracks by bbox IoU
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

        # 8. Expire lost tracks
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

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_or_create_identity(self, track_id: int, now: float) -> TrackIdentity:
        """Get existing identity or create a new pending one."""
        if track_id not in self._identity_cache:
            # Jitter last_verified so re-verifications are naturally staggered
            # across tracks. Without this, all tracks created at the same time
            # would re-verify simultaneously every REVERIFY_INTERVAL seconds.
            jitter = random.uniform(0, settings.REVERIFY_INTERVAL)
            self._identity_cache[track_id] = TrackIdentity(
                track_id=track_id,
                first_seen=now,
                last_seen=now,
                last_verified=now - jitter,  # Stagger initial re-verify timing
            )
        return self._identity_cache[track_id]

    def _resolve_name(self, user_id: str) -> str:
        """Resolve display name for a user_id, with DB fallback for new registrations."""
        name = self._name_map.get(user_id)
        if name:
            return name

        # User registered during active session — not in static name_map.
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

    def _recognize_batch(
        self,
        pending: list[tuple[TrackIdentity, np.ndarray]],
        now: float,
    ) -> None:
        """Run FAISS search for all pending tracks in batch.

        Each track's result is applied to its identity (recognized/unknown).
        """
        for identity, search_embedding in pending:
            result = self._faiss.search_with_margin(search_embedding)

            user_id = result.get("user_id")
            confidence = result.get("confidence", 0.0)
            is_ambiguous = result.get("is_ambiguous", False)

            logger.debug(
                "[TRACK-SCORE] track=%d user=%s confidence=%.4f ambiguous=%s status=%s",
                identity.track_id,
                user_id[:8] if user_id else "NONE",
                confidence,
                is_ambiguous,
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
                # Adaptive per-session enrollment
                if settings.ADAPTIVE_ENROLL_ENABLED and confidence >= settings.ADAPTIVE_ENROLL_MIN_CONFIDENCE:
                    self._try_adaptive_enroll(user_id, search_embedding, now)
            elif identity.recognition_status == "recognized":
                # Already recognized — don't downgrade on a single bad frame
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

        Uses a class-level global state so the per-user cap persists across
        session restarts (new tracker instances). Prevents unbounded FAISS
        index growth from adaptive embeddings.
        """
        state = RealtimeTracker._global_adaptive_state.get(user_id, {"count": 0, "last_time": 0.0})
        if state["count"] >= settings.ADAPTIVE_ENROLL_MAX_PER_USER:
            return
        if (now - state["last_time"]) < settings.ADAPTIVE_ENROLL_COOLDOWN:
            return

        emb = embedding / np.linalg.norm(embedding)
        self._faiss.add_adaptive(emb.astype(np.float32), user_id)
        state["count"] += 1
        state["last_time"] = now
        RealtimeTracker._global_adaptive_state[user_id] = state
        logger.info(
            "Adaptive enroll: user=%s count=%d/%d",
            user_id[:8],
            state["count"],
            settings.ADAPTIVE_ENROLL_MAX_PER_USER,
        )

    def _match_embeddings_to_tracks(
        self,
        det_bboxes: np.ndarray,
        embeddings: list[np.ndarray],
        tracked: sv.Detections,
    ) -> dict[int, np.ndarray]:
        """Match InsightFace embeddings to ByteTrack tracks by IoU.

        Uses the Hungarian algorithm for optimal exclusive 1:1 assignment.
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

        # Hungarian algorithm: maximize IoU → minimize (1 - IoU)
        cost_matrix = 1.0 - iou_matrix
        row_indices, col_indices = linear_sum_assignment(cost_matrix)

        result: dict[int, np.ndarray] = {}
        for row, col in zip(row_indices, col_indices):
            if iou_matrix[row, col] > 0.3:
                track_id = int(tracked.tracker_id[row])
                result[track_id] = embeddings[col]

        return result

    def _expire_lost_tracks(self, now: float, active_track_ids: set[int] | None = None) -> None:
        """Remove stale tracks from identity cache."""
        if active_track_ids is None:
            active_track_ids = set()

        stale_threshold = settings.TRACK_LOST_TIMEOUT
        to_remove = [
            tid
            for tid, identity in self._identity_cache.items()
            if tid not in active_track_ids and (now - identity.last_seen) > stale_threshold
        ]
        for tid in to_remove:
            del self._identity_cache[tid]
            self._prev_bboxes.pop(tid, None)

    @staticmethod
    def _compute_iou(box_a: np.ndarray, box_b: np.ndarray) -> float:
        """Compute IoU between two [x1, y1, x2, y2] boxes."""
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
    def _compute_iou_norm(box_a: list[float], box_b: list[float]) -> float:
        """Compute IoU between two normalized [x1, y1, x2, y2] boxes."""
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
    def _nms_faces(
        bboxes: list[list[float]],
        confidences: list[float],
        embeddings: list[np.ndarray],
        iou_threshold: float = 0.5,
    ) -> tuple[list, list, list]:
        """Non-maximum suppression to remove duplicate detections."""
        if not bboxes:
            return bboxes, confidences, embeddings

        indices = list(range(len(bboxes)))
        indices.sort(key=lambda i: confidences[i], reverse=True)

        keep: list[int] = []
        for i in indices:
            suppress = False
            for j in keep:
                iou = RealtimeTracker._compute_iou(np.array(bboxes[i]), np.array(bboxes[j]))
                if iou > iou_threshold:
                    suppress = True
                    break
            if not suppress:
                keep.append(i)

        return (
            [bboxes[i] for i in keep],
            [confidences[i] for i in keep],
            [embeddings[i] for i in keep],
        )
