# Scalable Cloud Architecture — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Optimize the IAMS backend to handle 2 classrooms × 50 students concurrently with ~3-5 second recognition cycles on a $48/mo DigitalOcean droplet (4 vCPU / 8GB RAM).

**Architecture:** Optimized monolith — 4 Uvicorn workers with shared FAISS (mmap) and ONNX Runtime, Redis for batch queuing + pub/sub + presence state, async fire-and-forget face processing, event-driven presence tracking.

**Tech Stack:** FastAPI, ONNX Runtime, FAISS (mmap), Redis, APScheduler, Docker Compose, MediaPipe (edge), React Native (mobile)

**Design Doc:** `docs/plans/2026-03-13-scalable-cloud-architecture-design.md`

---

## Task 1: Add Redis to Infrastructure

**Files:**
- Modify: `deploy/docker-compose.prod.yml`
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`
- Create: `backend/app/redis_client.py`

**Step 1: Add redis dependency to requirements.txt**

Add to `backend/requirements.txt`:
```
redis[hiredis]>=5.0.0,<6.0.0
```

**Step 2: Add Redis settings to config.py**

Add after line 87 (presence tracking settings) in `backend/app/config.py`:
```python
# Redis
REDIS_URL: str = "redis://localhost:6379/0"
REDIS_BATCH_QUEUE_PREFIX: str = "face_queue"
REDIS_PRESENCE_PREFIX: str = "presence"
REDIS_WS_CHANNEL: str = "ws_broadcast"
REDIS_BATCH_LOCK_KEY: str = "batch_lock"
REDIS_BATCH_LOCK_TIMEOUT: int = 30  # seconds
REDIS_BATCH_INTERVAL: float = 3.0  # seconds between batch runs
REDIS_BATCH_THRESHOLD: int = 10  # min faces to trigger immediate batch
```

**Step 3: Create Redis client module**

Create `backend/app/redis_client.py`:
```python
import redis.asyncio as redis
from app.config import settings
import logging

logger = logging.getLogger(__name__)

_redis_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.from_url(
            settings.REDIS_URL,
            decode_responses=False,
            max_connections=20,
        )
    return _redis_pool


async def close_redis():
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
        logger.info("Redis connection closed")
```

**Step 4: Add Redis to docker-compose.prod.yml**

Add after the backend service in `deploy/docker-compose.prod.yml`:
```yaml
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --maxmemory 64mb --maxmemory-policy allkeys-lru --save ""
    volumes:
      - redis_data:/data
    networks:
      - iams-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
```

Add `redis_data` to the volumes section. Add `redis` to the backend's `depends_on`.

Update backend environment to include:
```yaml
REDIS_URL: redis://redis:6379/0
```

**Step 5: Verify Redis starts locally**

Run: `docker run --rm -p 6379:6379 redis:7-alpine redis-server --maxmemory 64mb --save ""`
Expected: Redis server ready on port 6379

**Step 6: Commit**

```bash
git add backend/requirements.txt backend/app/config.py backend/app/redis_client.py deploy/docker-compose.prod.yml
git commit -m "feat: add Redis infrastructure for batch processing and pub/sub"
```

---

## Task 2: Convert InsightFace to ONNX Runtime Direct Inference

**Files:**
- Modify: `backend/app/services/ml/insightface_model.py`
- Modify: `backend/app/config.py`
- Modify: `backend/requirements.txt`

**Context:** Currently `insightface_model.py` uses `insightface.app.FaceAnalysis` which loads PyTorch models. For multi-worker sharing, we need ONNX Runtime sessions that share read-only memory across forked workers.

**Step 1: Add onnxruntime config**

Add to `backend/app/config.py` settings:
```python
# ONNX Runtime
ONNX_DET_MODEL_PATH: str = "data/models/det_10g.onnx"
ONNX_REC_MODEL_PATH: str = "data/models/w600k_r50.onnx"
ONNX_NUM_THREADS: int = 2  # threads per worker (4 workers × 2 = 8 total, but OS schedules across 4 vCPU)
```

**Step 2: Create ONNX model extraction script**

Create `backend/scripts/export_onnx_models.py`:
```python
"""Extract ONNX models from InsightFace model pack for direct ONNX Runtime usage.

Run once: python scripts/export_onnx_models.py
Creates: data/models/det_10g.onnx, data/models/w600k_r50.onnx
"""
import os
import shutil
from insightface.app import FaceAnalysis

def export():
    os.makedirs("data/models", exist_ok=True)
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))

    # The models are cached in ~/.insightface/models/buffalo_l/
    model_dir = os.path.expanduser("~/.insightface/models/buffalo_l")

    # Copy detection model (SCRFD 10g)
    det_src = os.path.join(model_dir, "det_10g.onnx")
    shutil.copy2(det_src, "data/models/det_10g.onnx")
    print(f"Copied detection model: {det_src}")

    # Copy recognition model (ArcFace w600k_r50)
    rec_src = os.path.join(model_dir, "w600k_r50.onnx")
    shutil.copy2(rec_src, "data/models/w600k_r50.onnx")
    print(f"Copied recognition model: {rec_src}")

    print("Done! Models saved to data/models/")

if __name__ == "__main__":
    export()
```

**Step 3: Refactor insightface_model.py to use ONNX Runtime directly**

Rewrite `backend/app/services/ml/insightface_model.py` to use `onnxruntime.InferenceSession` instead of `insightface.app.FaceAnalysis`. Key changes:

- Load ONNX models directly with `ort.InferenceSession(path, providers=["CPUExecutionProvider"])`
- Set `sess_options.inter_op_num_threads` and `intra_op_num_threads` from config
- Keep the same public API (`get_embedding()`, `get_embeddings_batch()`, `get_faces()`, `get_face_with_quality()`)
- Implement SCRFD detection preprocessing (resize to 640×640, normalize) and NMS postprocessing
- Implement ArcFace preprocessing (112×112 crop using 5-point landmark alignment, normalize to [-1,1])
- The `DetectedFace` dataclass stays the same

The ONNX session reads model weights as read-only memory, so after `fork()` all workers share the same physical RAM pages.

**Step 4: Run existing tests to verify same behavior**

Run: `cd backend && pytest tests/ -v`
Expected: All existing face recognition tests pass

**Step 5: Commit**

```bash
git add backend/app/services/ml/insightface_model.py backend/app/config.py backend/requirements.txt backend/scripts/export_onnx_models.py
git commit -m "feat: convert InsightFace to direct ONNX Runtime for multi-worker memory sharing"
```

---

## Task 3: Memory-Map FAISS Index for Multi-Worker Sharing

**Files:**
- Modify: `backend/app/services/ml/faiss_manager.py` (lines 40-62: `load_or_create_index()`)

**Step 1: Modify FAISS loading to use memory-mapped I/O**

In `backend/app/services/ml/faiss_manager.py`, modify `load_or_create_index()` (line 52):

Change:
```python
self.index = faiss.read_index(self.index_path)
```

To:
```python
self.index = faiss.read_index(self.index_path, faiss.IO_FLAG_MMAP)
```

This makes all workers read from the same physical memory pages. The index file on disk is the authoritative source.

**Step 2: Add index rebuild notification via Redis**

Add a method to notify other workers when the index changes (e.g., after registration):

```python
async def notify_index_changed(self):
    """Publish index change event so other workers reload."""
    from app.redis_client import get_redis
    r = await get_redis()
    await r.publish("faiss_reload", b"reload")

async def subscribe_index_changes(self):
    """Listen for index change events and reload."""
    from app.redis_client import get_redis
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("faiss_reload")
    async for message in pubsub.listen():
        if message["type"] == "message":
            self.load_or_create_index()
            logger.info("FAISS index reloaded from disk (notified by another worker)")
```

**Step 3: Update save() to notify after write**

Modify `save()` to call `notify_index_changed()` after writing to disk.

**Step 4: Verify FAISS works with mmap flag**

Run: `cd backend && pytest tests/ -k faiss -v`
Expected: All FAISS tests pass

**Step 5: Commit**

```bash
git add backend/app/services/ml/faiss_manager.py
git commit -m "feat: memory-map FAISS index for multi-worker sharing"
```

---

## Task 4: Implement Redis Batch Queue for Face Processing

**Files:**
- Create: `backend/app/services/batch_processor.py`
- Modify: `backend/app/routers/face.py` (lines 310-561: `/process` endpoint)

**Step 1: Create the batch processor service**

Create `backend/app/services/batch_processor.py`:

```python
"""
Async batch face processing pipeline.

RPi POSTs face crops → endpoint returns 202 → face pushed to Redis queue.
Batch worker triggers on threshold (10 faces) or timer (3 seconds).
One worker acquires Redis lock, processes batch, publishes results.
"""
import asyncio
import json
import time
import logging
from typing import Optional

from app.config import settings
from app.redis_client import get_redis

logger = logging.getLogger(__name__)


class BatchProcessor:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def enqueue_face(self, room_id: str, face_data: dict):
        """Push a face to the room's Redis queue."""
        r = await get_redis()
        queue_key = f"{settings.REDIS_BATCH_QUEUE_PREFIX}:{room_id}"
        payload = json.dumps(face_data).encode()
        await r.lpush(queue_key, payload)

        # Check if batch threshold reached → trigger immediate processing
        queue_len = await r.llen(queue_key)
        if queue_len >= settings.REDIS_BATCH_THRESHOLD:
            await r.publish("batch_trigger", room_id.encode())

    async def start(self):
        """Start the batch processing loop."""
        self._running = True
        self._task = asyncio.create_task(self._batch_loop())
        logger.info("Batch processor started")

    async def stop(self):
        """Stop the batch processing loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Batch processor stopped")

    async def _batch_loop(self):
        """Main loop: process batches on timer or trigger."""
        r = await get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe("batch_trigger")

        while self._running:
            try:
                # Wait for trigger or timeout
                msg = None
                try:
                    msg = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                        timeout=settings.REDIS_BATCH_INTERVAL,
                    )
                except asyncio.TimeoutError:
                    pass

                # Try to acquire lock and process
                await self._try_process_batch(r)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Batch loop error")
                await asyncio.sleep(1)

        await pubsub.unsubscribe("batch_trigger")

    async def _try_process_batch(self, r):
        """Attempt to acquire lock and process all room queues."""
        lock = r.lock(
            settings.REDIS_BATCH_LOCK_KEY,
            timeout=settings.REDIS_BATCH_LOCK_TIMEOUT,
            blocking=False,
        )
        acquired = await lock.acquire()
        if not acquired:
            return  # Another worker is processing

        try:
            # Find all room queues
            keys = []
            async for key in r.scan_iter(
                match=f"{settings.REDIS_BATCH_QUEUE_PREFIX}:*"
            ):
                keys.append(key)

            for queue_key in keys:
                await self._process_room_queue(r, queue_key)
        finally:
            await lock.release()

    async def _process_room_queue(self, r, queue_key: bytes):
        """Process all faces in a single room's queue."""
        # Pop all faces from queue
        faces = []
        while True:
            data = await r.rpop(queue_key)
            if data is None:
                break
            faces.append(json.loads(data))

        if not faces:
            return

        room_id = queue_key.decode().split(":")[-1]
        start_time = time.time()

        try:
            # Import here to avoid circular deps
            from app.services.face_service import FaceService
            from app.services.ml.insightface_model import insightface_model
            from app.services.ml.faiss_manager import faiss_manager

            face_service = FaceService()

            # Extract images from face data
            results = []
            for face in faces:
                image_bytes = face.get("image_bytes")
                if not image_bytes:
                    continue

                # Recognize using shared ONNX + FAISS
                user_id, confidence = await face_service.recognize_face(
                    image_bytes
                )
                results.append({
                    "face_data": face,
                    "user_id": user_id,
                    "confidence": confidence,
                    "room_id": room_id,
                })

            processing_time = (time.time() - start_time) * 1000

            # Publish results for WebSocket broadcast + presence tracking
            result_payload = json.dumps({
                "room_id": room_id,
                "results": results,
                "processing_time_ms": round(processing_time),
                "batch_size": len(faces),
                "timestamp": time.time(),
            }).encode()

            await r.publish(settings.REDIS_WS_CHANNEL, result_payload)

            logger.info(
                f"Batch processed: room={room_id}, faces={len(faces)}, "
                f"matched={sum(1 for r in results if r['user_id'])}, "
                f"time={processing_time:.0f}ms"
            )

        except Exception:
            logger.exception(f"Batch processing failed for {room_id}")


batch_processor = BatchProcessor()
```

**Step 2: Modify face router /process endpoint to return 202**

In `backend/app/routers/face.py`, modify the `/process` endpoint (line 310+) to:

1. Accept the request
2. Push each face to Redis queue via `batch_processor.enqueue_face()`
3. Return `202 Accepted` immediately with `{"status": "queued", "faces_queued": N}`

Keep the old synchronous path as a fallback (controlled by a config flag `USE_BATCH_PROCESSING: bool = True`).

**Step 3: Start/stop batch processor in main.py lifespan**

In `backend/app/main.py`, add to `startup_event()`:
```python
from app.services.batch_processor import batch_processor
await batch_processor.start()
```

Add to `shutdown_event()`:
```python
await batch_processor.stop()
```

**Step 4: Test batch processing locally**

Run: `cd backend && pytest tests/ -v`
Expected: Existing tests pass. New batch tests pass.

**Step 5: Commit**

```bash
git add backend/app/services/batch_processor.py backend/app/routers/face.py backend/app/main.py
git commit -m "feat: async batch face processing pipeline with Redis queue"
```

---

## Task 5: Implement Redis Pub/Sub WebSocket Broadcast

**Files:**
- Modify: `backend/app/routers/websocket.py` (lines 16-154: `ConnectionManager`)
- Modify: `backend/app/main.py`

**Step 1: Add Redis pub/sub listener to ConnectionManager**

Modify `ConnectionManager` in `backend/app/routers/websocket.py`:

```python
async def start_redis_listener(self):
    """Subscribe to Redis pub/sub for cross-worker broadcast."""
    from app.redis_client import get_redis
    from app.config import settings
    r = await get_redis()
    self._pubsub = r.pubsub()
    await self._pubsub.subscribe(settings.REDIS_WS_CHANNEL)
    self._listener_task = asyncio.create_task(self._listen_redis())

async def _listen_redis(self):
    """Process messages from Redis and broadcast to local WebSocket clients."""
    async for message in self._pubsub.listen():
        if message["type"] == "message":
            try:
                data = json.loads(message["data"])
                room_id = data.get("room_id")
                # Broadcast to relevant schedule connections
                await self._broadcast_batch_results(data)
            except Exception:
                logger.exception("Redis listener error")

async def _broadcast_batch_results(self, data: dict):
    """Send batch recognition results to relevant WebSocket clients."""
    results = data.get("results", [])
    room_id = data.get("room_id")

    for result in results:
        user_id = result.get("user_id")
        if user_id and user_id in self.active_connections:
            await self.send_personal_message(
                {
                    "event": "student_checked_in",
                    "data": {
                        "user_id": user_id,
                        "room_id": room_id,
                        "confidence": result.get("confidence"),
                        "timestamp": result.get("timestamp"),
                    },
                },
                user_id,
            )

async def stop_redis_listener(self):
    """Stop the Redis pub/sub listener."""
    if hasattr(self, "_listener_task"):
        self._listener_task.cancel()
    if hasattr(self, "_pubsub"):
        await self._pubsub.unsubscribe()
```

**Step 2: Start/stop listener in main.py**

Add to `startup_event()`:
```python
from app.routers.websocket import manager
await manager.start_redis_listener()
```

Add to `shutdown_event()`:
```python
await manager.stop_redis_listener()
```

**Step 3: Add new WebSocket event types**

Add these event publishing methods to `ConnectionManager`:

```python
async def publish_presence_warning(self, data: dict):
    """Publish presence warning via Redis for cross-worker broadcast."""
    from app.redis_client import get_redis
    r = await get_redis()
    await r.publish(settings.REDIS_WS_CHANNEL, json.dumps({
        "event_type": "presence_warning",
        **data,
    }).encode())

async def publish_presence_score(self, data: dict):
    """Publish presence score update via Redis."""
    from app.redis_client import get_redis
    r = await get_redis()
    await r.publish(settings.REDIS_WS_CHANNEL, json.dumps({
        "event_type": "presence_score",
        **data,
    }).encode())
```

**Step 4: Run tests**

Run: `cd backend && pytest tests/ -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add backend/app/routers/websocket.py backend/app/main.py
git commit -m "feat: Redis pub/sub WebSocket broadcast for multi-worker support"
```

---

## Task 6: Redis-Backed Presence State

**Files:**
- Modify: `backend/app/services/presence_service.py`
- The in-memory `_active_sessions` dict moves to Redis

**Step 1: Create Redis presence state helpers**

Add to `backend/app/services/presence_service.py`:

```python
async def _redis_update_presence(self, room_id: str, student_id: str, timestamp: float):
    """Update student presence state in Redis."""
    from app.redis_client import get_redis
    r = await get_redis()
    key = f"{settings.REDIS_PRESENCE_PREFIX}:{room_id}:{student_id}"
    await r.hset(key, mapping={
        "last_seen": str(timestamp),
        "miss_count": 0,
    })
    # Increment present count
    await r.hincrby(key, "present_count", 1)

async def _redis_get_presence(self, room_id: str, student_id: str) -> dict:
    """Get student presence state from Redis."""
    from app.redis_client import get_redis
    r = await get_redis()
    key = f"{settings.REDIS_PRESENCE_PREFIX}:{room_id}:{student_id}"
    data = await r.hgetall(key)
    if not data:
        return {"last_seen": 0, "miss_count": 0, "present_count": 0, "total_scans": 0}
    return {
        "last_seen": float(data.get(b"last_seen", 0)),
        "miss_count": int(data.get(b"miss_count", 0)),
        "present_count": int(data.get(b"present_count", 0)),
        "total_scans": int(data.get(b"total_scans", 0)),
    }

async def _redis_increment_miss(self, room_id: str, student_id: str) -> int:
    """Increment miss counter, return new value."""
    from app.redis_client import get_redis
    r = await get_redis()
    key = f"{settings.REDIS_PRESENCE_PREFIX}:{room_id}:{student_id}"
    new_count = await r.hincrby(key, "miss_count", 1)
    return new_count

async def _redis_increment_total_scans(self, room_id: str, student_id: str):
    """Increment total scan count."""
    from app.redis_client import get_redis
    r = await get_redis()
    key = f"{settings.REDIS_PRESENCE_PREFIX}:{room_id}:{student_id}"
    await r.hincrby(key, "total_scans", 1)

async def _redis_clear_room(self, room_id: str):
    """Clear all presence state for a room (on session end)."""
    from app.redis_client import get_redis
    r = await get_redis()
    async for key in r.scan_iter(match=f"{settings.REDIS_PRESENCE_PREFIX}:{room_id}:*"):
        await r.delete(key)
```

**Step 2: Update process_session_scan() to use Redis state**

Modify the core scan logic in `process_session_scan()` (lines 372-535) to:
1. Read presence state from Redis instead of in-memory dict
2. Write updates to Redis
3. Keep the 60-second DB bulk write
4. Keep the early leave detection logic but read miss_count from Redis

**Step 3: Update batch_processor to feed presence state**

When batch results come in, update Redis presence state:
```python
# In batch_processor._process_room_queue()
for result in results:
    if result["user_id"]:
        await presence_service._redis_update_presence(
            room_id, result["user_id"], time.time()
        )
```

**Step 4: Run tests**

Run: `cd backend && pytest tests/ -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add backend/app/services/presence_service.py backend/app/services/batch_processor.py
git commit -m "feat: Redis-backed presence state for multi-worker consistency"
```

---

## Task 7: Configure Multi-Worker Uvicorn

**Files:**
- Modify: `backend/Dockerfile` (lines 52-58: CMD)
- Modify: `backend/app/main.py` (startup/shutdown lifecycle)
- Modify: `backend/run.py`

**Step 1: Update Dockerfile CMD for 4 workers**

In `backend/Dockerfile`, change the CMD to:
```dockerfile
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*", \
     "--log-level", "info"]
```

**Step 2: Handle per-worker initialization**

With multiple workers, `startup_event()` runs in EACH worker. We need to ensure:
- Each worker loads its own ONNX session (shared pages via fork)
- Each worker loads FAISS with mmap (shared pages)
- Only ONE worker starts the batch processor loop (use Redis lock)
- Each worker starts its own Redis pub/sub listener (for WebSocket)

Modify `startup_event()` in `backend/app/main.py`:
```python
import os

async def startup_event():
    worker_id = os.getpid()
    logger.info(f"Worker {worker_id} starting up...")

    # Every worker: load models (shared memory via fork)
    await insightface_model.load_model()
    faiss_manager.load_or_create_index()

    # Every worker: connect to Redis
    from app.redis_client import get_redis
    await get_redis()

    # Every worker: start WebSocket Redis listener
    from app.routers.websocket import manager
    await manager.start_redis_listener()

    # Every worker: start batch processor (Redis lock ensures only one processes at a time)
    from app.services.batch_processor import batch_processor
    await batch_processor.start()

    # Every worker: start FAISS reload listener
    asyncio.create_task(faiss_manager.subscribe_index_changes())

    # Every worker: start presence scan scheduler
    # (Redis lock in scan cycle ensures only one worker runs the scan)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_presence_scan_cycle,
        "interval",
        seconds=settings.SCAN_INTERVAL_SECONDS,
        max_instances=1,
    )
    scheduler.start()
```

**Step 3: Update run.py for local development**

Update `backend/run.py` to support `--workers` flag:
```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=args.workers,
        reload=args.workers == 1,  # reload only in single-worker mode
    )
```

**Step 4: Test with single worker first**

Run: `cd backend && python run.py --workers 1`
Expected: Server starts, health check passes

**Step 5: Test with 4 workers**

Run: `cd backend && python run.py --workers 4`
Expected: 4 worker PIDs in logs, health check passes

**Step 6: Commit**

```bash
git add backend/Dockerfile backend/app/main.py backend/run.py
git commit -m "feat: configure 4 Uvicorn workers with per-worker initialization"
```

---

## Task 8: RPi Smart Sampler

**Files:**
- Create: `edge/app/smart_sampler.py`
- Modify: `edge/app/main.py` (lines 184-279: `run_single_scan()`)
- Modify: `edge/app/config.py`
- Modify: `edge/app/sender.py`

**Step 1: Add Smart Sampler config**

Add to `edge/app/config.py`:
```python
# Smart Sampler
SEND_INTERVAL: float = float(os.getenv("SEND_INTERVAL", "3"))
DEDUP_WINDOW: float = float(os.getenv("DEDUP_WINDOW", "5"))
FACE_GONE_TIMEOUT: float = float(os.getenv("FACE_GONE_TIMEOUT", "10"))
IOU_MATCH_THRESHOLD: float = float(os.getenv("IOU_MATCH_THRESHOLD", "0.3"))
USE_SMART_SAMPLER: bool = os.getenv("USE_SMART_SAMPLER", "true").lower() == "true"
```

**Step 2: Create Smart Sampler module**

Create `edge/app/smart_sampler.py`:

```python
"""
Smart Sampler: reduces redundant face transmissions.

- Tracks faces across frames using IoU matching
- Deduplicates: skips faces already sent within DEDUP_WINDOW
- Best-frame selection: picks highest confidence + least blur
- Immediate send on new face (new track ID)
- Sends face_gone event when track disappears for FACE_GONE_TIMEOUT
"""
import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TrackedFace:
    track_id: int
    bbox: List[int]  # [x, y, w, h]
    confidence: float
    last_seen: float
    last_sent: float = 0.0
    best_frame_data: Optional[object] = None  # FaceData with highest quality
    best_confidence: float = 0.0
    is_new: bool = True


class SmartSampler:
    def __init__(self, config):
        self.config = config
        self._tracks: Dict[int, TrackedFace] = {}
        self._next_track_id: int = 0
        self._iou_threshold = config.IOU_MATCH_THRESHOLD

    def update(
        self,
        detections: list,
        face_data_list: list,
        current_time: Optional[float] = None,
    ) -> Tuple[List[object], List[int]]:
        """
        Process new detections, return (faces_to_send, gone_track_ids).

        Args:
            detections: List of FaceBox from detector
            face_data_list: List of FaceData from processor (parallel to detections)
            current_time: Override for testing

        Returns:
            faces_to_send: FaceData objects that should be sent to backend
            gone_track_ids: Track IDs that have disappeared
        """
        now = current_time or time.time()
        faces_to_send = []
        matched_track_ids = set()

        # Match detections to existing tracks
        for det, face_data in zip(detections, face_data_list):
            if face_data is None:
                continue

            bbox = det.to_list() if hasattr(det, "to_list") else det
            track_id = self._match_or_create(bbox, now)
            matched_track_ids.add(track_id)

            track = self._tracks[track_id]
            track.last_seen = now
            track.bbox = bbox
            track.confidence = det.confidence if hasattr(det, "confidence") else 0

            # Update best frame if this one is better
            if track.confidence > track.best_confidence:
                track.best_confidence = track.confidence
                track.best_frame_data = face_data

            # Send if: new face OR dedup window expired
            if track.is_new:
                faces_to_send.append(face_data)
                track.last_sent = now
                track.is_new = False
                track.best_confidence = 0  # Reset for next window
                logger.debug(f"New face track {track_id}, sending immediately")
            elif (now - track.last_sent) >= self.config.DEDUP_WINDOW:
                # Send best frame from this window
                to_send = track.best_frame_data or face_data
                faces_to_send.append(to_send)
                track.last_sent = now
                track.best_confidence = 0
                track.best_frame_data = None

        # Check for gone faces
        gone_track_ids = []
        stale_ids = []
        for tid, track in self._tracks.items():
            if tid not in matched_track_ids:
                if (now - track.last_seen) >= self.config.FACE_GONE_TIMEOUT:
                    gone_track_ids.append(tid)
                    stale_ids.append(tid)

        for tid in stale_ids:
            del self._tracks[tid]

        return faces_to_send, gone_track_ids

    def _match_or_create(self, bbox: List[int], now: float) -> int:
        """Match bbox to existing track or create new one."""
        best_iou = 0
        best_tid = None

        for tid, track in self._tracks.items():
            iou = self._compute_iou(bbox, track.bbox)
            if iou > best_iou:
                best_iou = iou
                best_tid = tid

        if best_iou >= self._iou_threshold and best_tid is not None:
            return best_tid

        # Create new track
        tid = self._next_track_id
        self._next_track_id += 1
        self._tracks[tid] = TrackedFace(
            track_id=tid,
            bbox=bbox,
            confidence=0,
            last_seen=now,
            is_new=True,
        )
        return tid

    @staticmethod
    def _compute_iou(box1: List[int], box2: List[int]) -> float:
        """IoU between two [x, y, w, h] boxes."""
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2

        xi1 = max(x1, x2)
        yi1 = max(y1, y2)
        xi2 = min(x1 + w1, x2 + w2)
        yi2 = min(y1 + h1, y2 + h2)

        inter = max(0, xi2 - xi1) * max(0, yi2 - yi1)
        union = w1 * h1 + w2 * h2 - inter

        return inter / union if union > 0 else 0

    @property
    def active_tracks(self) -> int:
        return len(self._tracks)
```

**Step 3: Integrate Smart Sampler into EdgeDevice main loop**

Modify `edge/app/main.py` `run_single_scan()` (line 184) to:

1. Run detection and processing as before
2. Pass results through `SmartSampler.update()`
3. Only send the filtered faces (not all detected)
4. Send `face_gone` events for disappeared tracks
5. Use `SEND_INTERVAL` (3s) instead of `SCAN_INTERVAL` (60s) when smart sampler is active

**Step 4: Update sender to handle face_gone events**

Add to `edge/app/sender.py` `SyncBackendSender`:
```python
def send_face_gone(self, room_id: str, track_ids: list):
    """Notify backend that tracked faces have disappeared."""
    payload = {
        "room_id": room_id,
        "event": "face_gone",
        "track_ids": track_ids,
        "timestamp": datetime.utcnow().isoformat(),
    }
    # Fire and forget, don't queue on failure
    try:
        self.client.post(
            f"{self.base_url}/api/v1/face/gone",
            json=payload,
            timeout=5,
        )
    except Exception:
        pass  # Non-critical, presence service handles via timeout
```

**Step 5: Commit**

```bash
git add edge/app/smart_sampler.py edge/app/main.py edge/app/config.py edge/app/sender.py
git commit -m "feat: RPi smart sampler with IoU tracking, dedup, and face_gone events"
```

---

## Task 9: Update Edge Sender for Fire-and-Forget (202)

**Files:**
- Modify: `edge/app/sender.py` (lines 316-340: `send_faces()`)
- Modify: `edge/app/main.py`

**Step 1: Update sender to accept 202 responses**

In `edge/app/sender.py` `SyncBackendSender.send_faces()`, change the success check:

```python
# Before: only 200 was success
if response.status_code == 200:
    return response.json()

# After: 200 or 202 are both success
if response.status_code in (200, 202):
    return response.json()
```

**Step 2: Update main loop interval**

In `edge/app/main.py` `run_continuous()` (line 281), update sleep interval:

```python
# When smart sampler is active, use SEND_INTERVAL (3s) instead of SCAN_INTERVAL (60s)
if self.config.USE_SMART_SAMPLER and self._session_active:
    interval = self.config.SEND_INTERVAL
else:
    interval = self.scan_interval
```

**Step 3: Commit**

```bash
git add edge/app/sender.py edge/app/main.py
git commit -m "feat: edge sender accepts 202, uses 3s interval with smart sampler"
```

---

## Task 10: Shared embed_face() Pipeline for Registration-Recognition Alignment

**Files:**
- Create: `backend/app/services/ml/embedding_pipeline.py`
- Modify: `backend/app/services/face_service.py`

**Step 1: Extract shared embedding function**

Create `backend/app/services/ml/embedding_pipeline.py`:

```python
"""
Shared face embedding pipeline used by BOTH registration and recognition.

Guarantees identical preprocessing for both paths:
1. Detection: SCRFD (same model)
2. Alignment: 5-point landmark warp
3. Preprocessing: CLAHE + resize 112x112 + normalize [-1,1]
4. Embedding: ArcFace ONNX → 512-dim L2-normalized
"""
import numpy as np
import cv2
import logging
from typing import Optional, Tuple, List

from app.services.ml.insightface_model import insightface_model

logger = logging.getLogger(__name__)


async def embed_face(image_bytes: bytes) -> Optional[np.ndarray]:
    """
    Generate a 512-dim L2-normalized embedding from face image bytes.

    Used by both registration and recognition paths to ensure
    embeddings are in the same vector space.

    Returns None if no face detected or quality too low.
    """
    result = insightface_model.get_face_with_quality(image_bytes)
    if result is None:
        return None
    return result["embedding"]


async def embed_faces_batch(images: List[bytes]) -> List[Optional[np.ndarray]]:
    """Batch version of embed_face. Returns list parallel to input."""
    results = []
    for img_bytes in images:
        emb = await embed_face(img_bytes)
        results.append(emb)
    return results


def validate_registration_embeddings(
    embeddings: List[np.ndarray],
    min_cross_similarity: float = 0.7,
) -> Tuple[bool, str]:
    """
    Validate that all registration embeddings are from the same person.

    Checks pairwise cosine similarity between all embeddings.
    Returns (is_valid, message).
    """
    if len(embeddings) < 2:
        return True, "Single embedding, no cross-validation needed"

    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            sim = float(np.dot(embeddings[i], embeddings[j]))
            if sim < min_cross_similarity:
                return False, (
                    f"Embeddings {i} and {j} have low similarity ({sim:.3f}). "
                    f"Ensure all captures are of the same person."
                )

    return True, "All embeddings are consistent"


def average_embeddings(embeddings: List[np.ndarray]) -> np.ndarray:
    """Average and L2-normalize embeddings for FAISS storage."""
    avg = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(avg)
    if norm > 0:
        avg = avg / norm
    return avg
```

**Step 2: Update face_service.py to use shared pipeline**

In `backend/app/services/face_service.py`:

1. Import the shared pipeline:
```python
from app.services.ml.embedding_pipeline import (
    embed_face,
    validate_registration_embeddings,
    average_embeddings,
)
```

2. In `register_face()` (line 79-127), replace direct `insightface_model.get_embedding()` calls with `await embed_face(image_bytes)`

3. Add cross-capture validation after generating all embeddings:
```python
is_valid, msg = validate_registration_embeddings(embeddings)
if not is_valid:
    return 0, msg, quality_reports
```

4. In `recognize_face()` (line 219-254), replace direct embedding call with `await embed_face(image_bytes)`

**Step 3: Run tests**

Run: `cd backend && pytest tests/ -v`
Expected: All tests pass with same behavior

**Step 4: Commit**

```bash
git add backend/app/services/ml/embedding_pipeline.py backend/app/services/face_service.py
git commit -m "feat: shared embed_face() pipeline for registration-recognition alignment"
```

---

## Task 11: Mobile WebSocket Event Handlers

**Files:**
- Modify: `mobile/src/hooks/useWebSocket.ts`
- Modify: `mobile/src/constants/config.ts`

**Step 1: Add new event types to useWebSocket**

In `mobile/src/hooks/useWebSocket.ts`, extend `UseWebSocketOptions`:

```typescript
interface UseWebSocketOptions {
  // existing
  onAttendanceUpdate?: (message: WebSocketMessage) => void;
  onEarlyLeave?: (message: WebSocketMessage) => void;
  onSessionStart?: (message: WebSocketMessage) => void;
  onSessionEnd?: (message: WebSocketMessage) => void;
  onConnected?: () => void;
  autoConnect?: boolean;
  // new
  onPresenceWarning?: (message: WebSocketMessage) => void;
  onPresenceScore?: (message: WebSocketMessage) => void;
  onStudentCheckedIn?: (message: WebSocketMessage) => void;
}
```

Register the new callbacks in the effect (around lines 86-109):

```typescript
if (onPresenceWarning) {
  subs.push(websocketService.on('presence_warning', onPresenceWarningRef.current));
}
if (onPresenceScore) {
  subs.push(websocketService.on('presence_score', onPresenceScoreRef.current));
}
if (onStudentCheckedIn) {
  subs.push(websocketService.on('student_checked_in', onStudentCheckedInRef.current));
}
```

**Step 2: Commit**

```bash
git add mobile/src/hooks/useWebSocket.ts
git commit -m "feat: add presence_warning, presence_score, student_checked_in WebSocket events"
```

---

## Task 12: Update face_gone Backend Endpoint

**Files:**
- Modify: `backend/app/routers/face.py`
- Modify: `backend/app/services/presence_service.py`

**Step 1: Add /face/gone endpoint**

Add to `backend/app/routers/face.py`:

```python
@router.post("/gone", status_code=200)
async def face_gone(request: dict):
    """Receive face_gone events from RPi smart sampler."""
    room_id = request.get("room_id")
    track_ids = request.get("track_ids", [])
    timestamp = request.get("timestamp")

    if room_id:
        # Notify presence service that faces have left
        from app.services.presence_service import PresenceService
        presence_service = PresenceService()
        await presence_service.handle_face_gone(room_id, track_ids, timestamp)

    return {"status": "ok", "processed": len(track_ids)}
```

**Step 2: Add handle_face_gone to presence service**

Add to `PresenceService`:
```python
async def handle_face_gone(self, room_id: str, track_ids: list, timestamp: str):
    """Handle face_gone events from RPi smart sampler.

    This provides early warning that a student may be leaving.
    The 60-second confirmation scan still runs as the authoritative check.
    """
    logger.info(f"Face gone event: room={room_id}, tracks={track_ids}")
    # For now, log the event. The 60-second scan handles miss counting.
    # In future, this can trigger immediate presence_warning WebSocket events.
```

**Step 3: Commit**

```bash
git add backend/app/routers/face.py backend/app/services/presence_service.py
git commit -m "feat: face_gone endpoint for RPi early leave detection"
```

---

## Task 13: Update Deployment Configuration

**Files:**
- Modify: `deploy/docker-compose.prod.yml`
- Modify: `deploy/deploy.sh`
- Modify: `deploy/nginx.conf`

**Step 1: Final docker-compose.prod.yml updates**

Ensure the complete stack includes:
1. `backend` with `workers=4`, `depends_on: [redis, mediamtx]`, `REDIS_URL` env var
2. `redis` service (from Task 1)
3. `mediamtx`, `coturn`, `nginx`, `certbot` (existing)

**Step 2: Update nginx.conf for multi-worker WebSocket**

Ensure nginx uses `upstream` with `ip_hash` for sticky WebSocket sessions:

```nginx
upstream backend {
    ip_hash;  # Sticky sessions for WebSocket
    server backend:8000;
}
```

This ensures a WebSocket connection stays with the same worker. Combined with Redis pub/sub, all workers still receive all messages.

**Step 3: Update deploy.sh**

Add Redis data directory handling and ensure new config files are synced.

**Step 4: Test deployment locally with docker-compose**

Run: `cd deploy && docker compose -f docker-compose.prod.yml up --build`
Expected: All 6 services start, health check passes

**Step 5: Commit**

```bash
git add deploy/docker-compose.prod.yml deploy/deploy.sh deploy/nginx.conf
git commit -m "feat: update deployment for multi-worker + Redis stack"
```

---

## Task 14: Integration Testing — 2-Room Simulation

**Files:**
- Create: `backend/tests/test_batch_processing.py`
- Create: `backend/tests/test_multi_room.py`

**Step 1: Write batch processing integration test**

```python
"""Test the batch processing pipeline end-to-end."""
import pytest
import asyncio
from unittest.mock import patch, MagicMock

async def test_batch_enqueue_and_process():
    """Faces enqueued to Redis are processed in batch."""
    # 1. Enqueue 10 faces for room_a
    # 2. Wait for batch_interval
    # 3. Verify all 10 were processed
    # 4. Verify results published to Redis pub/sub
    pass

async def test_batch_processes_multiple_rooms():
    """Faces from room_a and room_b are processed independently."""
    # 1. Enqueue 5 faces for room_a, 5 for room_b
    # 2. Verify both rooms processed in same batch cycle
    pass

async def test_202_response_from_process_endpoint():
    """Edge API returns 202 immediately when batch mode enabled."""
    # 1. POST to /api/v1/face/process
    # 2. Assert response.status_code == 202
    # 3. Assert response includes faces_queued count
    pass
```

**Step 2: Write multi-room simulation test**

```python
"""Simulate 2 rooms with 50 faces each."""
import pytest

async def test_concurrent_rooms_50_faces():
    """Two rooms submit 50 faces concurrently, all processed within 10s."""
    # 1. Generate 100 fake face payloads (50 per room)
    # 2. POST all concurrently
    # 3. Wait up to 10 seconds
    # 4. Verify all faces queued and processed
    pass
```

**Step 3: Run tests**

Run: `cd backend && pytest tests/test_batch_processing.py tests/test_multi_room.py -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/tests/test_batch_processing.py backend/tests/test_multi_room.py
git commit -m "test: integration tests for batch processing and multi-room simulation"
```

---

## Task Order & Dependencies

```
Task 1: Redis Infrastructure          ← foundation, do first
Task 2: ONNX Runtime Conversion       ← independent of Redis
Task 3: FAISS Memory-Map              ← depends on Task 1 (Redis notify)
Task 4: Batch Processor               ← depends on Task 1
Task 5: WebSocket Pub/Sub             ← depends on Task 1
Task 6: Redis Presence State          ← depends on Task 1, 4
Task 7: Multi-Worker Uvicorn          ← depends on Tasks 1-6
Task 8: RPi Smart Sampler             ← independent (edge-only)
Task 9: Edge Fire-and-Forget          ← depends on Task 4, 8
Task 10: Shared Embedding Pipeline    ← depends on Task 2
Task 11: Mobile WebSocket Events      ← depends on Task 5
Task 12: Face Gone Endpoint           ← depends on Task 8
Task 13: Deployment Config            ← depends on all above
Task 14: Integration Testing          ← last
```

**Parallelizable groups:**
- Group A (backend): Tasks 1 → 2 → 3 → 4 → 5 → 6 → 7
- Group B (edge): Tasks 8 → 9 (can run parallel to Group A)
- Group C (mobile): Task 11 (can run parallel to Groups A/B)
- Group D (alignment): Task 10 (after Task 2)
- Group E (integration): Tasks 12 → 13 → 14 (after all)
