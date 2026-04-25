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
from collections import deque
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

# Minimum number of consecutive frames a track must be seen before we
# emit it in the broadcast. At the onprem ~4 fps processing rate each
# withheld frame is ~250 ms of empty-overlay time; at the original value
# of 2 the admin saw a clearly visible ~250-500 ms gap between "face
# enters frame" and "first box drawn". Dropping to 1 emits on first
# detection, relying on SCRFD's own confidence threshold (0.3) and the
# downstream recognition gate (warming_up → recognized/unknown) to weed
# out false positives. ByteTrack's is_activated flag already provides a
# cheap second-opinion for the few frames where SCRFD fires on a shadow.
MIN_EMIT_FRAMES = 1


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
    drift_strike_count: int = 0  # Consecutive low-sim frames (must reach threshold to trigger)
    recognition_status: str = "pending"  # "pending" | "recognized" | "unknown"
    frames_seen: int = 0
    last_embedding: np.ndarray | None = None  # Detect track ID swaps
    anchor_embedding: np.ndarray | None = None  # Fixed reference from recognition time (never shifts)
    embedding_buffer: deque = field(default_factory=lambda: deque(maxlen=5))  # Recent quality-passed embeddings (FIFO, max 5)
    is_static: bool = False  # True = likely a poster/portrait, skip recognition
    first_center: tuple[float, float] | None = None  # Initial bbox center (normalized)
    last_bbox: list[float] | None = None  # Last normalized bbox [x1, y1, x2, y2] for coasting
    held_user_id: str | None = None  # Saved identity during hold window
    held_name: str | None = None
    held_confidence: float = 0.0
    held_at: float = 0.0  # When identity was saved for hold
    # Tri-state warm-up gating — see settings.UNKNOWN_CONFIRM_* and docstring on
    # _derive_recognition_state below. The client uses these to render
    # "Detecting…" instead of a premature "Unknown" while FAISS warms up.
    unknown_attempts: int = 0  # Consecutive FAISS misses since last hit
    best_score_seen: float = 0.0  # Peak cosine similarity across all FAISS attempts


@dataclass(frozen=True, slots=True)
class TrackResult:
    """Single track in a processed frame."""

    track_id: int
    bbox: list[float]  # [x1, y1, x2, y2] normalized 0-1
    velocity: list[float]  # [vx, vy, vw, vh] normalized units/second (center+size)
    user_id: str | None
    name: str | None
    confidence: float
    status: str  # "recognized" | "unknown" | "pending"  (legacy — kept for backward compat)
    is_active: bool  # True if matched to a detection this frame
    # Tri-state gating for the client overlay. "recognized" and "warming_up" both
    # prevent a red "Unknown" from flashing before the backend is confident. Only
    # "unknown" commits to the red label.
    recognition_state: str = "warming_up"  # "recognized" | "warming_up" | "unknown"


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
        schedule_id: str | None = None,
        camera_id: str | None = None,
    ) -> None:
        self._insight = insightface_model
        self._faiss = faiss_manager
        self._enrolled = enrolled_user_ids or set()
        self._name_map = name_map or {}
        # Recognition-evidence tagging. Used by evidence_writer.submit() to
        # anchor every captured row to the right schedule + physical camera.
        # Optional so the tracker remains instantiable in isolated unit
        # tests that don't care about evidence capture.
        self._schedule_id = schedule_id
        self._camera_id = camera_id or "unknown"
        # Frame-local counter that monotonically increments per successful
        # process() call. Stored on the event so an admin can reconstruct
        # frame ordering regardless of clock skew.
        self._frame_counter: int = 0
        # Per-user caches so the evidence intercept (called on every FAISS
        # decision) does ZERO extra DB / disk I/O after the first match.
        #   * bytes: the registered-angle JPEG loaded once per user.
        #   * ref  : the storage key assigned once by the writer, returned
        #            on the evidence draft of subsequent events.
        # Missing-user is cached explicitly (None value) so we don't retry
        # the DB lookup each frame for a user whose image_storage_key is
        # null (pre-Phase-2 registrations).
        self._evidence_reg_bytes: dict[str, bytes | None] = {}
        self._evidence_reg_ref: dict[str, str] = {}

        # ByteTrack with tuned parameters for face tracking
        self._tracker = sv.ByteTrack(
            track_activation_threshold=0.25,
            lost_track_buffer=int(settings.TRACK_LOST_TIMEOUT * settings.PROCESSING_FPS),
            minimum_matching_threshold=0.8,
            frame_rate=int(settings.PROCESSING_FPS),
        )

        # Identity cache: track_id -> TrackIdentity
        self._identity_cache: dict[int, TrackIdentity] = {}

        # Graveyard: recently-expired recognized tracks for spatial inheritance.
        # When a new track appears near a graveyarded track, it inherits the identity
        # instantly instead of starting from scratch. Prevents recognized→unknown flicker
        # when ByteTrack assigns a new track ID after briefly losing detection.
        self._identity_graveyard: list[TrackIdentity] = []

        # Previous frame bboxes for velocity computation: track_id -> [cx, cy, w, h]
        self._prev_bboxes: dict[int, list[float]] = {}
        self._processing_fps: float = settings.PROCESSING_FPS

        # Frame dimensions (set on first frame)
        self._frame_h: int = 0
        self._frame_w: int = 0

        # Timing-log throttle: emit a per-stage breakdown every N frames so
        # an operator can see where the per-frame budget is going without
        # drowning the log at 1-5 Hz. Tuned to roughly once per second at
        # PROCESSING_FPS=5.
        self._timing_log_every: int = 5
        self._timing_log_counter: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, frame: np.ndarray) -> TrackFrame:
        """Process one BGR frame: detect → track → recognize (new only).

        Pipeline shape (industry-standard tiered video analytics pattern —
        DeepStream / AWS Rekognition Streams / Azure Video Analyzer all use
        the same decomposition):

          1. **Detect every frame** via SCRFD. Returns bboxes + 5-pt
             keypoints only. Cheapest thing we can do per frame and still
             have tracking be meaningful.
          2. **Track every frame** via ByteTrack. Assigns stable integer
             track IDs to detections; internally runs a Kalman filter so a
             track survives single-frame detection misses.
          3. **Recognize sparsely** via ArcFace — only for tracks that are
             (a) newly seen, (b) due for periodic re-verification, or
             (c) currently flagged "unknown" and still inside the retry
             window. A classroom where the same 5 faces are sitting
             through a 1.5-hour lecture pays ArcFace cost only on entry +
             every REVERIFY_INTERVAL, not every frame × every face.

        Args:
            frame: BGR numpy array from FrameGrabber.

        Returns:
            TrackFrame with all current tracks and timing info.
        """
        t0 = time.monotonic()
        self._frame_h, self._frame_w = frame.shape[:2]
        now = time.monotonic()
        self._frame_counter += 1

        # ------------------------------------------------------------------
        # 1. SCRFD detection only — no ArcFace / landmarks / genderage.
        # ------------------------------------------------------------------
        t_det_start = time.monotonic()
        raw_dets = self._insight.detect(frame) if self._insight.app else []

        # Landmark-sanity filter — a real face has eyes above the nose
        # above the mouth, eyes horizontally separated, and a face-height
        # to eye-distance ratio in a human-plausible range. SCRFD false
        # positives on picture frames, shadowed wall textures, and similar
        # non-face patterns typically violate one of these; filtering here
        # removes the "Detecting…" ghost-box class of artifacts before
        # they ever reach ByteTrack (where they'd otherwise consume a
        # track slot for up to TRACK_LOST_TIMEOUT seconds).
        raw_dets = [d for d in raw_dets if self._kps_is_plausible(d.get("kps"))]

        t_det_ms = (time.monotonic() - t_det_start) * 1000.0

        if not raw_dets:
            self._expire_lost_tracks(now)
            duration_ms = (time.monotonic() - t0) * 1000.0
            self._log_timing(duration_ms, t_det_ms, 0.0, 0.0, 0, 0)
            return TrackFrame(
                tracks=[],
                fps=1000.0 / max(duration_ms, 0.1),
                processing_ms=duration_ms,
                timestamp=now,
            )

        # Split the detection records into parallel arrays. ``kpss`` carries
        # the 5-point landmarks (eyes / nose / mouth corners) that ArcFace
        # alignment needs later — we carry them all the way through NMS +
        # size filtering so the track↔keypoint correspondence survives.
        bboxes: list[list[float]] = []
        confidences: list[float] = []
        kpss: list[np.ndarray | None] = []
        for d in raw_dets:
            b = d["bbox"]
            bboxes.append([float(b[0]), float(b[1]), float(b[2]), float(b[3])])
            confidences.append(d["det_score"])
            kpss.append(d["kps"])

        # NMS first — dedupe overlapping detections before the size filter so
        # we don't accidentally drop the "good" copy of a near-duplicate pair.
        bboxes, confidences, kpss = self._nms_faces_kps(bboxes, confidences, kpss)

        # Size filter — reject detections too small to plausibly be a real
        # classroom face.
        #
        # History:
        #   - Originally ``frame_area * 0.0025`` → on 2304×1296 ≈7500 px²
        #     (~86 px side). Too big; rejected real classroom faces.
        #   - Fixed ~40×40 px² (1600 px²) floor set assuming SCRFD runs on
        #     the native 2304×1296 stream.
        #   - 2026-04-24: the on-prem FrameGrabber downscales to 1280×720
        #     before SCRFD, so a 40 px face on native becomes only ~22 px
        #     (~490 px²) in what SCRFD actually sees. The 1600-px² floor
        #     was silently dropping every real EB226 detection — observed
        #     with the wide-angle EB226 view where a clearly-visible
        #     person produced tracks=0 despite SCRFD scoring them 0.835
        #     at det_thresh=0.3. Rescale the floor against the actual
        #     incoming frame size: we want ~3% of the smaller frame side
        #     as the minimum face edge, which matches real classroom-
        #     distance faces while staying above SCRFD's typical
        #     ≤20 px false-positive size at any grabber resolution.
        _min_face_side = 0.03 * min(self._frame_w, self._frame_h)
        min_face_area = _min_face_side * _min_face_side
        filtered = [
            (b, c, k)
            for b, c, k in zip(bboxes, confidences, kpss)
            if (b[2] - b[0]) * (b[3] - b[1]) >= min_face_area
        ]
        if not filtered:
            self._expire_lost_tracks(now)
            duration_ms = (time.monotonic() - t0) * 1000.0
            self._log_timing(duration_ms, t_det_ms, 0.0, 0.0, 0, 0)
            return TrackFrame(
                tracks=[],
                fps=1000.0 / max(duration_ms, 0.1),
                processing_ms=duration_ms,
                timestamp=now,
            )
        bboxes, confidences, kpss = zip(*filtered)
        bboxes = list(bboxes)
        confidences = list(confidences)
        kpss = list(kpss)

        det_array = np.array(bboxes, dtype=np.float32)
        conf_array = np.array(confidences, dtype=np.float32)

        detections = sv.Detections(
            xyxy=det_array,
            confidence=conf_array,
        )

        # ------------------------------------------------------------------
        # 2. ByteTrack update → persistent track IDs.
        # ------------------------------------------------------------------
        t_track_start = time.monotonic()
        tracked = self._tracker.update_with_detections(detections)

        # Match each tracked box back to its originating detection so we can
        # look up the corresponding 5-point landmarks if we decide to
        # recognize this track. Same Hungarian-IoU assignment the old
        # embedding-matching code used — just carrying kps instead.
        track_kps = self._match_kps_to_tracks(det_array, kpss, tracked)
        t_track_ms = (time.monotonic() - t_track_start) * 1000.0

        # ------------------------------------------------------------------
        # 3. Per-track state update + lazy ArcFace (recognition only on
        #    tracks that actually need it this frame).
        # ------------------------------------------------------------------
        results: list[TrackResult] = []
        active_track_ids: set[int] = set()
        # Tracks that need recognition: [(identity, search_embedding,
        # live_crop, det_score, bbox_px)]. The tuple carries the evidence-
        # writer payload so _recognize_batch can produce one row + one JPEG
        # pair per FAISS decision without reaching back into the frame.
        pending_recognitions: list[
            tuple[TrackIdentity, np.ndarray, np.ndarray, float, list[int]]
        ] = []
        reverify_count = 0
        t_embed_total_ms = 0.0
        embeddings_computed = 0

        for i, track_id in enumerate(tracked.tracker_id):
            track_id = int(track_id)
            active_track_ids.add(track_id)

            bbox = tracked.xyxy[i]
            kps = track_kps.get(track_id)

            identity = self._get_or_create_identity(track_id, now, bbox=bbox)
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

            # -------- Decide up-front whether this track needs an embedding --------
            #
            # This is the key change vs. the old pipeline: embeddings are no
            # longer free (pre-computed by ``app.get()``). Each embedding we
            # request here costs one full ArcFace forward pass (~8 ms CPU).
            # For a classroom of 5 students sitting through a 1.5-hour class,
            # we want to pay that cost once per new track + once every
            # REVERIFY_INTERVAL — not N_faces × every frame.
            #
            # The rules below reproduce the previous behavior minus the
            # per-frame "drift check via anchor similarity" path — drift is
            # still caught, but now via the periodic re-verify's FAISS
            # search + identity-swap logic in ``_recognize_batch`` (worst
            # case: up to REVERIFY_INTERVAL seconds of stale identity before
            # a swap is detected, which in a stationary classroom is fine).
            is_first_recognition = identity.recognition_status == "pending"

            if identity.is_static:
                needs_recognition = False
            elif is_first_recognition:
                # New / just-drift-reset tracks — always try to recognize now.
                needs_recognition = True
            elif identity.recognition_status == "unknown":
                age = now - identity.first_seen
                # Graduated retry — same intent as before: aggressive early,
                # backs off so we don't spam FAISS with hopeless queries.
                if age < 1.0:
                    retry_interval = 0.0
                elif age < 5.0:
                    retry_interval = 0.3
                else:
                    retry_interval = 1.0
                needs_recognition = (now - identity.last_verified) > retry_interval
            else:
                # Recognized track — periodic re-verify only.
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

            # -------- Embedding + quality (only if we're going to use it) --------
            embedding: np.ndarray | None = None
            quality_passed = False
            if needs_recognition and kps is not None:
                # Quality gate first (cheap, ~1 ms). Bypass for pending tracks
                # so a slightly blurry first frame still gets a shot at FAISS
                # — the "warm up first, commit later" logic downstream already
                # handles noisy first recognitions.
                if is_first_recognition:
                    quality_passed = True
                else:
                    x1p, y1p, x2p, y2p = bbox.astype(int)
                    x1p, y1p = max(0, x1p), max(0, y1p)
                    x2p, y2p = min(self._frame_w, x2p), min(self._frame_h, y2p)
                    crop = frame[y1p:y2p, x1p:x2p]
                    if crop.size > 0:
                        quality_passed, _ = assess_recognition_quality(crop)

                if quality_passed:
                    emb_t0 = time.monotonic()
                    try:
                        embedding = self._insight.embed_from_kps(frame, kps)
                        embeddings_computed += 1
                    except Exception as exc:
                        # A single bad crop shouldn't kill the frame — log
                        # and continue; the track stays pending and we'll
                        # retry next frame with fresh kps.
                        logger.debug(
                            "embed_from_kps failed for track %d: %s", track_id, exc
                        )
                        embedding = None
                    t_embed_total_ms += (time.monotonic() - emb_t0) * 1000.0

            # Accumulate quality-passed embeddings for temporal aggregation
            # on first-recognition paths. ``maxlen=5`` FIFO so re-verifies
            # don't leak old embeddings into future first-recognitions.
            if quality_passed and embedding is not None:
                identity.embedding_buffer.append(embedding)
                identity.last_embedding = embedding

            # Collect for batch recognition
            if needs_recognition and quality_passed and embedding is not None:
                # For pending tracks (first recognition), accumulate a small buffer
                # before searching to reduce single-frame noise. At least 2 frames
                # must be in the buffer before we commit to a FAISS result.
                if (
                    identity.recognition_status == "pending"
                    and len(identity.embedding_buffer) < 3
                    and identity.frames_seen < 5  # Safety: don't buffer forever
                ):
                    if len(identity.embedding_buffer) < 2:
                        # Need at least 2 frames — skip this round
                        identity.last_verified = now
                        # Continue to bbox/velocity computation below (don't skip track)
                        norm_bbox = [
                            float(bbox[0]) / self._frame_w,
                            float(bbox[1]) / self._frame_h,
                            float(bbox[2]) / self._frame_w,
                            float(bbox[3]) / self._frame_h,
                        ]
                        cx = (norm_bbox[0] + norm_bbox[2]) / 2
                        cy = (norm_bbox[1] + norm_bbox[3]) / 2
                        w = norm_bbox[2] - norm_bbox[0]
                        h = norm_bbox[3] - norm_bbox[1]
                        prev = self._prev_bboxes.get(track_id)
                        if prev is not None:
                            pcx, pcy, pw, ph = prev
                            fps = self._processing_fps
                            velocity = [(cx - pcx) * fps, (cy - pcy) * fps, (w - pw) * fps, (h - ph) * fps]
                        else:
                            velocity = [0.0, 0.0, 0.0, 0.0]
                        self._prev_bboxes[track_id] = [cx, cy, w, h]
                        identity.last_bbox = norm_bbox
                        # Confirmation gate — hide single-frame tentative tracks
                        # from the client to suppress ghost boxes on transient
                        # SCRFD false positives. State still updates so the
                        # track is ready to emit on its next frame.
                        if identity.frames_seen < MIN_EMIT_FRAMES:
                            continue
                        d_uid, d_name, d_conf, d_status, d_state = self._get_display_identity(track_id, now)
                        results.append(TrackResult(
                            track_id=track_id, bbox=norm_bbox, velocity=velocity,
                            user_id=d_uid, name=d_name, confidence=d_conf,
                            status=d_status, is_active=True,
                            recognition_state=d_state,
                        ))
                        continue

                # Prepare search embedding (temporal average if available)
                if len(identity.embedding_buffer) >= 2:
                    avg = np.mean(identity.embedding_buffer, axis=0)
                    avg = avg / np.linalg.norm(avg)
                    search_emb = avg
                else:
                    search_emb = embedding

                # Evidence-writer payload — computed eagerly while the raw
                # frame + bbox are still in scope. A fresh bbox crop (not the
                # aligned 112x112 ArcFace input) is used for the audit trail
                # so the admin UI can show the student "as captured in frame".
                x1p, y1p, x2p, y2p = bbox.astype(int)
                x1p, y1p = max(0, x1p), max(0, y1p)
                x2p, y2p = min(self._frame_w, x2p), min(self._frame_h, y2p)
                live_crop_np = frame[y1p:y2p, x1p:x2p]
                # Fallback: skip the evidence row if the crop collapsed to
                # zero area — we'd have nothing to store.
                if live_crop_np.size == 0:
                    continue
                # Copy to decouple from the frame buffer; the evidence writer
                # may JPEG-encode this after a brief queue wait.
                live_crop_np = live_crop_np.copy()
                det_score = 0.0
                try:
                    det_score = float(tracked.confidence[i])
                except Exception:
                    det_score = 0.0
                bbox_px = [int(x1p), int(y1p), int(x2p), int(y2p)]
                pending_recognitions.append(
                    (identity, search_emb, live_crop_np, det_score, bbox_px)
                )

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

            # Confirmation gate — see MIN_EMIT_FRAMES docstring. A fresh
            # track must be seen at least twice before it appears in the
            # broadcast; until then it silently accrues identity state
            # (frames_seen, embedding_buffer) so the second-frame emission
            # is already warmed up.
            if identity.frames_seen < MIN_EMIT_FRAMES:
                continue

            # Apply identity hold: show held identity during hold window
            # so the frontend never sees recognized → unknown flicker
            d_uid, d_name, d_conf, d_status, d_state = self._get_display_identity(track_id, now)

            results.append(
                TrackResult(
                    track_id=track_id,
                    bbox=norm_bbox,
                    velocity=velocity,
                    user_id=d_uid,
                    name=d_name,
                    confidence=d_conf,
                    status=d_status,
                    is_active=True,
                    recognition_state=d_state,
                )
            )

        # 5b. Add coasting tracks: recognized tracks (or held tracks) that are
        # not detected this frame but were recently seen. This prevents bounding
        # box blinking when SCRFD misses a face for 1-2 frames.
        for tid, identity in self._identity_cache.items():
            if tid in active_track_ids:
                continue  # Already in results
            if identity.last_bbox is None:
                continue
            age = now - identity.last_seen
            if age > settings.TRACK_LOST_TIMEOUT:
                continue  # Too old, let it expire

            d_uid, d_name, d_conf, d_status, d_state = self._get_display_identity(tid, now)
            if d_status != "recognized":
                continue  # Only coast recognized (or held) tracks

            results.append(
                TrackResult(
                    track_id=tid,
                    bbox=identity.last_bbox,
                    velocity=[0.0, 0.0, 0.0, 0.0],
                    user_id=d_uid,
                    name=d_name,
                    confidence=d_conf,
                    status=d_status,
                    is_active=False,  # Not detected this frame, coasting
                    recognition_state=d_state,
                )
            )

        # ------------------------------------------------------------------
        # 4. Batch FAISS search for all tracks that earned an embedding
        #    this frame.
        # ------------------------------------------------------------------
        t_faiss_ms = 0.0
        if pending_recognitions:
            t_faiss_start = time.monotonic()
            self._recognize_batch(pending_recognitions, now)
            t_faiss_ms = (time.monotonic() - t_faiss_start) * 1000.0

            # Update results with newly recognized identities (with hold applied)
            updated: list[TrackResult] = []
            for r in results:
                if r.track_id in self._identity_cache:
                    d_uid, d_name, d_conf, d_status, d_state = self._get_display_identity(r.track_id, now)
                    updated.append(TrackResult(
                        track_id=r.track_id,
                        bbox=r.bbox,
                        velocity=r.velocity,
                        user_id=d_uid,
                        name=d_name,
                        confidence=d_conf,
                        status=d_status,
                        is_active=r.is_active,
                        recognition_state=d_state,
                    ))
                else:
                    updated.append(r)
            results = updated

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

        # Periodic per-stage timing so we can see where the budget goes
        # without drowning the log at 1+ Hz per pipeline.
        self._log_timing(
            duration_ms,
            t_det_ms,
            t_embed_total_ms,
            t_faiss_ms,
            embeddings_computed,
            len(results),
        )

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
        self._identity_graveyard.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_display_identity(
        self, track_id: int, now: float
    ) -> tuple[str | None, str | None, float, str, str]:
        """Return (user_id, name, confidence, status, recognition_state) with hold applied.

        ``status`` is the legacy per-track state — "pending" | "recognized" | "unknown".
        Kept for backward compatibility with older clients that ignore
        ``recognition_state``.

        ``recognition_state`` is the tri-state the new client consumes — see
        :py:meth:`_derive_recognition_state`. A "held" track is always reported as
        ``recognition_state="recognized"`` so the phone keeps the green box during
        brief drift re-verification.
        """
        identity = self._identity_cache[track_id]
        if (
            identity.recognition_status in ("pending", "unknown")
            and identity.held_user_id is not None
            and (now - identity.held_at) < settings.IDENTITY_HOLD_SECONDS
        ):
            return (
                identity.held_user_id,
                identity.held_name,
                identity.held_confidence,
                "recognized",
                "recognized",
            )
        recognition_state = self._derive_recognition_state(identity)
        return (
            identity.user_id,
            identity.name,
            identity.confidence,
            identity.recognition_status,
            recognition_state,
        )

    @staticmethod
    def _derive_recognition_state(identity: TrackIdentity) -> str:
        """Collapse the tracker's internal bookkeeping into a three-value signal
        for the overlay: ``"recognized"`` | ``"warming_up"`` | ``"unknown"``.

        Rules (evaluated top to bottom):

        1. ``recognition_status == "recognized"`` → ``"recognized"``.
        2. The track has been FAISS-rejected at least ``UNKNOWN_CONFIRM_ATTEMPTS``
           times **and** its best-seen cosine score is comfortably below
           ``RECOGNITION_THRESHOLD - UNKNOWN_CONFIRM_MARGIN`` → ``"unknown"``.
           Both clauses matter: a face hovering near threshold (e.g. peak 0.36 with
           threshold 0.38) stays in ``"warming_up"`` longer on the theory that a
           cleaner frame is likely imminent, while a face that has never produced a
           score above, say, 0.20 is clearly not enrolled and earns the red label
           quickly.
        3. Everything else (including fresh ``"pending"`` tracks and ``"unknown"``
           tracks still inside the confirm window) → ``"warming_up"`` so the
           overlay renders the neutral "Detecting…" label.
        """
        if identity.recognition_status == "recognized":
            return "recognized"
        confirm_attempts = settings.UNKNOWN_CONFIRM_ATTEMPTS
        score_ceiling = settings.RECOGNITION_THRESHOLD - settings.UNKNOWN_CONFIRM_MARGIN
        if (
            identity.unknown_attempts >= confirm_attempts
            and identity.best_score_seen < score_ceiling
        ):
            return "unknown"
        return "warming_up"

    def _get_or_create_identity(self, track_id: int, now: float, bbox: np.ndarray | None = None) -> TrackIdentity:
        """Get existing identity or create a new one (always goes through FAISS).

        We NEVER blindly inherit identity from graveyard spatially — that caused
        wrong identities to stick when person A leaves and person B enters the
        same spot. Every new track must earn its identity through FAISS recognition.

        The graveyard is kept only so that AFTER FAISS recognizes the new track,
        we can verify the identity matches what was there before (future use).
        """
        if track_id not in self._identity_cache:
            jitter = random.uniform(0, settings.REVERIFY_INTERVAL)
            self._identity_cache[track_id] = TrackIdentity(
                track_id=track_id,
                first_seen=now,
                last_seen=now,
                last_verified=now - jitter,
            )
        return self._identity_cache[track_id]

    def _resolve_name(self, user_id: str) -> str | None:
        """Resolve display name for a user_id.

        Returns the user's first_name if found (via in-memory map or DB fallback),
        or None if the user row no longer exists. Returning None — not the literal
        string "Unknown" — lets the caller distinguish "FAISS matched a stale vector
        pointing to a deleted user" from "backend genuinely recognised a user named
        Unknown". The former must become status='unknown'; the latter stays
        status='recognized' with name='Unknown' (unlikely but representable).
        """
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

        return None

    def _recognize_batch(
        self,
        pending: list[
            tuple[TrackIdentity, np.ndarray, np.ndarray, float, list[int]]
        ],
        now: float,
    ) -> None:
        """Run FAISS search for all pending tracks in a single batch call.

        Stacks embeddings into [N, 512] for BLAS-parallelized search with
        a single lock acquisition instead of N individual searches.

        For every decision (match and miss) a ``RecognitionEventDraft`` is
        fire-and-forget submitted to the evidence writer — behind the
        ``ENABLE_RECOGNITION_EVIDENCE`` flag, so VPS and dev setups don't
        pay the cost.
        """
        # Stack embeddings for batch search
        stacked = np.stack([emb for _, emb, _, _, _ in pending]).astype(np.float32)
        batch_results = self._faiss.search_batch_with_margin(stacked)

        for (identity, search_embedding, live_crop_np, det_score, bbox_px), result in zip(
            pending, batch_results
        ):
            user_id = result.get("user_id")
            confidence = result.get("confidence", 0.0)
            is_ambiguous = result.get("is_ambiguous", False)

            # Track peak cosine across the entire life of this track, not just
            # accepted matches. Feeds the _derive_recognition_state gate so faces
            # that keep scoring near threshold stay "warming_up" instead of
            # flipping to "unknown" the moment UNKNOWN_CONFIRM_ATTEMPTS is hit.
            if confidence > identity.best_score_seen:
                identity.best_score_seen = float(confidence)

            logger.debug(
                "[TRACK-SCORE] track=%d user=%s confidence=%.4f ambiguous=%s status=%s",
                identity.track_id,
                user_id[:8] if user_id else "NONE",
                confidence,
                is_ambiguous,
                "ACCEPT" if (user_id and not is_ambiguous) else "REJECT",
            )

            # Guard: a FAISS hit whose user_id no longer exists in the DB is a stale
            # embedding (e.g. orphaned adaptive vector after a user delete / reseed).
            # Treat it exactly like a miss so the track is not marked 'recognized'
            # and the client never shows a green box labelled 'Unknown'.
            resolved_name = self._resolve_name(user_id) if user_id is not None else None
            if user_id is not None and resolved_name is None:
                logger.warning(
                    "Track %d FAISS hit user_id=%s not in DB (orphaned embedding?)",
                    identity.track_id,
                    user_id[:8],
                )
                user_id = None

            if user_id is not None and not is_ambiguous:
                # Check if this is an IDENTITY SWAP (FAISS returned a different user)
                prev_user_id = identity.user_id
                is_swap = (
                    prev_user_id is not None
                    and prev_user_id != user_id
                    and identity.recognition_status == "recognized"
                )

                if is_swap:
                    # Only swap if new match is meaningfully better than current confidence.
                    # This prevents oscillation between two similar-looking registered users.
                    # Requires the new match to exceed current confidence by a margin.
                    swap_margin = 0.05
                    if confidence >= identity.confidence + swap_margin:
                        logger.warning(
                            "Track %d IDENTITY SWAP: %s (%.3f) -> %s (%.3f)",
                            identity.track_id,
                            identity.name,
                            identity.confidence,
                            resolved_name,
                            confidence,
                        )
                        identity.user_id = user_id
                        identity.confidence = confidence
                        identity.name = resolved_name
                        identity.anchor_embedding = search_embedding.copy()
                        identity.drift_strike_count = 0
                        # Clear held identity since the old one was wrong
                        identity.held_user_id = None
                        identity.held_name = None
                    else:
                        # Ambiguous swap attempt — keep current identity but log it
                        logger.debug(
                            "Track %d ambiguous swap rejected: current=%s (%.3f) vs new=%s (%.3f)",
                            identity.track_id,
                            identity.name,
                            identity.confidence,
                            resolved_name,
                            confidence,
                        )
                else:
                    # Same user, confirming — update confidence and anchor
                    identity.user_id = user_id
                    identity.confidence = confidence
                    identity.name = resolved_name
                    identity.recognition_status = "recognized"
                    identity.anchor_embedding = search_embedding.copy()
                    identity.drift_strike_count = 0
                    # Clear the warm-up counter — a successful match means any
                    # past misses were noise, not evidence of a stranger.
                    identity.unknown_attempts = 0
                    if prev_user_id is None:
                        logger.info(
                            "Track %d recognized: %s (%.3f)",
                            identity.track_id,
                            identity.name,
                            confidence,
                        )
                    # Adaptive enrollment — only after stable re-verification (prev_user_id == user_id).
                    # This prevents poisoning FAISS from a single wrong first-recognition.
                    # Requires: (1) already recognized as same user before (not first-time),
                    #           (2) confidence >= ADAPTIVE_ENROLL_MIN_CONFIDENCE (0.55),
                    #           (3) track has been alive for 10+ frames (~0.5s at 20fps).
                    is_stable_reverify = (prev_user_id == user_id and identity.frames_seen >= 10)
                    if (settings.ADAPTIVE_ENROLL_ENABLED
                        and is_stable_reverify
                        and confidence >= settings.ADAPTIVE_ENROLL_MIN_CONFIDENCE):
                        self._try_adaptive_enroll(user_id, search_embedding, now)
            elif identity.recognition_status == "recognized":
                # Already recognized — don't downgrade on a single bad frame.
                # Do not bump unknown_attempts either: a re-verify dip on a known
                # track is not evidence that the face is a stranger.
                logger.debug(
                    "Track %d re-verify missed (score=%.3f), keeping %s",
                    identity.track_id,
                    confidence,
                    identity.name,
                )
            else:
                # Pending or previously unknown track produced another miss.
                # Accumulate evidence toward committing to recognition_state="unknown".
                identity.recognition_status = "unknown"
                identity.confidence = confidence
                identity.unknown_attempts += 1
                logger.debug(
                    "Track %d unknown (score=%.3f peak=%.3f attempts=%d user=%s ambiguous=%s)",
                    identity.track_id,
                    confidence,
                    identity.best_score_seen,
                    identity.unknown_attempts,
                    user_id,
                    is_ambiguous,
                )

            # Fire-and-forget evidence capture. Every FAISS decision — match,
            # miss, or ambiguous — produces one row + one live JPEG; matched
            # decisions also include a registered-angle JPEG on first-match.
            # The writer drops events under back-pressure rather than blocking
            # the pipeline. See docs/plans/2026-04-22-recognition-evidence.
            if (
                settings.ENABLE_RECOGNITION_EVIDENCE
                and self._schedule_id is not None
            ):
                try:
                    self._submit_recognition_event(
                        identity=identity,
                        search_embedding=search_embedding,
                        live_crop=live_crop_np,
                        det_score=det_score,
                        bbox_px=bbox_px,
                        user_id=user_id,
                        confidence=float(confidence),
                        is_ambiguous=bool(is_ambiguous),
                    )
                except Exception:
                    # Evidence capture must never destabilise the pipeline.
                    logger.debug(
                        "evidence submit failed for track %d",
                        identity.track_id,
                        exc_info=True,
                    )

            identity.last_verified = now

    def _submit_recognition_event(
        self,
        identity: "TrackIdentity",
        search_embedding: np.ndarray,
        live_crop: np.ndarray,
        det_score: float,
        bbox_px: list[int],
        user_id: str | None,
        confidence: float,
        is_ambiguous: bool,
    ) -> None:
        """Build a RecognitionEventDraft and hand it to the evidence writer.

        Called from inside the per-track loop of ``_recognize_batch`` which
        runs on the pipeline's thread-pool executor. The hot path here
        **must stay sub-millisecond**; all non-trivial work (encoding,
        disk, DB) is deferred to the writer's async worker.

        Per-user caches (``_evidence_reg_bytes``, ``_evidence_reg_ref``)
        ensure ``_load_registered_crop_bytes`` runs at most once per user
        per process — not every frame.
        """
        from app.services.evidence_writer import (
            RecognitionEventDraft,
            evidence_writer,
        )

        matched = bool(user_id) and not is_ambiguous

        registered_crop_ref: str | None = None
        registered_crop_bytes: bytes | None = None
        if matched and user_id:
            cached_ref = self._evidence_reg_ref.get(user_id)
            if cached_ref:
                registered_crop_ref = cached_ref
            elif user_id not in self._evidence_reg_bytes:
                # First match for this user this process: one-shot DB+disk
                # read. Future events for the same user hit the cache.
                try:
                    self._evidence_reg_bytes[user_id] = (
                        self._load_registered_crop_bytes(user_id)
                    )
                except Exception:
                    logger.debug(
                        "Could not load registered crop for user %s",
                        user_id,
                        exc_info=True,
                    )
                    self._evidence_reg_bytes[user_id] = None
                registered_crop_bytes = self._evidence_reg_bytes[user_id]
            else:
                # Cached miss — user has no registered-image on disk.
                registered_crop_bytes = None

        draft = RecognitionEventDraft(
            schedule_id=str(self._schedule_id),
            student_id=str(user_id) if user_id else None,
            track_id=int(identity.track_id),
            camera_id=str(self._camera_id),
            frame_idx=int(self._frame_counter),
            similarity=float(confidence),
            threshold_used=float(settings.RECOGNITION_THRESHOLD),
            matched=matched,
            is_ambiguous=bool(is_ambiguous),
            det_score=float(det_score),
            embedding_norm=float(np.linalg.norm(search_embedding)),
            bbox={
                "x1": int(bbox_px[0]),
                "y1": int(bbox_px[1]),
                "x2": int(bbox_px[2]),
                "y2": int(bbox_px[3]),
            },
            live_crop=live_crop,
            model_name=str(settings.INSIGHTFACE_MODEL),
            registered_crop_bytes=registered_crop_bytes,
            registered_crop_ref=registered_crop_ref,
        )

        # Thread-safe post to the writer's loop. Returns immediately —
        # crop encoding + DB insert + WS broadcast happen on the writer's
        # async worker. If we're the one who supplied the bytes, record
        # the ref locally when the writer assigns it on the next event
        # cycle; we detect that via the draft.event_id reappearing in
        # writer state (too elaborate for this patch — instead, the
        # writer.remember_registered_crop is called reactively when
        # the first event flushes, and future drafts pull from that
        # cache via get_registered_crop_ref).
        evidence_writer.submit_threadsafe(draft)

        # Opportunistic: once the writer has materialised the ref, hoist
        # it into our local cache so subsequent events skip the bytes
        # payload on the wire.
        if matched and user_id and not registered_crop_ref:
            cached = evidence_writer.get_registered_crop_ref(user_id, "match")
            if cached:
                self._evidence_reg_ref[user_id] = cached

    def _load_registered_crop_bytes(self, user_id: str) -> bytes | None:
        """Read a single registered-angle JPEG for the user from the
        face-uploads volume. Called at most once per user per process
        (guarded by ``_evidence_reg_bytes`` cache in the caller).

        Returns None for pre-Phase-2 registrations that have no persisted
        ``image_storage_key``. The writer tolerates None and inserts the
        row with ``registered_crop_ref`` NULL.
        """
        from app.database import SessionLocal
        from app.models.face_embedding import FaceEmbedding
        from app.models.face_registration import FaceRegistration
        from app.utils.face_image_storage import FaceImageStorage

        db = SessionLocal()
        try:
            reg = (
                db.query(FaceRegistration)
                .filter(
                    FaceRegistration.user_id == user_id,
                    FaceRegistration.is_active.is_(True),
                )
                .first()
            )
            if not reg:
                return None
            emb = (
                db.query(FaceEmbedding)
                .filter(
                    FaceEmbedding.registration_id == reg.id,
                    FaceEmbedding.image_storage_key.isnot(None),
                )
                .first()
            )
            if not emb or not emb.image_storage_key:
                return None
            storage = FaceImageStorage()
            if not storage.exists(emb.image_storage_key):
                return None
            try:
                return storage.resolve_path(emb.image_storage_key).read_bytes()
            except Exception:
                return None
        finally:
            db.close()

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

    def _match_kps_to_tracks(
        self,
        det_bboxes: np.ndarray,
        kpss: list[np.ndarray | None],
        tracked: sv.Detections,
    ) -> dict[int, np.ndarray]:
        """Match 5-point landmarks to ByteTrack tracks by IoU.

        Same Hungarian-IoU assignment as the old
        ``_match_embeddings_to_tracks`` — just carrying keypoints instead of
        embeddings, because under the split detect/recognize pipeline we
        don't compute embeddings up front. Returns a map from track_id to
        the [5, 2] landmark array for its matched detection, or an empty
        map if no tracks / detections exist this frame.
        """
        if len(tracked) == 0 or len(det_bboxes) == 0:
            return {}

        # Vectorized IoU: broadcast [N,4] vs [M,4] → [N,M]
        t = tracked.xyxy.astype(np.float64)  # [N, 4]
        d = det_bboxes.astype(np.float64)    # [M, 4]

        x1 = np.maximum(t[:, None, 0], d[None, :, 0])
        y1 = np.maximum(t[:, None, 1], d[None, :, 1])
        x2 = np.minimum(t[:, None, 2], d[None, :, 2])
        y2 = np.minimum(t[:, None, 3], d[None, :, 3])
        inter = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)

        area_t = (t[:, 2] - t[:, 0]) * (t[:, 3] - t[:, 1])  # [N]
        area_d = (d[:, 2] - d[:, 0]) * (d[:, 3] - d[:, 1])  # [M]
        union = area_t[:, None] + area_d[None, :] - inter
        iou_matrix = np.where(union > 0, inter / union, 0.0)

        # Hungarian algorithm: maximize IoU → minimize (1 - IoU)
        cost_matrix = 1.0 - iou_matrix
        row_indices, col_indices = linear_sum_assignment(cost_matrix)

        result: dict[int, np.ndarray] = {}
        for row, col in zip(row_indices, col_indices):
            if iou_matrix[row, col] > 0.3 and kpss[col] is not None:
                track_id = int(tracked.tracker_id[row])
                result[track_id] = kpss[col]

        return result

    @staticmethod
    def _kps_is_plausible(kps: np.ndarray | None) -> bool:
        """Geometric sanity check on a SCRFD 5-point landmark set.

        Returns True if the landmarks are consistent with a real face:

        * eyes horizontally separated (non-degenerate)
        * eyes above nose above mouth vertically (Y grows downward in
          image coords, so ``eye_y <= nose_y <= mouth_y``)
        * face height (eyes→mouth) in a human-plausible ratio to face
          width (eye-to-eye): not too squat, not too elongated

        Returns True for missing / malformed kps too — we don't want the
        check to silently drop every detection if something upstream
        stops returning landmarks. The picture-frame false-positive case
        this is targeting always has landmarks (SCRFD always emits them
        for buffalo_l), so "no kps" is never going to be a ghost.
        """
        if kps is None:
            return True
        try:
            arr = np.asarray(kps, dtype=np.float32)
        except Exception:
            return True
        if arr.shape != (5, 2):
            return True

        eye_y = (float(arr[0, 1]) + float(arr[1, 1])) / 2.0
        nose_y = float(arr[2, 1])
        mouth_y = (float(arr[3, 1]) + float(arr[4, 1])) / 2.0
        eye_dx = abs(float(arr[0, 0]) - float(arr[1, 0]))

        # Eyes must be horizontally separated by at least 2 px — a tiny
        # epsilon so we don't reject legitimately tiny faces at camera
        # distance. At det_size=640, the smallest face SCRFD reliably
        # emits has eyes ~3-4 px apart, so 2 px is a safe floor.
        if eye_dx < 2.0:
            return False

        # Standard facial topology — eyes above nose above mouth. Allow
        # small equality-slack for extremely tilted or partially-occluded
        # faces that still deserve to be tracked.
        if not (eye_y - 1.0 <= nose_y <= mouth_y + 1.0):
            return False

        # Face aspect plausibility. A human face viewed roughly head-on
        # has a mouth-to-eye vertical span of ~0.5-1.5× the eye spacing.
        # We widen to [0.3, 2.5] to admit severe tilts but still reject
        # patently non-facial landmark configurations (e.g. a horizontal
        # band of reflections on a picture frame).
        face_height = mouth_y - eye_y
        if face_height < eye_dx * 0.3:
            return False
        if face_height > eye_dx * 2.5:
            return False

        return True

    def _log_timing(
        self,
        total_ms: float,
        det_ms: float,
        embed_ms: float,
        faiss_ms: float,
        embeddings_computed: int,
        tracks_emitted: int,
    ) -> None:
        """Emit a per-stage timing breakdown every N frames.

        Logged at INFO so it's visible in Dozzle without flipping to DEBUG.
        Helps answer "where is the 600 ms going?" without having to reach
        for a profiler.
        """
        self._timing_log_counter += 1
        if self._timing_log_counter % self._timing_log_every != 0:
            return
        # ``other_ms`` is the bookkeeping slice (NMS, ByteTrack update, IoU
        # matching, normalization, coasting, dedupe, expiry). Normally tiny
        # but worth making visible so we notice if it ever isn't.
        other_ms = max(0.0, total_ms - det_ms - embed_ms - faiss_ms)
        logger.info(
            "tracker timing: total=%.0fms | det=%.0fms embed=%.0fms (n=%d) faiss=%.0fms other=%.0fms | tracks=%d",
            total_ms,
            det_ms,
            embed_ms,
            embeddings_computed,
            faiss_ms,
            other_ms,
            tracks_emitted,
        )

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
    def _nms_faces_kps(
        bboxes: list[list[float]],
        confidences: list[float],
        kpss: list[np.ndarray | None],
        iou_threshold: float = 0.5,
    ) -> tuple[list, list, list]:
        """Non-maximum suppression over (bbox, conf, kps) triples.

        Same NMS as the old ``_nms_faces`` — parallel-array variant that
        keeps the kps slot aligned with bboxes/confidences. SCRFD itself
        does NMS internally, so this second pass rarely fires; it exists
        as a defensive dedupe in case two detections survive SCRFD's NMS
        with slightly different landmarks (typical for
        nearly-but-not-quite-duplicate faces at low threshold).
        """
        if not bboxes:
            return bboxes, confidences, kpss

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
            [kpss[i] for i in keep],
        )
