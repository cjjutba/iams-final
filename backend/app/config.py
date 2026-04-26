"""
IAMS Backend Configuration

Central configuration file using Pydantic Settings for all environment variables.
Includes JWT, Face Recognition, and Presence Tracking settings.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "IAMS"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str  # PostgreSQL connection string

    # JWT Settings
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rate Limiting
    RATE_LIMIT_AUTH: str = "10/minute"  # Auth endpoint rate limit
    RATE_LIMIT_ENABLED: bool = True

    # CORS
    CORS_ORIGINS: list[str] = []  # Must be explicitly set per environment

    # ONNX Runtime (thread control for multi-worker CPU efficiency)
    ONNX_INTRA_OP_THREADS: int = 4  # threads within a single op (1 worker × 4 = 4 vCPUs)
    ONNX_INTER_OP_THREADS: int = 2  # threads between ops (allows pipelining det + rec)

    # ML Sidecar (native macOS InsightFace process for CoreML/ANE acceleration)
    # When set, the realtime SCRFD + ArcFace path is proxied to a native
    # macOS process via HTTP loopback (host.docker.internal). The sidecar
    # is the only way to reach CoreMLExecutionProvider — Linux Docker
    # builds of ONNX Runtime can't see the Apple Neural Engine. Empty
    # string = run inference in-process (today's behaviour, CPU-only
    # inside the container). The gateway falls back to in-process if the
    # sidecar fails its boot-time health probe, so a missing sidecar
    # degrades to "no overlays" rather than a hard error.
    ML_SIDECAR_URL: str = ""
    # How long the gateway waits for the sidecar to respond per call.
    # Detection at det_size=960 on the ANE typically returns in 30-80ms;
    # 5s is a generous ceiling that still surfaces a wedged sidecar fast
    # enough that the pipeline's "no frames" detection trips.
    ML_SIDECAR_TIMEOUT_SECONDS: float = 5.0
    # JPEG quality for sidecar requests. 85 is the sweet spot — visually
    # indistinguishable from 95 for face crops, ~30% smaller payload.
    ML_SIDECAR_JPEG_QUALITY: int = 85

    # Face Recognition
    INSIGHTFACE_MODEL: str = "buffalo_l"
    INSIGHTFACE_DET_SIZE: int = 640  # 640 for best accuracy with main stream (480 for sub-stream)
    INSIGHTFACE_DET_THRESH: float = 0.3  # Detection confidence minimum (lowered for distant CCTV faces)
    # Static-shape ONNX model pack name (relative to ~/.insightface/models/).
    # When the named pack exists on disk, the loader prefers it over the
    # upstream INSIGHTFACE_MODEL because static-shape ONNX is required for
    # CoreMLExecutionProvider to delegate to the Apple Neural Engine. See
    # backend/scripts/export_static_models.py and the live-feed plan dated
    # 2026-04-25 (Step 2b). Set to the empty string to opt out and use the
    # dynamic-shape upstream model.
    INSIGHTFACE_STATIC_PACK_NAME: str = "buffalo_l_static"
    FAISS_INDEX_PATH: str = "data/faiss/faces.index"
    RECOGNITION_THRESHOLD: float = (
        0.38  # Cosine similarity threshold — CCTV cross-domain typically 0.35-0.55 without adaptive help
    )
    RECOGNITION_MARGIN: float = 0.06  # Min gap between top-1 and top-2 scores (reduced for similar-looking students)
    RECOGNITION_TOP_K: int = 3  # Number of neighbors to search in FAISS

    # ───────────────────────────────────────────────────────────────────────
    # Identity-swap hardening (added 2026-04-25 after the live EB227 swap
    # incident where two near-threshold faces traded labels frame-to-frame).
    # The original tracker accepted a swap on a single frame whose new
    # match exceeded the bound user's score by 0.05; at sim 0.45-0.50
    # (CCTV cross-domain noise band) the next frame's noise routinely
    # produced 0.06+ deltas, so the binding flipped on every reverify.
    #
    # The hardened path requires BOTH a larger margin AND sustained
    # consensus across multiple frames before the binding flips. Tuned to
    # be a no-op when sims are comfortably high (e.g. CCTV-enrolled users
    # at 0.75+) and a strict gate when sims hover in the 0.45-0.55 band
    # where a 1-frame flip is most likely a noise event, not a real
    # identity change.
    # ───────────────────────────────────────────────────────────────────────
    RECOGNITION_SWAP_MARGIN: float = 0.10  # Was hardcoded 0.05 — too small at near-threshold sims
    RECOGNITION_SWAP_MIN_STREAK: int = 3  # Consecutive frames a candidate must beat the bound user before the swap commits

    # Frame-level mutual exclusion: when two tracks in the same frame both
    # claim the same user_id as their top-1 (collision), resolve as a
    # bipartite assignment using top-K candidates so each user_id is bound
    # to at most one track per frame. The loser of an assignment falls
    # back to its top-2 if that clears RECOGNITION_THRESHOLD; otherwise
    # the track stays in warming_up (no green wrong-name label is ever
    # rendered). Set False to fall back to the legacy greedy "highest
    # confidence wins, others drop" behaviour from the post-hoc dedup at
    # the end of process().
    RECOGNITION_FRAME_MUTEX_ENABLED: bool = True

    # Stricter threshold for matches against students whose face_embeddings
    # rows do not include any ``cctv_*`` angle labels (phone-side
    # registration only). The cross-domain gap between phone selfies and
    # classroom CCTV typically lands these students in the 0.40-0.55 sim
    # range — exactly the band where two students' top-1 scores can flip
    # frame-to-frame. By bumping the effective threshold for THESE users
    # only, we refuse to commit a recognition until the score is high
    # enough that a swap would require sustained, decisive evidence
    # rather than a single ambiguous frame. Once the operator runs
    # ``scripts.cctv_enroll`` for the user (or the auto-enroller commits
    # captures from a live session), the user is no longer phone-only
    # and falls back to the standard RECOGNITION_THRESHOLD.
    #
    # Set to 0 to disable the bonus (treat phone-only and CCTV-enrolled
    # users equivalently).
    #
    # Tuning history:
    #   - 2026-04-25 first cut: 0.10 → strict gate at 0.55. Caught the
    #     swap-flicker problem at the cost of leaving phone-only
    #     students stranded in cross-domain noise band (sim 0.45-0.55).
    #     Christian, James, Febtwel observed showing "Unknown" in
    #     EB227 because their phone-only sims hovered just below 0.55.
    #   - 2026-04-26: lowered to 0.05. Strict gate at 0.50. The other
    #     hardening layers (vote-based swap, frame-mutex, oscillation
    #     suppressor, top-1/top-2 margin) are sufficient against the
    #     wrong-name risk; the 0.05 bonus keeps a small safety cushion
    #     above the standard threshold without permanently locking
    #     borderline students out of recognition. Auto-CCTV enrol then
    #     captures their first room-specific embeddings opportunistically,
    #     lifting them out of the noise band on subsequent sessions.
    RECOGNITION_PHONE_ONLY_THRESHOLD_BONUS: float = 0.05

    # Long-stability swap protection. The base swap-gate already requires
    # ``RECOGNITION_SWAP_MIN_STREAK`` consecutive frames before a
    # recognised track flips identity. For tracks that have been
    # successfully bound to the same user for a long time (e.g. an
    # entire 90-min lecture), the prior is even stronger that the
    # binding is correct, so the streak gate scales up to make the
    # late-session flip practically impossible.
    #
    # Tuning: at PROCESSING_FPS=20, 600 frames ≈ 30 s of continuous
    # tracking. After that, the streak gate becomes
    # ``RECOGNITION_SWAP_MIN_STREAK * RECOGNITION_LONG_STABILITY_STREAK_MULTIPLIER``
    # (default 3 × 3 = 9 frames) — about half a second of decisive
    # contradiction at 20 fps before the binding flips. At 5 fps backend
    # this is ~2 s, which is enough for a real identity change (e.g.
    # ByteTrack accidentally re-using a track id after a student leaves
    # and another sits in the same seat) but ridiculously slow for any
    # noise event.
    RECOGNITION_LONG_STABILITY_FRAMES: int = 600
    RECOGNITION_LONG_STABILITY_STREAK_MULTIPLIER: int = 3

    # Oscillation suppressor — third layer on top of the swap-margin gate
    # and the frame-mutex assignment. Even with both of those in place,
    # a track can still flap when two students take turns satisfying the
    # streak gate (e.g. Christian wins 3 frames, then James wins 3, then
    # Christian, ...). The suppressor watches the rolling history of
    # confirmed swaps on each track and, if more than
    # ``OSCILLATION_FLIPS_THRESHOLD`` swaps cross at least
    # ``OSCILLATION_DISTINCT_USERS`` distinct user_ids inside the last
    # ``OSCILLATION_WINDOW_SECONDS``, the overlay suppresses the displayed
    # name for ``OSCILLATION_UNCERTAIN_HOLD_S`` seconds. The track's
    # internal binding is preserved (no FAISS re-walk), only the broadcast
    # is silenced — better to render a blank "Detecting…" label than to
    # commit to either of two competing identities. Set
    # OSCILLATION_FLIPS_THRESHOLD to a very large number to disable this
    # layer without removing the bookkeeping.
    OSCILLATION_WINDOW_SECONDS: float = 8.0
    OSCILLATION_DISTINCT_USERS: int = 2
    OSCILLATION_FLIPS_THRESHOLD: int = 3
    OSCILLATION_UNCERTAIN_HOLD_S: float = 3.0
    USE_GPU: bool = True  # Use GPU if available, fallback to CPU
    MIN_FACE_IMAGES: int = 3  # Minimum images for registration
    MAX_FACE_IMAGES: int = 5  # Maximum images for registration

    # CCTV-side embedding synthesis: variants per (face_crop, camera).
    # Each registration generates 5 phone embeddings + (5 × N_cameras × variants)
    # synthetic embeddings tuned to each known camera's lens+colour profile.
    # 2 variants ≈ 20 sim vectors for a 2-camera classroom setup; bump to 3
    # for more pose diversity at the cost of larger per-user FAISS clusters.
    # Capped at 5 to keep the index size reasonable for ≥100 enrolled students.
    SIM_VARIANTS_PER_CAMERA: int = 2

    # Face Quality Gating
    QUALITY_GATE_ENABLED: bool = True
    QUALITY_BLUR_THRESHOLD: float = 100.0  # Laplacian variance minimum (CCTV)
    QUALITY_BLUR_THRESHOLD_MOBILE: float = 10.0  # Laplacian variance minimum (mobile CameraX bitmap capture)
    QUALITY_BRIGHTNESS_MIN: float = 40.0  # Mean pixel intensity minimum
    QUALITY_BRIGHTNESS_MAX: float = 220.0  # Mean pixel intensity maximum
    QUALITY_MIN_FACE_SIZE_RATIO: float = 0.05  # Face area / image area minimum
    QUALITY_MIN_DET_SCORE: float = 0.5  # SCRFD detection confidence minimum

    # Anti-Spoofing / Liveness Detection (LEGACY heuristic gates used during
    # registration only — these predate the MiniFASNet realtime path below.
    # Kept enabled because they're cheap and only run on phone-side selfie
    # uploads where their LBP / FFT thresholds were tuned. The CCTV realtime
    # path uses the LIVENESS_* settings.)
    ANTISPOOF_ENABLED: bool = True
    ANTISPOOF_REGISTRATION_STRICT: bool = True  # Block registration if spoof detected
    ANTISPOOF_RECOGNITION_LOG_ONLY: bool = True  # Only log during CCTV (no blocking)
    ANTISPOOF_EMBEDDING_VARIANCE_MIN: float = 0.1  # Min embedding cosine distance variance across angles
    ANTISPOOF_LBP_THRESHOLD: float = 0.15  # LBP texture uniformity threshold (lowered for mobile selfie)
    ANTISPOOF_FFT_THRESHOLD: float = 0.20  # FFT high-freq energy threshold (lowered for mobile selfie)

    # ───────────────────────────────────────────────────────────────────────
    # Realtime CCTV Liveness (MiniFASNet — added 2026-04-25)
    #
    # Passive liveness detector for the CCTV path. Catches "show a phone /
    # printed photo to the camera" presentation attacks that ArcFace alone
    # cannot distinguish from a real face. The model lives in the ML
    # sidecar (CoreML/ANE on the M5) — see backend/ml-sidecar/main.py and
    # app/services/ml/liveness_model.py.
    #
    # Operator workflow:
    #   1. backend/venv/bin/pip install torch torchvision     (one-time, ~700 MB)
    #   2. backend/venv/bin/python -m scripts.export_liveness_models
    #   3. Set LIVENESS_ENABLED=true here / in backend/.env.onprem
    #   4. Restart sidecar + api-gateway
    #
    # Gating policy (when LIVENESS_ENABLED=true):
    #   - Each face's liveness is checked at the same cadence as ArcFace
    #     re-verify (LIVENESS_RECHECK_INTERVAL_S, default 5 s).
    #   - When fused MiniFASNet "real" probability < LIVENESS_REAL_THRESHOLD
    #     for >= LIVENESS_SPOOF_CONSECUTIVE frames, the track is marked
    #     spoof and recognition is suppressed (overlay shows "Spoof detected"
    #     instead of a name; attendance is NOT credited).
    #   - When the same track later passes liveness for
    #     LIVENESS_REAL_RECOVERY_FRAMES frames in a row, the spoof flag
    #     clears and normal recognition resumes (a real student briefly
    #     misclassified can recover without the operator restarting).
    # ───────────────────────────────────────────────────────────────────────
    LIVENESS_ENABLED: bool = False
    # Threshold on the fused "real" softmax probability across MiniFASNetV2
    # (scale 2.7) and MiniFASNetV1SE (scale 4.0). 0.5 is the canonical
    # decision boundary for the published two-model fusion. Bump up if
    # phone/screen presentations slip through; bump down if real CCTV
    # faces in poor lighting are over-rejected.
    LIVENESS_REAL_THRESHOLD: float = 0.5
    # Per-track "spoof confirmed" debounce. A single transient mis-
    # classification from a glitchy frame should NOT suppress recognition
    # — require N consecutive frames below threshold before flipping
    # the broadcast state. At PROCESSING_FPS=20 with the recheck cadence
    # below, 2 means ~10 s of sustained spoof signal before suppression
    # commits. Set to 1 to suppress on first spoof verdict.
    LIVENESS_SPOOF_CONSECUTIVE: int = 2
    # Per-track "real recovery" debounce. Once a track is suppressed,
    # how many consecutive real verdicts do we need before unsuppressing?
    # Higher = stickier suppression (better against intermittent attacks
    # where the attacker briefly tilts the phone away to defeat the gate).
    LIVENESS_REAL_RECOVERY_FRAMES: int = 3
    # How often (seconds) to re-run liveness on already-bound tracks. Same
    # cadence as ArcFace re-verify — both share the embed batch boundary
    # in RealtimeTracker.process(). A static photo doesn't need a fresh
    # check every frame, but the bound is also the protection window: at
    # 5 s, an attacker who briefly removes the photo loses the gate
    # within 5 s of resuming. New tracks are always liveness-checked on
    # first frame regardless of this cadence.
    LIVENESS_RECHECK_INTERVAL_S: float = 5.0
    # Hard wall on per-frame liveness inference budget. The full embed
    # batch already drops to top N tracks based on
    # MAX_FIRST_RECOGNITIONS_PER_FRAME — same cap is reused here so the
    # liveness path can't blow the per-frame budget when 30+ students
    # walk in together.
    LIVENESS_MAX_PER_FRAME: int = 10

    # Adaptive Per-Session Enrollment
    # When a student is recognized with high confidence from CCTV, store that
    # real CCTV embedding in FAISS (RAM only, volatile) to boost future matches.
    #
    # DEFAULT-OFF as of 2026-04-25: a wrong first-match could lock in via
    # identity-swap suppression and then poison FAISS — the misidentified
    # user's real face crop would get appended to the wrong identity's vector
    # cluster, making the swap permanent for that session. Re-enable only
    # after raising RECOGNITION_THRESHOLD to >= 0.45 AND running a CCTV-side
    # re-enrollment pass (scripts/cctv_enroll.py) so canonical CCTV embeddings
    # exist for each enrolled student. The gate values below are intentionally
    # strict: 0.70 confidence + 30 frames stable + 30 s cooldown = at most
    # one adaptive embedding per user per minute, only on near-certain matches.
    ADAPTIVE_ENROLL_ENABLED: bool = False
    ADAPTIVE_ENROLL_MIN_CONFIDENCE: float = 0.70  # Was 0.55 — too permissive, poisoned FAISS during the 2026-04-25 swap incident
    ADAPTIVE_ENROLL_STABLE_FRAMES: int = 30  # Was hardcoded 10; raised to require ~1.5 s of consistent recognition before adaptive add
    ADAPTIVE_ENROLL_MAX_PER_USER: int = 3  # Max session embeddings per user (conservative to avoid corruption)
    ADAPTIVE_ENROLL_COOLDOWN: float = 30.0  # Seconds between adaptive enrollments per user (was too aggressive)

    # Presence Tracking (legacy scan-based — kept for backward compatibility)
    SCAN_INTERVAL_SECONDS: int = 15  # How often to run presence scans
    EARLY_LEAVE_THRESHOLD: int = 3  # Consecutive misses to flag early leave
    GRACE_PERIOD_MINUTES: int = 15  # Late grace period after class starts
    SESSION_BUFFER_MINUTES: int = 5  # Buffer before/after class for session

    # Real-Time Pipeline
    # 20 fps = 50 ms per-frame budget for SCRFD+ByteTrack+ArcFace. Faster identity
    # refresh means names appear on newly-seen faces in ~100 ms instead of ~200 ms
    # (first-recognition needs ~2 quality-gated frames to lock in). On the dev Mac
    # this will peg the backend container CPU (~1000 %) when multiple rooms are
    # active — if that becomes a bottleneck, drop to 10 fps: the phone's ML Kit
    # already owns 30 fps positions so backend FPS only affects name latency, not
    # box smoothness. Production override in backend/.env.production=5.
    PROCESSING_FPS: float = 20.0
    WS_BROADCAST_FPS: float = 20.0  # WebSocket broadcast rate (one broadcast per processed frame)

    # ByteTrack / Track Lifecycle
    TRACK_LOST_TIMEOUT: float = 2.0  # Seconds before removing lost track (coasting period)
    REVERIFY_INTERVAL: float = 5.0  # Re-run ArcFace on existing tracks (seconds)
    # Adaptive re-verify cadence: when N tracks > BASELINE the per-track
    # interval scales linearly so per-frame embed budget stays roughly
    # bounded. Set to 0 / 1 to effectively disable scaling. See
    # RealtimeTracker._compute_adaptive_reverify_interval. Tuned for the
    # typical 4-6 student classroom on the M5 + CoreML sidecar.
    ADAPTIVE_REVERIFY_BASELINE_TRACKS: int = 5

    # Hard wall-clock ceiling on the "warming_up" overlay state. The
    # near-threshold-stay-in-warming-up rule in
    # RealtimeTracker._derive_recognition_state used to be open-ended —
    # if a track's best-seen sim sat between (RECOGNITION_THRESHOLD - margin)
    # and RECOGNITION_THRESHOLD, the overlay stayed blue ("Detecting…")
    # forever on the theory that a cleaner frame might tip it over. In
    # practice that produced "stuck Detecting" UX (2026-04-25 — a real
    # user near the camera whose phone-only embedding produced sims in
    # the 0.40-0.44 dead zone). After this many seconds since first_seen
    # we commit to "unknown" regardless of score, so the operator knows
    # the system gave up on this face and can prompt CCTV-side enrolment.
    MAX_WARMING_UP_SECONDS: float = 8.0

    # Per-frame budget cap on first-recognition embeddings. Re-verifies
    # are already capped (MAX_REVERIFIES_PER_FRAME) so a stable scene's
    # embed cost is bounded; first-recognition was historically uncapped
    # because new faces "must lock in fast". That assumption breaks at
    # 30+ students walking in together — the embed wave dwarfs the
    # per-frame budget and the live overlay stutters for ~half a second.
    # Capping at 10 means latecomers in a 40-student class lock in 0.5-1 s
    # after the rush instead of all in one bursting frame, while small
    # rooms (≤10 fresh tracks) see no behaviour change.
    MAX_FIRST_RECOGNITIONS_PER_FRAME: int = 10

    # Auto CCTV enrolment — captures real CCTV embeddings opportunistically
    # during a student's first sessions, with no operator action and no
    # student UI. Trigger fires once per user lifetime when:
    #   (a) student is recognised at sim >= AUTO_CCTV_ENROLL_MIN_CONFIDENCE
    #       for >= AUTO_CCTV_ENROLL_MIN_STABLE_FRAMES frames in a row
    #   (b) they have fewer than AUTO_CCTV_ENROLL_LIFETIME_CAP rows in
    #       face_embeddings with angle_label like 'cctv_%'
    #   (c) at least AUTO_CCTV_ENROLL_CAPTURE_INTERVAL_S seconds since
    #       the last successful capture
    # On trigger, the realtime tracker buffers the recognition embedding +
    # crop. After AUTO_CCTV_ENROLL_TARGET_CAPTURES samples are collected,
    # they're committed to FAISS + DB + disk in a background thread via
    # the same path as scripts/cctv_enroll.py. Self-similarity check still
    # applies — captures whose mean sim to existing phone vectors is below
    # AUTO_CCTV_ENROLL_MIN_SELF_SIM are dropped without commit.
    #
    # Default ON as of 2026-04-25 swap-hardening pass. The earlier
    # safety concern (a wrong first-recognition could poison FAISS) is
    # now closed by the layered identity defenses: vote-based swap-gate,
    # frame-mutex Hungarian assignment, oscillation suppressor, and
    # phone-only stricter threshold. Auto-enrolment also opts itself
    # out of the offer when the current frame's decision was patched
    # by either the swap-gate (sustained candidate didn't reach streak)
    # or the frame-mutex (top-1 was claimed by another track) — so
    # uncertain frames never reach the auto-enroll buffer in the first
    # place. Combined with the lifetime cap and the commit-time
    # self-similarity gate, the auto path is now safe for the
    # production fleet to run unattended.
    AUTO_CCTV_ENROLL_ENABLED: bool = True
    # Tuning history:
    #   - 2026-04-25 first cut: 0.55 to align with the phone-only
    #     stricter threshold of the same value. Worked as a safety
    #     floor but stranded students whose first-encounter sim in a
    #     new room sat in the 0.45-0.55 band — they would show as
    #     "Detecting…" forever in that room because auto-enrol never
    #     fired to capture room-specific embeddings.
    #   - 2026-04-26: lowered to 0.50 alongside the phone-only bonus
    #     reduction. Now any sustained recognition above 0.50 sim
    #     triggers an auto-enrol attempt. Safety against noise still
    #     comes from the 60-frame stability gate, the 5 s capture
    #     spacing, and the commit-time self-similarity check
    #     (mean sim against existing phone embeddings >=
    #     AUTO_CCTV_ENROLL_MIN_SELF_SIM). Combined with per-room
    #     auto-enrol state (auto_cctv_enroller.py), this lets a
    #     student who was auto-enrolled in EB226 still trigger fresh
    #     captures the first time they appear in EB227.
    AUTO_CCTV_ENROLL_MIN_CONFIDENCE: float = 0.50
    AUTO_CCTV_ENROLL_MIN_STABLE_FRAMES: int = 60
    AUTO_CCTV_ENROLL_TARGET_CAPTURES: int = 5
    AUTO_CCTV_ENROLL_CAPTURE_INTERVAL_S: float = 5.0
    AUTO_CCTV_ENROLL_LIFETIME_CAP: int = 5
    AUTO_CCTV_ENROLL_MIN_SELF_SIM: float = 0.30
    AUTO_CCTV_ENROLL_DRY_RUN: bool = False  # If True, log what would be committed but don't write

    # Periodic mean-embedding re-validation interval. Every N frames the
    # tracker walks all currently-recognized tracks, computes the mean
    # of their recent embedding buffer (already maintained for first-
    # recognition aggregation), runs ONE batched FAISS search on those
    # means, and feeds the result through the same swap-gate as a
    # regular re-verify. This adds a strong "stability check" that's
    # noise-resistant — a single outlier frame can't flip the binding,
    # only a sustained shift in the mean can.
    #
    # At 5 fps backend, 150 frames ≈ 30 s; the cost is one batched FAISS
    # search per N=PROCESSING_FPS×30 frames per active session, which is
    # negligible (search_batch_with_margin already takes <5 ms for 4-6
    # tracks). Set to 0 to disable.
    REVALIDATION_INTERVAL_FRAMES: int = 150

    # Spatial+temporal identity hint (the "graveyard") for handling
    # intermittent visibility — a student who turns their head, briefly
    # walks off camera, or gets occluded loses their ByteTrack ID and
    # comes back as a new track. Without this, every re-entry has to
    # re-recognise from scratch and can land in the dead zone (sim
    # 0.30-0.45) for the same student whose phone-only enrolment was
    # marginal at this CCTV distance.
    #
    # When a recognised track expires, we record a tombstone with its
    # last bbox center. When a new track appears within
    # GRAVEYARD_MAX_DIST_NORMALIZED of EXACTLY ONE recent tombstone
    # (within GRAVEYARD_TTL_SECONDS), the new track gets a hint pointing
    # at the previous identity. The hint is then **independently
    # confirmed** by FAISS — only if the same user comes back as top-1
    # at sim >= (RECOGNITION_THRESHOLD - GRAVEYARD_RELAXED_THRESHOLD_DELTA)
    # do we commit. The hint never overrides FAISS top-1: if a different
    # user comes back as top-1 at full threshold, the hint is silently
    # discarded.
    #
    # Safety: setting GRAVEYARD_TTL_SECONDS=0 disables the feature
    # entirely (the lookup short-circuits). The previous attempt at
    # spatial inheritance (CLAUDE.md) was unsafe because it inherited
    # blindly; this version requires FAISS confirmation, so a wrong
    # person walking into the same spot can never inherit — they'd
    # have to actually FAISS-match to the previous user, which is
    # exactly the legitimate signal.
    IDENTITY_GRAVEYARD_TTL_SECONDS: float = 30.0
    IDENTITY_GRAVEYARD_MAX_DIST_NORMALIZED: float = 0.15
    IDENTITY_GRAVEYARD_RELAXED_THRESHOLD_DELTA: float = 0.10
    TRACK_CONFIRM_FRAMES: int = 1  # Recognize immediately on first detection

    # Drift Detection (track ID swap detection)
    DRIFT_SIM_THRESHOLD: float = 0.35  # Cosine sim below this = potential track swap (tolerates 40° head turns)
    DRIFT_CONSECUTIVE_REQUIRED: int = 3  # Consecutive low-sim frames before resetting identity

    # Identity Hold (sticky identity)
    IDENTITY_HOLD_SECONDS: float = 3.0  # Keep showing recognized identity during drift re-verification

    # Tri-state recognition gating (scan_result.recognition_state broadcast field).
    # After UNKNOWN_CONFIRM_ATTEMPTS consecutive FAISS misses on the same track AND
    # the best-seen cosine score stayed below RECOGNITION_THRESHOLD - UNKNOWN_CONFIRM_MARGIN,
    # the track commits to `recognition_state="unknown"` (red "Unknown" on the phone).
    # Below that — or while the peak score is near threshold — the track stays in
    # `recognition_state="warming_up"` so the overlay shows "Detecting…" (orange) instead
    # of misleadingly flashing "Unknown" for a registered user whose first few frames
    # happened to be blurry, off-axis, or shadowed.
    #
    # At PROCESSING_FPS=5 with graduated retries (instant / 0.3s / 1s), 15 attempts
    # corresponds to roughly 12-15 seconds before committing to "Unknown" — long
    # enough for almost any registered face to land a clean match, short enough that
    # a truly unauthorised face still gets red-flagged quickly.
    UNKNOWN_CONFIRM_ATTEMPTS: int = 15
    UNKNOWN_CONFIRM_MARGIN: float = 0.05

    # Fast-commit path for *obvious* unknowns (added 2026-04-25 alongside
    # the live-feed-overlay deploy). When a track's best-seen similarity
    # stays under UNKNOWN_FAST_COMMIT_SCORE for at least
    # UNKNOWN_FAST_COMMIT_ATTEMPTS frames, commit to ``unknown`` even if
    # UNKNOWN_CONFIRM_ATTEMPTS hasn't been reached yet. Rationale: a face
    # producing 0.0 / 0.0 / 0.0 cosine similarity is clearly not enrolled
    # — making the operator wait the full warm-up window for *that* case
    # is wasted UX. Faces that score near threshold (e.g. 0.30 vs 0.38)
    # still go through the gentle UNKNOWN_CONFIRM_ATTEMPTS gate so a real
    # student with brief blur isn't red-flagged.
    UNKNOWN_FAST_COMMIT_SCORE: float = 0.10
    UNKNOWN_FAST_COMMIT_ATTEMPTS: int = 3

    # Track-Based Presence
    EARLY_LEAVE_TIMEOUT: float = 300.0  # Fallback: 5 min absent before early-leave alert (per-schedule override in DB)
    PRESENCE_FLUSH_INTERVAL: float = 10.0  # Seconds between DB presence flushes

    # Frame Grabber
    # Match PROCESSING_FPS so FFmpeg doesn't decode frames the pipeline will drop.
    # "More than 1000 frames duplicated" warnings in the logs indicate a mismatch —
    # keep this equal to or slightly above PROCESSING_FPS.
    FRAME_GRABBER_FPS: float = 20.0
    FRAME_GRABBER_WIDTH: int = 1280  # 720p — gives ~50-80px faces even on wide-angle lenses
    FRAME_GRABBER_HEIGHT: int = 720  # Consistent across all cameras

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PRESENCE_PREFIX: str = "presence"
    REDIS_WS_CHANNEL: str = "ws_broadcast"

    # RTSP
    DEFAULT_RTSP_URL: str = ""  # Fallback RTSP URL (set via env var)

    # WebRTC Streaming (mediamtx + WHEP — replaces HLS for <300ms latency)
    USE_WEBRTC_STREAMING: bool = True  # True=WebRTC, False=fall back to HLS/legacy
    MEDIAMTX_EXTERNAL: bool = False  # True = mediamtx runs as separate container (skip subprocess)
    MEDIAMTX_API_URL: str = "http://localhost:9997"  # mediamtx REST API (internal only)
    MEDIAMTX_WEBRTC_URL: str = "http://localhost:8889"  # mediamtx WHEP endpoint (internal only)
    MEDIAMTX_RTSP_URL: str = "rtsp://localhost:8554"  # mediamtx RTSP endpoint (for recognition in push mode)
    WEBRTC_STUN_URLS: str = "stun:stun.l.google.com:19302"  # Comma-separated STUN URLs (free Google STUN)
    WEBRTC_TURN_URL: str = ""  # Optional: "turn:your-server:3478"
    WEBRTC_TURN_USERNAME: str = ""  # TURN username (empty = no TURN)
    WEBRTC_TURN_CREDENTIAL: str = ""  # TURN credential

    # mediamtx subprocess settings
    MEDIAMTX_BIN_PATH: str = "bin/mediamtx"  # Path to mediamtx binary (relative to backend/)
    MEDIAMTX_CONFIG_PATH: str = "mediamtx.yml"  # Path to mediamtx config (relative to backend/)

    # Recognition
    RECOGNITION_FPS: float = 10.0  # Frames/sec for attendance engine recognition loop
    RECOGNITION_MAX_BATCH_SIZE: int = 50  # Max faces per batch forward pass
    RECOGNITION_MAX_DIM: int = 1280  # Cap frame dimension for detection (balances accuracy vs speed)

    # Service Role (determines which components start)
    # "api-gateway" | "all" (dev)
    SERVICE_ROLE: str = "all"

    # Edge Gateway
    EDGE_API_KEY: str = "edge-secret-key-change-in-production"  # RPi auth

    # Re-enrollment Monitoring
    REENROLL_CHECK_ENABLED: bool = True
    REENROLL_SIMILARITY_THRESHOLD: float = 0.55  # Mean similarity below this triggers re-enroll prompt
    REENROLL_WINDOW_SIZE: int = 20  # Rolling window of recent similarity scores

    # File Storage
    UPLOAD_DIR: str = "data/uploads/faces"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Email (Resend)
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "IAMS <noreply@iams.jrmsu.edu.ph>"
    EMAIL_ENABLED: bool = False  # Master kill switch — set True when Resend API key is configured

    # Notification Jobs
    DAILY_DIGEST_HOUR: int = 18  # Hour (0-23) to send daily digest
    WEEKLY_DIGEST_HOUR: int = 19  # Hour (0-23) to send weekly digest (Sundays)
    NOTIFICATION_RETENTION_DAYS: int = 90  # Days to keep read notifications
    LOW_ATTENDANCE_CHECK_WINDOW_DAYS: int = 30  # Rolling window for low attendance check
    LOW_ATTENDANCE_RENOTIFY_DAYS: int = 7  # Min days between re-notification for low attendance

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    LOG_MAX_BYTES: int = 10485760  # 10MB
    LOG_BACKUP_COUNT: int = 5

    # ───────────────────────────────────────────────────────────────────────
    # Feature flags (2026-04-22 two-app split)
    #
    # The backend image boots into one of two profiles, controlled by these
    # flags:
    #
    # - FULL (on-prem Mac): all flags True — SCRFD + ArcFace + FAISS, every
    #   router, background jobs, frame grabbers. This is the default.
    # - THIN (public VPS):  only AUTH / USERS / SCHEDULES / ROOMS / HEALTH
    #   enabled. The VPS serves the faculty app (login + schedule list + video
    #   relay) and never touches student PII, face embeddings, or attendance
    #   data. Heavy ML imports are skipped, so the VPS container is cheap.
    #
    # See backend/.env.vps.example for the VPS profile and
    # docs/plans/2026-04-22-two-app-split/DESIGN.md for the rationale.
    # ───────────────────────────────────────────────────────────────────────

    ENABLE_ML: bool = True  # SCRFD + ArcFace + FAISS + insightface model load
    ENABLE_REDIS: bool = True  # Identity cache + WS pubsub (tied to ML)
    ENABLE_FRAME_GRABBERS: bool = True  # Persistent RTSP readers (tied to ML)
    ENABLE_BACKGROUND_JOBS: bool = True  # APScheduler, session lifecycle, digests

    # Router-level flags. Always-on routers: auth, users, schedules, rooms, health.
    ENABLE_FACE_ROUTES: bool = True  # /api/v1/face/*
    ENABLE_ATTENDANCE_ROUTES: bool = True  # /api/v1/attendance/*
    ENABLE_PRESENCE_ROUTES: bool = True  # /api/v1/presence/*
    ENABLE_ANALYTICS_ROUTES: bool = True  # /api/v1/analytics/*
    ENABLE_NOTIFICATION_ROUTES: bool = True  # /api/v1/notifications/*
    ENABLE_AUDIT_ROUTES: bool = True  # /api/v1/audit/*
    ENABLE_EDGE_ROUTES: bool = True  # /api/v1/edge/*
    ENABLE_SETTINGS_ROUTES: bool = True  # /api/v1/settings/*
    ENABLE_WS_ROUTES: bool = True  # /api/v1/ws/*
    ENABLE_RECOGNITION_ROUTES: bool = True  # /api/v1/recognitions/*
    ENABLE_ACTIVITY_ROUTES: bool = True  # /api/v1/activity/* — unified event timeline

    # ───────────────────────────────────────────────────────────────────────
    # Recognition Evidence (docs/plans/2026-04-22-recognition-evidence)
    #
    # Every FAISS decision on the realtime pipeline is captured as a row in
    # ``recognition_events`` plus a pair of JPEG crops (live probe + matched
    # registered angle) on disk. Disabled on the VPS thin profile.
    # ───────────────────────────────────────────────────────────────────────
    ENABLE_RECOGNITION_EVIDENCE: bool = True  # Master switch — capture writer lifecycle
    RECOGNITION_EVIDENCE_CROP_ROOT: str = "/var/lib/iams/crops"  # Inside the container
    RECOGNITION_EVIDENCE_CROP_QUALITY: int = 92  # JPEG quality; bumped 75 → 92 on 2026-04-25 — the recognition panel UI showed visibly mushy crops at 75
    RECOGNITION_EVIDENCE_QUEUE_SIZE: int = 1000  # Drop threshold — pipeline must never back-pressure
    RECOGNITION_EVIDENCE_BATCH_ROWS: int = 50  # DB flush trigger — whichever comes first
    RECOGNITION_EVIDENCE_BATCH_MS: int = 500  # DB flush interval

    # Per-(student, decision-state, camera) suppression window for evidence
    # capture. Without this the 5-second re-verify cadence × per-track churn
    # × 2 concurrent cameras flooded the Student Record Detail "Recent
    # detections" panel with 50+ near-identical crops per minute (a static
    # subject in front of a static camera produces visually-identical JPEGs
    # every reverify). Added 2026-04-25.
    #
    # Within this window, repeat events with the *same* outcome — same
    # matched user_id, same matched/ambiguous flags — are dropped at the
    # tracker's submit site so they never reach the writer queue, the DB,
    # disk, or the WebSocket. State changes (new identity swap, miss → match,
    # match → ambiguous, etc.) bypass the throttle so we never lose a
    # genuine signal. Set to 0 to disable.
    RECOGNITION_EVIDENCE_THROTTLE_S: float = 10.0

    # Live-display broadcast rate for the admin Face Comparison panel —
    # an independent fast lane that bypasses the 10 s evidence-persistence
    # throttle so the operator UI feels live for static subjects.
    #
    # Distinction:
    #   - RECOGNITION_EVIDENCE_THROTTLE_S (above): gates DB rows + disk
    #     JPEGs + the `recognition_event` WS message used by the Recognition
    #     Stream panel. 10 s is right for an audit trail.
    #   - LIVE_DISPLAY_BROADCAST_HZ (here): gates an ephemeral
    #     `live_crop_update` WS message used only by the Face Comparison
    #     sheet's Live Crop view. No DB/disk writes — pure broadcast.
    #
    # Bandwidth: ~50 KB JPEG × 1 Hz × N recognized students. At N=5 that
    # is ~250 KB/s on the per-schedule WS, trivial on LAN. Bump down for
    # heavier classrooms or remote operators on slower links. Set to 0 to
    # disable the fast lane entirely (panel falls back to the 10 s
    # recognition_event cadence).
    LIVE_DISPLAY_BROADCAST_HZ: float = 1.0

    # Margin around the SCRFD bbox before cropping for the audit trail.
    # 0.35 means the crop expands 35 % outward on each side, giving a head
    # + shoulders framing instead of a tight face-only crop. Added
    # 2026-04-25 — without margin, classroom-distance crops at 60×80 px
    # rendered as mush in the admin recognition stream panel.
    EVIDENCE_CROP_MARGIN_PCT: float = 0.35
    # Upscale target (long edge) for tiny crops. Faces shot at >5 m on a
    # 1280×720 source frame yield ~50 px crops; we upscale to 240 px with
    # INTER_CUBIC so the panel renders sharp instead of asking the
    # browser to bilinear-upscale a 50-px JPEG into a 240-px display box.
    EVIDENCE_CROP_TARGET_LONG_EDGE: int = 240

    # Retention — daily APScheduler job prunes crops + rows past these limits.
    # Dry-run is ON by default until the operator has confirmed at least one
    # sweep logs the expected delete set, to keep a config mistake from wiping
    # the thesis corpus.
    ENABLE_RECOGNITION_EVIDENCE_RETENTION: bool = True
    RECOGNITION_EVIDENCE_RETENTION_DRY_RUN: bool = True
    RECOGNITION_CROP_RETENTION_DAYS: int = 30
    RECOGNITION_EVENT_RETENTION_DAYS: int = 365
    RECOGNITION_EVIDENCE_RETENTION_MAX_DELETES: int = 10000  # Hard safety cap per run

    # ───────────────────────────────────────────────────────────────────────
    # Recognition Evidence — Phase 5 (enterprise hardening)
    #
    # Backend selector: "filesystem" keeps crops in the host-mounted Docker
    # volume (Phases 1–4). "minio" puts them in an S3-compatible object
    # store on the same host, and crop fetches become 302 redirects to
    # time-limited presigned URLs. The API never proxies bytes.
    #
    # Cutover procedure is in docs/plans/2026-04-22-recognition-evidence/
    # RUNBOOK.md §Phase 5 — flip this env var, restart, run the migration
    # script to backfill existing FS crops into MinIO.
    # ───────────────────────────────────────────────────────────────────────
    RECOGNITION_EVIDENCE_BACKEND: str = "filesystem"  # "filesystem" | "minio"

    # MinIO (S3-compatible) client config. Only read when BACKEND=="minio".
    MINIO_ENDPOINT: str = "minio:9000"  # Docker-network hostname
    MINIO_ACCESS_KEY: str = "iams"
    MINIO_SECRET_KEY: str = "iams-minio-dev-key"  # Override via env in prod
    MINIO_SECURE: bool = False  # TLS to MinIO; onprem LAN = plain HTTP
    MINIO_BUCKET: str = "iams-recognition-evidence"
    MINIO_REGION: str = "us-east-1"  # S3 API requires a region string; unused locally

    # Presigned-URL TTL for the 302 redirect path served from
    # /api/v1/recognitions/{id}/live-crop and /registered-crop. Short TTL so
    # a leaked URL can't be replayed for long; just long enough for a normal
    # page render + image fetch.
    RECOGNITION_EVIDENCE_SIGNED_URL_TTL: int = 60  # seconds

    # Access auditing: every crop fetch inserts a recognition_access_audit
    # row. Feeds the /audit/recognition-access admin page. Independent of
    # the storage backend — works for filesystem and MinIO.
    ENABLE_RECOGNITION_ACCESS_AUDIT: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# Initialize settings
settings = Settings()

# --- Startup validation: catch dangerous defaults in production ---
# Only enforce in explicit production mode (DEBUG=False AND not in test runner)
_is_testing = "pytest" in sys.modules or os.getenv("TESTING", "").lower() in ("1", "true")
if not settings.DEBUG and not _is_testing:
    if settings.SECRET_KEY == "dev-secret-key-change-in-production":
        raise RuntimeError("SECRET_KEY must be changed in production")
    if settings.EDGE_API_KEY == "edge-secret-key-change-in-production":
        raise RuntimeError("EDGE_API_KEY must be changed in production")


class _HLSAccessFilter(logging.Filter):
    """
    Drop uvicorn access-log records for routine HLS media delivery.

    The mobile player polls playlist.m3u8 several times per second and
    fetches a new .m4s segment every ~0.5 s.  None of these lines carry
    actionable information during normal operation and they drown out
    everything else in the terminal.
    """

    _HLS_NOISE = ("playlist.m3u8", ".m4s", "init.mp4")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "/hls/" not in msg:
            return True
        return not any(token in msg for token in self._HLS_NOISE)


def setup_logging() -> logging.Logger:
    """
    Setup structured logging with file rotation

    Returns:
        Configured logger instance
    """
    # Suppress noisy HLS media delivery from uvicorn's access log
    logging.getLogger("uvicorn.access").addFilter(_HLSAccessFilter())

    # SQLAlchemy echoes every BEGIN/COMMIT/query at INFO when echo=True.
    # Silence it here regardless of the engine echo setting so it doesn't
    # drown out application logs.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logger = logging.getLogger("iams")

    # Set level based on debug mode
    if settings.DEBUG:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Create logs directory if it doesn't exist
    log_path = Path(settings.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        settings.LOG_FILE, maxBytes=settings.LOG_MAX_BYTES, backupCount=settings.LOG_BACKUP_COUNT
    )

    # Console handler
    console_handler = logging.StreamHandler()

    # Format: [timestamp] [level] [module] message
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers if not already added
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


# Initialize logger
logger = setup_logging()
