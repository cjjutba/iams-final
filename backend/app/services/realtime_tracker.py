"""
RealtimeTracker — ByteTrack face tracking with cached ArcFace recognition.

Detect every frame, track always, recognize only NEW faces. Once a track ID
is associated with a name, the name sticks until the track is lost or the
re-verify interval elapses.

Performance on M5 MacBook Pro (Apple Silicon):
  SCRFD ~10ms + ByteTrack ~2ms + ArcFace ~8ms (new tracks only) ≈ 15ms/frame
  At 10fps (100ms budget), 85ms headroom.
"""

import logging
import time
from dataclasses import dataclass, field

import numpy as np
import supervision as sv

from app.config import settings

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
    recognition_status: str = "pending"  # "pending" | "recognized" | "unknown"
    frames_seen: int = 0


@dataclass(frozen=True, slots=True)
class TrackResult:
    """Single track in a processed frame."""

    track_id: int
    bbox: list[float]  # [x1, y1, x2, y2] normalized 0-1
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
        bboxes, confidences, embeddings_list = self._nms_faces(
            bboxes, confidences, embeddings_list
        )

        det_array = np.array(bboxes, dtype=np.float32)
        conf_array = np.array(confidences, dtype=np.float32)

        detections = sv.Detections(
            xyxy=det_array,
            confidence=conf_array,
        )

        # 3. ByteTrack update → persistent track IDs
        tracked = self._tracker.update_with_detections(detections)

        # 4. Match embeddings to tracked detections by IoU
        track_embeddings = self._match_embeddings_to_tracks(
            det_array, embeddings_list, tracked
        )

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

            # Recognize if: new track, or re-verify interval elapsed
            needs_recognition = (
                identity.recognition_status == "pending"
                or (
                    identity.recognition_status != "pending"
                    and (now - identity.last_verified) > settings.REVERIFY_INTERVAL
                )
            )

            if needs_recognition and embedding is not None:
                self._recognize_track(identity, embedding, now)

            # Normalize bbox to 0-1
            norm_bbox = [
                float(bbox[0]) / self._frame_w,
                float(bbox[1]) / self._frame_h,
                float(bbox[2]) / self._frame_w,
                float(bbox[3]) / self._frame_h,
            ]

            results.append(TrackResult(
                track_id=track_id,
                bbox=norm_bbox,
                user_id=identity.user_id,
                name=identity.name,
                confidence=identity.confidence,
                status=identity.recognition_status,
                is_active=True,
            ))

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
        return {
            identity.user_id
            for identity in self._identity_cache.values()
            if identity.user_id is not None
        }

    def reset(self) -> None:
        """Clear all tracking state."""
        self._tracker.reset()
        self._identity_cache.clear()

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

    def _recognize_track(
        self, identity: TrackIdentity, embedding: np.ndarray, now: float
    ) -> None:
        """Run ArcFace + FAISS search for a track and cache the result."""
        result = self._faiss.search_with_margin(embedding)

        user_id = result.get("user_id")
        confidence = result.get("confidence", 0.0)
        is_ambiguous = result.get("is_ambiguous", False)

        if user_id is not None and not is_ambiguous:
            identity.user_id = user_id
            identity.confidence = confidence
            identity.name = self._resolve_name(user_id)
            identity.recognition_status = "recognized"

            if confidence > 0.3:
                logger.debug(
                    "Track %d recognized: %s (%.3f)",
                    identity.track_id, identity.name, confidence,
                )
        else:
            identity.recognition_status = "unknown"
            identity.confidence = confidence

        identity.last_verified = now

    def _match_embeddings_to_tracks(
        self,
        det_bboxes: np.ndarray,
        embeddings: list[np.ndarray],
        tracked: sv.Detections,
    ) -> dict[int, np.ndarray]:
        """Match InsightFace embeddings to ByteTrack tracks by IoU.

        Returns:
            Dict mapping track_id -> embedding for matched tracks.
        """
        if len(tracked) == 0 or len(det_bboxes) == 0:
            return {}

        result: dict[int, np.ndarray] = {}

        for i, track_id in enumerate(tracked.tracker_id):
            track_bbox = tracked.xyxy[i]
            best_iou = 0.0
            best_idx = -1

            for j, det_bbox in enumerate(det_bboxes):
                iou = self._compute_iou(track_bbox, det_bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_idx = j

            if best_idx >= 0 and best_iou > 0.3:
                result[int(track_id)] = embeddings[best_idx]

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
            ious = np.array([
                RealtimeTracker._compute_iou(bboxes[i], bboxes[j])
                for j in remaining
            ])
            indices = remaining[ious <= iou_threshold]

        return (
            [bboxes[i] for i in keep],
            [confidences[i] for i in keep],
            [embeddings[i] for i in keep],
        )

    def _expire_lost_tracks(
        self, now: float, active_ids: set[int] | None = None
    ) -> None:
        """Remove tracks that have been lost for > TRACK_LOST_TIMEOUT."""
        expired = []
        for track_id, identity in self._identity_cache.items():
            if active_ids is not None and track_id in active_ids:
                continue
            if (now - identity.last_seen) > settings.TRACK_LOST_TIMEOUT:
                expired.append(track_id)

        for track_id in expired:
            identity = self._identity_cache.pop(track_id)
            if identity.recognition_status == "recognized":
                logger.debug(
                    "Track %d expired: %s (was visible %.1fs)",
                    track_id,
                    identity.name,
                    now - identity.first_seen,
                )
