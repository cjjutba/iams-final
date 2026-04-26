"""
Auto CCTV Enrolment — sliding-window edition (2026-04-26)

Opportunistically captures real CCTV face embeddings during a student's
sessions and adds them to FAISS + the face_embeddings table — same data
shape as scripts/cctv_enroll.py would produce, but triggered automatically
with no operator action and no student UI.

Flow
----
1. The realtime tracker calls ``offer_capture(user_id, embedding,
   crop_bgr, confidence, frames_seen, blur_score)`` on every recognition
   decision that crossed the recognition threshold.
2. This module checks all eligibility gates (confidence, stability,
   capture spacing, daily-throttle when at the cap) and if they pass,
   appends the ``(embedding, crop, quality)`` to a per-(user, room)
   buffer.
3. When the buffer reaches ``AUTO_CCTV_ENROLL_TARGET_CAPTURES``, the
   batch is handed off to a background worker for commit. The worker
   runs:
     a) **Self-similarity gate** — same as the manual cctv_enroll path
        (mean cosine sim against the user's phone embedding >=
        AUTO_CCTV_ENROLL_MIN_SELF_SIM).
     b) **Swap-safe gate** — each capture is FAISS-searched against the
        current index; if any OTHER user's existing embeddings beat the
        claimed user's existing embeddings by more than
        ``RECOGNITION_MARGIN`` minus the configured swap-safe margin,
        the entire batch is dropped. This is the structural defence
        against the 2026-04-25 Desiree↔Ivy Leah identity-swap failure.
     c) **Sliding-window eviction** — when the (user, room) is at the
        cap, the lowest-quality existing CCTV embedding (composite of
        confidence + crop sharpness; NULL = most-evictable) is removed
        from face_embeddings + faiss_manager.user_map + the on-disk
        JPEG before the new capture is inserted.
4. After successful commit, the per-(user, room) replacement counter is
   bumped (one replacement = one batch, not one capture) so a single
   bad-lighting day can't rewrite the cluster.

Safety
------
The 2026-04-25 morning adaptive-enrollment failure modes (wrong-identity
poisoning the cluster) are closed by structural design:

* **Per-capture cross-user check.** A wrong-identity batch fails the
  swap-safe gate on at least one capture and the whole batch is
  discarded — no half-state is ever written.
* **Buffer-then-validate, not write-on-each-frame.** A wrong lock-in
  has to survive the stability window, the per-capture spacing, the
  self-similarity gate, AND the swap-safe gate at commit time.
* **Daily throttle past the cap.** Even with everything else right,
  no more than ``AUTO_CCTV_ENROLL_DAILY_REPLACEMENT_LIMIT`` batches
  can replace existing captures per UTC day per (user, room). Cluster
  drift speed is bounded.
* **No FAISS write from the realtime thread.** Commit happens in a
  background worker so a slow DB doesn't block the live overlay; the
  realtime thread just appends to an in-memory deque.

Boundary
--------
This module does NOT decide whether to recognise a face — that's the
tracker's job. It just observes confident recognitions and decides
whether THIS recognition should also become a permanent training
example. It never writes to FAISS unless the manual ``cctv_enroll``
contract PLUS the swap-safe gate are satisfied.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

import cv2
import numpy as np

from app.config import settings

logger = logging.getLogger("iams.auto_cctv_enroller")


@dataclass
class _UserRoomEnrollState:
    """Per-(user, room) auto-enrolment state, in memory only.

    Persists across sessions on the same gateway process. The
    ``cctv_count`` counter is bootstrapped from the DB at startup so
    sliding-window state stays consistent across server restarts.

    Why per-room: CCTV embeddings captured from one camera (e.g. EB226)
    don't always generalise to another camera (e.g. EB227) — different
    lens, lighting, and seating angle produce different embedding
    distributions. Tracking captures per (user, room) lets us hit the
    cap independently in each room, so a student auto-enrolled in
    EB226 still gets captured the first time they appear in EB227.
    Replaces the single-namespace per-user counter (Phase 1, 2026-04-25).
    """

    # face_embeddings rows with angle_label cctv_<room>_*. Bootstrapped
    # from DB at startup; updated post-commit. When this reaches the
    # configured lifetime cap, we switch from append-mode to sliding-
    # window replacement mode.
    cctv_count: int = 0
    # Buffer carries dicts: {embedding, crop_bytes, confidence, blur_score, quality, captured_at}
    buffer: deque = field(default_factory=lambda: deque(maxlen=10))
    last_capture_at: float = 0.0
    first_capture_at: float = 0.0
    consecutive_high_conf_frames: int = 0
    last_user_id_seen_at: float = 0.0  # monotonic ts of last call for this (user, room) — gates the sighting-gap reset
    last_track_id: int | None = None  # informational — kept for log context
    commit_in_flight: bool = False  # prevents double-submit while worker runs

    # Sliding-window replacement throttle (2026-04-26).
    # Counts BATCHES (not individual captures) committed in replacement
    # mode within the current UTC day. Pre-cap commits don't count
    # because they're filling rather than replacing.
    replacements_today: int = 0
    replacement_window_utc_date: str = ""  # ISO date string ("2026-04-26") for current day

    def reset_buffer(self) -> None:
        self.buffer.clear()
        self.first_capture_at = 0.0
        self.last_capture_at = 0.0
        self.consecutive_high_conf_frames = 0


# Sentinel room key for legacy ``cctv_<idx>`` rows (no room context).
# These contribute to the user's "has any cctv" status but do NOT
# saturate any specific room's lifetime cap, so a user with five
# legacy captures still triggers auto-enrol in every room they
# subsequently appear in. Legacy rows ARE evictable when picked as
# the lowest-quality candidate during sliding-window replacement.
_LEGACY_ROOM_KEY = "_legacy"


def _compute_quality(confidence: float, blur_score: float | None) -> float:
    """Composite quality score: confidence + normalized sharpness.

    Both inputs are ∈ [0, 1] after normalisation. Output ∈ [0, 1].
    Used both for picking the eviction victim AND deciding whether the
    new candidate beats the worst existing — same scale on both sides.

    Configurable weights via settings.AUTO_CCTV_ENROLL_QUALITY_*. Default
    is 0.6 confidence + 0.4 normalized blur (BLUR_NORM_MAX=200 sets the
    "very sharp" ceiling on the M5 + Reolink combo).
    """
    conf = max(0.0, min(1.0, confidence))
    if blur_score is None or blur_score < 0:
        norm_blur = 0.0
    else:
        norm_blur = max(0.0, min(1.0, blur_score / max(1.0, settings.AUTO_CCTV_ENROLL_BLUR_NORM_MAX)))
    return (
        settings.AUTO_CCTV_ENROLL_QUALITY_CONFIDENCE_WEIGHT * conf
        + settings.AUTO_CCTV_ENROLL_QUALITY_BLUR_WEIGHT * norm_blur
    )


def _utc_today_str() -> str:
    """Current UTC date as 'YYYY-MM-DD' for the daily-throttle window."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class AutoCctvEnroller:
    """Process-wide singleton coordinating auto-enrolment across all sessions.

    One instance is created at api-gateway startup; SessionPipeline /
    RealtimeTracker call ``offer_capture`` on every confident recognition.
    """

    _instance: "AutoCctvEnroller | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "AutoCctvEnroller":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_once()
        return cls._instance

    def _init_once(self) -> None:
        # Per-(user_id, room_key) state. The room key is the
        # normalised room.stream_key (e.g. ``"eb226"``). State for the
        # same user_id under different room_keys is tracked
        # independently, so the lifetime cap fires per room rather
        # than globally.
        self._states: dict[tuple[str, str], _UserRoomEnrollState] = {}
        self._states_lock = threading.RLock()
        # Single-threaded executor: serialises commits so two simultaneous
        # buffer-full events don't both try to grab DB transactions /
        # mutate FAISS at once.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="auto-cctv-enroll")
        self._initialised = False
        # Counter of orphan FAISS vectors created by sliding-window
        # eviction (IndexFlatIP can't truly delete; only the user_map
        # entry is removed). Operator can query this to decide when to
        # run scripts.rebuild_faiss to compact the index.
        self._orphans_since_boot: int = 0

    def bootstrap_from_db(self) -> None:
        """Populate per-(user, room) cctv_count from the DB so the
        sliding-window logic stays consistent across server restarts.

        Parses each ``face_embeddings.angle_label`` via
        ``app.utils.cctv_label.parse_cctv_label``:
          * ``cctv_<idx>``           — legacy, room-agnostic. Bucketed
            under the ``_legacy`` sentinel; doesn't fill any specific
            room's cap, so a user with only legacy captures still
            triggers fresh per-room captures going forward.
          * ``cctv_<room>_<idx>``    — modern, room-scoped. Bucketed
            under that room.

        Cheap: one query per gateway startup. Safe to call again later
        if you want to refresh after a manual enrol.
        """
        from app.database import SessionLocal
        from app.models.face_embedding import FaceEmbedding
        from app.models.face_registration import FaceRegistration
        from app.utils.cctv_label import parse_cctv_label

        db = SessionLocal()
        try:
            rows = (
                db.query(FaceRegistration.user_id, FaceEmbedding.angle_label)
                .join(FaceEmbedding, FaceEmbedding.registration_id == FaceRegistration.id)
                .filter(FaceEmbedding.angle_label.like("cctv_%"))
                .filter(FaceRegistration.is_active.is_(True))
                .all()
            )
            counts: dict[tuple[str, str], int] = {}
            for user_id, label in rows:
                room_key, idx = parse_cctv_label(label)
                if idx is None:
                    continue
                key = (str(user_id), room_key or _LEGACY_ROOM_KEY)
                counts[key] = counts.get(key, 0) + 1
            with self._states_lock:
                for key, cnt in counts.items():
                    state = self._states.setdefault(key, _UserRoomEnrollState())
                    state.cctv_count = cnt
            self._initialised = True
            logger.info(
                "AutoCctvEnroller bootstrap: %d (user, room) pair(s) already have "
                "cctv enrolment (legacy and per-room rows combined) | "
                "config: enabled=%s min_conf=%.2f stable_frames=%d target=%d "
                "interval_s=%.1f sighting_gap_s=%.1f cap=%d self_sim=%.2f "
                "replacement=%s daily_replace_limit=%d swap_safe_margin=%.2f dry_run=%s",
                len(counts),
                settings.AUTO_CCTV_ENROLL_ENABLED,
                settings.AUTO_CCTV_ENROLL_MIN_CONFIDENCE,
                settings.AUTO_CCTV_ENROLL_MIN_STABLE_FRAMES,
                settings.AUTO_CCTV_ENROLL_TARGET_CAPTURES,
                settings.AUTO_CCTV_ENROLL_CAPTURE_INTERVAL_S,
                settings.AUTO_CCTV_ENROLL_SIGHTING_GAP_S,
                settings.AUTO_CCTV_ENROLL_LIFETIME_CAP,
                settings.AUTO_CCTV_ENROLL_MIN_SELF_SIM,
                settings.AUTO_CCTV_ENROLL_REPLACEMENT_ENABLED,
                settings.AUTO_CCTV_ENROLL_DAILY_REPLACEMENT_LIMIT,
                settings.AUTO_CCTV_ENROLL_SWAP_SAFE_MARGIN,
                settings.AUTO_CCTV_ENROLL_DRY_RUN,
            )
        except Exception:
            logger.exception("AutoCctvEnroller bootstrap failed (will run uninitialised)")
        finally:
            db.close()

    def _get_state(self, user_id: str, room_key: str) -> _UserRoomEnrollState:
        with self._states_lock:
            return self._states.setdefault(
                (user_id, room_key), _UserRoomEnrollState()
            )

    def _normalise_room(self, room_stream_key: str | None) -> str:
        """Return the canonical room key used as the per-room state key.

        Empty / None falls back to ``"unknown"`` so the offer still gets
        rate-limited and capped — better to have *some* memory of "we
        already captured for this user in this null-room context" than
        to flood when room context is missing (e.g. CLI invocations).
        """
        from app.utils.cctv_label import normalize_room_key

        return normalize_room_key(room_stream_key) or "unknown"

    def _maybe_reset_replacement_window(self, state: _UserRoomEnrollState) -> None:
        """Reset replacements_today when crossing into a new UTC day."""
        today = _utc_today_str()
        if state.replacement_window_utc_date != today:
            state.replacement_window_utc_date = today
            state.replacements_today = 0

    def offer_capture(
        self,
        *,
        user_id: str,
        track_id: int,
        embedding: np.ndarray,
        crop_bgr: np.ndarray | None,
        confidence: float,
        frames_seen: int,
        room_stream_key: str | None = None,
        blur_score: float | None = None,
    ) -> None:
        """Called by RealtimeTracker on every confident recognition.

        Returns immediately. Heavy work (DB writes, disk I/O, FAISS
        mutation) happens on the background executor when a buffer fills.
        Designed to be called from the realtime hot path with negligible
        overhead — typical cost is one dict lookup + a few comparisons.

        ``blur_score`` is the Laplacian variance of the crop. The realtime
        tracker's ``assess_recognition_quality`` already computes this
        for the gating decision; passing it through saves a redundant
        cv2.cvtColor + cv2.Laplacian call here.
        """
        if not settings.AUTO_CCTV_ENROLL_ENABLED:
            return
        if not user_id:
            return

        room_key = self._normalise_room(room_stream_key)
        state = self._get_state(user_id, room_key)

        if state.commit_in_flight:
            return

        # Gating: cap reached?
        cap_reached = state.cctv_count >= settings.AUTO_CCTV_ENROLL_LIFETIME_CAP
        if cap_reached:
            if not settings.AUTO_CCTV_ENROLL_REPLACEMENT_ENABLED:
                # Legacy hard-stop behaviour
                return
            # Sliding-window mode — check daily throttle. Note: we do
            # not block buffer fills here, only commits that would
            # actually replace existing rows. Buffering a few extra
            # captures we'll throw away is cheap; the gate that
            # matters runs at commit time. We early-out only if
            # the throttle is fully spent so we don't waste hot-path
            # cycles for a no-op.
            self._maybe_reset_replacement_window(state)
            if state.replacements_today >= settings.AUTO_CCTV_ENROLL_DAILY_REPLACEMENT_LIMIT:
                return

        # Stability counter — sustained presence of the SAME user_id in
        # the SAME room, even across ByteTrack re-identifications.
        # Reset condition is a SIGHTING GAP — if the same user hasn't
        # been seen in this room for ≥ AUTO_CCTV_ENROLL_SIGHTING_GAP_S
        # seconds, the counter resets (the student left the room and a
        # later return is a fresh stability window). Track-id changes
        # within that gap are tracker-quality noise and do NOT reset.
        # Identity-correctness still holds because user_id is matched
        # exactly — a flicker that misidentified would be caught by the
        # frame-mutex / swap-gate BEFORE offer_capture is even called,
        # and the commit-time self-similarity + swap-safe gates are the
        # final floor.
        now = time.monotonic()
        sighting_gap = (
            (now - state.last_user_id_seen_at)
            if state.last_user_id_seen_at > 0
            else 0.0
        )
        if sighting_gap > settings.AUTO_CCTV_ENROLL_SIGHTING_GAP_S:
            state.consecutive_high_conf_frames = 0
            state.reset_buffer()
        state.last_track_id = track_id  # informational; doesn't gate
        state.last_user_id_seen_at = now
        state.consecutive_high_conf_frames += 1

        # Confidence + stability gates
        if confidence < settings.AUTO_CCTV_ENROLL_MIN_CONFIDENCE:
            return
        if state.consecutive_high_conf_frames < settings.AUTO_CCTV_ENROLL_MIN_STABLE_FRAMES:
            return

        # Capture-spacing gate — wait between consecutive captures so the
        # buffer covers diverse poses, not 5 frames from the same instant.
        if (now - state.last_capture_at) < settings.AUTO_CCTV_ENROLL_CAPTURE_INTERVAL_S:
            return

        # OK — accept this capture into the buffer.
        if crop_bgr is None or crop_bgr.size == 0:
            return
        try:
            ok, jpg = cv2.imencode(".jpg", crop_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
            crop_bytes = jpg.tobytes() if ok else b""
        except Exception:
            crop_bytes = b""

        composite_quality = _compute_quality(confidence, blur_score)
        state.buffer.append({
            "embedding": embedding.astype(np.float32, copy=True),
            "crop_bytes": crop_bytes,
            "confidence": float(confidence),
            "blur_score": float(blur_score) if blur_score is not None else None,
            "quality": composite_quality,
            "captured_at": now,
        })
        state.last_capture_at = now
        if state.first_capture_at == 0.0:
            state.first_capture_at = now

        logger.info(
            "auto-cctv: buffered capture %d/%d for user=%s room=%s conf=%.3f "
            "blur=%s quality=%.3f frames=%d (mode=%s, %d/%d existing)",
            len(state.buffer),
            settings.AUTO_CCTV_ENROLL_TARGET_CAPTURES,
            user_id[:8],
            room_key,
            confidence,
            f"{blur_score:.1f}" if blur_score is not None else "n/a",
            composite_quality,
            frames_seen,
            "replace" if cap_reached else "fill",
            state.cctv_count,
            settings.AUTO_CCTV_ENROLL_LIFETIME_CAP,
        )

        # Commit threshold reached?
        if len(state.buffer) >= settings.AUTO_CCTV_ENROLL_TARGET_CAPTURES:
            buffered = list(state.buffer)
            state.commit_in_flight = True
            state.reset_buffer()
            self._executor.submit(
                self._commit_batch, user_id, buffered, room_key
            )

    def _commit_batch(
        self,
        user_id: str,
        captures: list[dict],
        room_key: str,
    ) -> None:
        """Background commit. Must not raise into the executor."""
        try:
            self._do_commit(user_id, captures, room_key)
        except Exception:
            logger.exception(
                "auto-cctv: commit failed for user=%s room=%s",
                user_id[:8],
                room_key,
            )
        finally:
            state = self._get_state(user_id, room_key)
            state.commit_in_flight = False

    def _swap_safe_check(
        self,
        captures: list[dict],
        user_id: str,
    ) -> tuple[bool, str]:
        """Per-capture cross-user FAISS check.

        For each new embedding, search the live FAISS index. If any OTHER
        user's existing vectors come closer than the claimed user's by
        more than ``AUTO_CCTV_ENROLL_SWAP_SAFE_MARGIN``, refuse the entire
        batch. This is the structural defence against the 2026-04-25
        Desiree↔Ivy Leah failure mode: a single ambiguous capture is
        enough to discard the whole commit.

        Returns (passed, reason). When passed, reason is empty.
        """
        from app.services.ml.faiss_manager import faiss_manager

        margin = settings.AUTO_CCTV_ENROLL_SWAP_SAFE_MARGIN
        # Generous k so we find the user's own vectors plus other users'
        # nearby ones even on indexes with many vectors per user.
        k = max(20, settings.RECOGNITION_TOP_K * 5)

        for i, cap in enumerate(captures):
            results = faiss_manager.search(cap["embedding"], k=k, threshold=0.0)
            if not results:
                # Empty index — first commit for this user post-rebuild.
                # No competing users to swap-check against; safe by definition.
                continue
            claimed_top = max(
                (sim for uid, sim in results if uid == user_id),
                default=None,
            )
            competing_top = max(
                (sim for uid, sim in results if uid != user_id),
                default=None,
            )
            if claimed_top is None:
                # The claimed user has zero existing vectors in FAISS.
                # This shouldn't happen in practice (offer_capture can
                # only fire for already-recognised users) but guard
                # against it anyway. Without a baseline to compare
                # against, fall back to "competing must be below
                # RECOGNITION_THRESHOLD" — the realtime path's own
                # commit floor.
                if competing_top is not None and competing_top >= settings.RECOGNITION_THRESHOLD:
                    return False, (
                        f"capture {i}: claimed user has no FAISS baseline AND a different "
                        f"user (sim={competing_top:.3f}) clears RECOGNITION_THRESHOLD"
                    )
                continue
            if competing_top is None:
                continue  # No other users in the result — trivially safe
            if competing_top > claimed_top - margin:
                return False, (
                    f"capture {i}: a different user matched at sim={competing_top:.3f} "
                    f"vs claimed user at sim={claimed_top:.3f} (margin {margin:.2f}); "
                    f"this batch is too close to a wrong-identity to be safely committed"
                )

        return True, ""

    def _select_eviction_victims(
        self,
        existing: list,
        n_needed: int,
        new_quality_min: float,
    ) -> list:
        """Pick the lowest-quality existing CCTV embeddings to evict.

        ``existing`` is a list of FaceEmbedding rows for this (user, room).
        ``n_needed`` is the number of victims required (= number of new
        captures to insert). ``new_quality_min`` is the lowest quality
        in the new batch — we only return a victim if its quality is
        STRICTLY LOWER than this, so we never trade a sharp existing
        capture for a blurry new one. NULL quality is treated as the
        most-evictable (i.e. always loses).

        Returns up to ``n_needed`` victims sorted ascending by quality.
        Caller decides whether to commit or skip based on len() of the
        returned list.
        """
        # Pair each row with its effective quality (NULL -> -inf so it
        # loses every comparison)
        scored = []
        for row in existing:
            q = row.quality_score
            scored.append((q if q is not None else -1.0, row))
        # Sort ascending — lowest quality first
        scored.sort(key=lambda t: t[0])
        victims = []
        for q, row in scored:
            if len(victims) >= n_needed:
                break
            # Only evict if the existing row is meaningfully worse than
            # the new candidates — strict-less-than guards against
            # endless churn between captures of equal quality.
            if q < new_quality_min:
                victims.append(row)
        return victims

    def _do_commit(
        self,
        user_id: str,
        captures: list[dict],
        room_key: str,
    ) -> None:
        from app.database import SessionLocal
        from app.repositories.face_repository import FaceRepository
        from app.services.ml.faiss_manager import faiss_manager
        from app.utils.cctv_label import build_cctv_label, parse_cctv_label
        from app.utils.face_image_storage import FaceImageStorage

        if settings.AUTO_CCTV_ENROLL_DRY_RUN:
            logger.info(
                "auto-cctv DRY_RUN: would commit %d captures for user=%s room=%s "
                "(mean conf=%.3f mean quality=%.3f)",
                len(captures),
                user_id[:8],
                room_key,
                float(np.mean([c["confidence"] for c in captures])),
                float(np.mean([c["quality"] for c in captures])),
            )
            return

        db = SessionLocal()
        try:
            repo = FaceRepository(db)
            registration = repo.get_by_user(user_id)
            if registration is None:
                logger.warning(
                    "auto-cctv: user=%s has no active registration; refusing commit",
                    user_id[:8],
                )
                return

            # ── Gate 1: self-similarity (mean sim to phone embedding) ──
            existing_phone_emb = np.frombuffer(
                registration.embedding_vector, dtype=np.float32
            )
            new_embs = np.stack([c["embedding"] for c in captures]).astype(np.float32)
            sims_to_phone = (new_embs @ existing_phone_emb).tolist()
            mean_sim = float(np.mean(sims_to_phone))
            if mean_sim < settings.AUTO_CCTV_ENROLL_MIN_SELF_SIM:
                logger.warning(
                    "auto-cctv: self-similarity gate failed for user=%s room=%s "
                    "(mean=%.3f < %.3f); discarding %d captures",
                    user_id[:8],
                    room_key,
                    mean_sim,
                    settings.AUTO_CCTV_ENROLL_MIN_SELF_SIM,
                    len(captures),
                )
                return

            # ── Gate 2: swap-safe per-capture cross-user check ─────────
            passed, reason = self._swap_safe_check(captures, user_id)
            if not passed:
                logger.warning(
                    "auto-cctv: swap-safe gate failed for user=%s room=%s — %s; "
                    "discarding %d captures",
                    user_id[:8],
                    room_key,
                    reason,
                    len(captures),
                )
                return

            # ── Sliding-window: pick eviction victims if at cap ────────
            state = self._get_state(user_id, room_key)
            existing_room_rows = repo.get_cctv_embeddings_by_user(user_id, room_key)
            # Track the legacy bucket separately — when we're committing
            # for a real room and at the cap, prefer evicting from the
            # legacy (room-agnostic) bucket FIRST since those captures
            # have no room calibration. This preserves the room-scoped
            # cluster's coverage.
            legacy_rows = repo.get_cctv_embeddings_by_user(user_id, "_legacy")
            existing_combined = existing_room_rows + legacy_rows

            victims = []
            cap = settings.AUTO_CCTV_ENROLL_LIFETIME_CAP
            current_count = len(existing_room_rows)  # only room-scoped count toward cap
            replacement_mode = current_count >= cap

            if replacement_mode:
                if not settings.AUTO_CCTV_ENROLL_REPLACEMENT_ENABLED:
                    logger.info(
                        "auto-cctv: cap reached for user=%s room=%s and replacement "
                        "disabled; skipping commit",
                        user_id[:8],
                        room_key,
                    )
                    return
                # Daily throttle gate — recheck post-buffer because the
                # buffer may have filled across a window boundary.
                self._maybe_reset_replacement_window(state)
                if state.replacements_today >= settings.AUTO_CCTV_ENROLL_DAILY_REPLACEMENT_LIMIT:
                    logger.info(
                        "auto-cctv: daily replacement throttle reached for user=%s "
                        "room=%s (%d/%d batches today); discarding batch",
                        user_id[:8],
                        room_key,
                        state.replacements_today,
                        settings.AUTO_CCTV_ENROLL_DAILY_REPLACEMENT_LIMIT,
                    )
                    return
                # Pick victims. Quality of the new batch sets the floor —
                # we never trade a sharp existing for a blurry new.
                new_quality_min = float(min(c["quality"] for c in captures))
                victims = self._select_eviction_victims(
                    existing_combined, len(captures), new_quality_min
                )
                if not victims:
                    logger.info(
                        "auto-cctv: no eviction candidate for user=%s room=%s — "
                        "every existing capture has quality ≥ new batch floor (%.3f); "
                        "skipping batch",
                        user_id[:8],
                        room_key,
                        new_quality_min,
                    )
                    return
                # If we couldn't find enough victims, only commit as many
                # new captures as we can pair with a victim — that keeps
                # the cap honoured. (Common case: 5 new, 5 victims, all good.)
                if len(victims) < len(captures):
                    captures = sorted(captures, key=lambda c: c["quality"], reverse=True)[: len(victims)]
                    new_embs = np.stack([c["embedding"] for c in captures]).astype(np.float32)

            # ── Pick next cctv_<room>_<idx> labels ─────────────────────
            # Counted PER ROOM so each room's index space is independent.
            # Legacy ``cctv_<idx>`` rows and other rooms' rows are ignored
            # when computing ``next_idx`` for this room.
            existing_embs = repo.get_embeddings_by_registration(str(registration.id))
            existing_room_indices: list[int] = []
            for emb in existing_embs:
                emb_room, emb_idx = parse_cctv_label(emb.angle_label)
                if emb_idx is None:
                    continue
                if emb_room == room_key:
                    existing_room_indices.append(emb_idx)
            next_idx = max(existing_room_indices, default=-1) + 1
            labels = [
                build_cctv_label(room_key, next_idx + i)
                for i in range(len(captures))
            ]

            # ── Evict victims (DB row + FAISS user_map + JPEG) ─────────
            victim_faiss_ids: list[int] = []
            victim_storage_keys: list[str] = []
            for v in victims:
                victim_faiss_ids.append(int(v.faiss_id))
                if v.image_storage_key:
                    victim_storage_keys.append(v.image_storage_key)
            if victim_faiss_ids:
                deleted = repo.delete_embeddings_by_faiss_ids(victim_faiss_ids)
                # Pop from FAISS user_map (orphaned vector remains in
                # IndexFlatIP — no top-K can return it, but ntotal
                # inflates. Periodic scripts.rebuild_faiss is the cleanup.)
                for fid in victim_faiss_ids:
                    try:
                        faiss_manager.remove(fid)
                    except Exception:
                        logger.debug("auto-cctv: FAISS user_map remove failed for fid=%d", fid, exc_info=True)
                self._orphans_since_boot += len(victim_faiss_ids)
                logger.info(
                    "auto-cctv: evicted %d CCTV row(s) for user=%s room=%s "
                    "(rows deleted=%d, FAISS orphans since boot=%d)",
                    len(victim_faiss_ids),
                    user_id[:8],
                    room_key,
                    deleted,
                    self._orphans_since_boot,
                )

            # ── Add new captures to FAISS ──────────────────────────────
            try:
                faiss_ids = faiss_manager.add_batch(
                    new_embs, [user_id] * len(new_embs)
                )
            except Exception:
                # FAISS failed — try to rollback the victim deletions.
                # The orphan bookkeeping is already updated; that's fine
                # because they ARE orphans now (we removed them from
                # user_map). The DB rows are gone; rebuild_faiss after
                # restart is the recovery.
                logger.exception(
                    "auto-cctv: FAISS add failed for user=%s room=%s after evicting %d victim(s)",
                    user_id[:8],
                    room_key,
                    len(victim_faiss_ids),
                )
                if victim_faiss_ids:
                    try:
                        db.commit()  # commit the victim deletions so DB and FAISS stay in sync
                    except Exception:
                        db.rollback()
                return

            # ── DB persist + crop storage in one transaction ──────────
            try:
                entries = []
                for fid, cap, label in zip(faiss_ids, captures, labels):
                    entries.append({
                        "faiss_id": fid,
                        "embedding_vector": cap["embedding"].astype(np.float32).tobytes(),
                        "angle_label": label,
                        "quality_score": cap["quality"],
                    })
                repo.create_embeddings_batch(str(registration.id), entries)
                db.commit()

                # Persist crops (best effort)
                storage = FaceImageStorage()
                keys_by_faiss: dict[int, str] = {}
                for fid, cap, label in zip(faiss_ids, captures, labels):
                    if not cap["crop_bytes"]:
                        continue
                    key = storage.save_registration_image(user_id, label, cap["crop_bytes"])
                    if key:
                        keys_by_faiss[int(fid)] = key
                if keys_by_faiss:
                    repo.set_image_storage_keys(str(registration.id), keys_by_faiss)
                    db.commit()

                # Best-effort delete of evicted JPEGs (after the main
                # commit so a delete failure doesn't roll back the
                # insert). The storage_key files becoming orphans is
                # harmless — they're never referenced from the DB.
                for storage_key in victim_storage_keys:
                    try:
                        path = storage.resolve_path(storage_key)
                        path.unlink(missing_ok=True)
                    except Exception:
                        logger.debug(
                            "auto-cctv: failed to delete evicted JPEG key=%s",
                            storage_key,
                            exc_info=True,
                        )

                faiss_manager.save()

                # Update in-memory accounting. cctv_count is the per-room
                # row count (refreshed from DB rather than incremented
                # blindly so it matches reality even after evictions
                # crossed bucket boundaries).
                refreshed_count = len(repo.get_cctv_embeddings_by_user(user_id, room_key))
                state.cctv_count = refreshed_count
                if replacement_mode:
                    state.replacements_today += 1

                logger.info(
                    "auto-cctv: COMMITTED %d captures for user=%s room=%s mode=%s "
                    "(faiss_ids=%s mean_sim_to_phone=%.3f mean_quality=%.3f "
                    "evicted=%d new_total=%d/%d replacements_today=%d/%d)",
                    len(captures),
                    user_id[:8],
                    room_key,
                    "replace" if replacement_mode else "fill",
                    faiss_ids,
                    mean_sim,
                    float(np.mean([c["quality"] for c in captures])),
                    len(victims),
                    refreshed_count,
                    cap,
                    state.replacements_today,
                    settings.AUTO_CCTV_ENROLL_DAILY_REPLACEMENT_LIMIT,
                )
            except Exception:
                db.rollback()
                # Best-effort FAISS rollback for the new captures
                for fid in faiss_ids:
                    try:
                        faiss_manager.remove(fid)
                    except Exception:
                        pass
                logger.exception(
                    "auto-cctv: DB persist failed for user=%s room=%s; FAISS rolled back",
                    user_id[:8],
                    room_key,
                )
        finally:
            db.close()


# Module-level accessor — mirrors the pattern used by faiss_manager,
# insightface_model, etc.
auto_cctv_enroller = AutoCctvEnroller()
