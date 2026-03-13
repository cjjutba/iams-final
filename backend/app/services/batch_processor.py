"""
Batch Face Processing Pipeline

Async batch processor that decouples face submission from recognition.
RPi POSTs face crops -> endpoint returns 202 -> faces pushed to Redis queue.
Background worker triggers on threshold (N faces) or timer (M seconds),
acquires a Redis lock, processes the batch, and publishes results.
"""

import asyncio
import json
import time

from app.config import logger, settings
from app.redis_client import get_redis


class BatchProcessor:
    """Async batch face processing pipeline backed by Redis."""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

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
        logger.debug(f"Enqueued face to {queue_key}")

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
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("BatchProcessor stopped")

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _batch_loop(self) -> None:
        """Main loop: sleep up to REDIS_BATCH_INTERVAL, then try to process."""
        while not self._stop_event.is_set():
            try:
                # Wait for the configured interval (or until stopped)
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=settings.REDIS_BATCH_INTERVAL,
                    )
                    # If we get here, the stop event was set
                    break
                except asyncio.TimeoutError:
                    # Normal timeout — time to check for work
                    pass

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
                    batch_results.append(
                        {"index": i, "user_id": None, "confidence": None, "error": str(e)}
                    )

            if images_bytes:
                # Use batch recognition if available, else fall back to sequential
                recognition_results = await face_service.recognize_batch(images_bytes)

                for rec in recognition_results:
                    batch_results.append({
                        "user_id": rec.get("user_id"),
                        "confidence": rec.get("confidence"),
                        "error": rec.get("error"),
                    })
        finally:
            db.close()

        elapsed_ms = int((time.time() - start) * 1000)

        # Build result summary
        matched = [br for br in batch_results if br.get("user_id")]

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

        logger.info(
            f"Batch complete for room {room_id}: "
            f"{len(matched)}/{batch_size} matched in {elapsed_ms}ms"
        )


# Singleton instance
batch_processor = BatchProcessor()
