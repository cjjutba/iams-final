"""
Batch Face Processing Pipeline

Async batch processor that decouples face submission from recognition.
RPi POSTs face crops -> endpoint returns 202 -> faces pushed to Redis queue.
Background worker triggers on threshold (N faces) or timer (M seconds),
acquires a Redis lock, processes the batch, and publishes results.
"""

import asyncio
import contextlib
import json
import time

from app.config import logger, settings
from app.redis_client import get_redis


class BatchProcessor:
    """Async batch face processing pipeline backed by Redis."""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._threshold_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def enqueue_face(self, room_id: str, face_data: dict) -> None:
        """Push a single face payload onto the Redis queue for *room_id*.

        Args:
            room_id: Room identifier (used as queue suffix).
            face_data: Dict with at least ``image`` (base64) and optional
                       ``bbox``, ``request_id``, ``timestamp``.
        """
        r = await get_redis()
        queue_key = f"{settings.REDIS_BATCH_QUEUE_PREFIX}:{room_id}"
        payload = json.dumps(face_data)
        await r.rpush(queue_key, payload.encode())

        # Check if batch threshold reached — trigger immediate processing
        queue_len = await r.llen(queue_key)
        if queue_len >= settings.REDIS_BATCH_THRESHOLD:
            self._threshold_event.set()

        logger.debug(f"Enqueued face to {queue_key} (queue_len={queue_len})")

    async def start(self) -> None:
        """Start the background batch-processing loop."""
        if self._task is not None and not self._task.done():
            logger.warning("BatchProcessor already running")
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._batch_loop())
        logger.info(
            f"BatchProcessor started (interval={settings.REDIS_BATCH_INTERVAL}s, "
            f"threshold={settings.REDIS_BATCH_THRESHOLD})"
        )

    async def stop(self) -> None:
        """Cancel the background loop gracefully."""
        if self._task is None or self._task.done():
            return
        self._stop_event.set()
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        logger.info("BatchProcessor stopped")

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _batch_loop(self) -> None:
        """Main loop: process on timer or threshold trigger."""
        while not self._stop_event.is_set():
            try:
                # Wait for: threshold trigger, stop event, or timer expiry
                self._threshold_event.clear()
                done, _ = await asyncio.wait(
                    [
                        asyncio.create_task(self._stop_event.wait()),
                        asyncio.create_task(self._threshold_event.wait()),
                    ],
                    timeout=settings.REDIS_BATCH_INTERVAL,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                # Cancel pending tasks from the wait set
                for task in _:
                    task.cancel()

                if self._stop_event.is_set():
                    break

                r = await get_redis()
                await self._try_process_batch(r)

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("BatchProcessor loop error")
                # Back off briefly before retrying to avoid a tight error loop
                await asyncio.sleep(1)

    async def _try_process_batch(self, r) -> None:
        """Acquire a Redis lock, discover room queues, and process each."""
        # Try to acquire a distributed lock (NX + EX)
        lock_acquired = await r.set(
            settings.REDIS_BATCH_LOCK_KEY.encode(),
            b"1",
            nx=True,
            ex=settings.REDIS_BATCH_LOCK_TIMEOUT,
        )
        if not lock_acquired:
            logger.debug("BatchProcessor: another worker holds the lock, skipping")
            return

        try:
            # Discover all room queues matching the prefix
            pattern = f"{settings.REDIS_BATCH_QUEUE_PREFIX}:*"
            queue_keys: list[bytes] = []
            async for key in r.scan_iter(match=pattern.encode()):
                queue_keys.append(key)

            if not queue_keys:
                return

            for queue_key in queue_keys:
                try:
                    await self._process_room_queue(r, queue_key)
                except Exception:
                    logger.exception(f"Error processing queue {queue_key}")
        finally:
            # Release the lock
            await r.delete(settings.REDIS_BATCH_LOCK_KEY.encode())

    async def _process_room_queue(self, r, queue_key: bytes) -> None:
        """Pop all faces from a room queue, run recognition, publish results."""
        # Pop all items atomically via pipeline
        pipe = r.pipeline()
        pipe.lrange(queue_key, 0, -1)
        pipe.delete(queue_key)
        results = await pipe.execute()
        raw_items: list[bytes] = results[0]

        if not raw_items:
            return

        # Decode payloads
        face_payloads: list[dict] = []
        for raw in raw_items:
            try:
                face_payloads.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                logger.warning("Skipping malformed face payload in batch queue")

        if not face_payloads:
            return

        # Extract room_id from queue key (face_queue:room_id)
        queue_key_str = queue_key.decode() if isinstance(queue_key, bytes) else queue_key
        room_id = queue_key_str.split(":", 1)[1] if ":" in queue_key_str else "unknown"

        batch_size = len(face_payloads)
        logger.info(f"Processing batch of {batch_size} faces for room {room_id}")
        start = time.time()

        # Run recognition via FaceService (lazy import to avoid circular deps)
        from app.database import SessionLocal
        from app.services.face_service import FaceService

        db = SessionLocal()
        try:
            face_service = FaceService(db)
            batch_results = []

            # Collect image bytes for batch recognition
            import base64

            images_bytes: list[bytes] = []
            valid_indices: list[int] = []

            for i, payload in enumerate(face_payloads):
                try:
                    b64_str = payload.get("image", "")
                    if "," in b64_str:
                        b64_str = b64_str.split(",", 1)[1]
                    img_bytes = base64.b64decode(b64_str, validate=True)
                    images_bytes.append(img_bytes)
                    valid_indices.append(i)
                except Exception as e:
                    logger.warning(f"Batch face {i}: invalid image data: {e}")
                    batch_results.append({"index": i, "user_id": None, "confidence": None, "error": str(e)})

            if images_bytes:
                recognition_results = await face_service.recognize_batch(images_bytes)

                for rec in recognition_results:
                    batch_results.append(
                        {
                            "user_id": rec.get("user_id"),
                            "confidence": rec.get("confidence"),
                            "error": rec.get("error"),
                        }
                    )

            # Build matched list
            matched = [br for br in batch_results if br.get("user_id")]

            # Feed detections to presence/attendance tracking
            if matched:
                await self._log_presence(db, room_id, matched)

        finally:
            db.close()

        elapsed_ms = int((time.time() - start) * 1000)

        # Publish results to Redis ws_broadcast channel
        broadcast_payload = {
            "room_id": room_id,
            "event_type": "batch_results",
            "results": matched,
            "processing_time_ms": elapsed_ms,
            "batch_size": batch_size,
            "timestamp": time.time(),
        }

        try:
            await r.publish(
                settings.REDIS_WS_CHANNEL.encode(),
                json.dumps(broadcast_payload).encode(),
            )
            logger.debug(f"Published batch results to {settings.REDIS_WS_CHANNEL}")
        except Exception:
            logger.exception("Failed to publish batch results to Redis channel")

        logger.info(f"Batch complete for room {room_id}: {len(matched)}/{batch_size} matched in {elapsed_ms}ms")

    async def _log_presence(self, db, room_id: str, matched: list[dict]) -> None:
        """Feed matched detections to the presence/attendance tracking system."""
        from datetime import datetime

        from app.repositories.schedule_repository import ScheduleRepository
        from app.services.presence_service import PresenceService

        try:
            schedule_repo = ScheduleRepository(db)
            presence_service = PresenceService(db)

            now = datetime.utcnow()
            scan_time = now.time()
            scan_day = now.weekday()

            try:
                current_schedule = schedule_repo.get_current_schedule(room_id, scan_day, scan_time)
            except (ValueError, Exception) as e:
                logger.warning(f"Schedule lookup failed for room {room_id}: {e}")
                current_schedule = None

            if current_schedule:
                schedule_id = str(current_schedule.id)
                logged = 0
                for result in matched:
                    try:
                        await presence_service.feed_detection(
                            schedule_id=schedule_id,
                            user_id=result["user_id"],
                            confidence=result.get("confidence", 0.0),
                        )
                        logged += 1
                    except Exception as e:
                        logger.error(f"Failed to log presence for user {result['user_id']}: {e}")
                logger.info(f"Logged {logged}/{len(matched)} detections to schedule {schedule_id}")
            else:
                logger.warning(
                    f"No active schedule for room {room_id} at {scan_time}. "
                    "Recognition completed but presence not logged."
                )
        except Exception:
            logger.exception("Failed to log presence in batch processor")


# Singleton instance
batch_processor = BatchProcessor()
