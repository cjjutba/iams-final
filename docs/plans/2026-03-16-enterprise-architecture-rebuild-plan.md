# IAMS Enterprise Architecture Rebuild — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild IAMS as an enterprise-grade attendance system with containerized multi-worker architecture, Redis Streams event bus, Reolink camera support, and real-time WebRTC streaming.

**Architecture:** Three-tier (RPi Camera Gateway → VPS Multi-Container → Mobile Apps). Single VPS runs 7 Docker containers: API Gateway, Detection Worker, Recognition Worker, Redis, mediamtx, nginx, coturn. Workers communicate via Redis Streams. RPi acts as lightweight relay (zero ML).

**Tech Stack:** FastAPI, InsightFace (SCRFD + ArcFace), FAISS, Redis Streams, mediamtx, Docker Compose, React Native, Zustand, Reanimated 3

**Design Doc:** `docs/plans/2026-03-16-enterprise-architecture-rebuild-design.md`

---

## What to KEEP vs REWRITE

### KEEP (no changes needed)
- `backend/app/models/` — All SQLAlchemy models
- `backend/app/schemas/` — All Pydantic schemas
- `backend/app/repositories/` — All repository classes
- `backend/app/database.py` — DB connection
- `backend/app/utils/` — Security, exceptions, dependencies, audit
- `backend/app/services/ml/insightface_model.py` — InsightFace wrapper
- `backend/app/services/ml/faiss_manager.py` — FAISS manager
- `backend/app/services/ml/embedding_pipeline.py` — Embedding pipeline
- `backend/app/services/ml/face_quality.py` — Quality gates
- `backend/app/services/ml/anti_spoof.py` — Anti-spoof checks
- `backend/app/services/face_service.py` — Face registration logic
- `backend/app/services/auth_service.py` — Auth logic
- `backend/app/services/enrollment_service.py` — Enrollment logic
- `backend/app/services/notification_service.py` — Notification logic
- `backend/app/services/webrtc_service.py` — WebRTC WHEP proxy
- `backend/app/services/mediamtx_service.py` — mediamtx lifecycle
- `backend/app/routers/auth.py` — Auth endpoints
- `backend/app/routers/face.py` — Face registration endpoints
- `backend/app/routers/users.py` — User endpoints
- `backend/app/routers/rooms.py` — Room endpoints
- `backend/app/routers/schedules.py` — Schedule endpoints
- `backend/app/routers/attendance.py` — Attendance endpoints
- `backend/app/routers/notifications.py` — Notification endpoints
- `backend/app/routers/webrtc.py` — WebRTC signaling
- `backend/app/routers/analytics.py` — Analytics
- `backend/app/routers/presence.py` — Presence REST endpoints
- `backend/app/redis_client.py` — Redis connection (extend, don't rewrite)
- All mobile screens, components, stores, navigation (update hooks only)

### REWRITE (new enterprise architecture)
- `backend/app/services/stream_bus.py` — NEW: Redis Streams event bus
- `backend/app/workers/detection_worker.py` — NEW: Standalone detection process
- `backend/app/workers/recognition_worker.py` — NEW: Standalone recognition process
- `backend/app/workers/__init__.py` — NEW
- `backend/app/workers/base_worker.py` — NEW: Shared worker base class
- `backend/app/services/track_fusion_service.py` — REWRITE: Use Redis Streams input
- `backend/app/services/presence_service.py` — REWRITE: Use Redis Streams for events
- `backend/app/services/session_scheduler.py` — REWRITE: Full auto-session lifecycle
- `backend/app/routers/live_stream.py` — REWRITE: Simplified, Redis Streams driven
- `backend/app/routers/edge_ws.py` — REWRITE: Frame ingestion for Reolink gateway
- `backend/app/routers/websocket.py` — REWRITE: Multi-channel broadcaster
- `backend/app/main.py` — REWRITE: Role-based startup (api-gateway vs worker)
- `backend/app/config.py` — EXTEND: Add SERVICE_ROLE, worker settings
- `edge/app/main.py` — REWRITE: Reolink dual-stream gateway
- `edge/app/camera.py` — REWRITE: RTSP from Reolink (not picamera)
- `edge/app/stream_relay.py` — REWRITE: FFmpeg sub-stream relay
- `edge/app/frame_sampler.py` — NEW: Main-stream frame sampler
- `edge/app/config.py` — REWRITE: Reolink settings
- `deploy/docker-compose.prod.yml` — REWRITE: Multi-container
- `mobile/src/hooks/useDetectionWebSocket.ts` — UPDATE: Match new message format
- `mobile/src/hooks/useAttendanceWebSocket.ts` — NEW: Live attendance updates

### DELETE (superseded by new architecture)
- `backend/app/services/compositor_service.py` — Replaced by detection worker
- `backend/app/services/local_camera_service.py` — Dev only, not needed
- `backend/app/services/hls_service.py` — HLS dropped, WebRTC only
- `backend/app/services/batch_processor.py` — Replaced by Redis Streams
- `backend/app/services/live_stream_service.py` — Merged into live_stream router
- `backend/app/services/edge_relay_service.py` — Replaced by Redis Streams
- `backend/app/routers/hls.py` — HLS dropped
- `backend/app/services/tracking_service.py` — Replaced by track fusion
- `edge/app/detector.py` — No ML on RPi
- `edge/app/processor.py` — No ML on RPi
- `edge/app/sender.py` — Replaced by WebSocket
- `edge/app/centroid_tracker.py` — No tracking on RPi
- `edge/app/smart_sampler.py` — Replaced by frame_sampler
- `edge/app/queue_manager.py` — Replaced by simpler deque in gateway

---

## Phase 1: Foundation — Redis Streams Event Bus

### Task 1: Redis Streams Client Wrapper

**Files:**
- Create: `backend/app/services/stream_bus.py`
- Modify: `backend/app/redis_client.py`

**Step 1: Create the Redis Streams event bus**

```python
# backend/app/services/stream_bus.py
"""
Redis Streams event bus for inter-service communication.
Enterprise pattern: event-driven pipeline with consumer groups.
"""
import json
import logging
import time
from typing import Any

import redis.asyncio as redis

from app.redis_client import get_redis

logger = logging.getLogger(__name__)

# Stream names
STREAM_FRAMES = "stream:frames:{room_id}"
STREAM_DETECTIONS = "stream:detections:{room_id}"
STREAM_RECOGNITION_REQ = "stream:recognition_req"
STREAM_RECOGNITIONS = "stream:recognitions"
STREAM_ATTENDANCE = "stream:attendance:{schedule_id}"
STREAM_ALERTS = "stream:alerts"
STREAM_METRICS = "stream:metrics"


class StreamBus:
    """Redis Streams wrapper for publishing and consuming events."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    # ── Publishing ──────────────────────────────────────────────

    async def publish(
        self, stream: str, data: dict[str, Any], maxlen: int = 100
    ) -> str:
        """Publish a message to a Redis Stream. Returns message ID."""
        # Redis Streams require all values to be strings or bytes
        payload = {"data": json.dumps(data), "ts": str(time.time())}
        msg_id = await self.redis.xadd(stream, payload, maxlen=maxlen)
        return msg_id

    async def publish_frame(self, room_id: str, frame_data: dict) -> str:
        stream = STREAM_FRAMES.format(room_id=room_id)
        return await self.publish(stream, frame_data, maxlen=10)

    async def publish_detections(self, room_id: str, detections: dict) -> str:
        stream = STREAM_DETECTIONS.format(room_id=room_id)
        return await self.publish(stream, detections, maxlen=30)

    async def publish_recognition_request(self, request: dict) -> str:
        return await self.publish(STREAM_RECOGNITION_REQ, request, maxlen=100)

    async def publish_recognition_result(self, result: dict) -> str:
        return await self.publish(STREAM_RECOGNITIONS, result, maxlen=100)

    async def publish_attendance(self, schedule_id: str, update: dict) -> str:
        stream = STREAM_ATTENDANCE.format(schedule_id=schedule_id)
        return await self.publish(stream, update, maxlen=1000)

    async def publish_alert(self, alert: dict) -> str:
        return await self.publish(STREAM_ALERTS, alert, maxlen=500)

    async def publish_metrics(self, metrics: dict) -> str:
        return await self.publish(STREAM_METRICS, metrics, maxlen=100)

    # ── Consuming ───────────────────────────────────────────────

    async def ensure_group(self, stream: str, group: str):
        """Create consumer group if it doesn't exist."""
        try:
            await self.redis.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 1,
        block: int = 5000,
    ) -> list[tuple[str, dict]]:
        """Read messages from a consumer group. Returns [(msg_id, data)]."""
        results = await self.redis.xreadgroup(
            group, consumer, {stream: ">"}, count=count, block=block
        )
        messages = []
        for _stream_name, entries in results:
            for msg_id, fields in entries:
                data_str = fields.get(b"data") or fields.get("data")
                if data_str:
                    if isinstance(data_str, bytes):
                        data_str = data_str.decode()
                    messages.append((msg_id, json.loads(data_str)))
        return messages

    async def ack(self, stream: str, group: str, msg_id: str):
        """Acknowledge a processed message."""
        await self.redis.xack(stream, group, msg_id)

    async def consume_multiple(
        self,
        streams: dict[str, str],
        group: str,
        consumer: str,
        count: int = 1,
        block: int = 5000,
    ) -> list[tuple[str, str, dict]]:
        """Read from multiple streams. Returns [(stream, msg_id, data)]."""
        results = await self.redis.xreadgroup(
            group, consumer, streams, count=count, block=block
        )
        messages = []
        for stream_name, entries in results:
            if isinstance(stream_name, bytes):
                stream_name = stream_name.decode()
            for msg_id, fields in entries:
                data_str = fields.get(b"data") or fields.get("data")
                if data_str:
                    if isinstance(data_str, bytes):
                        data_str = data_str.decode()
                    messages.append((stream_name, msg_id, json.loads(data_str)))
        return messages


# ── Singleton ─────────────────────────────────────────────────

_bus: StreamBus | None = None


async def get_stream_bus() -> StreamBus:
    global _bus
    if _bus is None:
        r = await get_redis()
        _bus = StreamBus(r)
    return _bus
```

**Step 2: Verify Redis Streams work**

Run: `cd backend && python -c "import asyncio; from app.services.stream_bus import StreamBus; print('StreamBus imported OK')"`
Expected: `StreamBus imported OK`

**Step 3: Commit**

```bash
git add backend/app/services/stream_bus.py
git commit -m "feat: add Redis Streams event bus for inter-service communication"
```

---

### Task 2: Config — Add SERVICE_ROLE and Worker Settings

**Files:**
- Modify: `backend/app/config.py`

**Step 1: Add new settings to the Settings class**

Add these fields to the `Settings` class in `config.py`:

```python
    # Service Role (determines which components start)
    # "api-gateway" | "detection-worker" | "recognition-worker" | "all" (dev)
    SERVICE_ROLE: str = "all"

    # Worker Settings
    DETECTION_FPS: float = 3.0  # Frames per second to process for detection
    RECOGNITION_BATCH_SIZE: int = 10  # Max faces to recognize in one batch
    TRACK_COAST_MS: int = 500  # Track coast duration before LOST (ms)
    TRACK_DELETE_MS: int = 2000  # Time in LOST before deletion (ms)
    TRACK_CONFIRM_HITS: int = 3  # Consecutive detections to confirm track
    FUSION_OUTPUT_FPS: float = 30.0  # Track fusion output rate

    # Edge Gateway
    EDGE_API_KEY: str = "edge-secret-key-change-in-production"  # RPi auth

    # Stream Consumer Groups
    DETECTION_GROUP: str = "detection-workers"
    RECOGNITION_GROUP: str = "recognition-workers"
    ATTENDANCE_GROUP: str = "attendance-writers"
```

**Step 2: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add SERVICE_ROLE and worker settings to config"
```

---

### Task 3: Worker Base Class

**Files:**
- Create: `backend/app/workers/__init__.py`
- Create: `backend/app/workers/base_worker.py`

**Step 1: Create the workers package and base class**

```python
# backend/app/workers/__init__.py
```

```python
# backend/app/workers/base_worker.py
"""
Base class for Redis Streams workers.
Handles consumer group setup, graceful shutdown, and health metrics.
"""
import asyncio
import json
import logging
import signal
import time
from abc import ABC, abstractmethod

from app.config import settings
from app.redis_client import get_redis
from app.services.stream_bus import StreamBus, get_stream_bus

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """Base class for all stream-consuming workers."""

    def __init__(self, name: str, group: str, consumer_id: str = "worker-1"):
        self.name = name
        self.group = group
        self.consumer_id = consumer_id
        self.running = False
        self.bus: StreamBus | None = None
        self.frames_processed = 0
        self.errors = 0
        self.start_time = time.time()
        self._last_metrics_time = time.time()

    async def setup(self):
        """Initialize connections and models. Override for custom setup."""
        self.bus = await get_stream_bus()
        logger.info(f"[{self.name}] Worker initialized")

    @abstractmethod
    async def get_streams(self) -> dict[str, str]:
        """Return {stream_name: ">"} dict of streams to consume."""
        ...

    @abstractmethod
    async def process_message(self, stream: str, msg_id: str, data: dict):
        """Process a single message from a stream."""
        ...

    async def run(self):
        """Main worker loop."""
        self.running = True
        await self.setup()

        # Create consumer groups for all streams
        streams = await self.get_streams()
        for stream_name in streams:
            await self.bus.ensure_group(stream_name, self.group)

        logger.info(f"[{self.name}] Listening on streams: {list(streams.keys())}")

        while self.running:
            try:
                messages = await self.bus.consume_multiple(
                    streams={s: ">" for s in streams},
                    group=self.group,
                    consumer=self.consumer_id,
                    count=5,
                    block=1000,
                )

                for stream, msg_id, data in messages:
                    try:
                        await self.process_message(stream, msg_id, data)
                        await self.bus.ack(stream, self.group, msg_id)
                        self.frames_processed += 1
                    except Exception as e:
                        self.errors += 1
                        logger.error(
                            f"[{self.name}] Error processing {msg_id}: {e}",
                            exc_info=True,
                        )

                # Publish metrics every 10 seconds
                now = time.time()
                if now - self._last_metrics_time >= 10:
                    await self._publish_metrics()
                    self._last_metrics_time = now

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.name}] Stream read error: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info(f"[{self.name}] Worker stopped")

    async def _publish_metrics(self):
        if self.bus:
            await self.bus.publish_metrics(
                {
                    "worker": self.name,
                    "frames_processed": self.frames_processed,
                    "errors": self.errors,
                    "uptime_seconds": int(time.time() - self.start_time),
                }
            )

    def stop(self):
        self.running = False


def run_worker(worker: BaseWorker):
    """Entry point for running a worker as a standalone process."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown(sig, frame):
        logger.info(f"[{worker.name}] Received {sig}, shutting down...")
        worker.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        loop.run_until_complete(worker.run())
    finally:
        loop.close()
```

**Step 2: Commit**

```bash
git add backend/app/workers/
git commit -m "feat: add worker base class with Redis Streams consumption loop"
```

---

## Phase 2: Workers — Detection & Recognition Containers

### Task 4: Detection Worker

**Files:**
- Create: `backend/app/workers/detection_worker.py`

This worker consumes 12MP JPEG frames from Redis, runs SCRFD detection, crops faces, assigns track IDs, and publishes detections + recognition requests.

**Step 1: Create the detection worker**

```python
# backend/app/workers/detection_worker.py
"""
Detection Worker — Standalone container process.

Consumes: stream:frames:{room_id}  (12MP JPEG snapshots from RPi)
Publishes: stream:detections:{room_id}  (bboxes + track IDs)
           stream:recognition_req  (new/unidentified track face crops)

Uses SCRFD (InsightFace) for face detection. Runs at ~3 FPS per room.
"""
import base64
import logging
import time

import cv2
import numpy as np

from app.config import settings
from app.services.ml.insightface_model import get_model
from app.services.stream_bus import STREAM_FRAMES, STREAM_RECOGNITION_REQ
from app.workers.base_worker import BaseWorker, run_worker

logger = logging.getLogger(__name__)


class SimpleTracker:
    """IoU + centroid tracker for assigning stable track IDs across frames."""

    def __init__(self, iou_threshold: float = 0.3, max_lost: int = 5):
        self.next_id = 1
        self.tracks: dict[int, dict] = {}  # track_id -> {bbox, lost_count, identified}
        self.iou_threshold = iou_threshold
        self.max_lost = max_lost

    def update(self, detections: list[dict]) -> list[dict]:
        """Match new detections to existing tracks. Returns detections with track_id."""
        if not self.tracks:
            # First frame — assign new IDs to all
            for det in detections:
                det["track_id"] = self.next_id
                det["is_new"] = True
                self.tracks[self.next_id] = {
                    "bbox": det["bbox"],
                    "lost_count": 0,
                    "identified": False,
                }
                self.next_id += 1
            return detections

        # Compute IoU between existing tracks and new detections
        track_ids = list(self.tracks.keys())
        track_bboxes = [self.tracks[tid]["bbox"] for tid in track_ids]
        det_bboxes = [d["bbox"] for d in detections]

        matched_dets = set()
        matched_tracks = set()

        if track_bboxes and det_bboxes:
            iou_matrix = self._compute_iou_matrix(track_bboxes, det_bboxes)

            # Greedy matching (highest IoU first)
            while True:
                if iou_matrix.size == 0:
                    break
                max_idx = np.unravel_index(iou_matrix.argmax(), iou_matrix.shape)
                max_iou = iou_matrix[max_idx]
                if max_iou < self.iou_threshold:
                    break
                t_idx, d_idx = max_idx
                tid = track_ids[t_idx]
                detections[d_idx]["track_id"] = tid
                detections[d_idx]["is_new"] = False
                self.tracks[tid]["bbox"] = detections[d_idx]["bbox"]
                self.tracks[tid]["lost_count"] = 0
                matched_dets.add(d_idx)
                matched_tracks.add(t_idx)
                iou_matrix[t_idx, :] = -1
                iou_matrix[:, d_idx] = -1

        # Unmatched detections → new tracks
        for i, det in enumerate(detections):
            if i not in matched_dets:
                det["track_id"] = self.next_id
                det["is_new"] = True
                self.tracks[self.next_id] = {
                    "bbox": det["bbox"],
                    "lost_count": 0,
                    "identified": False,
                }
                self.next_id += 1

        # Unmatched tracks → increment lost count, remove if too old
        for i, tid in enumerate(track_ids):
            if i not in matched_tracks:
                self.tracks[tid]["lost_count"] += 1
                if self.tracks[tid]["lost_count"] > self.max_lost:
                    del self.tracks[tid]

        return detections

    def mark_identified(self, track_id: int):
        if track_id in self.tracks:
            self.tracks[track_id]["identified"] = True

    def is_identified(self, track_id: int) -> bool:
        return self.tracks.get(track_id, {}).get("identified", False)

    def _compute_iou_matrix(
        self, boxes_a: list[list], boxes_b: list[list]
    ) -> np.ndarray:
        a = np.array(boxes_a, dtype=float)  # [N, 4] as [x1, y1, x2, y2]
        b = np.array(boxes_b, dtype=float)  # [M, 4]

        # Intersection
        inter_x1 = np.maximum(a[:, None, 0], b[None, :, 0])
        inter_y1 = np.maximum(a[:, None, 1], b[None, :, 1])
        inter_x2 = np.minimum(a[:, None, 2], b[None, :, 2])
        inter_y2 = np.minimum(a[:, None, 3], b[None, :, 3])
        inter_area = np.maximum(0, inter_x2 - inter_x1) * np.maximum(
            0, inter_y2 - inter_y1
        )

        # Union
        area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
        area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
        union = area_a[:, None] + area_b[None, :] - inter_area

        return inter_area / np.maximum(union, 1e-6)


class DetectionWorker(BaseWorker):
    def __init__(self):
        super().__init__(
            name="detection-worker",
            group=settings.DETECTION_GROUP,
        )
        self.model = None
        self.trackers: dict[str, SimpleTracker] = {}  # room_id -> tracker
        self.room_ids: list[str] = []

    async def setup(self):
        await super().setup()
        # Load InsightFace model (SCRFD detector only needed here,
        # but buffalo_l loads both — we only use det_model)
        logger.info(f"[{self.name}] Loading InsightFace model...")
        self.model = get_model()
        logger.info(f"[{self.name}] Model loaded")

        # Discover active rooms from Redis or config
        # For now, subscribe to all stream:frames:* patterns
        # We'll dynamically add rooms as frames arrive

    async def get_streams(self) -> dict[str, str]:
        # We consume from all room frame streams
        # Start with known rooms, dynamically add more
        r = await self.bus.redis if self.bus else None
        streams = {}
        if r:
            # Scan for existing frame streams
            async for key in r.scan_iter(match=b"stream:frames:*"):
                key_str = key.decode() if isinstance(key, bytes) else key
                streams[key_str] = ">"
                room_id = key_str.replace("stream:frames:", "")
                self.room_ids.append(room_id)
        # If no streams exist yet, create placeholder streams for known rooms
        if not streams:
            # We'll handle dynamic room discovery in the consume loop
            streams["stream:frames:default"] = ">"
        return streams

    async def process_message(self, stream: str, msg_id: str, data: dict):
        room_id = data.get("room_id", "unknown")
        t_start = time.time()

        # Decode JPEG frame
        frame_b64 = data.get("frame_b64", "")
        if not frame_b64:
            return

        frame_bytes = base64.b64decode(frame_b64)
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            logger.warning(f"[{self.name}] Failed to decode frame from {room_id}")
            return

        orig_h, orig_w = frame.shape[:2]

        # Downscale to 1080p for detection (keep original for cropping)
        det_frame = frame
        scale = 1.0
        if orig_w > 1920:
            scale = 1920 / orig_w
            det_h = int(orig_h * scale)
            det_frame = cv2.resize(frame, (1920, det_h))

        # Run SCRFD detection
        faces = self.model.detect_faces(det_frame)

        # Build detection list with bboxes mapped to original resolution
        detections = []
        for face_info in faces:
            bbox = face_info["bbox"]  # [x1, y1, x2, y2] in det_frame coords
            confidence = face_info.get("det_score", face_info.get("confidence", 0.0))

            # Map back to original 12MP coordinates
            if scale != 1.0:
                orig_bbox = [
                    int(bbox[0] / scale),
                    int(bbox[1] / scale),
                    int(bbox[2] / scale),
                    int(bbox[3] / scale),
                ]
            else:
                orig_bbox = [int(b) for b in bbox]

            detections.append(
                {
                    "bbox": orig_bbox,
                    "confidence": float(confidence),
                    "landmarks": face_info.get("landmarks"),
                }
            )

        # Track assignment
        tracker = self.trackers.setdefault(room_id, SimpleTracker())
        tracked_dets = tracker.update(detections)

        # Normalize bboxes to 0-1 for WebSocket output
        norm_detections = []
        recognition_requests = []

        for det in tracked_dets:
            bbox = det["bbox"]
            norm_bbox = [
                bbox[0] / orig_w,
                bbox[1] / orig_h,
                bbox[2] / orig_w,
                bbox[3] / orig_h,
            ]

            norm_det = {
                "track_id": det["track_id"],
                "bbox": norm_bbox,
                "confidence": det["confidence"],
                "is_new": det.get("is_new", False),
            }
            norm_detections.append(norm_det)

            # If new or unidentified track, crop face and request recognition
            if det.get("is_new") or not tracker.is_identified(det["track_id"]):
                # Crop face from ORIGINAL 12MP frame
                x1, y1, x2, y2 = bbox
                # Add 20% padding
                pad_w = int((x2 - x1) * 0.2)
                pad_h = int((y2 - y1) * 0.2)
                cx1 = max(0, x1 - pad_w)
                cy1 = max(0, y1 - pad_h)
                cx2 = min(orig_w, x2 + pad_w)
                cy2 = min(orig_h, y2 + pad_h)
                face_crop = frame[cy1:cy2, cx1:cx2]

                if face_crop.size > 0:
                    _, crop_jpeg = cv2.imencode(
                        ".jpg", face_crop, [cv2.IMWRITE_JPEG_QUALITY, 90]
                    )
                    crop_b64 = base64.b64encode(crop_jpeg.tobytes()).decode()

                    recognition_requests.append(
                        {
                            "room_id": room_id,
                            "track_id": det["track_id"],
                            "face_crop_b64": crop_b64,
                            "bbox": det["bbox"],
                            "confidence": det["confidence"],
                            "timestamp": data.get("timestamp", ""),
                        }
                    )

        # Publish detections
        await self.bus.publish_detections(
            room_id,
            {
                "room_id": room_id,
                "timestamp": data.get("timestamp", ""),
                "frame_width": orig_w,
                "frame_height": orig_h,
                "detections": norm_detections,
                "face_count": len(norm_detections),
            },
        )

        # Publish recognition requests (only for new/unidentified tracks)
        for req in recognition_requests:
            await self.bus.publish_recognition_request(req)

        latency_ms = (time.time() - t_start) * 1000
        if len(norm_detections) > 0:
            logger.info(
                f"[{self.name}] room={room_id} faces={len(norm_detections)} "
                f"new={len(recognition_requests)} latency={latency_ms:.0f}ms"
            )


# ── Entry point ─────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    worker = DetectionWorker()
    run_worker(worker)
```

**Step 2: Verify import**

Run: `cd backend && python -c "from app.workers.detection_worker import DetectionWorker; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/app/workers/detection_worker.py
git commit -m "feat: add detection worker — SCRFD face detection via Redis Streams"
```

---

### Task 5: Recognition Worker

**Files:**
- Create: `backend/app/workers/recognition_worker.py`

**Step 1: Create the recognition worker**

```python
# backend/app/workers/recognition_worker.py
"""
Recognition Worker — Standalone container process.

Consumes: stream:recognition_req  (face crops from detection worker)
Publishes: stream:recognitions  (identity matches from FAISS)

Uses ArcFace (InsightFace) for embedding + FAISS for nearest neighbor search.
Event-driven: only processes new/unidentified tracks, not every frame.
"""
import base64
import logging
import time

import cv2
import numpy as np

from app.config import settings
from app.database import SessionLocal
from app.repositories.face_repository import FaceRepository
from app.repositories.user_repository import UserRepository
from app.services.ml.faiss_manager import get_faiss_manager
from app.services.ml.insightface_model import get_model
from app.services.stream_bus import STREAM_RECOGNITION_REQ
from app.workers.base_worker import BaseWorker, run_worker

logger = logging.getLogger(__name__)


class RecognitionWorker(BaseWorker):
    def __init__(self):
        super().__init__(
            name="recognition-worker",
            group=settings.RECOGNITION_GROUP,
        )
        self.model = None
        self.faiss_mgr = None
        # Cache: user_id -> {name, student_id} (TTL managed manually)
        self._user_cache: dict[str, dict] = {}

    async def setup(self):
        await super().setup()
        logger.info(f"[{self.name}] Loading InsightFace model...")
        self.model = get_model()
        logger.info(f"[{self.name}] Loading FAISS index...")
        self.faiss_mgr = get_faiss_manager()
        logger.info(
            f"[{self.name}] Ready — FAISS has {self.faiss_mgr.index.ntotal} vectors"
        )

    async def get_streams(self) -> dict[str, str]:
        return {STREAM_RECOGNITION_REQ: ">"}

    async def process_message(self, stream: str, msg_id: str, data: dict):
        room_id = data.get("room_id", "unknown")
        track_id = data.get("track_id", -1)
        t_start = time.time()

        # Decode face crop
        crop_b64 = data.get("face_crop_b64", "")
        if not crop_b64:
            return

        crop_bytes = base64.b64decode(crop_b64)
        nparr = np.frombuffer(crop_bytes, np.uint8)
        face_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if face_img is None:
            logger.warning(f"[{self.name}] Failed to decode face crop for track {track_id}")
            return

        # Generate embedding using ArcFace
        embedding = self.model.get_embedding(face_img)
        if embedding is None:
            logger.debug(f"[{self.name}] No face found in crop for track {track_id}")
            return

        # FAISS search
        results = self.faiss_mgr.search(embedding, top_k=settings.RECOGNITION_TOP_K)
        if not results:
            logger.debug(f"[{self.name}] No FAISS match for track {track_id}")
            return

        top_match = results[0]
        similarity = float(top_match[0])
        user_id = top_match[1]

        # Threshold check with margin
        if similarity < settings.RECOGNITION_THRESHOLD:
            logger.debug(
                f"[{self.name}] Below threshold: {similarity:.3f} < {settings.RECOGNITION_THRESHOLD}"
            )
            return

        # Margin check (top-1 vs top-2)
        if len(results) > 1:
            second_sim = float(results[1][0])
            margin = similarity - second_sim
            if margin < settings.RECOGNITION_MARGIN:
                logger.debug(
                    f"[{self.name}] Margin too small: {margin:.3f} < {settings.RECOGNITION_MARGIN}"
                )
                return

        # Lookup user info (cached)
        user_info = await self._get_user_info(user_id)

        # Publish recognition result
        result = {
            "room_id": room_id,
            "track_id": track_id,
            "user_id": user_id,
            "name": user_info.get("name", "Unknown"),
            "student_id": user_info.get("student_id", ""),
            "similarity": round(similarity, 4),
            "timestamp": data.get("timestamp", ""),
        }
        await self.bus.publish_recognition_result(result)

        latency_ms = (time.time() - t_start) * 1000
        logger.info(
            f"[{self.name}] track={track_id} → {user_info.get('name', '?')} "
            f"sim={similarity:.3f} latency={latency_ms:.0f}ms"
        )

    async def _get_user_info(self, user_id: str) -> dict:
        """Get user name and student_id, with in-memory cache."""
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        info = {"name": "Unknown", "student_id": ""}
        try:
            db = SessionLocal()
            try:
                user_repo = UserRepository(db)
                user = user_repo.get_by_id(user_id)
                if user:
                    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                    info = {
                        "name": full_name or user.email,
                        "student_id": getattr(user, "student_id", "") or "",
                    }
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[{self.name}] DB lookup failed for {user_id}: {e}")

        self._user_cache[user_id] = info
        return info


# ── Entry point ─────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    worker = RecognitionWorker()
    run_worker(worker)
```

**Step 2: Verify import**

Run: `cd backend && python -c "from app.workers.recognition_worker import RecognitionWorker; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add backend/app/workers/recognition_worker.py
git commit -m "feat: add recognition worker — ArcFace + FAISS via Redis Streams"
```

---

## Phase 3: API Gateway — Ingestion, Track Fusion, WebSocket

### Task 6: Edge Frame Ingestion WebSocket

**Files:**
- Rewrite: `backend/app/routers/edge_ws.py`

This is the WebSocket endpoint that RPi camera gateways connect to for sending 12MP JPEG frames.

**Step 1: Rewrite edge_ws.py**

```python
# backend/app/routers/edge_ws.py
"""
Edge WebSocket — Frame ingestion from RPi Camera Gateways.

RPi connects via WebSocket, sends 12MP JPEG snapshots at 2-3 FPS.
Frames are validated and published to Redis stream:frames:{room_id}.
"""
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.services.stream_bus import get_stream_bus

logger = logging.getLogger(__name__)
router = APIRouter()

# Track connected edge devices
_edge_devices: dict[str, dict] = {}  # room_id -> {ws, connected_at, last_heartbeat}


def get_edge_devices() -> dict:
    return _edge_devices


@router.websocket("/ws/edge/{room_id}")
async def edge_websocket(websocket: WebSocket, room_id: str):
    """Accept WebSocket from RPi camera gateway."""
    # Verify API key from query params
    api_key = websocket.query_params.get("key", "")
    if api_key != settings.EDGE_API_KEY:
        await websocket.close(code=4001, reason="Invalid API key")
        return

    await websocket.accept()
    _edge_devices[room_id] = {
        "connected_at": time.time(),
        "last_heartbeat": time.time(),
        "frames_received": 0,
    }
    logger.info(f"[edge-ws] RPi connected for room {room_id}")

    bus = await get_stream_bus()

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "")

            if msg_type == "frame":
                # Validate required fields
                if not data.get("frame_b64"):
                    continue

                data["room_id"] = room_id

                # Publish to Redis stream for detection worker
                await bus.publish_frame(room_id, data)
                _edge_devices[room_id]["frames_received"] += 1
                _edge_devices[room_id]["last_heartbeat"] = time.time()

            elif msg_type == "heartbeat":
                _edge_devices[room_id]["last_heartbeat"] = time.time()
                _edge_devices[room_id]["camera_status"] = data.get(
                    "camera_status", "unknown"
                )
                _edge_devices[room_id]["cpu_percent"] = data.get("cpu_percent", 0)
                # Send ack
                await websocket.send_text(
                    json.dumps({"type": "heartbeat_ack", "ts": time.time()})
                )

    except WebSocketDisconnect:
        logger.info(f"[edge-ws] RPi disconnected from room {room_id}")
    except Exception as e:
        logger.error(f"[edge-ws] Error for room {room_id}: {e}")
    finally:
        _edge_devices.pop(room_id, None)
```

**Step 2: Commit**

```bash
git add backend/app/routers/edge_ws.py
git commit -m "feat: rewrite edge WebSocket for frame ingestion from RPi gateway"
```

---

### Task 7: Track Fusion Engine (Redis Streams Input)

**Files:**
- Rewrite: `backend/app/services/track_fusion_service.py`

**Step 1: Rewrite track fusion to consume from Redis Streams**

The track fusion engine runs inside the API gateway process. It consumes `stream:detections:{room}` and `stream:recognitions`, maintains Kalman-filtered tracks, and provides a `get_tracks(room_id)` method for the WebSocket broadcaster.

This file is large (~300 lines). The key changes from the current version:
- Input comes from Redis Streams (not direct function calls)
- Kalman filter parameters tuned per design doc
- Track lifecycle: TENTATIVE → CONFIRMED → LOST → DELETED
- Normalized bboxes (0-1) throughout
- Identity merged from recognition stream

Keep the existing Kalman filter math. Change the data flow to read from Redis Streams via a background asyncio task that runs in the API gateway process.

**Key structure:**

```python
# backend/app/services/track_fusion_service.py
"""
Track Fusion Engine — Merges detections + recognitions into smooth 30 FPS output.

Runs as a background task inside the API Gateway container.
Consumes: stream:detections:{room_id}, stream:recognitions
Provides: get_tracks(room_id) for WebSocket broadcaster
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field

import numpy as np

from app.config import settings
from app.services.stream_bus import (
    STREAM_DETECTIONS,
    STREAM_RECOGNITIONS,
    get_stream_bus,
)

logger = logging.getLogger(__name__)


@dataclass
class FusedTrack:
    track_id: int
    bbox: list[float]  # [x1, y1, x2, y2] normalized 0-1
    confidence: float
    state: str  # "tentative" | "confirmed" | "lost"
    hit_count: int = 0
    lost_count: int = 0
    last_update: float = 0.0
    # Identity (filled by recognition stream)
    user_id: str | None = None
    name: str | None = None
    student_id: str | None = None
    similarity: float | None = None
    # Kalman state
    kalman_state: np.ndarray | None = None
    kalman_cov: np.ndarray | None = None


class TrackFusionEngine:
    """Fuses detections and recognitions into smooth, identified tracks."""

    def __init__(self):
        self.rooms: dict[str, dict[int, FusedTrack]] = {}  # room_id -> {track_id -> track}
        self._running = False
        self._task: asyncio.Task | None = None
        # Kalman matrices (shared across all tracks)
        self._dt = 1.0 / settings.FUSION_OUTPUT_FPS
        self._init_kalman_matrices()

    def _init_kalman_matrices(self):
        """8-dim Kalman: [cx, cy, w, h, vx, vy, vw, vh]"""
        dt = self._dt
        self.F = np.eye(8)
        self.F[0, 4] = dt
        self.F[1, 5] = dt
        self.F[2, 6] = dt
        self.F[3, 7] = dt
        self.H = np.zeros((4, 8))
        self.H[0, 0] = 1
        self.H[1, 1] = 1
        self.H[2, 2] = 1
        self.H[3, 3] = 1
        self.Q = np.eye(8) * 1.0
        self.Q[4:, 4:] *= 0.1  # Low velocity noise (seated students)
        self.R = np.eye(4) * 4.0  # Trust detections closely

    async def start(self, room_ids: list[str] | None = None):
        """Start consuming detection and recognition streams."""
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("[track-fusion] Started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[track-fusion] Stopped")

    async def _consume_loop(self):
        """Background task consuming detection and recognition streams."""
        bus = await get_stream_bus()

        # We'll poll for detection streams dynamically
        det_group = "track-fusion"
        rec_group = "track-fusion"

        await bus.ensure_group(STREAM_RECOGNITIONS, rec_group)

        while self._running:
            try:
                # Discover detection streams
                r = bus.redis
                det_streams = []
                async for key in r.scan_iter(match=b"stream:detections:*"):
                    key_str = key.decode() if isinstance(key, bytes) else key
                    det_streams.append(key_str)
                    await bus.ensure_group(key_str, det_group)

                if not det_streams:
                    await asyncio.sleep(0.5)
                    continue

                # Build stream dict
                streams = {s: ">" for s in det_streams}
                streams[STREAM_RECOGNITIONS] = ">"

                messages = await bus.consume_multiple(
                    streams=streams,
                    group=det_group,
                    consumer="fusion-1",
                    count=10,
                    block=100,  # 100ms block for responsive fusion
                )

                for stream, msg_id, data in messages:
                    if "detections" in stream:
                        self._handle_detections(data)
                    elif "recognitions" in stream:
                        self._handle_recognition(data)
                    await bus.ack(stream, det_group, msg_id)

                # Predict step for all rooms (Kalman coast)
                self._predict_all()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[track-fusion] Error: {e}", exc_info=True)
                await asyncio.sleep(0.5)

    def _handle_detections(self, data: dict):
        """Update tracks from detection worker output."""
        room_id = data.get("room_id", "unknown")
        detections = data.get("detections", [])
        now = time.time()

        if room_id not in self.rooms:
            self.rooms[room_id] = {}

        tracks = self.rooms[room_id]

        # Update existing tracks and create new ones
        seen_track_ids = set()
        for det in detections:
            tid = det.get("track_id", -1)
            bbox = det.get("bbox", [0, 0, 0, 0])
            conf = det.get("confidence", 0.0)
            is_new = det.get("is_new", False)
            seen_track_ids.add(tid)

            if tid in tracks:
                track = tracks[tid]
                track.bbox = bbox
                track.confidence = conf
                track.hit_count += 1
                track.lost_count = 0
                track.last_update = now
                if track.state == "tentative" and track.hit_count >= settings.TRACK_CONFIRM_HITS:
                    track.state = "confirmed"
                elif track.state == "lost":
                    track.state = "confirmed"
                # Kalman update
                self._kalman_update(track, bbox)
            elif is_new:
                track = FusedTrack(
                    track_id=tid,
                    bbox=bbox,
                    confidence=conf,
                    state="tentative",
                    hit_count=1,
                    last_update=now,
                )
                self._kalman_init(track, bbox)
                tracks[tid] = track

        # Mark unseen tracks as losing
        for tid, track in list(tracks.items()):
            if tid not in seen_track_ids:
                track.lost_count += 1
                coast_ms = settings.TRACK_COAST_MS
                delete_ms = settings.TRACK_DELETE_MS
                elapsed_ms = (now - track.last_update) * 1000

                if elapsed_ms > delete_ms:
                    del tracks[tid]
                elif elapsed_ms > coast_ms and track.state != "lost":
                    track.state = "lost"

    def _handle_recognition(self, data: dict):
        """Merge identity from recognition worker into a track."""
        room_id = data.get("room_id", "unknown")
        track_id = data.get("track_id", -1)

        if room_id not in self.rooms:
            return

        track = self.rooms[room_id].get(track_id)
        if track:
            track.user_id = data.get("user_id")
            track.name = data.get("name")
            track.student_id = data.get("student_id")
            track.similarity = data.get("similarity")

    def _predict_all(self):
        """Kalman predict step for all active tracks."""
        for room_id, tracks in self.rooms.items():
            for track in tracks.values():
                if track.kalman_state is not None:
                    self._kalman_predict(track)

    def _kalman_init(self, track: FusedTrack, bbox: list[float]):
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        track.kalman_state = np.array([cx, cy, w, h, 0, 0, 0, 0], dtype=float)
        track.kalman_cov = np.eye(8) * 10.0

    def _kalman_predict(self, track: FusedTrack):
        if track.kalman_state is None:
            return
        track.kalman_state = self.F @ track.kalman_state
        track.kalman_cov = self.F @ track.kalman_cov @ self.F.T + self.Q
        # Update bbox from predicted state
        s = track.kalman_state
        track.bbox = [s[0] - s[2] / 2, s[1] - s[3] / 2, s[0] + s[2] / 2, s[1] + s[3] / 2]

    def _kalman_update(self, track: FusedTrack, bbox: list[float]):
        if track.kalman_state is None:
            self._kalman_init(track, bbox)
            return
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        z = np.array([cx, cy, w, h])
        S = self.H @ track.kalman_cov @ self.H.T + self.R
        K = track.kalman_cov @ self.H.T @ np.linalg.inv(S)
        track.kalman_state = track.kalman_state + K @ (z - self.H @ track.kalman_state)
        track.kalman_cov = (np.eye(8) - K @ self.H) @ track.kalman_cov
        # Update bbox from corrected state
        s = track.kalman_state
        track.bbox = [s[0] - s[2] / 2, s[1] - s[3] / 2, s[0] + s[2] / 2, s[1] + s[3] / 2]

    def get_tracks(self, room_id: str) -> list[dict]:
        """Get current fused tracks for a room (called by WebSocket broadcaster)."""
        tracks = self.rooms.get(room_id, {})
        result = []
        for track in tracks.values():
            if track.state == "lost":
                continue  # Don't send lost tracks to mobile
            entry = {
                "id": track.track_id,
                "bbox": track.bbox,
                "conf": track.confidence,
                "state": track.state,
            }
            if track.user_id:
                entry["identity"] = {
                    "user_id": track.user_id,
                    "name": track.name,
                    "student_id": track.student_id,
                    "similarity": track.similarity,
                }
            result.append(entry)
        return result

    def get_identified_users(self, room_id: str) -> dict[str, dict]:
        """Get all identified users in a room. Used by presence engine."""
        tracks = self.rooms.get(room_id, {})
        users = {}
        for track in tracks.values():
            if track.user_id and track.state == "confirmed":
                users[track.user_id] = {
                    "name": track.name,
                    "student_id": track.student_id,
                    "similarity": track.similarity,
                    "track_id": track.track_id,
                }
        return users


# Singleton
_engine: TrackFusionEngine | None = None


def get_track_fusion_engine() -> TrackFusionEngine:
    global _engine
    if _engine is None:
        _engine = TrackFusionEngine()
    return _engine
```

**Step 2: Commit**

```bash
git add backend/app/services/track_fusion_service.py
git commit -m "feat: rewrite track fusion engine with Redis Streams + Kalman filter"
```

---

### Task 8: Live Stream WebSocket (Simplified)

**Files:**
- Rewrite: `backend/app/routers/live_stream.py`

The current file is 785 lines. The new version is much simpler — it just reads from track fusion and broadcasts.

**Step 1: Rewrite live_stream.py**

```python
# backend/app/routers/live_stream.py
"""
Live Stream WebSocket — Broadcasts fused tracks to mobile clients.

Faculty connects to /ws/stream/{schedule_id} and receives:
- fused_tracks at 30 FPS (bbox + identity for overlay)
- heartbeat every 5 seconds

All detection/recognition logic is in separate workers.
This router just reads from TrackFusionEngine and broadcasts.
"""
import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import SessionLocal
from app.repositories.schedule_repository import ScheduleRepository
from app.services.track_fusion_service import get_track_fusion_engine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/stream/{schedule_id}")
async def stream_websocket(websocket: WebSocket, schedule_id: str):
    """Stream fused tracks for a schedule's room."""
    await websocket.accept()

    # Resolve room_id from schedule
    db = SessionLocal()
    try:
        schedule_repo = ScheduleRepository(db)
        schedule = schedule_repo.get_by_id(schedule_id)
        if not schedule or not schedule.room_id:
            await websocket.send_text(
                json.dumps({"type": "error", "message": "Schedule or room not found"})
            )
            await websocket.close()
            return
        room_id = str(schedule.room_id)
    finally:
        db.close()

    # Send connection info
    await websocket.send_text(
        json.dumps(
            {
                "type": "connected",
                "mode": "webrtc",
                "room_id": room_id,
                "schedule_id": schedule_id,
            }
        )
    )

    engine = get_track_fusion_engine()
    target_interval = 1.0 / 30.0  # 30 FPS
    last_heartbeat = time.time()

    try:
        while True:
            t_start = time.time()

            # Get current fused tracks
            tracks = engine.get_tracks(room_id)

            # Send fused tracks
            msg = {
                "type": "fused_tracks",
                "room_id": room_id,
                "ts": int(time.time() * 1000),
                "tracks": tracks,
            }
            await websocket.send_text(json.dumps(msg))

            # Heartbeat every 5 seconds
            if time.time() - last_heartbeat >= 5.0:
                await websocket.send_text(json.dumps({"type": "heartbeat"}))
                last_heartbeat = time.time()

            # Rate limit to 30 FPS
            elapsed = time.time() - t_start
            sleep_time = max(0, target_interval - elapsed)
            await asyncio.sleep(sleep_time)

    except WebSocketDisconnect:
        logger.info(f"[live-stream] Client disconnected from {schedule_id}")
    except Exception as e:
        logger.error(f"[live-stream] Error: {e}", exc_info=True)
```

**Step 2: Commit**

```bash
git add backend/app/routers/live_stream.py
git commit -m "feat: simplify live stream WebSocket — reads from track fusion engine"
```

---

### Task 9: Attendance WebSocket Broadcaster

**Files:**
- Rewrite: `backend/app/routers/websocket.py`

**Step 1: Rewrite websocket.py with multi-channel broadcasting**

```python
# backend/app/routers/websocket.py
"""
WebSocket Broadcaster — Multi-channel real-time delivery.

Channels:
- /ws/attendance/{schedule_id}  — Live attendance updates
- /ws/alerts/{user_id}          — Early-leave alerts, notifications
- /ws/health                    — System health metrics
"""
import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.stream_bus import (
    STREAM_ALERTS,
    STREAM_ATTENDANCE,
    get_stream_bus,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class BroadcastManager:
    """Manages WebSocket connections and broadcasts from Redis Streams."""

    def __init__(self):
        # schedule_id -> set of WebSocket connections
        self.attendance_clients: dict[str, set[WebSocket]] = {}
        # user_id -> set of WebSocket connections
        self.alert_clients: dict[str, set[WebSocket]] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start consuming Redis Streams and broadcasting to connected clients."""
        self._running = True
        self._task = asyncio.create_task(self._broadcast_loop())
        logger.info("[broadcaster] Started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    # ── Connection management ─────────────────────────────────

    def add_attendance_client(self, schedule_id: str, ws: WebSocket):
        self.attendance_clients.setdefault(schedule_id, set()).add(ws)

    def remove_attendance_client(self, schedule_id: str, ws: WebSocket):
        if schedule_id in self.attendance_clients:
            self.attendance_clients[schedule_id].discard(ws)

    def add_alert_client(self, user_id: str, ws: WebSocket):
        self.alert_clients.setdefault(user_id, set()).add(ws)

    def remove_alert_client(self, user_id: str, ws: WebSocket):
        if user_id in self.alert_clients:
            self.alert_clients[user_id].discard(ws)

    # ── Broadcasting ──────────────────────────────────────────

    async def _broadcast_loop(self):
        bus = await get_stream_bus()
        group = "broadcaster"

        # We dynamically discover attendance streams
        await bus.ensure_group(STREAM_ALERTS, group)

        while self._running:
            try:
                # Discover attendance streams for active schedules
                r = bus.redis
                streams = {STREAM_ALERTS: ">"}
                async for key in r.scan_iter(match=b"stream:attendance:*"):
                    key_str = key.decode() if isinstance(key, bytes) else key
                    await bus.ensure_group(key_str, group)
                    streams[key_str] = ">"

                messages = await bus.consume_multiple(
                    streams=streams,
                    group=group,
                    consumer="broadcaster-1",
                    count=20,
                    block=500,
                )

                for stream, msg_id, data in messages:
                    if "attendance" in stream:
                        # Extract schedule_id from stream name
                        sid = stream.replace("stream:attendance:", "")
                        await self._send_to_attendance_clients(sid, data)
                    elif "alerts" in stream:
                        await self._send_alert(data)
                    await bus.ack(stream, group, msg_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[broadcaster] Error: {e}", exc_info=True)
                await asyncio.sleep(0.5)

    async def _send_to_attendance_clients(self, schedule_id: str, data: dict):
        clients = self.attendance_clients.get(schedule_id, set())
        msg = json.dumps({"type": "attendance_update", **data})
        dead = set()
        for ws in clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        clients -= dead

    async def _send_alert(self, data: dict):
        # Alerts go to specific users (faculty for the schedule, and the student)
        user_ids = data.get("notify_user_ids", [])
        msg = json.dumps({"type": "alert", **data})
        for uid in user_ids:
            clients = self.alert_clients.get(uid, set())
            dead = set()
            for ws in clients:
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.add(ws)
            clients -= dead


# Singleton
_manager: BroadcastManager | None = None


def get_broadcast_manager() -> BroadcastManager:
    global _manager
    if _manager is None:
        _manager = BroadcastManager()
    return _manager


# ── Endpoints ─────────────────────────────────────────────────


@router.websocket("/ws/attendance/{schedule_id}")
async def attendance_websocket(websocket: WebSocket, schedule_id: str):
    await websocket.accept()
    manager = get_broadcast_manager()
    manager.add_attendance_client(schedule_id, websocket)
    logger.info(f"[ws] Attendance client connected for {schedule_id}")

    try:
        while True:
            # Keep connection alive, handle pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove_attendance_client(schedule_id, websocket)


@router.websocket("/ws/alerts/{user_id}")
async def alerts_websocket(websocket: WebSocket, user_id: str):
    await websocket.accept()
    manager = get_broadcast_manager()
    manager.add_alert_client(user_id, websocket)
    logger.info(f"[ws] Alert client connected for {user_id}")

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove_alert_client(user_id, websocket)
```

**Step 2: Commit**

```bash
git add backend/app/routers/websocket.py
git commit -m "feat: rewrite WebSocket broadcaster with multi-channel Redis Streams consumption"
```

---

## Phase 4: Presence Engine & Session Automation

### Task 10: Presence Engine (Redis Streams)

**Files:**
- Rewrite: `backend/app/services/presence_service.py`

**Step 1: Rewrite presence service**

The presence engine runs inside the API gateway. Every 60 seconds, it queries the track fusion engine for identified users, compares against enrolled students, updates attendance, and publishes events.

Key logic to preserve from existing code:
- 60-second scan interval
- 3 consecutive misses → early leave
- Grace period (15 min)
- Presence score calculation

Rewrite to use Redis Streams for output (attendance updates, alerts) instead of direct WebSocket calls. Read identified users from `TrackFusionEngine.get_identified_users(room_id)`.

This file is large. The core structure:

```python
# backend/app/services/presence_service.py
# Key methods:
# - start_session(schedule_id) — begin tracking
# - end_session(schedule_id) — finalize
# - run_scan_cycle() — called every 60s by APScheduler
# - _scan_room(session) — check who's present
# - _check_early_leave(session, student_id) — 3-miss threshold
# - _publish_attendance_update(session) — Redis stream
# - _publish_alert(session, student, severity) — Redis stream
```

The implementation should follow the existing pattern in `presence_service.py` but replace direct WebSocket calls with `bus.publish_attendance()` and `bus.publish_alert()`, and read detections from `get_track_fusion_engine().get_identified_users(room_id)` instead of `recognition_service.get_detections()`.

**Step 2: Commit**

```bash
git add backend/app/services/presence_service.py
git commit -m "feat: rewrite presence engine with Redis Streams output"
```

---

### Task 11: Session Scheduler (Auto-Lifecycle)

**Files:**
- Rewrite: `backend/app/services/session_scheduler.py`

The session scheduler auto-starts and auto-ends attendance sessions based on the schedules table. It runs as an APScheduler job every 60 seconds inside the API gateway.

Preserve existing logic but ensure it integrates with the rewritten presence service.

**Step 1: Commit after rewrite**

```bash
git add backend/app/services/session_scheduler.py
git commit -m "feat: rewrite session scheduler for auto-lifecycle management"
```

---

### Task 12: API Gateway main.py (Role-Based Startup)

**Files:**
- Rewrite: `backend/app/main.py`

**Step 1: Rewrite main.py**

The key change: startup behavior depends on `SERVICE_ROLE` env var.

- `api-gateway`: Start FastAPI + TrackFusion + Presence Engine + WebSocket Broadcaster + APScheduler
- `detection-worker`: Run DetectionWorker (handled by `__main__` in worker file)
- `recognition-worker`: Run RecognitionWorker (handled by `__main__` in worker file)
- `all`: Start everything (for local development)

```python
# In main.py startup event:
@app.on_event("startup")
async def startup():
    # Always: DB check, Redis, FAISS load
    await check_db_connection()
    await get_redis()

    role = settings.SERVICE_ROLE

    if role in ("api-gateway", "all"):
        # Load models for face registration endpoint
        from app.services.ml.insightface_model import get_model
        get_model()

        # Load FAISS
        from app.services.ml.faiss_manager import get_faiss_manager
        get_faiss_manager()

        # Start Track Fusion Engine (background consumer)
        from app.services.track_fusion_service import get_track_fusion_engine
        engine = get_track_fusion_engine()
        await engine.start()

        # Start WebSocket Broadcaster
        from app.routers.websocket import get_broadcast_manager
        broadcaster = get_broadcast_manager()
        await broadcaster.start()

        # Start mediamtx
        from app.services.mediamtx_service import start_mediamtx
        await start_mediamtx()

        # Start APScheduler (presence scans, session management)
        scheduler.start()
        # ... add jobs
```

Remove references to deleted services (HLS, compositor, local_camera, batch_processor, edge_relay).
Remove the HLS router include.

**Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: rewrite main.py with role-based startup for multi-container deployment"
```

---

## Phase 5: Edge Gateway — RPi Camera Gateway for Reolink

### Task 13: RPi Camera Gateway (Complete Rewrite)

**Files:**
- Rewrite: `edge/app/config.py`
- Rewrite: `edge/app/main.py`
- Create: `edge/app/frame_sampler.py`
- Rewrite: `edge/app/stream_relay.py`
- Rewrite: `edge/app/camera.py`
- Delete: `edge/app/detector.py`, `edge/app/processor.py`, `edge/app/sender.py`,
          `edge/app/centroid_tracker.py`, `edge/app/smart_sampler.py`
- Update: `edge/requirements.txt`

**Step 1: Rewrite edge config**

```python
# edge/app/config.py
"""RPi Camera Gateway configuration."""
import os

# Reolink P340 RTSP URLs
CAMERA_IP = os.getenv("CAMERA_IP", "192.168.1.100")
CAMERA_USER = os.getenv("CAMERA_USER", "admin")
CAMERA_PASS = os.getenv("CAMERA_PASS", "password")
RTSP_MAIN = f"rtsp://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}:554/h264Preview_01_main"
RTSP_SUB = f"rtsp://{CAMERA_USER}:{CAMERA_PASS}@{CAMERA_IP}:554/h264Preview_01_sub"

# VPS connection
VPS_HOST = os.getenv("VPS_HOST", "167.71.217.44")
VPS_WS_URL = f"ws://{VPS_HOST}/api/v1/ws/edge"
VPS_RTSP_URL = f"rtsp://{VPS_HOST}:8554"
EDGE_API_KEY = os.getenv("EDGE_API_KEY", "edge-secret-key-change-in-production")
ROOM_ID = os.getenv("ROOM_ID", "room-1")

# Frame sampling
SAMPLE_FPS = float(os.getenv("SAMPLE_FPS", "3.0"))  # 2GB RPi: use 2.0
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "85"))

# Offline queue
QUEUE_MAXLEN = 100
QUEUE_TTL_SECONDS = 120
RECONNECT_MAX_DELAY = 30
```

**Step 2: Create frame sampler**

```python
# edge/app/frame_sampler.py
"""
Frame Sampler — Captures frames from Reolink main stream, encodes as JPEG,
sends to VPS via WebSocket. Ultra-lightweight, no ML.
"""
import base64
import json
import logging
import time
from collections import deque
from datetime import datetime

import cv2

from app.config import (
    JPEG_QUALITY,
    QUEUE_MAXLEN,
    QUEUE_TTL_SECONDS,
    ROOM_ID,
    RTSP_MAIN,
    SAMPLE_FPS,
)

logger = logging.getLogger(__name__)


class FrameSampler:
    """Samples frames from Reolink main stream at configured FPS."""

    def __init__(self):
        self.cap = None
        self.running = False
        self.offline_queue = deque(maxlen=QUEUE_MAXLEN)
        self._frame_interval = 1.0 / SAMPLE_FPS

    def start(self):
        """Open RTSP connection to Reolink main stream."""
        logger.info(f"Opening RTSP main stream: {RTSP_MAIN}")
        self.cap = cv2.VideoCapture(RTSP_MAIN, cv2.CAP_FFMPEG)
        # Set buffer size to minimum for lowest latency
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open RTSP: {RTSP_MAIN}")
        self.running = True
        logger.info("Main stream opened successfully")

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()

    def sample_frame(self) -> dict | None:
        """Capture one frame, encode as JPEG, return as message dict."""
        if not self.cap or not self.cap.isOpened():
            return None

        ret, frame = self.cap.read()
        if not ret:
            logger.warning("Failed to read frame from main stream")
            return None

        h, w = frame.shape[:2]

        # Encode as JPEG
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        _, jpeg_bytes = cv2.imencode(".jpg", frame, encode_params)
        frame_b64 = base64.b64encode(jpeg_bytes.tobytes()).decode("ascii")

        return {
            "type": "frame",
            "room_id": ROOM_ID,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "frame_b64": frame_b64,
            "frame_width": w,
            "frame_height": h,
            "source": "reolink_p340",
        }

    def queue_frame(self, frame_msg: dict):
        """Add frame to offline queue (drops oldest if full)."""
        frame_msg["queued_at"] = time.time()
        self.offline_queue.append(frame_msg)

    def drain_queue(self) -> list[dict]:
        """Get all queued frames that haven't expired."""
        now = time.time()
        valid = []
        while self.offline_queue:
            msg = self.offline_queue.popleft()
            if now - msg.get("queued_at", 0) < QUEUE_TTL_SECONDS:
                valid.append(msg)
        return valid
```

**Step 3: Rewrite stream relay**

```python
# edge/app/stream_relay.py
"""
Stream Relay — FFmpeg RTSP sub-stream relay to VPS mediamtx.
Remux only (no transcode), minimal CPU usage.
"""
import logging
import subprocess
import threading

from app.config import ROOM_ID, RTSP_SUB, VPS_RTSP_URL

logger = logging.getLogger(__name__)


class StreamRelay:
    """Relay Reolink sub-stream to VPS mediamtx via FFmpeg."""

    def __init__(self):
        self.process = None
        self._thread = None

    def start(self):
        """Start FFmpeg RTSP relay in a background thread."""
        target_url = f"{VPS_RTSP_URL}/{ROOM_ID}"
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-rtsp_transport", "tcp",
            "-i", RTSP_SUB,
            "-c", "copy",  # No transcode — remux only
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            target_url,
        ]
        logger.info(f"Starting RTSP relay: {RTSP_SUB} → {target_url}")
        self._thread = threading.Thread(target=self._run, args=(cmd,), daemon=True)
        self._thread.start()

    def _run(self, cmd):
        while True:
            try:
                self.process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                logger.info("FFmpeg relay started")
                self.process.wait()
                logger.warning("FFmpeg relay exited, restarting in 5s...")
            except Exception as e:
                logger.error(f"FFmpeg relay error: {e}")
            import time
            time.sleep(5)

    def stop(self):
        if self.process:
            self.process.terminate()
```

**Step 4: Rewrite main.py (gateway entry point)**

```python
# edge/app/main.py
"""
RPi Camera Gateway — Ultra-lightweight entry point.
1. Start FFmpeg sub-stream relay to VPS mediamtx
2. Sample main stream at 2-3 FPS, send JPEG frames to VPS via WebSocket
3. Handle offline queuing and reconnection
"""
import asyncio
import json
import logging
import time

import websockets

from app.config import EDGE_API_KEY, RECONNECT_MAX_DELAY, ROOM_ID, VPS_WS_URL
from app.frame_sampler import FrameSampler
from app.stream_relay import StreamRelay

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


async def run_gateway():
    """Main gateway loop."""
    relay = StreamRelay()
    sampler = FrameSampler()

    # Start sub-stream relay (FFmpeg background thread)
    relay.start()

    # Start main-stream sampler
    sampler.start()

    reconnect_delay = 1
    ws_url = f"{VPS_WS_URL}/{ROOM_ID}?key={EDGE_API_KEY}"

    while True:
        try:
            logger.info(f"Connecting to VPS: {ws_url}")
            async with websockets.connect(ws_url, ping_interval=10) as ws:
                logger.info("Connected to VPS WebSocket")
                reconnect_delay = 1  # Reset on successful connect

                # Drain offline queue first
                queued = sampler.drain_queue()
                for msg in queued:
                    msg.pop("queued_at", None)
                    await ws.send(json.dumps(msg))
                if queued:
                    logger.info(f"Sent {len(queued)} queued frames")

                # Main sampling loop
                heartbeat_interval = 10.0
                last_heartbeat = time.time()
                frame_interval = 1.0 / sampler._frame_interval

                while True:
                    t_start = time.time()

                    # Sample and send frame
                    frame_msg = sampler.sample_frame()
                    if frame_msg:
                        await ws.send(json.dumps(frame_msg))

                    # Periodic heartbeat
                    if time.time() - last_heartbeat >= heartbeat_interval:
                        import psutil
                        heartbeat = {
                            "type": "heartbeat",
                            "room_id": ROOM_ID,
                            "camera_status": "connected",
                            "cpu_percent": psutil.cpu_percent(),
                            "ram_percent": psutil.virtual_memory().percent,
                            "uptime_seconds": int(time.time() - t_start),
                        }
                        await ws.send(json.dumps(heartbeat))
                        last_heartbeat = time.time()

                    # Rate limit
                    elapsed = time.time() - t_start
                    sleep_time = max(0, sampler._frame_interval - elapsed)
                    await asyncio.sleep(sleep_time)

        except (websockets.ConnectionClosed, OSError, ConnectionRefusedError) as e:
            logger.warning(f"VPS connection lost: {e}. Reconnecting in {reconnect_delay}s...")

            # Queue frames while disconnected (sample a few)
            for _ in range(3):
                frame_msg = sampler.sample_frame()
                if frame_msg:
                    sampler.queue_frame(frame_msg)
                await asyncio.sleep(sampler._frame_interval)

            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, RECONNECT_MAX_DELAY)

        except Exception as e:
            logger.error(f"Gateway error: {e}", exc_info=True)
            await asyncio.sleep(5)


def main():
    asyncio.run(run_gateway())


if __name__ == "__main__":
    main()
```

**Step 5: Update edge requirements.txt**

```
opencv-python-headless==4.9.0.80
websockets>=12.0
psutil>=5.9
```

No MediaPipe, no ML libraries. Lightweight.

**Step 6: Commit**

```bash
git add edge/
git commit -m "feat: rewrite RPi as ultra-lightweight Reolink camera gateway"
```

---

## Phase 6: Deployment — Docker Compose Multi-Container

### Task 14: Docker Compose Production Config

**Files:**
- Rewrite: `deploy/docker-compose.prod.yml`

**Step 1: Write multi-container Docker Compose**

Use the Docker Compose config from Section 13 of the design doc. Key changes from current:
- Single `backend` container → 3 containers: `api-gateway`, `detection-worker`, `recognition-worker`
- Each uses the same Docker image but different `command`
- Add resource limits
- Add health checks per container

**Step 2: Update nginx.conf**

Ensure WebSocket upgrade headers for all `/ws/` paths:
- `/api/v1/ws/edge/` — Edge frame ingestion
- `/api/v1/ws/stream/` — Live stream
- `/api/v1/ws/attendance/` — Attendance updates
- `/api/v1/ws/alerts/` — Alerts

**Step 3: Commit**

```bash
git add deploy/
git commit -m "feat: multi-container Docker Compose with API gateway + workers"
```

---

### Task 15: Health Check Endpoint

**Files:**
- Create: `backend/app/routers/health.py` (or add to existing)

**Step 1: Create deep health check**

Implement `GET /api/v1/health` that checks:
- Database connectivity + latency
- Redis connectivity + latency + active streams
- FAISS index status (vector count)
- mediamtx status (active paths)
- Edge device status (from `edge_ws.get_edge_devices()`)
- Worker status (from `stream:metrics` last 30s)

Use the JSON format from design doc Section 12.

**Step 2: Commit**

```bash
git add backend/app/routers/health.py
git commit -m "feat: add deep health check endpoint for all system components"
```

---

## Phase 7: Mobile App Updates

### Task 16: Update useDetectionWebSocket Hook

**Files:**
- Modify: `mobile/src/hooks/useDetectionWebSocket.ts`

**Step 1: Update to match new message format**

The new format from track fusion is slightly different. Key changes:
- Track identity is nested: `track.identity.{user_id, name, student_id, similarity}`
- Bounding boxes are normalized (0-1), not pixel coordinates
- `track.state` is `"tentative"` | `"confirmed"` (no `"lost"` sent)
- Timestamp is `ts` (unix ms), not ISO string

Update the TypeScript interfaces and parsing logic to match.

**Step 2: Commit**

```bash
git add mobile/src/hooks/useDetectionWebSocket.ts
git commit -m "feat: update detection WebSocket hook for new track fusion format"
```

---

### Task 17: Create useAttendanceWebSocket Hook

**Files:**
- Create: `mobile/src/hooks/useAttendanceWebSocket.ts`

**Step 1: Create the hook**

```typescript
// mobile/src/hooks/useAttendanceWebSocket.ts
// Connects to /ws/attendance/{scheduleId}
// Returns: { summary, students, isConnected }
// Updates live when attendance changes
```

This hook powers the faculty live attendance dashboard and student status updates.

**Step 2: Commit**

```bash
git add mobile/src/hooks/useAttendanceWebSocket.ts
git commit -m "feat: add attendance WebSocket hook for live dashboard updates"
```

---

## Phase 8: Integration Testing & Polish

### Task 18: End-to-End Test (Local Dev)

**Step 1: Run all containers locally**

```bash
cd deploy
docker compose -f docker-compose.prod.yml up --build
```

**Step 2: Test edge → detection → recognition flow**

- Send a test frame via WebSocket to `/ws/edge/test-room`
- Verify it appears in `stream:frames:test-room`
- Verify detection worker processes it and publishes to `stream:detections:test-room`
- Verify recognition worker processes face crops

**Step 3: Test live stream flow**

- Connect to `/ws/stream/{schedule_id}` via WebSocket
- Verify fused tracks are received at ~30 FPS

**Step 4: Test presence engine**

- Create a test schedule in the database
- Verify auto-session start/stop works
- Verify attendance updates appear on `/ws/attendance/{schedule_id}`

---

### Task 19: Deploy to VPS

**Step 1: Deploy**

```bash
bash deploy/deploy.sh
```

**Step 2: Verify**

- Check `GET /api/v1/health` returns all components healthy
- Check Dozzle logs for all 3 containers running
- Connect RPi to VPS and verify frame ingestion works

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: deployment adjustments for production VPS"
```

---

## Task Dependency Graph

```
Phase 1 (Foundation)
  Task 1: Redis Streams bus
  Task 2: Config updates
  Task 3: Worker base class
      │
      ▼
Phase 2 (Workers) — can be parallel
  Task 4: Detection Worker ─────────┐
  Task 5: Recognition Worker ───────┤
      │                             │
      ▼                             │
Phase 3 (API Gateway)               │
  Task 6: Edge WS ingestion         │
  Task 7: Track Fusion Engine ◄─────┘
  Task 8: Live Stream WS
  Task 9: Attendance Broadcaster
      │
      ▼
Phase 4 (Presence)
  Task 10: Presence Engine
  Task 11: Session Scheduler
  Task 12: main.py rewrite
      │
      ▼
Phase 5 (Edge) — independent
  Task 13: RPi Camera Gateway
      │
      ▼
Phase 6 (Deployment)
  Task 14: Docker Compose
  Task 15: Health check
      │
      ▼
Phase 7 (Mobile)
  Task 16: Detection WS hook update
  Task 17: Attendance WS hook
      │
      ▼
Phase 8 (Integration)
  Task 18: E2E test
  Task 19: Deploy to VPS
```

---

## Sprint Execution Order

For a sprint with multiple developers or sequential solo work:

| Priority | Task | Est. Time | Blocks |
|----------|------|-----------|--------|
| P0 | Task 1: Redis Streams bus | 30 min | Everything |
| P0 | Task 2: Config updates | 15 min | Workers |
| P0 | Task 3: Worker base class | 30 min | Workers |
| P1 | Task 4: Detection Worker | 1.5 hr | Track Fusion |
| P1 | Task 5: Recognition Worker | 1 hr | Track Fusion |
| P1 | Task 6: Edge WS ingestion | 30 min | Workers |
| P1 | Task 7: Track Fusion Engine | 1.5 hr | Live Stream |
| P1 | Task 8: Live Stream WS | 30 min | Mobile |
| P1 | Task 9: Attendance Broadcaster | 45 min | Mobile |
| P2 | Task 10: Presence Engine | 1.5 hr | Alerts |
| P2 | Task 11: Session Scheduler | 30 min | Automation |
| P2 | Task 12: main.py rewrite | 1 hr | Deployment |
| P2 | Task 13: RPi Camera Gateway | 1.5 hr | E2E test |
| P3 | Task 14: Docker Compose | 45 min | Deployment |
| P3 | Task 15: Health check | 30 min | Monitoring |
| P3 | Task 16: Detection WS hook | 30 min | Live feed |
| P3 | Task 17: Attendance WS hook | 30 min | Dashboard |
| P4 | Task 18: E2E test | 1 hr | Deploy |
| P4 | Task 19: Deploy to VPS | 30 min | Demo |
| **Total** | | **~13 hours** | |
