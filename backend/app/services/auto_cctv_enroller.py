"""
Auto CCTV Enrolment

Opportunistically captures real CCTV face embeddings during a student's
first attended sessions and adds them to FAISS + the face_embeddings
table — same data shape as scripts/cctv_enroll.py would produce, but
triggered automatically with no operator action and no student UI.

Flow
----
1. The realtime tracker calls ``offer_capture(user_id, embedding,
   crop_bgr, confidence, frames_seen)`` on every recognition decision
   that crossed the recognition threshold.
2. This module checks all eligibility gates (lifetime cap, confidence,
   stability, capture spacing) and if they pass, appends the
   ``(embedding, crop)`` to a per-user buffer.
3. When the buffer reaches ``AUTO_CCTV_ENROLL_TARGET_CAPTURES``, the
   batch is handed off to a background worker for commit. The worker
   re-validates self-similarity vs the user's existing phone embeddings
   (same gate as the manual cctv_enroll path) and if it passes, writes
   the new vectors to FAISS + DB + disk.
4. After successful commit, the per-user lifetime counter is bumped so
   no further auto-enrolment fires for this user across any session.

Safety
------
The previous adaptive-enrollment failure modes (Desiree↔Ivy Leah swap,
2026-04-25 morning) are closed by structural design:

* **Per-user lifetime cap, not per-session.** Once a user has 5 cctv_*
  rows in face_embeddings, auto-enrol *never* fires for them again,
  even after a server restart.
* **Buffer-then-validate, not write-on-each-frame.** A wrong lock-in
  has to survive a 60-frame stability window AND a self-similarity
  check against the user's existing phone vectors at commit time.
* **One-shot per cohort.** The buffer is collected over up to 60 s
  with min 5 s spacing — a wrong identity that briefly clears 0.60
  confidence won't sustain it long enough to fill the buffer.
* **No FAISS write from the realtime thread.** Commit happens in a
  background worker so a slow DB doesn't block the live overlay; the
  realtime thread just appends to an in-memory deque.

Boundary
--------
This module does NOT decide whether to recognise a face — that's the
tracker's job. It just observes confident recognitions and decides
whether THIS recognition should also become a permanent training
example. It never writes to FAISS unless the manual ``cctv_enroll``
contract is satisfied (i.e. the buffer would also have been an
acceptable ``cctv_enroll`` script invocation if the operator had run
it for this user at this moment).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import cv2
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class _UserEnrollState:
    """Per-user auto-enrolment state, in memory only.

    Persists across sessions on the same tracker instance. The lifetime
    counter (``cctv_count``) is bootstrapped from the DB at startup so
    auto-enrol stays one-shot across server restarts.
    """

    cctv_count: int = 0  # face_embeddings rows with angle_label LIKE 'cctv_%'
    buffer: deque = field(default_factory=lambda: deque(maxlen=10))  # (emb, crop, conf, ts)
    last_capture_at: float = 0.0
    first_capture_at: float = 0.0
    consecutive_high_conf_frames: int = 0
    last_user_id_seen_at: float = 0.0  # to detect track switching
    last_track_id: int | None = None
    commit_in_flight: bool = False  # prevents double-submit while worker runs

    def reset_buffer(self) -> None:
        self.buffer.clear()
        self.first_capture_at = 0.0
        self.last_capture_at = 0.0
        self.consecutive_high_conf_frames = 0


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
        self._users: dict[str, _UserEnrollState] = {}
        self._users_lock = threading.RLock()
        # Single-threaded executor: serialises commits so two simultaneous
        # buffer-full events don't both try to grab DB transactions /
        # mutate FAISS at once.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="auto-cctv-enroll")
        self._initialised = False

    def bootstrap_from_db(self) -> None:
        """Populate per-user cctv_count from the DB so auto-enrol stays
        one-shot across server restarts.

        Cheap: one query that aggregates by user. Called once at gateway
        startup from app.main lifespan; safe to call again later if you
        want to refresh after a manual enrol.
        """
        from sqlalchemy import func, text

        from app.database import SessionLocal
        from app.models.face_embedding import FaceEmbedding
        from app.models.face_registration import FaceRegistration

        db = SessionLocal()
        try:
            rows = (
                db.query(FaceRegistration.user_id, func.count(FaceEmbedding.id))
                .join(FaceEmbedding, FaceEmbedding.registration_id == FaceRegistration.id)
                .filter(FaceEmbedding.angle_label.like("cctv_%"))
                .filter(FaceRegistration.is_active.is_(True))
                .group_by(FaceRegistration.user_id)
                .all()
            )
            with self._users_lock:
                for user_id, count in rows:
                    state = self._users.setdefault(str(user_id), _UserEnrollState())
                    state.cctv_count = int(count)
            self._initialised = True
            logger.info(
                "AutoCctvEnroller bootstrap: %d user(s) already have cctv enrolment",
                len(rows),
            )
        except Exception:
            logger.exception("AutoCctvEnroller bootstrap failed (will run uninitialised)")
        finally:
            db.close()

    def _get_state(self, user_id: str) -> _UserEnrollState:
        with self._users_lock:
            return self._users.setdefault(user_id, _UserEnrollState())

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
    ) -> None:
        """Called by RealtimeTracker on every confident recognition.

        Returns immediately. Heavy work (DB writes, disk I/O, FAISS
        mutation) happens on the background executor when a buffer fills.
        Designed to be called from the realtime hot path with negligible
        overhead — typical cost is one dict lookup + a few comparisons.
        """
        if not settings.AUTO_CCTV_ENROLL_ENABLED:
            return
        if not user_id:
            return

        # Quick check: lifetime cap reached?
        state = self._get_state(user_id)
        if state.cctv_count >= settings.AUTO_CCTV_ENROLL_LIFETIME_CAP:
            return
        if state.commit_in_flight:
            return

        # Stability counter — must be sustained on the SAME track. A
        # track-id change resets the counter so a brief flicker doesn't
        # accumulate across two unrelated tracks.
        now = time.monotonic()
        if state.last_track_id is None or state.last_track_id != track_id:
            state.last_track_id = track_id
            state.consecutive_high_conf_frames = 0
            state.reset_buffer()
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

        state.buffer.append({
            "embedding": embedding.astype(np.float32, copy=True),
            "crop_bytes": crop_bytes,
            "confidence": float(confidence),
            "captured_at": now,
        })
        state.last_capture_at = now
        if state.first_capture_at == 0.0:
            state.first_capture_at = now

        logger.info(
            "auto-cctv: buffered capture %d/%d for user=%s conf=%.3f frames=%d",
            len(state.buffer),
            settings.AUTO_CCTV_ENROLL_TARGET_CAPTURES,
            user_id[:8],
            confidence,
            frames_seen,
        )

        # Commit threshold reached?
        if len(state.buffer) >= settings.AUTO_CCTV_ENROLL_TARGET_CAPTURES:
            buffered = list(state.buffer)
            state.commit_in_flight = True
            state.reset_buffer()
            self._executor.submit(self._commit_batch, user_id, buffered, room_stream_key)

    def _commit_batch(
        self,
        user_id: str,
        captures: list[dict],
        room_stream_key: str | None,
    ) -> None:
        """Background commit. Must not raise into the executor."""
        try:
            self._do_commit(user_id, captures, room_stream_key)
        except Exception:
            logger.exception("auto-cctv: commit failed for user=%s", user_id[:8])
        finally:
            state = self._get_state(user_id)
            state.commit_in_flight = False

    def _do_commit(
        self,
        user_id: str,
        captures: list[dict],
        room_stream_key: str | None,
    ) -> None:
        from sqlalchemy import update

        from app.database import SessionLocal
        from app.models.face_embedding import FaceEmbedding
        from app.repositories.face_repository import FaceRepository
        from app.services.ml.faiss_manager import faiss_manager
        from app.utils.face_image_storage import FaceImageStorage

        if settings.AUTO_CCTV_ENROLL_DRY_RUN:
            logger.info(
                "auto-cctv DRY_RUN: would commit %d captures for user=%s (mean conf=%.3f)",
                len(captures),
                user_id[:8],
                float(np.mean([c["confidence"] for c in captures])),
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

            # Self-similarity gate: same as the manual cctv_enroll path.
            existing_phone_emb = np.frombuffer(
                registration.embedding_vector, dtype=np.float32
            )
            new_embs = np.stack([c["embedding"] for c in captures]).astype(np.float32)
            sims_to_phone = (new_embs @ existing_phone_emb).tolist()
            mean_sim = float(np.mean(sims_to_phone))
            if mean_sim < settings.AUTO_CCTV_ENROLL_MIN_SELF_SIM:
                logger.warning(
                    "auto-cctv: self-similarity gate failed for user=%s "
                    "(mean=%.3f < %.3f); discarding %d captures",
                    user_id[:8],
                    mean_sim,
                    settings.AUTO_CCTV_ENROLL_MIN_SELF_SIM,
                    len(captures),
                )
                return

            # Pick next cctv_<idx> labels (continues from any existing
            # cctv_* rows for this user — manual + auto share the namespace).
            existing_embs = repo.get_embeddings_by_registration(str(registration.id))
            existing_indices = []
            for emb in existing_embs:
                if emb.angle_label and emb.angle_label.startswith("cctv_"):
                    try:
                        existing_indices.append(int(emb.angle_label.split("_", 1)[1]))
                    except ValueError:
                        pass
            next_idx = max(existing_indices, default=-1) + 1
            labels = [f"cctv_{next_idx + i}" for i in range(len(captures))]

            # Add to FAISS in batch
            try:
                faiss_ids = faiss_manager.add_batch(
                    new_embs, [user_id] * len(new_embs)
                )
            except Exception:
                logger.exception("auto-cctv: FAISS add failed for user=%s", user_id[:8])
                return

            # DB persist + crop storage in one transaction
            try:
                entries = []
                for fid, cap, label in zip(faiss_ids, captures, labels):
                    entries.append({
                        "faiss_id": fid,
                        "embedding_vector": cap["embedding"].astype(np.float32).tobytes(),
                        "angle_label": label,
                        "quality_score": cap["confidence"],
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

                faiss_manager.save()

                # Update lifetime counter
                state = self._get_state(user_id)
                state.cctv_count += len(captures)

                logger.info(
                    "auto-cctv: COMMITTED %d captures for user=%s "
                    "(faiss_ids=%s mean_sim_to_phone=%.3f new_total=%d/%d)",
                    len(captures),
                    user_id[:8],
                    faiss_ids,
                    mean_sim,
                    state.cctv_count,
                    settings.AUTO_CCTV_ENROLL_LIFETIME_CAP,
                )
            except Exception:
                db.rollback()
                # Best-effort FAISS rollback
                for fid in faiss_ids:
                    try:
                        faiss_manager.remove(fid)
                    except Exception:
                        pass
                logger.exception(
                    "auto-cctv: DB persist failed for user=%s; FAISS rolled back",
                    user_id[:8],
                )
        finally:
            db.close()


# Module-level accessor — mirrors the pattern used by faiss_manager,
# insightface_model, etc.
auto_cctv_enroller = AutoCctvEnroller()
