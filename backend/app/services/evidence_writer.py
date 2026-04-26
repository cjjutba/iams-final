"""
Recognition-event evidence writer.

Every FAISS decision in the realtime pipeline fires a ``submit(draft)``.
The draft is pushed onto a bounded ``asyncio.Queue``. Two background
workers drain the queue:

1. **Crop worker** — JPEG-encodes the live probe crop (and, on a first
   match for a given registration angle, copies the registered-angle JPEG
   once) to ``RECOGNITION_EVIDENCE_CROP_ROOT/<yyyy-mm-dd>/<event_id>-live.jpg``.
2. **DB worker** — batches 50 rows or flushes every 500 ms (whichever comes
   first) into ``recognition_events`` via a single ``executemany`` INSERT.

Back-pressure policy is **drop, never block**: when the queue is full we
bump a drop counter and log at WARNING at most once every 30 s. The
pipeline keeps running at full frame rate; only the audit trail gets
lossy. This is the right tradeoff — a missed event is annoying, a dropped
frame makes the attendance decision wrong.

Contract with callers:
  - ``submit(draft)`` is a non-blocking coroutine that returns immediately
    on success or drop.
  - ``start()`` / ``stop()`` are called from the FastAPI lifespan. ``stop``
    drains a small final batch with a bounded timeout; remaining rows are
    discarded.
  - The WebSocket push is a side effect of the DB write path — one
    "recognition_event" message per successfully persisted row.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import cv2
import numpy as np

from app.config import settings
from app.database import SessionLocal
from app.services.evidence_storage import evidence_storage

# Use the app's `iams` logger so startup + lifecycle messages land in the
# same container log stream as the rest of the app (root logger is
# configured at WARNING, which swallows our INFO otherwise).
logger = logging.getLogger("iams")

# Drop-log suppression window — so a long queue-full event doesn't flood the
# log with hundreds of identical WARNING lines.
_DROP_LOG_WINDOW_S = 30.0


@dataclass
class RecognitionEventDraft:
    """In-memory payload for one FAISS decision.

    Kept as a plain dataclass (not a Pydantic model) to minimise per-event
    overhead on the hot pipeline path. Serialization happens at write time.

    The ``live_crop`` field carries the raw BGR uint8 aligned crop produced
    by SCRFD (typically 112x112). The writer encodes it once and writes the
    bytes to disk — callers MUST NOT mutate the array after submit.
    """

    schedule_id: str
    student_id: Optional[str]
    track_id: int
    camera_id: str
    frame_idx: int
    similarity: float
    threshold_used: float
    matched: bool
    is_ambiguous: bool
    det_score: float
    embedding_norm: float
    bbox: dict[str, int]
    live_crop: np.ndarray
    model_name: str
    # Resolved display name for student_id. Plumbed from realtime_tracker so the
    # WS broadcast renders the name without a DB hit on the hot path. None for
    # misses, ambiguous decisions, and orphaned-embedding hits (user row gone).
    student_name: Optional[str] = None
    # Optional on first-match-for-identity; subsequent events for the same
    # identity reuse the cached ref on the TrackIdentity, so the writer
    # doesn't re-copy the same JPEG 20 times per second.
    registered_crop_bytes: Optional[bytes] = None
    registered_crop_ref: Optional[str] = None
    # Assigned by the writer just before enqueueing, so the crop file name
    # matches the DB row id without an extra round-trip.
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)


class EvidenceWriter:
    """Singleton writer — one instance per process, owned by the FastAPI app.

    Access via the module-level ``evidence_writer`` singleton.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[RecognitionEventDraft] = asyncio.Queue(
            maxsize=max(16, settings.RECOGNITION_EVIDENCE_QUEUE_SIZE)
        )
        self._tasks: list[asyncio.Task] = []
        self._started = False
        self._stopping = False
        self._last_drop_log_at: float = 0.0
        self._dropped_total: int = 0
        self._written_total: int = 0
        # Reference to the uvicorn event loop, captured when start() runs.
        # The realtime pipeline executes tracker.process() in a thread-pool
        # executor so it cannot reach the loop via get_event_loop(); it must
        # post submit() coroutines via run_coroutine_threadsafe(...).
        self._loop: asyncio.AbstractEventLoop | None = None
        # Cheap de-dup so we don't copy the same registered-angle JPEG over
        # and over for the same session. Bounded to stop unbounded growth
        # across a long-running process.
        self._registered_ref_cache: dict[tuple[str, str], str] = {}
        self._registered_ref_cache_max = 4096

    # -- lifecycle --------------------------------------------------------

    async def start(self) -> None:
        if self._started:
            return
        if not settings.ENABLE_RECOGNITION_EVIDENCE:
            logger.info(
                "EvidenceWriter disabled (ENABLE_RECOGNITION_EVIDENCE=false) — no capture"
            )
            return

        # Capture the running loop so off-thread producers can reach us.
        self._loop = asyncio.get_running_loop()

        self._tasks.append(asyncio.create_task(self._run_worker(), name="evidence-worker"))
        self._started = True
        logger.info(
            "EvidenceWriter started — backend=%s queue_size=%d",
            settings.RECOGNITION_EVIDENCE_BACKEND,
            self._queue.maxsize,
        )

    def submit_threadsafe(self, draft: RecognitionEventDraft) -> None:
        """Producer API callable from any thread.

        The realtime pipeline runs ``tracker.process()`` on a thread-pool
        executor, so it can't use ``submit()`` (a coroutine). This wrapper
        posts the coroutine to the uvicorn loop via
        ``run_coroutine_threadsafe``, returning immediately. Drops silently
        if the writer isn't started or the queue is near capacity — the
        pipeline must never back-pressure on recognition-evidence I/O.
        """
        if not self._started or self._stopping or self._loop is None:
            return
        # Back-pressure relief: drop the event without scheduling the task
        # at all when the queue is already near-full. Cheaper than bouncing
        # through run_coroutine_threadsafe only to hit QueueFull inside
        # submit(). Threshold matches the existing 10% head-room policy.
        try:
            high_water = max(1, int(self._queue.maxsize * 0.9))
            if self._queue.qsize() >= high_water:
                self._dropped_total += 1
                now = time.monotonic()
                if (now - self._last_drop_log_at) >= _DROP_LOG_WINDOW_S:
                    logger.warning(
                        "EvidenceWriter: back-pressure drop — qsize=%d (total_dropped=%d)",
                        self._queue.qsize(),
                        self._dropped_total,
                    )
                    self._last_drop_log_at = now
                return
        except Exception:
            # Never let a queue-introspection oddity crash the hot path.
            pass

        try:
            asyncio.run_coroutine_threadsafe(self.submit(draft), self._loop)
        except RuntimeError:
            # Loop closed between our check and the post — pipeline is
            # shutting down. Silent drop is correct here.
            pass

    async def stop(self) -> None:
        if not self._started:
            return
        self._stopping = True
        # Give the worker up to 3 s to drain current in-flight items, then
        # cancel. We deliberately don't wait for the queue to empty — at
        # shutdown we prioritise clean exit over full fidelity.
        try:
            await asyncio.wait_for(self._queue.join(), timeout=3.0)
        except asyncio.TimeoutError:
            logger.warning(
                "EvidenceWriter: queue did not drain within 3s at shutdown — dropping remainder"
            )
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.clear()
        self._started = False
        self._stopping = False
        logger.info(
            "EvidenceWriter stopped — written=%d dropped=%d",
            self._written_total,
            self._dropped_total,
        )

    # -- producer API -----------------------------------------------------

    async def submit(self, draft: RecognitionEventDraft) -> None:
        """Non-blocking submit. Drops the event if the queue is full."""
        if not self._started or self._stopping:
            return
        try:
            self._queue.put_nowait(draft)
        except asyncio.QueueFull:
            self._dropped_total += 1
            now = time.monotonic()
            if (now - self._last_drop_log_at) >= _DROP_LOG_WINDOW_S:
                logger.warning(
                    "EvidenceWriter: queue full — dropped event (total_dropped=%d)",
                    self._dropped_total,
                )
                self._last_drop_log_at = now

    def stats(self) -> dict[str, int]:
        """For /health or a future metrics endpoint."""
        return {
            "written_total": self._written_total,
            "dropped_total": self._dropped_total,
            "queue_size": self._queue.qsize(),
            "queue_max": self._queue.maxsize,
        }

    # -- helper: cached registered-crop save -------------------------------

    def remember_registered_crop(
        self, user_id: str, angle_label: str, ref: str
    ) -> None:
        """Once the writer has materialised a user's registered-angle JPEG
        under the evidence crop root, callers (e.g. the pipeline's identity
        cache) record the ref so subsequent events skip the disk copy.

        Bounded to prevent unbounded growth. At cap, drop oldest by dict
        re-ordering — not strictly LRU but good enough.
        """
        key = (user_id, angle_label)
        if key in self._registered_ref_cache:
            return
        if len(self._registered_ref_cache) >= self._registered_ref_cache_max:
            # Evict the first (oldest) inserted key. Python 3.7+ dicts are
            # insertion-ordered so this is cheap + O(1).
            try:
                oldest = next(iter(self._registered_ref_cache))
                del self._registered_ref_cache[oldest]
            except StopIteration:
                pass
        self._registered_ref_cache[key] = ref

    def get_registered_crop_ref(
        self, user_id: str, angle_label: str
    ) -> Optional[str]:
        return self._registered_ref_cache.get((user_id, angle_label))

    # -- worker -----------------------------------------------------------

    async def _run_worker(self) -> None:
        """Single background coroutine that handles both crop I/O + DB batch.

        We combine both responsibilities in one worker (rather than two
        separate asyncio tasks) to simplify ordering: a row is inserted only
        *after* its crop JPEG has been written, so any live_crop_ref in the
        table is guaranteed to resolve on disk. At our ~10 fps pipeline
        cadence the serial worker is nowhere near the bottleneck.
        """
        batch: list[tuple[RecognitionEventDraft, str, Optional[str]]] = []
        last_flush_at = time.monotonic()
        batch_ms = max(50, settings.RECOGNITION_EVIDENCE_BATCH_MS)
        batch_rows = max(1, settings.RECOGNITION_EVIDENCE_BATCH_ROWS)

        while True:
            timeout = max(
                0.0,
                (batch_ms / 1000.0) - (time.monotonic() - last_flush_at),
            )
            try:
                draft = await asyncio.wait_for(
                    self._queue.get(), timeout=timeout if batch else None
                )
            except asyncio.TimeoutError:
                # Timer-driven flush — write whatever we have, then loop.
                if batch:
                    await self._flush(batch)
                    batch = []
                last_flush_at = time.monotonic()
                continue

            # Encode + persist crops before we promise anything to the DB.
            try:
                live_ref = self._write_live_crop(draft)
                reg_ref = self._maybe_write_registered_crop(draft)
            except Exception:
                logger.exception(
                    "EvidenceWriter: crop write failed for track %d — skipping row",
                    draft.track_id,
                )
                self._queue.task_done()
                continue

            batch.append((draft, live_ref, reg_ref))
            self._queue.task_done()

            # Flush on size.
            if len(batch) >= batch_rows:
                await self._flush(batch)
                batch = []
                last_flush_at = time.monotonic()

    # -- crop writers (sync — serial) ------------------------------------

    def _write_live_crop(self, draft: RecognitionEventDraft) -> str:
        """JPEG-encode the live probe crop and persist via storage
        abstraction. Returns the storage key (relative ref)."""
        params = [
            int(cv2.IMWRITE_JPEG_QUALITY),
            int(settings.RECOGNITION_EVIDENCE_CROP_QUALITY),
        ]
        ok, buf = cv2.imencode(".jpg", draft.live_crop, params)
        if not ok:
            raise RuntimeError("cv2.imencode returned False for live crop")
        key = evidence_storage.make_key(str(draft.event_id), "live")
        evidence_storage.put(key, buf.tobytes())
        return key

    def _maybe_write_registered_crop(
        self, draft: RecognitionEventDraft
    ) -> Optional[str]:
        # Miss / ambiguous — no registered crop to pair.
        if not draft.matched or not draft.student_id:
            return None
        # Ref already on the draft? Caller cached it — reuse.
        if draft.registered_crop_ref:
            return draft.registered_crop_ref
        # Bytes supplied on first-match — persist once via storage, cache ref.
        if draft.registered_crop_bytes:
            key = evidence_storage.make_key(str(draft.event_id), "reg")
            evidence_storage.put(key, draft.registered_crop_bytes)
            return key
        return None

    # -- DB flush ---------------------------------------------------------

    async def _flush(
        self,
        batch: list[tuple[RecognitionEventDraft, str, Optional[str]]],
    ) -> None:
        """Single-transaction executemany insert. Offloaded to a thread so
        it doesn't block the event loop while Postgres chews on it."""
        if not batch:
            return
        try:
            await asyncio.to_thread(self._flush_sync, batch)
            self._written_total += len(batch)
        except Exception:
            logger.exception(
                "EvidenceWriter: flush failed for batch of %d — rows discarded",
                len(batch),
            )
            return
        # Best-effort WS broadcast per row. Isolated in its own try so a
        # broadcast failure doesn't block the next batch.
        try:
            await self._broadcast_batch(batch)
        except Exception:
            logger.debug("EvidenceWriter: WS broadcast suppressed", exc_info=True)

    def _flush_sync(
        self,
        batch: list[tuple[RecognitionEventDraft, str, Optional[str]]],
    ) -> None:
        from sqlalchemy import text

        db = SessionLocal()
        try:
            rows = []
            now = datetime.now()
            for draft, live_ref, reg_ref in batch:
                rows.append(
                    {
                        "id": str(draft.event_id),
                        "schedule_id": draft.schedule_id,
                        "student_id": draft.student_id,
                        "track_id": draft.track_id,
                        "camera_id": draft.camera_id,
                        "frame_idx": draft.frame_idx,
                        "similarity": float(draft.similarity),
                        "threshold_used": float(draft.threshold_used),
                        "matched": bool(draft.matched),
                        "is_ambiguous": bool(draft.is_ambiguous),
                        "det_score": float(draft.det_score),
                        "embedding_norm": float(draft.embedding_norm),
                        "bbox": draft.bbox,
                        "live_crop_ref": live_ref,
                        "registered_crop_ref": reg_ref,
                        "model_name": draft.model_name,
                        "created_at": now,
                    }
                )

            # Use JSONB-aware cast on bbox so SQLAlchemy serializes properly.
            db.execute(
                text(
                    """
                    INSERT INTO recognition_events (
                        id, schedule_id, student_id, track_id, camera_id,
                        frame_idx, similarity, threshold_used, matched,
                        is_ambiguous, det_score, embedding_norm, bbox,
                        live_crop_ref, registered_crop_ref, model_name, created_at
                    ) VALUES (
                        :id, :schedule_id, :student_id, :track_id, :camera_id,
                        :frame_idx, :similarity, :threshold_used, :matched,
                        :is_ambiguous, :det_score, :embedding_norm,
                        CAST(:bbox AS JSONB),
                        :live_crop_ref, :registered_crop_ref, :model_name, :created_at
                    )
                    """
                ),
                [_with_json_bbox(r) for r in rows],
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def _broadcast_batch(
        self,
        batch: list[tuple[RecognitionEventDraft, str, Optional[str]]],
    ) -> None:
        """Push a ``recognition_event`` message per row.

        Fans out on two channels:

        - The schedule channel (``/ws/attendance/{schedule_id}``) — drives
          the live-feed page's recognition stream and the bbox identity
          updates.
        - The student channel (``/ws/student/{student_id}``) — drives the
          Student Record Detail page's "Recent detections" panel.
          Misses + ambiguous decisions have no student_id and are skipped
          on this channel.

        No-op if WS routes are disabled (VPS thin profile).
        """
        if not settings.ENABLE_WS_ROUTES:
            return
        try:
            from app.routers.websocket import ws_manager
        except Exception:
            return
        for draft, live_ref, reg_ref in batch:
            payload: dict[str, Any] = {
                "type": "recognition_event",
                "event_id": str(draft.event_id),
                "schedule_id": draft.schedule_id,
                "student_id": draft.student_id,
                "student_name": draft.student_name,
                "track_id": draft.track_id,
                "camera_id": draft.camera_id,
                "frame_idx": draft.frame_idx,
                "similarity": float(draft.similarity),
                "threshold_used": float(draft.threshold_used),
                "matched": bool(draft.matched),
                "is_ambiguous": bool(draft.is_ambiguous),
                "det_score": float(draft.det_score),
                "bbox": draft.bbox,
                "model_name": draft.model_name,
                "server_time_ms": int(time.time() * 1000),
                "crop_urls": {
                    "live": f"{settings.API_PREFIX}/recognitions/{draft.event_id}/live-crop",
                    "registered": (
                        f"{settings.API_PREFIX}/recognitions/{draft.event_id}/registered-crop"
                        if reg_ref
                        else None
                    ),
                },
            }
            try:
                await ws_manager.broadcast_attendance(draft.schedule_id, payload)
            except Exception:
                # Don't let a WS failure (bad client) kill the batch.
                logger.debug(
                    "WS broadcast_attendance failed for event %s",
                    draft.event_id,
                    exc_info=True,
                )
            if draft.student_id:
                try:
                    await ws_manager.broadcast_student(
                        str(draft.student_id), payload
                    )
                except Exception:
                    logger.debug(
                        "WS broadcast_student failed for event %s",
                        draft.event_id,
                        exc_info=True,
                    )


def _with_json_bbox(row: dict[str, Any]) -> dict[str, Any]:
    """Serialise the bbox dict to a JSON string for CAST(AS JSONB).

    SQLAlchemy's parameter binding won't auto-JSON a dict via raw ``text()``.
    """
    import json as _json

    out = dict(row)
    out["bbox"] = _json.dumps(row["bbox"])
    return out


# Module-level singleton. Lifespan calls start/stop.
evidence_writer = EvidenceWriter()
