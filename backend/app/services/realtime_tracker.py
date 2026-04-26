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

import cv2
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

    # Spatial+temporal identity hint inherited from the graveyard.
    # See settings.IDENTITY_GRAVEYARD_* and RealtimeTracker._lookup_graveyard_hint.
    # The hint never auto-applies — it just lowers the FAISS commit
    # threshold for THIS specific user_id when this user comes back as
    # top-1. If FAISS keeps returning a different user, the hint is
    # discarded silently after the first non-matching top-1.
    hint_user_id: str | None = None
    hint_user_name: str | None = None
    hint_set_at: float = 0.0

    # Vote-based swap gate (added 2026-04-25 swap-hardening pass).
    # When this track is already bound to user X but FAISS returns user Y
    # with confidence > X + RECOGNITION_SWAP_MARGIN, we don't flip
    # immediately. Instead Y becomes the swap candidate; the streak
    # increments on every consecutive frame that keeps Y as the top-1
    # over X, and the swap commits only when streak >=
    # RECOGNITION_SWAP_MIN_STREAK. Any frame where the binding user X
    # comes back as top-1 (or a third user Z appears) resets the
    # candidate. This filters single-frame FAISS noise events that used
    # to flip the label every reverify in the 0.45-0.55 cross-domain
    # band, while still allowing genuine identity changes (e.g. ByteTrack
    # accidentally re-using a track id across two students) to flip in
    # ~0.6 s at 5 fps backend.
    swap_candidate_user_id: str | None = None
    swap_candidate_streak: int = 0
    swap_candidate_best_conf: float = 0.0
    swap_candidate_first_seen_at: float = 0.0

    # Rolling history of recently committed identity swaps. Each entry
    # is (timestamp, new_user_id). Drives the oscillation suppressor in
    # _derive_recognition_state — if more than OSCILLATION_FLIPS_THRESHOLD
    # swaps span ≥ OSCILLATION_DISTINCT_USERS distinct users inside the
    # last OSCILLATION_WINDOW_SECONDS, the broadcast for this track
    # silences the displayed name (overlay shows "Detecting…") until
    # the flapping cools off. Bounded at 16 to keep memory trivial; the
    # window check trims older entries on the read side.
    swap_history: deque = field(default_factory=lambda: deque(maxlen=16))
    # When the suppressor fires this becomes the wall-clock-monotonic
    # cutoff before which the broadcast keeps the silenced label, even
    # if subsequent frames don't add to swap_history. Reset to 0.0 once
    # the cooldown expires.
    oscillation_uncertain_until: float = 0.0

    # ──────────────────────────────────────────────────────────────────
    # Liveness state (MiniFASNet — added 2026-04-25)
    #
    # Updated each time the track gets a fresh liveness probe (same
    # cadence as ArcFace re-verify, gated by LIVENESS_RECHECK_INTERVAL_S).
    # The _streak counters debounce the suppression decision so a single
    # noisy frame doesn't flip the visible label.
    #
    # Default ``liveness_label="unknown"`` and ``liveness_score=1.0``: a
    # brand-new track is NOT pre-emptively marked spoof; only an actual
    # check (with verdict "spoof", repeated LIVENESS_SPOOF_CONSECUTIVE
    # times) flips ``liveness_suppressed=True``. This keeps the tracker
    # forward-compatible with sessions where the liveness pack isn't
    # loaded — every track stays unknown→treated-as-real.
    # ──────────────────────────────────────────────────────────────────
    liveness_score: float = 1.0
    liveness_label: str = "unknown"  # "real" | "spoof" | "unknown"
    liveness_last_check: float = 0.0
    liveness_spoof_streak: int = 0
    liveness_real_streak: int = 0
    liveness_suppressed: bool = False


@dataclass(slots=True)
class IdentityTombstone:
    """Recently-expired recognised track. Used by the spatial+temporal
    identity hint logic to help re-entries lock in faster — see
    RealtimeTracker._lookup_graveyard_hint and the settings docstring
    in app.config for the safety rationale.

    Stored fields are intentionally minimal: enough to spatially match a
    new track and tag it with a hint user_id; FAISS still does the actual
    identity confirmation.
    """

    user_id: str
    name: str | None
    bbox_center: tuple[float, float]  # normalised (cx, cy)
    expired_at: float  # wall-clock epoch seconds


@dataclass
class _BatchDecision:
    """Per-track tentative decision used by ``_recognize_batch``'s
    multi-phase resolver.

    Phase 1 (gather) populates everything from FAISS + hint rescue +
    name resolution. Phase 2 (swap-gate) may revert ``user_id`` /
    ``confidence`` back to the incumbent and set ``swap_blocked=True``.
    Phase 3 (frame-mutex / Hungarian) may downgrade a colliding loser
    to its top-2 fallback or null out ``user_id`` (track is shown as
    "Detecting…" instead of getting a wrong-name green box). Phase 4
    (commit) mutates identity state and submits evidence using the
    final values.

    Stored as mutable so each phase can rewrite without rebuilding the
    list. This dataclass lives only inside the batch call — never
    persisted to the identity cache.
    """
    identity: "TrackIdentity"
    search_embedding: np.ndarray
    live_crop: np.ndarray
    det_score: float
    bbox_px: list[int]

    # Resolved by Phase 1 (FAISS + hint rescue + name resolution).
    # Reflects the *final* committed identity for this frame after
    # subsequent phases run; the original FAISS top-1 lives in
    # ``top1_user_id`` for evidence + diagnostics.
    user_id: str | None
    confidence: float
    is_ambiguous: bool
    resolved_name: str | None

    # Used by Phase 3 (frame-mutex Hungarian) to fall back when a
    # track loses a collision. Top-2 must clear RECOGNITION_THRESHOLD
    # for the resolver to consider it.
    top1_user_id: str | None
    top1_score: float
    top2_user_id: str | None
    top2_score: float

    # True when Phase 2 (swap-gate) reverted a swap attempt because
    # the streak threshold wasn't met. Phase 4 skips the IDENTITY SWAP
    # log line in this case to avoid repeating "swap rejected" every
    # frame the candidate sustains.
    swap_blocked: bool = False
    # True when Phase 3 (frame-mutex) downgraded this track to top-2
    # or cleared its binding. Phase 4 logs the demotion.
    mutex_demoted: bool = False
    # True when this decision was synthesised by the periodic mean-
    # embedding revalidation pass rather than a live frame. Phase 4
    # skips the evidence-writer submit (the placeholder crop/bbox
    # would write garbage rows) and the auto-CCTV enroller offer.
    is_revalidation: bool = False


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
    # Independent liveness signal (MiniFASNet — added 2026-04-25). Orthogonal to
    # ``recognition_state``: a face can be ``recognition_state="warming_up"``
    # AND ``liveness_state="spoof"`` simultaneously — the overlay should render
    # the spoof label in that case. ``"unknown"`` means liveness wasn't
    # checked yet (or the pack isn't loaded — clients treat as real).
    liveness_state: str = "unknown"  # "real" | "spoof" | "unknown"
    liveness_score: float = 0.0  # Fused MiniFASNet "real" softmax (0-1)


@dataclass(frozen=True, slots=True)
class TrackFrame:
    """Result of processing one frame through the realtime tracker.

    Per-stage timing fields (``det_ms``, ``embed_ms``, ``faiss_ms``) are
    propagated to the WS ``frame_update`` payload so the admin live page
    HUD can show where the per-frame budget is going. ``other_ms`` =
    ``processing_ms - det_ms - embed_ms - faiss_ms`` is computed at the
    broadcast site and not stored here.

    ``rtp_pts_90k`` carries the upstream RTSP/RTP source PTS (90 kHz
    timebase) for the frame this result describes, captured by
    ``FrameGrabber.grab_with_pts()``. It travels through the WS payload
    so the admin live overlay can align the bbox draw to the matching
    video frame on the WHEP-played ``<video>`` element. None when the
    grabber didn't capture PTS (test mocks, legacy callers).
    """

    tracks: list[TrackResult]
    fps: float
    processing_ms: float
    timestamp: float
    det_ms: float = 0.0
    embed_ms: float = 0.0
    faiss_ms: float = 0.0
    rtp_pts_90k: int | None = None
    # Backend wall-clock (epoch ms) when the FrameGrabber drained this
    # frame off FFmpeg stdout. Travels through the WS payload as
    # ``detected_at_ms`` so clients can compute end-to-end display latency
    # against ``Date.now()`` / ``System.currentTimeMillis()``. ``None``
    # when the frame came from a test fixture or a legacy caller that
    # didn't pass it through ``process()``.
    captured_at_ms: int | None = None


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
        phone_only_user_ids: set[str] | None = None,
        liveness_model=None,
    ) -> None:
        self._insight = insightface_model
        self._faiss = faiss_manager
        # Liveness is optional. ``None`` = liveness gating disabled (the
        # tracker won't suppress recognitions on spoof verdicts and
        # broadcasts liveness_state="unknown" for every track). When set,
        # the model implements ``predict_batch(frame, bboxes) -> [dict]``
        # — both the in-process LivenessModel and RemoteLivenessModel
        # satisfy this. See app.services.ml.inference.set_liveness_model.
        self._liveness = liveness_model
        self._enrolled = enrolled_user_ids or set()
        self._name_map = name_map or {}
        # Set of user_ids whose face_embeddings include zero ``cctv_*``
        # rows — i.e. the registration is phone-side only and embeddings
        # for these users will land in the cross-domain noise band when
        # matched against classroom CCTV crops. The match path applies
        # ``RECOGNITION_PHONE_ONLY_THRESHOLD_BONUS`` to require a higher
        # score before committing a recognition for these users. The
        # set is snapshotted at session start; tracks newly enrolled
        # via ``cctv_enroll`` mid-session fall back to the standard
        # threshold only after the next session restart.
        self._phone_only: set[str] = set(phone_only_user_ids or set())
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

        # Per-(student_id-or-track, matched, ambiguous) last-submit timestamps.
        # Drives the RECOGNITION_EVIDENCE_THROTTLE_S window: repeat events
        # with the same outcome inside the window are dropped before they
        # reach the evidence writer queue, so the audit log + recognition
        # panel UI no longer fill up with 50+ near-identical crops per minute
        # of a static subject. The dict is per-tracker (and trackers are
        # per-camera-per-schedule) so each (student, camera) pair keeps its
        # own clock.
        self._evidence_last_submit: dict[tuple[str, bool, bool], float] = {}

        # ByteTrack with tuned parameters for face tracking
        self._tracker = sv.ByteTrack(
            track_activation_threshold=0.25,
            lost_track_buffer=int(settings.TRACK_LOST_TIMEOUT * settings.PROCESSING_FPS),
            minimum_matching_threshold=0.8,
            frame_rate=int(settings.PROCESSING_FPS),
        )

        # Identity cache: track_id -> TrackIdentity
        self._identity_cache: dict[int, TrackIdentity] = {}

        # Graveyard: recently-expired recognized tracks. Stores tombstones
        # used to seed a spatial+temporal identity HINT on new tracks that
        # appear in the same place soon after a recognised track died. The
        # hint lowers the FAISS commit threshold for that specific user
        # only — it never overrides FAISS top-1 and never inherits blindly,
        # so a different person walking into the same spot can never
        # accidentally take the previous identity. See
        # ``IdentityTombstone``, ``_lookup_graveyard_hint``, and the
        # IDENTITY_GRAVEYARD_* docstring in app.config for full rationale.
        self._identity_graveyard: list[IdentityTombstone] = []

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

    def process(
        self,
        frame: np.ndarray,
        rtp_pts_90k: int | None = None,
        captured_at_ms: int | None = None,
    ) -> TrackFrame:
        """Process one BGR frame: detect → track → recognize (new only).

        ``rtp_pts_90k`` is the upstream RTSP/RTP PTS captured by the
        ``FrameGrabber`` alongside this frame. It is opaque to the
        tracker — we propagate it through ``TrackFrame`` so the
        broadcaster can ship it to the admin overlay for video-aligned
        bbox rendering (live-feed plan 2026-04-25 Step 3).

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

        # Periodic mean-embedding re-validation. Runs every N frames
        # (settings.REVALIDATION_INTERVAL_FRAMES) — one batched FAISS
        # search across every currently-recognized track using the
        # mean of that track's embedding buffer rather than a single
        # noisy frame. Feeds results through the same swap-gate as a
        # regular re-verify, so stability + correctness use the same
        # rules. Cheap (~5 ms for 6 tracks) and runs before SCRFD so
        # it doesn't compete with the per-frame budget cap.
        if (
            settings.REVALIDATION_INTERVAL_FRAMES > 0
            and self._frame_counter % settings.REVALIDATION_INTERVAL_FRAMES == 0
        ):
            try:
                self._periodic_revalidation(now)
            except Exception:
                logger.debug("periodic_revalidation failed", exc_info=True)

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
                det_ms=t_det_ms,
                rtp_pts_90k=rtp_pts_90k,
                captured_at_ms=captured_at_ms,
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
                det_ms=t_det_ms,
                rtp_pts_90k=rtp_pts_90k,
                captured_at_ms=captured_at_ms,
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
        # 3a. PRE-PASS — decide which tracks need an ArcFace embedding this
        #     frame, then run them through ArcFace as ONE batched ONNX call.
        #
        #     Why: the previous design called ``embed_from_kps`` once per
        #     face inside the main loop, which serialised N forward passes
        #     and N HTTP round-trips to the sidecar. With N=4 active faces
        #     that was ~120 ms of embed work per frame on the M5 + CoreML
        #     sidecar; collapsed into a single batched call it's ~30-40 ms.
        #
        #     The decision logic must be identical to what the main loop
        #     would compute, otherwise we'd waste embeds (pre-pass too
        #     permissive) or lose recognitions (pre-pass too strict).
        #     ``_should_embed_track`` is shared by both passes. The
        #     pre-pass is read-only on identity state — no field mutations,
        #     no _get_or_create_identity (defers creation to the main loop).
        #     Per-frame reverify-cap accounting is done locally in the
        #     pre-pass; the main loop trusts the decision dict instead of
        #     recomputing.
        # ------------------------------------------------------------------
        prepass_decisions: dict[int, dict] = {}
        pending_kps_list: list[np.ndarray] = []
        pending_track_ids: list[int] = []
        # Parallel array of bboxes for the same set of tracks — fed to the
        # liveness batch right after embed. Captured here (instead of being
        # re-derived from track_id → identity) so the bbox seen by liveness
        # is the SCRFD pixel-space bbox for THIS frame, not a stale cache.
        pending_bboxes_list: list[tuple[int, int, int, int]] = []
        adaptive_reverify_interval = self._compute_adaptive_reverify_interval(tracked)

        # Per-frame budget caps. Reverify cap was already in place; the
        # first-recognition cap is the 40+ faces guardrail — without it
        # a 30-student "everyone walks in together" wave would queue 30
        # ArcFace passes in one frame and crater the live overlay's fps
        # for ~half a second.
        max_first_rec = max(1, int(settings.MAX_FIRST_RECOGNITIONS_PER_FRAME))
        prepass_reverify_count = 0
        prepass_first_rec_count = 0
        for i, track_id in enumerate(tracked.tracker_id):
            track_id = int(track_id)
            kps = track_kps.get(track_id)
            bbox = tracked.xyxy[i]

            decision = self._should_embed_track(
                track_id=track_id,
                bbox=bbox,
                kps=kps,
                frame=frame,
                now=now,
                reverify_interval=adaptive_reverify_interval,
                reverify_count_so_far=prepass_reverify_count,
            )

            # First-recognition cap. Pending tracks above the per-frame
            # budget get deferred to a later frame — their decision flips
            # to "no embed this frame" so the main loop won't try to
            # consume an embedding that doesn't exist. Track is created
            # normally; it just stays in "warming_up" one extra frame.
            if (
                decision["needs_recognition"]
                and decision["quality_passed"]
                and decision.get("is_first_recognition")
                and prepass_first_rec_count >= max_first_rec
            ):
                decision = dict(decision)
                decision["needs_recognition"] = False
                decision["quality_passed"] = False

            prepass_decisions[track_id] = decision

            if decision["needs_recognition"] and decision.get("is_reverify"):
                prepass_reverify_count += 1
            if (
                decision["needs_recognition"]
                and decision.get("is_first_recognition")
            ):
                prepass_first_rec_count += 1

            if decision["needs_recognition"] and decision["quality_passed"] and kps is not None:
                pending_kps_list.append(kps)
                pending_track_ids.append(track_id)
                # Bbox in frame pixel coords — same source the embed call
                # uses, so liveness sees exactly what ArcFace sees.
                pending_bboxes_list.append((
                    int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]),
                ))

        # ------------------------------------------------------------------
        # 3b. BATCH EMBED — one ArcFace forward pass for everyone who needs
        #     one this frame. On the sidecar path this is also one HTTP
        #     round-trip (one JPEG encode + one POST instead of N).
        # ------------------------------------------------------------------
        embeddings_by_track: dict[int, np.ndarray] = {}
        t_embed_total_ms = 0.0
        if pending_kps_list:
            emb_t0 = time.monotonic()
            try:
                embs = self._insight.embed_from_kps_batch(frame, pending_kps_list)
                if embs.shape[0] != len(pending_track_ids):
                    raise RuntimeError(
                        f"embed batch size mismatch: got {embs.shape[0]}, expected {len(pending_track_ids)}"
                    )
                for tid, emb in zip(pending_track_ids, embs):
                    # Treat all-zero rows (degenerate alignment) as "no embed"
                    if float(np.linalg.norm(emb)) < 1e-6:
                        continue
                    embeddings_by_track[tid] = emb
            except Exception as exc:
                # Fallback: per-face embed if the batched call failed (sidecar
                # restart, network blip, ORT error). One bad batch should not
                # blank the whole frame's overlays — fall through and let any
                # successful single-face calls still light up.
                logger.warning(
                    "Batched embed failed (n=%d): %s; falling back to per-face",
                    len(pending_kps_list), exc,
                )
                for tid, kps in zip(pending_track_ids, pending_kps_list):
                    try:
                        embeddings_by_track[tid] = self._insight.embed_from_kps(frame, kps)
                    except Exception:
                        logger.debug(
                            "Per-face embed fallback also failed for track %d", tid,
                            exc_info=True,
                        )
            t_embed_total_ms = (time.monotonic() - emb_t0) * 1000.0

        # ------------------------------------------------------------------
        # 3a-bis. BATCH LIVENESS — passive presentation-attack detection.
        #
        #     Runs on the same set of tracks the embed batch covered, so
        #     liveness sees exactly the faces ArcFace is about to bind. We
        #     piggy-back on the embed cadence rather than maintaining a
        #     parallel "needs liveness now?" pre-pass — the worst case is
        #     that a track gets liveness-checked more often than
        #     LIVENESS_RECHECK_INTERVAL_S would strictly require, which is
        #     conservative (more spoof protection, not less).
        #
        #     Per-track gating (LIVENESS_RECHECK_INTERVAL_S) further trims
        #     the call to only the tracks that actually need a fresh check.
        #     A new track is always checked. A suppressed track is also
        #     always re-checked so it has a chance to recover.
        #
        #     Failure policy: any exception from the call (sidecar down,
        #     network blip, missing pack) is logged once at debug level
        #     and the loop proceeds — every track keeps its previous
        #     liveness state. Recognition is NOT held up by a flaky
        #     liveness layer; spoof gating reverts to "no gate this frame".
        # ------------------------------------------------------------------
        if (
            self._liveness is not None
            and settings.LIVENESS_ENABLED
            and pending_track_ids
        ):
            self._run_liveness_batch(
                frame=frame,
                pending_track_ids=pending_track_ids,
                pending_bboxes_list=pending_bboxes_list,
                now=now,
            )

        # ------------------------------------------------------------------
        # 3. Per-track state update + recognition decisions (using the
        #    pre-computed batched embeddings).
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
        embeddings_computed = len(embeddings_by_track)

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

            # -------- Decision + embedding lookup (computed in pre-pass) --------
            #
            # The pre-pass (above) ran ``_should_embed_track`` for every
            # detection in this frame and made one batched ArcFace call for
            # all the qualifying ones. We just consume that decision here —
            # ``embeddings_by_track[track_id]`` is set iff the pre-pass
            # decided to embed AND the batch call succeeded for this row.
            decision = prepass_decisions.get(track_id, {})
            is_first_recognition = decision.get("is_first_recognition", identity.recognition_status == "pending")
            needs_recognition = decision.get("needs_recognition", False)

            embedding = embeddings_by_track.get(track_id)
            quality_passed = embedding is not None

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
                        l_state, l_score = self._liveness_fields(identity)
                        results.append(TrackResult(
                            track_id=track_id, bbox=norm_bbox, velocity=velocity,
                            user_id=d_uid, name=d_name, confidence=d_conf,
                            status=d_status, is_active=True,
                            recognition_state=d_state,
                            liveness_state=l_state, liveness_score=l_score,
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
                #
                # Margin + upscale (added 2026-04-25): the previous code did
                # a tight bbox-only crop, which produced ~60×80 px crops on
                # classroom-distance faces. Once scaled into the recognition
                # stream panel UI those rendered as mush. We now expand the
                # crop by EVIDENCE_CROP_MARGIN_PCT (default 35 %), then
                # upscale tiny results to a long-edge target so the panel
                # always renders sharp. Operates on the source frame so the
                # crop is the highest-fidelity copy we have access to.
                x1f, y1f, x2f, y2f = (float(v) for v in bbox)
                bw = x2f - x1f
                bh = y2f - y1f
                margin = settings.EVIDENCE_CROP_MARGIN_PCT
                x1p = max(0, int(x1f - margin * bw))
                y1p = max(0, int(y1f - margin * bh))
                x2p = min(self._frame_w, int(x2f + margin * bw))
                y2p = min(self._frame_h, int(y2f + margin * bh))
                live_crop_np = frame[y1p:y2p, x1p:x2p]
                # Fallback: skip the evidence row if the crop collapsed to
                # zero area — we'd have nothing to store.
                if live_crop_np.size == 0:
                    continue
                # Upscale-to-target so the recognition panel UI doesn't
                # render a 60-px crop scaled 4× into a 240-px box (which
                # is what produced the "blurred face" complaint on
                # 2026-04-25). cv2.resize with INTER_CUBIC produces a
                # noticeably sharper upscale than the browser's CSS
                # bilinear scaling.
                target = settings.EVIDENCE_CROP_TARGET_LONG_EDGE
                ch, cw = live_crop_np.shape[:2]
                long_edge = max(ch, cw)
                if 0 < long_edge < target:
                    scale = target / float(long_edge)
                    new_size = (max(1, int(cw * scale)), max(1, int(ch * scale)))
                    live_crop_np = cv2.resize(live_crop_np, new_size, interpolation=cv2.INTER_CUBIC)
                else:
                    # Copy to decouple from the frame buffer; the evidence
                    # writer may JPEG-encode this after a brief queue wait.
                    live_crop_np = live_crop_np.copy()
                det_score = 0.0
                try:
                    det_score = float(tracked.confidence[i])
                except Exception:
                    det_score = 0.0
                bbox_px = [int(x1p), int(y1p), int(x2p), int(y2p)]
                # Liveness gate: a track currently flagged as a confirmed
                # spoof (debounced via LIVENESS_SPOOF_CONSECUTIVE) is NOT
                # asked for a FAISS recognition. The bbox still appears in
                # the broadcast (operator sees the detection) but no
                # identity is bound, so attendance + presence are not
                # credited. The liveness layer will keep re-checking on
                # subsequent frames; once it produces
                # LIVENESS_REAL_RECOVERY_FRAMES consecutive "real"
                # verdicts, suppression clears and recognition resumes.
                if identity.liveness_suppressed:
                    continue
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
            l_state, l_score = self._liveness_fields(identity)

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
                    liveness_state=l_state,
                    liveness_score=l_score,
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
            l_state, l_score = self._liveness_fields(identity)

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
                    liveness_state=l_state,
                    liveness_score=l_score,
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
                    l_state, l_score = self._liveness_fields(self._identity_cache.get(r.track_id))
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
                        liveness_state=l_state,
                        liveness_score=l_score,
                    ))
                else:
                    updated.append(r)
            results = updated

        # 7. Cross-batch user_id mutual exclusion — defensive belt for the
        # cases the in-batch frame-mutex (Phase 3 of _recognize_batch) can't
        # see. Two scenarios reach this layer:
        #   (a) one track is currently in the batch (re-verifying) and the
        #       other is coasting on a cached binding — only the coasting
        #       track is in `results` without having gone through the
        #       Hungarian step.
        #   (b) ``RECOGNITION_FRAME_MUTEX_ENABLED`` is False (operator
        #       override) and the in-batch resolver is bypassed.
        # Original behaviour was to *drop* the loser's track from
        # ``results`` entirely, which made one of the two boxes vanish
        # from the live overlay. We keep the box but null out the
        # identity (overlay shows "Detecting…") so the operator still
        # sees both faces tracked while attendance only counts one.
        seen_users: dict[str, int] = {}
        deduped_results: list[TrackResult] = []
        for r in results:
            if r.user_id and r.user_id in seen_users:
                existing_idx = seen_users[r.user_id]
                existing = deduped_results[existing_idx]
                if r.confidence > existing.confidence:
                    # Current row wins — demote the previous holder to
                    # warming_up. We rebuild it as a frozen TrackResult
                    # rather than mutating in place (TrackResult is
                    # immutable by design). Liveness state stays with
                    # the demoted track — its liveness verdict is
                    # independent of which user_id won the dedup.
                    deduped_results[existing_idx] = TrackResult(
                        track_id=existing.track_id,
                        bbox=existing.bbox,
                        velocity=existing.velocity,
                        user_id=None,
                        name=None,
                        confidence=0.0,
                        status="pending",
                        is_active=existing.is_active,
                        recognition_state="warming_up",
                        liveness_state=existing.liveness_state,
                        liveness_score=existing.liveness_score,
                    )
                    seen_users[r.user_id] = len(deduped_results)
                    deduped_results.append(r)
                else:
                    # Existing keeps the user; current row demotes.
                    deduped_results.append(TrackResult(
                        track_id=r.track_id,
                        bbox=r.bbox,
                        velocity=r.velocity,
                        user_id=None,
                        name=None,
                        confidence=0.0,
                        status="pending",
                        is_active=r.is_active,
                        recognition_state="warming_up",
                        liveness_state=r.liveness_state,
                        liveness_score=r.liveness_score,
                    ))
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
            det_ms=t_det_ms,
            embed_ms=t_embed_total_ms,
            faiss_ms=t_faiss_ms,
            rtp_pts_90k=rtp_pts_90k,
            captured_at_ms=captured_at_ms,
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
        # Also clear the evidence throttle ledger so the first event of a
        # new session always fires (even if the same student was throttled
        # 1 s before the previous session ended).
        self._evidence_last_submit.clear()

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

        Oscillation suppressor: when this track has been flapping between
        identities (see ``_maybe_arm_oscillation_suppressor``), we surface
        ``recognition_state="warming_up"`` with no user_id/name until the
        cooldown expires. The track's internal binding is preserved (so
        attendance + presence keep updating) — we just refuse to commit to
        either name on the visible overlay during the noisy window.
        """
        identity = self._identity_cache[track_id]
        if (
            identity.oscillation_uncertain_until > 0.0
            and now < identity.oscillation_uncertain_until
        ):
            return (
                None,
                None,
                identity.confidence,
                "pending",
                "warming_up",
            )
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
        recognition_state = self._derive_recognition_state(identity, now=now)
        return (
            identity.user_id,
            identity.name,
            identity.confidence,
            identity.recognition_status,
            recognition_state,
        )

    @staticmethod
    def _derive_recognition_state(identity: TrackIdentity, now: float | None = None) -> str:
        """Collapse the tracker's internal bookkeeping into a three-value signal
        for the overlay: ``"recognized"`` | ``"warming_up"`` | ``"unknown"``.

        Rules (evaluated top to bottom):

        1. ``recognition_status == "recognized"`` → ``"recognized"``.
        2. Wall-clock ceiling: a track that has been visible for more than
           ``MAX_WARMING_UP_SECONDS`` and is still not recognised commits to
           ``"unknown"`` regardless of score. Without this the
           "stay-in-warming-up if best score is near threshold" rule below
           had no upper bound — a track whose best sim sat in the dead
           zone between ``score_ceiling`` and ``RECOGNITION_THRESHOLD``
           (typically a 5-pt window) stayed blue forever. The 2026-04-25
           "stuck Detecting" UX bug was exactly this case.
        3. The track has been FAISS-rejected at least ``UNKNOWN_CONFIRM_ATTEMPTS``
           times **and** its best-seen cosine score is comfortably below
           ``RECOGNITION_THRESHOLD - UNKNOWN_CONFIRM_MARGIN`` → ``"unknown"``.
           Both clauses matter: a face hovering near threshold (e.g. peak 0.36 with
           threshold 0.38) stays in ``"warming_up"`` longer on the theory that a
           cleaner frame is likely imminent, while a face that has never produced a
           score above, say, 0.20 is clearly not enrolled and earns the red label
           quickly.
        4. Everything else (including fresh ``"pending"`` tracks and ``"unknown"``
           tracks still inside the confirm window) → ``"warming_up"`` so the
           overlay renders the neutral "Detecting…" label.
        """
        if identity.recognition_status == "recognized":
            return "recognized"
        confirm_attempts = settings.UNKNOWN_CONFIRM_ATTEMPTS
        score_ceiling = settings.RECOGNITION_THRESHOLD - settings.UNKNOWN_CONFIRM_MARGIN

        # Wall-clock ceiling on warming_up. Kicks in regardless of score so
        # the dead zone between score_ceiling and RECOGNITION_THRESHOLD
        # can't trap a track in "Detecting…" forever. ``now`` is optional
        # for backwards compatibility with callers (tests etc.) that
        # didn't pass it; in that case the ceiling is skipped and behaviour
        # falls back to the score-based gates below.
        if (
            now is not None
            and identity.first_seen > 0.0
            and (now - identity.first_seen) > settings.MAX_WARMING_UP_SECONDS
        ):
            return "unknown"

        # Fast-commit path for obvious unknowns (added 2026-04-25). A face
        # whose peak similarity has stayed below
        # ``UNKNOWN_FAST_COMMIT_SCORE`` (default 0.10) for at least
        # ``UNKNOWN_FAST_COMMIT_ATTEMPTS`` frames is clearly not enrolled
        # — flip to red immediately rather than make the operator wait the
        # full UNKNOWN_CONFIRM_ATTEMPTS window. See config.py for rationale.
        if (
            identity.unknown_attempts >= settings.UNKNOWN_FAST_COMMIT_ATTEMPTS
            and identity.best_score_seen < settings.UNKNOWN_FAST_COMMIT_SCORE
        ):
            return "unknown"

        if (
            identity.unknown_attempts >= confirm_attempts
            and identity.best_score_seen < score_ceiling
        ):
            return "unknown"
        return "warming_up"

    @staticmethod
    def _liveness_fields(identity: TrackIdentity | None) -> tuple[str, float]:
        """Map per-track liveness bookkeeping → (state, score) for the broadcast.

        States:
          * ``"spoof"`` — track is currently suppressed (debounce satisfied).
            Overlay should render the bbox in spoof colours regardless of
            ``recognition_state``. This is the gate the front-end keys off
            of for the "Spoof detected" label.
          * ``"real"`` — most recent verdict was real; track is not
            suppressed. Overlay renders normally.
          * ``"unknown"`` — never checked yet, or in the middle of debounce
            (e.g. saw one spoof but not enough to flip suppression). We
            don't expose mid-debounce verdicts to the client to avoid
            "spoof flicker" — the streak counters are the smoothing.
        """
        if identity is None:
            return ("unknown", 0.0)
        if identity.liveness_suppressed:
            return ("spoof", float(identity.liveness_score))
        if identity.liveness_label == "real":
            return ("real", float(identity.liveness_score))
        return ("unknown", float(identity.liveness_score))

    def _run_liveness_batch(
        self,
        *,
        frame: np.ndarray,
        pending_track_ids: list[int],
        pending_bboxes_list: list[tuple[int, int, int, int]],
        now: float,
    ) -> None:
        """Run a fused-MiniFASNet liveness probe on a subset of this frame's
        tracks and update each ``TrackIdentity``'s spoof bookkeeping.

        Side-effects only — returns nothing. The per-track flags are read by
        ``_get_display_identity`` (for the broadcast) and by the recognition
        gate (to suppress identity binding on spoof verdicts).

        Selection:
          * A track is checked iff it appears in ``pending_track_ids`` AND
            (it has never been checked OR last check is older than
            ``LIVENESS_RECHECK_INTERVAL_S`` OR it's currently suppressed —
            we keep checking suppressed tracks so a real student briefly
            misclassified can recover).
          * The per-frame budget cap (``LIVENESS_MAX_PER_FRAME``) trims
            the call list deterministically — first N tracks in the
            pending order — so the liveness layer can't blow the per-frame
            sidecar budget when 30+ students walk in at once.

        Failure handling:
          One try/except wraps the whole batch. A sidecar miss leaves
          identity state untouched (no gate is applied this frame).
        """
        if self._liveness is None or not pending_track_ids:
            return

        recheck_interval = float(settings.LIVENESS_RECHECK_INTERVAL_S)
        max_per_frame = max(1, int(settings.LIVENESS_MAX_PER_FRAME))

        eligible_tids: list[int] = []
        eligible_bboxes: list[tuple[int, int, int, int]] = []
        for tid, bbox in zip(pending_track_ids, pending_bboxes_list):
            identity = self._identity_cache.get(tid)
            if identity is None:
                # New track — check on first frame regardless of cadence
                eligible_tids.append(tid)
                eligible_bboxes.append(bbox)
                continue
            stale = (now - identity.liveness_last_check) >= recheck_interval
            if stale or identity.liveness_suppressed or identity.liveness_label == "unknown":
                eligible_tids.append(tid)
                eligible_bboxes.append(bbox)
            if len(eligible_tids) >= max_per_frame:
                break
        if not eligible_tids:
            return

        try:
            preds = self._liveness.predict_batch(frame, eligible_bboxes)
        except Exception as exc:
            logger.debug("Liveness batch failed (n=%d): %s", len(eligible_tids), exc)
            return

        if len(preds) != len(eligible_tids):
            logger.warning(
                "Liveness predictions count mismatch: got %d, expected %d",
                len(preds), len(eligible_tids),
            )
            return

        threshold = float(settings.LIVENESS_REAL_THRESHOLD)
        spoof_streak_required = max(1, int(settings.LIVENESS_SPOOF_CONSECUTIVE))
        real_recovery_required = max(1, int(settings.LIVENESS_REAL_RECOVERY_FRAMES))

        for tid, pred in zip(eligible_tids, preds):
            identity = self._identity_cache.get(tid)
            if identity is None:
                # Track's TrackIdentity hasn't been created yet — happens
                # when the very first frame for a track makes it through
                # the embed batch but the per-track loop (where the
                # identity is created) hasn't executed yet. Skip; the
                # next liveness batch will catch it. Recognition can't
                # commit on this frame anyway because the per-track loop
                # also requires the embedding buffer to fill.
                continue
            score = (
                float(pred.get("score", 0.0))
                if isinstance(pred, dict)
                else float(getattr(pred, "score", 0.0))
            )
            label = (
                str(pred.get("label", "unknown"))
                if isinstance(pred, dict)
                else str(getattr(pred, "label", "unknown"))
            )
            self._apply_liveness_verdict(
                identity=identity,
                score=score,
                label=label,
                now=now,
                threshold=threshold,
                spoof_streak_required=spoof_streak_required,
                real_recovery_required=real_recovery_required,
            )

    @staticmethod
    def _apply_liveness_verdict(
        *,
        identity: TrackIdentity,
        score: float,
        label: str,
        now: float,
        threshold: float,
        spoof_streak_required: int,
        real_recovery_required: int,
    ) -> None:
        """Fold one liveness verdict into a TrackIdentity's debounced state.

        Spoof flips suppression on after ``spoof_streak_required`` consecutive
        spoof verdicts. Real flips suppression off after
        ``real_recovery_required`` consecutive real verdicts. A single noise
        event can never flip the broadcast — the streak counters are the
        debounce.

        Reset semantics: a real verdict clears ``liveness_spoof_streak``;
        a spoof verdict clears ``liveness_real_streak``. So the counters
        track "how many in a row of THIS class", not "how many seen ever".
        """
        identity.liveness_score = score
        identity.liveness_label = label
        identity.liveness_last_check = now
        if label == "spoof" or score < threshold:
            identity.liveness_spoof_streak += 1
            identity.liveness_real_streak = 0
            if identity.liveness_spoof_streak >= spoof_streak_required:
                identity.liveness_suppressed = True
        else:
            identity.liveness_real_streak += 1
            identity.liveness_spoof_streak = 0
            if (
                identity.liveness_suppressed
                and identity.liveness_real_streak >= real_recovery_required
            ):
                identity.liveness_suppressed = False

    def _compute_adaptive_reverify_interval(self, tracked) -> float:
        """Scale REVERIFY_INTERVAL up when many tracks are present.

        Re-verifying every ``REVERIFY_INTERVAL`` seconds is fine for a
        small classroom but burns embed budget when N grows. This keeps
        the per-frame embed work roughly bounded:

          effective = REVERIFY_INTERVAL × max(1.0, N / N_baseline)

        At ``N_baseline=5`` (typical classroom), the interval is the
        configured value. At N=10 it doubles. At N=20 it quadruples.
        Re-verification is purely an identity-drift safety net — slowing
        it down only delays the *detection* of an identity swap, never
        the initial recognition (first-recognition is uncapped).
        """
        n_tracks = len(tracked.tracker_id) if tracked is not None else 0
        baseline = max(1.0, float(settings.ADAPTIVE_REVERIFY_BASELINE_TRACKS))
        scale = max(1.0, n_tracks / baseline)
        return float(settings.REVERIFY_INTERVAL) * scale

    def _should_embed_track(
        self,
        *,
        track_id: int,
        bbox: np.ndarray,
        kps: np.ndarray | None,
        frame: np.ndarray,
        now: float,
        reverify_interval: float,
        reverify_count_so_far: int,
    ) -> dict:
        """Read-only decision: would this track need an ArcFace embed now?

        Mirrors the legacy in-loop decision so the pre-pass and main loop
        agree exactly. Returns a dict the caller can stash in
        ``prepass_decisions[track_id]`` and consult inside the main loop
        instead of recomputing.

        Returns:
            ``{"needs_recognition": bool, "quality_passed": bool,
               "is_first_recognition": bool, "is_reverify": bool}``
        """
        # No keypoints means we cannot align — never embed.
        if kps is None:
            return {
                "needs_recognition": False,
                "quality_passed": False,
                "is_first_recognition": False,
                "is_reverify": False,
            }

        identity = self._identity_cache.get(track_id)
        # New track: identity will be created in the main loop. Treat as
        # first-recognition with quality bypassed so the first frame gets
        # one shot at FAISS — same behaviour the old in-loop logic had.
        if identity is None:
            return {
                "needs_recognition": True,
                "quality_passed": True,
                "is_first_recognition": True,
                "is_reverify": False,
            }

        is_first_recognition = identity.recognition_status == "pending"

        # Decision tree — must match the order of the original in-loop logic.
        if identity.is_static:
            needs_recognition = False
        elif is_first_recognition:
            needs_recognition = True
        elif identity.recognition_status == "unknown":
            age = now - identity.first_seen
            if age < 1.0:
                retry_interval = 0.0
            elif age < 5.0:
                retry_interval = 0.3
            else:
                retry_interval = 1.0
            needs_recognition = (now - identity.last_verified) > retry_interval
        else:
            # Recognised track — drift-aware periodic re-verify.
            if identity.last_drift_time > 0 and (now - identity.last_drift_time) < 3.0:
                effective_interval = 1.0
            else:
                effective_interval = reverify_interval
            needs_recognition = (now - identity.last_verified) > effective_interval

        # Re-verify cap: pending/unknown tracks are uncapped (must be
        # recognised ASAP); recognised re-verifies share a per-frame budget.
        is_reverify = needs_recognition and identity.recognition_status == "recognized"
        if is_reverify and reverify_count_so_far >= MAX_REVERIFIES_PER_FRAME:
            needs_recognition = False
            is_reverify = False

        # Quality gate — bypass for pending tracks (warming-up logic
        # downstream tolerates a noisy first frame). For everything else,
        # check the bbox crop for blur/brightness/size before paying the
        # ArcFace cost.
        quality_passed = False
        if needs_recognition:
            if is_first_recognition:
                quality_passed = True
            else:
                x1p, y1p, x2p, y2p = bbox.astype(int)
                x1p, y1p = max(0, x1p), max(0, y1p)
                x2p, y2p = min(self._frame_w, x2p), min(self._frame_h, y2p)
                crop = frame[y1p:y2p, x1p:x2p]
                if crop.size > 0:
                    quality_passed, _ = assess_recognition_quality(crop)

        return {
            "needs_recognition": needs_recognition,
            "quality_passed": quality_passed,
            "is_first_recognition": is_first_recognition,
            "is_reverify": is_reverify,
        }

    def _get_or_create_identity(self, track_id: int, now: float, bbox: np.ndarray | None = None) -> TrackIdentity:
        """Get existing identity or create a new one (always goes through FAISS).

        We NEVER blindly inherit identity from the graveyard. The new track
        is always created with a clean ``recognition_status='pending'`` and
        must earn its identity through FAISS. What the graveyard CAN do is
        seed a *hint* on the new identity — when there's exactly one
        recently-expired recognised track in spatial proximity, the new
        track gets ``hint_user_id`` set to that user. The hint then lowers
        the FAISS commit threshold ONLY for that specific user_id, only if
        FAISS independently returns the hint user as top-1. So if a
        different person walks into the same spot, FAISS top-1 is someone
        else and the hint is silently discarded — never inherited blindly.
        """
        if track_id not in self._identity_cache:
            jitter = random.uniform(0, settings.REVERIFY_INTERVAL)
            ident = TrackIdentity(
                track_id=track_id,
                first_seen=now,
                last_seen=now,
                last_verified=now - jitter,
            )

            # Spatial+temporal identity hint. Only fires when bbox is
            # provided AND exactly one tombstone is in proximity (see
            # _lookup_graveyard_hint safety logic).
            if bbox is not None and self._frame_w > 0 and self._frame_h > 0:
                bbox_norm = [
                    float(bbox[0]) / self._frame_w,
                    float(bbox[1]) / self._frame_h,
                    float(bbox[2]) / self._frame_w,
                    float(bbox[3]) / self._frame_h,
                ]
                tomb = self._lookup_graveyard_hint(bbox_norm, now)
                if tomb is not None:
                    ident.hint_user_id = tomb.user_id
                    ident.hint_user_name = tomb.name
                    ident.hint_set_at = now
                    self._consume_tombstone(tomb)
                    logger.info(
                        "Track %d created with identity hint user=%s name=%s "
                        "(tombstone aged %.1fs at center (%.2f, %.2f))",
                        track_id,
                        tomb.user_id[:8],
                        tomb.name,
                        now - tomb.expired_at,
                        tomb.bbox_center[0],
                        tomb.bbox_center[1],
                    )

            self._identity_cache[track_id] = ident
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

        Multi-phase resolver pipeline (added 2026-04-25 to close the
        identity-swap class of bugs that surfaced during the live EB227
        sessions where two near-threshold tracks would trade labels every
        reverify):

          Phase 1 — gather: compute one ``_BatchDecision`` per track from
            the FAISS result + spatial-graveyard hint rescue + name lookup.
            **No identity-cache mutation here.** Decisions are tentative.
          Phase 2 — swap-gate: per-track vote-based filter. A FAISS result
            naming a different user than the current binding only commits
            when both the ``RECOGNITION_SWAP_MARGIN`` (cosine delta) and
            ``RECOGNITION_SWAP_MIN_STREAK`` (consecutive frames) gates pass.
            A blocked swap reverts ``decision.user_id`` to the incumbent so
            the rest of the pipeline sees a stable target.
          Phase 3 — frame-mutex: when two tracks in the same frame both
            target the same ``user_id``, solve as a Hungarian bipartite
            assignment over (track × {top-1, top-2}) so each user is bound
            to at most one track. The loser falls back to its top-2 if
            that clears threshold; otherwise its binding is cleared and
            the overlay shows "Detecting…" rather than committing to a
            wrong-name green box.
          Phase 4 — commit: apply the resolved decision to the identity
            cache, update swap history (drives the oscillation suppressor
            in ``_derive_recognition_state``), and submit the recognition
            event to the evidence writer.

        Each phase is a separate helper so the flow stays auditable.
        """
        if not pending:
            return

        # ----- Phase 1: FAISS batch + tentative decisions -----
        stacked = np.stack([emb for _, emb, _, _, _ in pending]).astype(np.float32)
        batch_results = self._faiss.search_batch_with_margin(stacked)
        decisions = self._gather_decisions(pending, batch_results, now)

        # ----- Phase 2: per-track swap-gate (vote-based) -----
        for d in decisions:
            self._apply_swap_gate(d, now)

        # ----- Phase 3: frame-level mutual exclusion (Hungarian) -----
        if settings.RECOGNITION_FRAME_MUTEX_ENABLED:
            self._resolve_frame_mutex(decisions)

        # ----- Phase 4: mutate identity state + submit evidence -----
        for d in decisions:
            self._commit_decision(d, now)

    def _gather_decisions(
        self,
        pending: list[tuple[TrackIdentity, np.ndarray, np.ndarray, float, list[int]]],
        batch_results: list[dict],
        now: float,
    ) -> list[_BatchDecision]:
        """Phase 1 — assemble one ``_BatchDecision`` per pending track.

        Hint-rescue is applied here (it shapes the tentative ``user_id``)
        but identity-state mutation is deferred to Phase 4. The only
        identity field touched in this phase is ``best_score_seen``,
        which is read-only for the rest of the pipeline so updating it
        eagerly is safe.
        """
        decisions: list[_BatchDecision] = []
        for (identity, search_embedding, live_crop_np, det_score, bbox_px), result in zip(
            pending, batch_results
        ):
            user_id = result.get("user_id")
            confidence = float(result.get("confidence", 0.0))
            is_ambiguous = bool(result.get("is_ambiguous", False))
            top1_user_id = result.get("top1_user_id")
            top1_score = float(result.get("top1_score", 0.0))
            top2_user_id = result.get("top2_user_id")
            top2_score = float(result.get("top2_score", 0.0))

            # Track the lifetime peak so the "warming_up" gate in
            # _derive_recognition_state stays meaningful even when the
            # current frame's score is low.
            if confidence > identity.best_score_seen:
                identity.best_score_seen = confidence

            # ----- Spatial+temporal identity hint rescue --------------
            # A new track that inherited a hint from the graveyard
            # (someone recently recognised left this spot, came back)
            # gets a relaxed commit threshold for ONLY that user_id.
            # Same safety guard as before: top-1 must equal the hint
            # user AND clear the relaxed threshold; otherwise the hint
            # is silently discarded.
            if (
                user_id is None
                and identity.hint_user_id is not None
                and top1_user_id is not None
                and settings.IDENTITY_GRAVEYARD_TTL_SECONDS > 0
            ):
                relaxed_threshold = (
                    settings.RECOGNITION_THRESHOLD
                    - settings.IDENTITY_GRAVEYARD_RELAXED_THRESHOLD_DELTA
                )
                if top1_user_id == identity.hint_user_id and top1_score >= relaxed_threshold:
                    logger.info(
                        "Track %d HINT-RESCUED: %s at sim %.3f (relaxed thr %.2f, full thr %.2f)",
                        identity.track_id,
                        identity.hint_user_name or top1_user_id[:8],
                        top1_score,
                        relaxed_threshold,
                        settings.RECOGNITION_THRESHOLD,
                    )
                    user_id = top1_user_id
                    confidence = top1_score
                    is_ambiguous = False
                    identity.hint_user_id = None
                    identity.hint_user_name = None
                else:
                    if top1_user_id != identity.hint_user_id:
                        logger.debug(
                            "Track %d hint discarded: top1=%s != hint=%s",
                            identity.track_id,
                            top1_user_id[:8] if top1_user_id else "NONE",
                            identity.hint_user_id[:8],
                        )
                        identity.hint_user_id = None
                        identity.hint_user_name = None

            # Phone-only stricter threshold. A user with no ``cctv_*``
            # embeddings is recognising entirely off cross-domain phone
            # selfie data — its score distribution sits inside the
            # noise band where two students can trade scores frame to
            # frame. We refuse to commit until the score clears
            # ``RECOGNITION_THRESHOLD + RECOGNITION_PHONE_ONLY_THRESHOLD_BONUS``,
            # so the overlay shows "Detecting…" rather than a possibly-
            # wrong name. The track keeps tracking spatially via
            # ByteTrack — recognition just stays withheld until the
            # student is CCTV-enrolled.
            #
            # Applied AFTER the standard ambiguity check so a user_id
            # cleared by the FAISS-side margin gate cannot leak through.
            # Applied to the standard match (user_id) only — the raw
            # top1_user_id is left untouched so the graveyard hint
            # rescue can still fire on its own relaxed-threshold path.
            phone_only_bonus = settings.RECOGNITION_PHONE_ONLY_THRESHOLD_BONUS
            if (
                user_id is not None
                and phone_only_bonus > 0.0
                and user_id in self._phone_only
            ):
                strict_threshold = settings.RECOGNITION_THRESHOLD + phone_only_bonus
                if confidence < strict_threshold:
                    logger.info(
                        "Track %d phone-only gate: %s sim=%.3f < strict=%.2f (raise via cctv_enroll)",
                        identity.track_id,
                        user_id[:8],
                        confidence,
                        strict_threshold,
                    )
                    user_id = None
                    is_ambiguous = True  # Surface as a miss, not a match
                    # confidence kept for diagnostics; not used downstream
                    # for binding because user_id is now None.

            # Resolve display name. A FAISS hit whose user_id no longer
            # exists in the DB is a stale/orphaned vector — treat it as
            # a miss so the track never displays a green box for a
            # user_id we can't render.
            resolved_name: str | None = None
            if user_id is not None:
                resolved_name = self._resolve_name(user_id)
                if resolved_name is None:
                    logger.warning(
                        "Track %d FAISS hit user_id=%s not in DB (orphaned embedding?)",
                        identity.track_id,
                        user_id[:8],
                    )
                    user_id = None

            logger.debug(
                "[TRACK-SCORE] track=%d user=%s confidence=%.4f ambiguous=%s",
                identity.track_id,
                user_id[:8] if user_id else "NONE",
                confidence,
                is_ambiguous,
            )

            decisions.append(_BatchDecision(
                identity=identity,
                search_embedding=search_embedding,
                live_crop=live_crop_np,
                det_score=det_score,
                bbox_px=bbox_px,
                user_id=user_id,
                confidence=confidence,
                is_ambiguous=is_ambiguous,
                resolved_name=resolved_name,
                top1_user_id=top1_user_id,
                top1_score=top1_score,
                top2_user_id=top2_user_id,
                top2_score=top2_score,
            ))
        return decisions

    def _apply_swap_gate(self, d: _BatchDecision, now: float) -> None:
        """Phase 2 — vote-based swap rejection for an incumbent track.

        Only fires when the track is already ``recognized`` AND the
        FAISS result names a *different* user. Otherwise the decision
        is a confirmation (or a brand-new recognition) and passes through
        untouched.

        The streak counter advances when consecutive frames sustain the
        candidate user; any frame where the incumbent comes back as
        top-1 (or a third user appears, or the score dips below the
        margin) clears the candidate. The swap commits only when the
        streak reaches ``RECOGNITION_SWAP_MIN_STREAK``. While the streak
        is below threshold, ``decision.user_id`` is rewritten back to
        the incumbent so Phases 3 + 4 see a stable target.

        This does NOT prevent recognition of a different user on a
        ``pending``/``unknown`` track — those still take the FAISS top-1
        immediately because there is no incumbent to protect.
        """
        identity = d.identity
        prev_user_id = identity.user_id
        is_potential_swap = (
            d.user_id is not None
            and prev_user_id is not None
            and prev_user_id != d.user_id
            and identity.recognition_status == "recognized"
        )
        if not is_potential_swap:
            # No swap to gate. If the FAISS top-1 came back as the
            # incumbent, clear any in-flight candidate so an old
            # candidate doesn't survive across a sane re-confirmation.
            if d.user_id == prev_user_id:
                identity.swap_candidate_user_id = None
                identity.swap_candidate_streak = 0
                identity.swap_candidate_best_conf = 0.0
            return

        # Cosine-margin gate — must be meaningfully higher than the
        # current binding before we even consider voting on the swap.
        margin = settings.RECOGNITION_SWAP_MARGIN
        if d.confidence < identity.confidence + margin:
            # Below margin — keep incumbent and reset any in-flight
            # candidate (the candidate streak only counts frames where
            # the margin gate also passed).
            if identity.swap_candidate_user_id is not None:
                logger.debug(
                    "Track %d swap below margin: cur=%s (%.3f) vs new=%s (%.3f) — candidate cleared",
                    identity.track_id,
                    identity.name,
                    identity.confidence,
                    d.resolved_name,
                    d.confidence,
                )
            identity.swap_candidate_user_id = None
            identity.swap_candidate_streak = 0
            identity.swap_candidate_best_conf = 0.0
            d.user_id = prev_user_id
            d.confidence = identity.confidence
            d.resolved_name = identity.name
            d.swap_blocked = True
            return

        # Margin gate passed — vote bookkeeping. Same candidate as last
        # frame extends the streak; a different candidate starts over.
        if identity.swap_candidate_user_id == d.user_id:
            identity.swap_candidate_streak += 1
            if d.confidence > identity.swap_candidate_best_conf:
                identity.swap_candidate_best_conf = d.confidence
        else:
            identity.swap_candidate_user_id = d.user_id
            identity.swap_candidate_streak = 1
            identity.swap_candidate_best_conf = d.confidence
            identity.swap_candidate_first_seen_at = now

        # Long-stability streak scaling. Tracks that have been visible
        # (and bound) for longer than ``RECOGNITION_LONG_STABILITY_FRAMES``
        # raise the streak gate by a multiplier — a 30-min lecture's
        # worth of evidence behind the existing binding shouldn't be
        # overturned by ~0.5 s of contradiction. Tracks short of the
        # stability mark use the standard streak, so first-recognition
        # behaviour is unchanged.
        min_streak = settings.RECOGNITION_SWAP_MIN_STREAK
        stability_frames = settings.RECOGNITION_LONG_STABILITY_FRAMES
        if (
            stability_frames > 0
            and identity.frames_seen >= stability_frames
            and settings.RECOGNITION_LONG_STABILITY_STREAK_MULTIPLIER > 1
        ):
            min_streak = min_streak * settings.RECOGNITION_LONG_STABILITY_STREAK_MULTIPLIER
        if identity.swap_candidate_streak >= min_streak:
            # Streak satisfied — commit the swap by leaving d.user_id /
            # d.confidence untouched. Reset bookkeeping so the next
            # frame starts fresh.
            logger.warning(
                "Track %d IDENTITY SWAP committed after %d-frame streak: %s (%.3f) -> %s (%.3f)",
                identity.track_id,
                identity.swap_candidate_streak,
                identity.name,
                identity.confidence,
                d.resolved_name,
                d.confidence,
            )
            identity.swap_candidate_user_id = None
            identity.swap_candidate_streak = 0
            identity.swap_candidate_best_conf = 0.0
            return

        # Streak still below threshold — block the swap and keep the
        # incumbent visible while the candidate accrues votes.
        logger.debug(
            "Track %d swap pending (streak %d/%d): cur=%s (%.3f) vs cand=%s (%.3f)",
            identity.track_id,
            identity.swap_candidate_streak,
            min_streak,
            identity.name,
            identity.confidence,
            d.resolved_name,
            d.confidence,
        )
        d.user_id = prev_user_id
        d.confidence = identity.confidence
        d.resolved_name = identity.name
        d.swap_blocked = True

    def _resolve_frame_mutex(self, decisions: list[_BatchDecision]) -> None:
        """Phase 3 — Hungarian bipartite assignment when two tracks in
        the same frame both target the same ``user_id``.

        Treats incumbents (tracks already ``recognized`` and re-confirming
        their existing user_id) as locked: they claim their user up
        front, and only challengers compete for what's left. This means
        a long-stable track can never be displaced by a new track whose
        FAISS result happens to score higher this frame — the new track
        either gets its top-2 fallback or stays in warming_up.

        For challengers, the cost matrix has rows = challenger tracks
        and columns = (top-1 + top-2 candidate users) ∪ (slack columns
        worth zero, one per row). Hungarian minimisation with cost =
        -similarity picks the assignment that maximises total similarity
        while respecting the one-user-per-track constraint.
        """
        if len(decisions) < 2:
            return

        # Build the incumbent set: tracks re-confirming their existing
        # binding. Their user_id is locked off the auction.
        incumbents: dict[str, _BatchDecision] = {}
        challengers: list[_BatchDecision] = []
        for d in decisions:
            if (
                d.user_id is not None
                and d.identity.recognition_status == "recognized"
                and d.identity.user_id == d.user_id
            ):
                # Two incumbents claiming the same user shouldn't
                # happen (each user has at most one current binding by
                # the dedup contract). If it does, keep the
                # higher-confidence one as the incumbent and demote the
                # other to a challenger so Hungarian can re-route it.
                existing = incumbents.get(d.user_id)
                if existing is None or d.confidence > existing.confidence:
                    if existing is not None:
                        challengers.append(existing)
                    incumbents[d.user_id] = d
                else:
                    challengers.append(d)
            elif d.user_id is not None:
                challengers.append(d)
            # If d.user_id is None (no FAISS hit / ambiguous / cleared
            # by name resolution) the track has nothing to compete for.

        if not challengers:
            return

        # Detect whether challengers actually collide with anything.
        # If every challenger's top-1 is unique AND not already held by
        # an incumbent, no resolution is needed — they all keep their
        # FAISS result.
        challenger_users = [c.user_id for c in challengers]
        collision_users = set()
        seen: dict[str, int] = {}
        for u in challenger_users:
            if u in seen:
                collision_users.add(u)
            seen[u] = seen.get(u, 0) + 1
        for c in challengers:
            if c.user_id in incumbents:
                collision_users.add(c.user_id)
        if not collision_users:
            return

        # Build the candidate user set from challenger top-1 + top-2.
        # Exclude users already locked by incumbents — challengers can
        # never win those.
        threshold = settings.RECOGNITION_THRESHOLD
        cand_users: list[str] = []
        for c in challengers:
            if c.user_id and c.user_id not in incumbents and c.user_id not in cand_users:
                cand_users.append(c.user_id)
            if (
                c.top2_user_id
                and c.top2_user_id != c.user_id
                and c.top2_user_id not in incumbents
                and c.top2_user_id not in cand_users
                and c.top2_score >= threshold
            ):
                cand_users.append(c.top2_user_id)

        n = len(challengers)
        m = len(cand_users)
        # Square cost matrix: cols = candidates ∪ slack (one per row).
        # Slack cost 0 means "no assignment" — preferred only when no
        # real candidate has positive value (i.e. cost < 0).
        BIG = 1e6
        cost = np.full((n, n + m), BIG, dtype=np.float64)
        for r, c in enumerate(challengers):
            if c.user_id and c.user_id in cand_users:
                col = cand_users.index(c.user_id)
                cost[r][col] = -float(c.confidence)
            if (
                c.top2_user_id
                and c.top2_user_id != c.user_id
                and c.top2_user_id in cand_users
                and c.top2_score >= threshold
            ):
                col = cand_users.index(c.top2_user_id)
                cost[r][col] = -float(c.top2_score)
            # Slack column for "stay in warming_up" — costs zero so any
            # negative real assignment beats it.
            cost[r][m + r] = 0.0

        try:
            row_ind, col_ind = linear_sum_assignment(cost)
        except Exception:
            logger.exception("frame-mutex Hungarian failed; leaving decisions untouched")
            return

        for r, col in zip(row_ind, col_ind):
            d = challengers[r]
            if col < m:
                assigned = cand_users[col]
                if assigned == d.user_id:
                    continue  # kept top-1, no change
                # Routed to top-2 (or top-1 of a different track that
                # this row's top-1 wasn't claimed by anyone else, which
                # cannot happen given how cand_users is built).
                if assigned == d.top2_user_id:
                    prev_user = d.user_id
                    d.user_id = d.top2_user_id
                    d.confidence = d.top2_score
                    d.resolved_name = self._resolve_name(d.top2_user_id)
                    d.mutex_demoted = True
                    logger.info(
                        "Track %d frame-mutex: top-1=%s claimed by another track; "
                        "fell back to top-2=%s (%.3f)",
                        d.identity.track_id,
                        prev_user[:8] if prev_user else "NONE",
                        d.top2_user_id[:8],
                        d.top2_score,
                    )
            else:
                # Slack column — no assignment. Clear the binding so
                # the track shows as warming_up rather than committing
                # to a wrong name.
                if d.user_id is not None:
                    prev_user = d.user_id
                    logger.info(
                        "Track %d frame-mutex: lost claim on %s and no top-2 fallback; demoted",
                        d.identity.track_id,
                        prev_user[:8],
                    )
                    d.user_id = None
                    d.resolved_name = None
                    d.is_ambiguous = True  # so commit treats this as a non-match
                    d.mutex_demoted = True

    def _commit_decision(self, d: _BatchDecision, now: float) -> None:
        """Phase 4 — apply the resolved decision to identity state + emit
        evidence.

        The branching here mirrors the original ``_recognize_batch`` body
        with one structural change: by the time we get here, ``d.user_id``
        already reflects the swap-gate + frame-mutex outcome, so the
        "is this a swap?" check just compares against the cached identity
        and either confirms or applies the (already-vetted) flip.
        """
        identity = d.identity
        user_id = d.user_id
        confidence = d.confidence
        resolved_name = d.resolved_name
        is_ambiguous = d.is_ambiguous
        search_embedding = d.search_embedding

        if user_id is not None and not is_ambiguous:
            prev_user_id = identity.user_id
            is_swap = (
                prev_user_id is not None
                and prev_user_id != user_id
                and identity.recognition_status == "recognized"
            )

            if is_swap:
                # The swap already cleared the swap-gate AND any
                # frame-mutex contention. Apply it.
                identity.user_id = user_id
                identity.confidence = confidence
                identity.name = resolved_name
                identity.anchor_embedding = search_embedding.copy()
                identity.drift_strike_count = 0
                identity.held_user_id = None
                identity.held_name = None
                # Record in oscillation history. Phase suppressor in
                # _derive_recognition_state reads this to decide whether
                # to silence the broadcast name during flip-flopping.
                identity.swap_history.append((now, user_id))
                self._maybe_arm_oscillation_suppressor(identity, now)
            else:
                # First-time recognition or re-confirmation — happy path.
                identity.user_id = user_id
                identity.confidence = confidence
                identity.name = resolved_name
                identity.recognition_status = "recognized"
                identity.anchor_embedding = search_embedding.copy()
                identity.drift_strike_count = 0
                identity.unknown_attempts = 0
                if prev_user_id is None:
                    logger.info(
                        "Track %d recognized: %s (%.3f)",
                        identity.track_id,
                        identity.name,
                        confidence,
                    )

                # Adaptive enrolment — only on stable re-verifies. Same
                # gates as the legacy path. The vote-based swap-gate
                # already guarantees at least RECOGNITION_SWAP_MIN_STREAK
                # frames of agreement before a swap commits, so a wrong
                # first-recognition can't poison this path through a
                # single noisy frame.
                is_stable_reverify = (
                    prev_user_id == user_id
                    and identity.frames_seen >= settings.ADAPTIVE_ENROLL_STABLE_FRAMES
                )
                if (
                    settings.ADAPTIVE_ENROLL_ENABLED
                    and is_stable_reverify
                    and confidence >= settings.ADAPTIVE_ENROLL_MIN_CONFIDENCE
                ):
                    self._try_adaptive_enroll(user_id, search_embedding, now)

                # Auto CCTV enrolment — opportunistic capture during the
                # student's first attended sessions. The enroller has
                # its own gates; we just offer every confident
                # recognition and let it decide.
                #
                # Guard: skip the offer when this frame's decision had
                # to be patched by either the swap-gate (a competing
                # candidate failed the streak gate) or the frame-mutex
                # (top-1 was claimed by another track and we fell back
                # to top-2). In both cases, FAISS *did* think a different
                # user was the better match this frame; while the
                # downstream gates correctly held the binding, accepting
                # the live crop into auto-enrolment would be feeding
                # ambiguous data into a supposedly high-confidence
                # training set. The auto-enroller's own buffer-then-
                # validate path provides defense in depth, but this
                # guard short-circuits before we even buffer.
                if not (d.swap_blocked or d.mutex_demoted or d.is_revalidation):
                    try:
                        from app.services.auto_cctv_enroller import auto_cctv_enroller
                        auto_cctv_enroller.offer_capture(
                            user_id=user_id,
                            track_id=identity.track_id,
                            embedding=search_embedding,
                            crop_bgr=d.live_crop,
                            confidence=confidence,
                            frames_seen=identity.frames_seen,
                            room_stream_key=self._camera_id,
                        )
                    except Exception:
                        logger.debug(
                            "auto-cctv offer failed for track %d", identity.track_id,
                            exc_info=True,
                        )
        elif identity.recognition_status == "recognized":
            # Already recognized — don't downgrade on a single bad
            # frame. Keep the binding; do NOT bump unknown_attempts.
            logger.debug(
                "Track %d re-verify missed (score=%.3f), keeping %s",
                identity.track_id,
                confidence,
                identity.name,
            )
        else:
            # Pending / previously-unknown track produced another miss.
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

        # Fire-and-forget evidence capture. We pass d.user_id (post-
        # mutex) and d.is_ambiguous so the writer reflects the actual
        # committed identity, not the raw FAISS top-1.
        #
        # Skipped for the periodic revalidation pass — that path
        # carries placeholder crop/bbox values (we re-search using the
        # buffer mean, not a live frame) so feeding them to the writer
        # would store garbage in the audit trail. The live recognition
        # path keeps writing as before; revalidation is silent state-
        # only.
        if (
            settings.ENABLE_RECOGNITION_EVIDENCE
            and self._schedule_id is not None
            and not d.is_revalidation
        ):
            try:
                self._submit_recognition_event(
                    identity=identity,
                    search_embedding=search_embedding,
                    live_crop=d.live_crop,
                    det_score=d.det_score,
                    bbox_px=d.bbox_px,
                    user_id=user_id,
                    student_name=resolved_name,
                    confidence=float(confidence),
                    is_ambiguous=bool(is_ambiguous),
                    now=now,
                )
            except Exception:
                logger.debug(
                    "evidence submit failed for track %d",
                    identity.track_id,
                    exc_info=True,
                )

        identity.last_verified = now

    def _periodic_revalidation(self, now: float) -> None:
        """Audit every recognized track using the MEAN of its recent
        embedding buffer rather than a single live frame.

        Why this exists:
          The per-frame swap-gate already protects against single-frame
          noise events, but the protection is reactive — it only fires
          when FAISS *this frame* names a different user. A track can
          drift slowly: each individual frame matches the bound user at
          0.50, but the temporal mean of the last 5 frames matches a
          DIFFERENT user at 0.55. Without periodic mean re-search we'd
          never detect that. With it, we re-confirm the binding from
          the most stable signal we have — and if the mean disagrees,
          the swap-gate's vote+margin gate handles the rest.

          This is the "cron job" the operator asked for, but inlined
          into the per-frame loop at low cadence so it doesn't need a
          separate scheduler. At 5 fps backend × 150 frames = ~30 s
          cadence; FAISS cost is one batched query for 4-6 tracks ≈ a
          few ms. No new threads, no scheduling drift.

        How:
          1. Collect every track in identity_cache that is currently
             ``recognized`` AND has at least 3 buffered embeddings.
          2. Compute the L2-normalised mean of each track's buffer.
          3. Run ONE ``search_batch_with_margin`` call for the stack.
          4. For each result: synthesise a ``_BatchDecision`` with the
             mean-based scores and feed it through ``_apply_swap_gate``
             so the streak-and-margin rules apply identically to live
             frames. Frame-mutex is NOT re-run here — the tracks aren't
             competing for shared user_ids in this path; we're only
             auditing existing bindings.
          5. Commit the resolved decisions back to identity state via
             ``_commit_decision`` so attendance/presence picks up any
             corrections without delay.
        """
        candidates: list[tuple[TrackIdentity, np.ndarray]] = []
        for identity in self._identity_cache.values():
            if identity.recognition_status != "recognized":
                continue
            if len(identity.embedding_buffer) < 3:
                continue
            try:
                avg = np.mean(np.asarray(list(identity.embedding_buffer)), axis=0)
                norm = float(np.linalg.norm(avg))
                if norm <= 0:
                    continue
                avg = (avg / norm).astype(np.float32, copy=False)
            except Exception:
                continue
            candidates.append((identity, avg))

        if not candidates:
            return

        stacked = np.stack([emb for _, emb in candidates]).astype(np.float32)
        try:
            batch_results = self._faiss.search_batch_with_margin(stacked)
        except Exception:
            logger.debug("revalidation FAISS search failed", exc_info=True)
            return

        # Synthesize one _BatchDecision per track and feed it through
        # the swap-gate + commit pipeline. The live_crop / det_score /
        # bbox_px fields are only used by the evidence writer and the
        # auto-CCTV enroller; both are guarded with `if d.live_crop ...`
        # / mutex_demoted checks so a None-equivalent placeholder is
        # safe. We use empty-shape sentinels rather than None to keep
        # the dataclass's typed fields happy without changing its API.
        empty_crop = np.zeros((0, 0, 3), dtype=np.uint8)
        decisions: list[_BatchDecision] = []
        for (identity, avg), result in zip(candidates, batch_results):
            user_id = result.get("user_id")
            confidence = float(result.get("confidence", 0.0))
            is_ambiguous = bool(result.get("is_ambiguous", False))
            top1_user_id = result.get("top1_user_id")
            top1_score = float(result.get("top1_score", 0.0))
            top2_user_id = result.get("top2_user_id")
            top2_score = float(result.get("top2_score", 0.0))

            # Phone-only stricter threshold — same gate as in
            # _gather_decisions, applied here so the revalidation path
            # can't accidentally bind a phone-only user it would have
            # rejected in a live frame.
            phone_only_bonus = settings.RECOGNITION_PHONE_ONLY_THRESHOLD_BONUS
            if (
                user_id is not None
                and phone_only_bonus > 0.0
                and user_id in self._phone_only
            ):
                strict_threshold = settings.RECOGNITION_THRESHOLD + phone_only_bonus
                if confidence < strict_threshold:
                    user_id = None
                    is_ambiguous = True

            resolved_name: str | None = None
            if user_id is not None:
                resolved_name = self._resolve_name(user_id)
                if resolved_name is None:
                    user_id = None

            decisions.append(_BatchDecision(
                identity=identity,
                search_embedding=avg,
                live_crop=empty_crop,
                det_score=0.0,
                bbox_px=[0, 0, 0, 0],
                user_id=user_id,
                confidence=confidence,
                is_ambiguous=is_ambiguous,
                resolved_name=resolved_name,
                top1_user_id=top1_user_id,
                top1_score=top1_score,
                top2_user_id=top2_user_id,
                top2_score=top2_score,
                is_revalidation=True,
            ))

        # Same swap-gate logic the live path uses — vote-based,
        # streak-counted, with long-stability scaling. A
        # revalidation-driven swap is held to the same standard as a
        # live one.
        for d in decisions:
            self._apply_swap_gate(d, now)

        # Skip frame-mutex: the revalidation pass operates on every
        # currently-recognised track, not on a contention pool. If
        # there's a real "two tracks bound to the same user" condition
        # it will already have been resolved by the live path before
        # we got here.

        for d in decisions:
            self._commit_decision(d, now)

        logger.info(
            "revalidation pass: audited %d recognized track(s); "
            "swap-gate decisions applied via mean-embedding search",
            len(decisions),
        )

    def _maybe_arm_oscillation_suppressor(self, identity: TrackIdentity, now: float) -> None:
        """Arm the oscillation suppressor when ``identity.swap_history`` shows
        too many flips across too many distinct users in too little time.

        Reads the gates from settings:
          OSCILLATION_WINDOW_SECONDS — rolling window size
          OSCILLATION_DISTINCT_USERS — min distinct users that must appear
          OSCILLATION_FLIPS_THRESHOLD — min number of swaps in the window

        When armed, ``identity.oscillation_uncertain_until`` is pushed to
        ``now + OSCILLATION_UNCERTAIN_HOLD_S``. The display layer
        (``_get_display_identity``) reads that field and silences the
        broadcast name until the cooldown expires. The track's internal
        binding is preserved so attendance counters and presence logs
        keep firing — only the visible label is suppressed.
        """
        window = settings.OSCILLATION_WINDOW_SECONDS
        if window <= 0:
            return
        cutoff = now - window
        recent = [(t, u) for (t, u) in identity.swap_history if t >= cutoff]
        if len(recent) < settings.OSCILLATION_FLIPS_THRESHOLD:
            return
        distinct = len({u for _, u in recent})
        if distinct < settings.OSCILLATION_DISTINCT_USERS:
            return
        identity.oscillation_uncertain_until = now + settings.OSCILLATION_UNCERTAIN_HOLD_S
        logger.warning(
            "Track %d OSCILLATION suppressor armed: %d swaps over %d users in last %.1fs",
            identity.track_id,
            len(recent),
            distinct,
            window,
        )

    def _submit_recognition_event(
        self,
        identity: "TrackIdentity",
        search_embedding: np.ndarray,
        live_crop: np.ndarray,
        det_score: float,
        bbox_px: list[int],
        user_id: str | None,
        student_name: str | None,
        confidence: float,
        is_ambiguous: bool,
        now: float,
    ) -> None:
        """Build a RecognitionEventDraft and hand it to the evidence writer.

        Called from inside the per-track loop of ``_recognize_batch`` which
        runs on the pipeline's thread-pool executor. The hot path here
        **must stay sub-millisecond**; all non-trivial work (encoding,
        disk, DB) is deferred to the writer's async worker.

        Per-user caches (``_evidence_reg_bytes``, ``_evidence_reg_ref``)
        ensure ``_load_registered_crop_bytes`` runs at most once per user
        per process — not every frame.

        ``now`` is the monotonic timestamp from ``process()``; it drives the
        per-(student, decision-state) throttle so a static subject doesn't
        produce 50+ near-identical events per minute (the "stale faces"
        complaint on the Student Record Detail page, 2026-04-25).
        """
        from app.services.evidence_writer import (
            RecognitionEventDraft,
            evidence_writer,
        )

        matched = bool(user_id) and not is_ambiguous

        # Throttle: drop repeat events with the same outcome inside the
        # configured window. Keyed on (identity, matched, ambiguous) so a
        # genuine state change (miss → match, match → ambiguous, identity
        # swap to a different user) always bypasses the gate. For misses
        # we key on the track id since there's no student_id to anchor to;
        # this still dedupes per-track rapid-fire UNKNOWN reads.
        throttle_window = float(settings.RECOGNITION_EVIDENCE_THROTTLE_S)
        if throttle_window > 0.0:
            key_anchor = (
                str(user_id) if user_id else f"track:{int(identity.track_id)}"
            )
            key = (key_anchor, bool(matched), bool(is_ambiguous))
            last = self._evidence_last_submit.get(key)
            if last is not None and (now - last) < throttle_window:
                # Within window — silently drop. No DB row, no JPEG, no WS
                # broadcast. Attendance/presence state are unaffected since
                # they live on a separate code path (TrackPresenceService).
                return
            self._evidence_last_submit[key] = now

            # Bound the dict so a long-running session with many distinct
            # transient track ids can't grow it without limit. 1024 anchors
            # at ~80 bytes each is ~80 KB worst case, plenty of head-room
            # for any realistic classroom.
            if len(self._evidence_last_submit) > 1024:
                # Cheap eviction: drop entries older than 5× the throttle
                # window. They can never fire the gate again anyway.
                cutoff = now - (throttle_window * 5.0)
                stale = [k for k, t in self._evidence_last_submit.items() if t < cutoff]
                for k in stale:
                    del self._evidence_last_submit[k]

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
            student_name=student_name if matched else None,
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
        """Remove stale tracks from identity cache.

        Recognised tracks leave a tombstone in the graveyard so the next
        new track in the same spatial neighbourhood gets a hint pointing
        at the prior identity. See ``_lookup_graveyard_hint``.
        """
        if active_track_ids is None:
            active_track_ids = set()

        stale_threshold = settings.TRACK_LOST_TIMEOUT
        to_remove = [
            tid
            for tid, identity in self._identity_cache.items()
            if tid not in active_track_ids and (now - identity.last_seen) > stale_threshold
        ]
        for tid in to_remove:
            ident = self._identity_cache[tid]
            # Tombstone capture: only for recognised tracks (Unknown +
            # warming_up tombstones would just spam the graveyard with
            # no identity signal). Requires last_bbox so we have a
            # spatial anchor to match against.
            if (
                settings.IDENTITY_GRAVEYARD_TTL_SECONDS > 0
                and ident.recognition_status == "recognized"
                and ident.user_id is not None
                and ident.last_bbox is not None
            ):
                cx = (ident.last_bbox[0] + ident.last_bbox[2]) / 2.0
                cy = (ident.last_bbox[1] + ident.last_bbox[3]) / 2.0
                self._identity_graveyard.append(
                    IdentityTombstone(
                        user_id=ident.user_id,
                        name=ident.name,
                        bbox_center=(cx, cy),
                        expired_at=now,
                    )
                )
            del self._identity_cache[tid]
            self._prev_bboxes.pop(tid, None)

        # Bound the graveyard: prune anything past TTL on each expire pass.
        # Cheap (graveyard is typically <20 entries even in a busy room).
        if self._identity_graveyard:
            ttl = settings.IDENTITY_GRAVEYARD_TTL_SECONDS
            self._identity_graveyard = [
                t for t in self._identity_graveyard
                if (now - t.expired_at) <= ttl
            ]

    def _lookup_graveyard_hint(
        self, bbox_norm: list[float], now: float
    ) -> IdentityTombstone | None:
        """Return the single tombstone within spatial + temporal proximity, or None.

        Safety rule: hint is set ONLY when there is exactly one viable
        tombstone in the spatial neighbourhood. If two recently-expired
        recognised tracks both sit within the radius, we have no way to
        know which one re-entered the frame — return None and let FAISS
        decide unaided.
        """
        if not self._identity_graveyard:
            return None
        ttl = settings.IDENTITY_GRAVEYARD_TTL_SECONDS
        if ttl <= 0:
            return None
        max_dist = settings.IDENTITY_GRAVEYARD_MAX_DIST_NORMALIZED

        cx = (bbox_norm[0] + bbox_norm[2]) / 2.0
        cy = (bbox_norm[1] + bbox_norm[3]) / 2.0

        candidates: list[IdentityTombstone] = []
        for tomb in self._identity_graveyard:
            if (now - tomb.expired_at) > ttl:
                continue
            tcx, tcy = tomb.bbox_center
            # Use Chebyshev (max) distance so the radius is a square in
            # normalised space — matches operator intuition of "near here"
            # better than Euclidean and is faster.
            if max(abs(cx - tcx), abs(cy - tcy)) > max_dist:
                continue
            candidates.append(tomb)

        if len(candidates) == 1:
            return candidates[0]
        # 0 candidates → no nearby recent identity, hint stays None.
        # >1 candidates → ambiguous, refuse to hint (defensive).
        return None

    def _consume_tombstone(self, tomb: IdentityTombstone) -> None:
        """Remove a tombstone after a new track inherited it as hint.

        We only let one new track inherit any given tombstone — without
        this, two simultaneously-spawning new tracks near the same dead
        spot would both claim the same identity hint.
        """
        try:
            self._identity_graveyard.remove(tomb)
        except ValueError:
            pass

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
