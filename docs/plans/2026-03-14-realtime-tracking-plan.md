# Real-Time Face Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split face detection (RPi, real-time) from recognition (VPS, async) so bounding boxes track faces at camera FPS with <50ms latency.

**Architecture:** RPi pushes MediaPipe bounding boxes via WebSocket to VPS, which relays them to mobile clients. VPS recognition service runs at 2 FPS and sends identity mappings (track_id → user_id) separately. Mobile merges both streams: boxes render instantly, names appear when identity resolves.

**Tech Stack:** Python WebSocket (websockets library on RPi), FastAPI WebSocket (backend), React Native (mobile), mediamtx (WebRTC video)

---

### Task 1: Backend — EdgeRelayService singleton

**Files:**
- Create: `backend/app/services/edge_relay_service.py`

**Step 1: Create the EdgeRelayManager class**

This is the core relay that receives edge bounding boxes and fans them out to mobile WebSocket clients.

```python
"""
Edge Relay Service

Receives real-time bounding box data from RPi edge devices via WebSocket
and fans out to connected mobile clients. Acts as a relay between the
edge device (which is behind NAT) and mobile viewers.
"""

import asyncio
import time
from dataclasses import dataclass, field

from starlette.websockets import WebSocket

from app.config import settings

import logging

logger = logging.getLogger(__name__)


@dataclass
class RoomRelay:
    """Per-room state for edge relay."""

    room_id: str
    edge_ws: WebSocket | None = None
    mobile_clients: set[WebSocket] = field(default_factory=set)
    last_detections: dict | None = None
    last_update_time: float = 0.0
    identity_cache: dict[str, dict] = field(default_factory=dict)
    # identity_cache maps track_id -> {"user_id": ..., "name": ..., "student_id": ..., "confidence": ...}


class EdgeRelayManager:
    """
    Singleton that manages edge-to-mobile bounding box relay.

    - RPi connects via /api/v1/edge/ws?room_id=XXX
    - Mobile clients register when they connect to /api/v1/stream/{schedule_id}
    - Edge detections are forwarded to all registered mobile clients
    - Identity updates from recognition service are merged and forwarded
    """

    def __init__(self) -> None:
        self._rooms: dict[str, RoomRelay] = {}
        self._lock = asyncio.Lock()

    async def register_edge(self, room_id: str, ws: WebSocket) -> None:
        """Register an edge device WebSocket for a room."""
        async with self._lock:
            relay = self._rooms.get(room_id)
            if relay is None:
                relay = RoomRelay(room_id=room_id)
                self._rooms[room_id] = relay
            relay.edge_ws = ws
        logger.info(f"Edge device registered for room {room_id}")

    async def unregister_edge(self, room_id: str) -> None:
        """Unregister an edge device from a room."""
        async with self._lock:
            relay = self._rooms.get(room_id)
            if relay:
                relay.edge_ws = None
                if not relay.mobile_clients:
                    del self._rooms[room_id]
        logger.info(f"Edge device unregistered from room {room_id}")

    async def register_mobile(self, room_id: str, ws: WebSocket) -> None:
        """Register a mobile viewer WebSocket for a room."""
        async with self._lock:
            relay = self._rooms.get(room_id)
            if relay is None:
                relay = RoomRelay(room_id=room_id)
                self._rooms[room_id] = relay
            relay.mobile_clients.add(ws)
        logger.info(f"Mobile client registered for room {room_id} (total: {len(self._rooms.get(room_id, RoomRelay(room_id=room_id)).mobile_clients)})")

    async def unregister_mobile(self, room_id: str, ws: WebSocket) -> None:
        """Unregister a mobile viewer from a room."""
        async with self._lock:
            relay = self._rooms.get(room_id)
            if relay:
                relay.mobile_clients.discard(ws)
                if not relay.mobile_clients and relay.edge_ws is None:
                    del self._rooms[room_id]

    async def relay_edge_detections(self, room_id: str, message: dict) -> None:
        """
        Receive edge detections and fan out to mobile clients.

        Merges cached identity info into detections before forwarding.

        Args:
            room_id: Room identifier
            message: Raw edge detection message with structure:
                {
                    "type": "edge_detections",
                    "room_id": str,
                    "timestamp": str,
                    "frame_width": int,
                    "frame_height": int,
                    "detections": [
                        {"bbox": [x, y, w, h], "confidence": float, "track_id": str},
                        ...
                    ]
                }
        """
        async with self._lock:
            relay = self._rooms.get(room_id)
            if not relay or not relay.mobile_clients:
                return

            # Merge cached identity into detections
            detections = message.get("detections", [])
            for det in detections:
                track_id = det.get("track_id")
                if track_id and track_id in relay.identity_cache:
                    identity = relay.identity_cache[track_id]
                    det["user_id"] = identity.get("user_id")
                    det["name"] = identity.get("name")
                    det["student_id"] = identity.get("student_id")
                    det["similarity"] = identity.get("confidence")

            relay.last_detections = message
            relay.last_update_time = time.time()
            clients = set(relay.mobile_clients)

        # Send outside lock to avoid holding it during I/O
        dead_clients: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_json(message)
            except Exception:
                dead_clients.append(client)

        # Clean up dead clients
        if dead_clients:
            async with self._lock:
                relay = self._rooms.get(room_id)
                if relay:
                    for dc in dead_clients:
                        relay.mobile_clients.discard(dc)

    async def push_identity_update(self, room_id: str, mappings: list[dict]) -> None:
        """
        Receive identity resolution from recognition service and forward to mobile.

        Args:
            room_id: Room identifier
            mappings: List of identity mappings:
                [
                    {
                        "track_id": str,
                        "user_id": str,
                        "name": str,
                        "student_id": str,
                        "confidence": float
                    },
                    ...
                ]
        """
        async with self._lock:
            relay = self._rooms.get(room_id)
            if not relay:
                return

            # Update identity cache
            for mapping in mappings:
                track_id = mapping.get("track_id")
                if track_id:
                    relay.identity_cache[track_id] = mapping

            # Prune stale identities (keep last 100)
            if len(relay.identity_cache) > 100:
                # Keep only the most recent entries
                keys = list(relay.identity_cache.keys())
                for key in keys[:-100]:
                    del relay.identity_cache[key]

            clients = set(relay.mobile_clients)

        # Forward identity update to mobile clients
        identity_msg = {
            "type": "identity_update",
            "mappings": mappings,
        }
        dead_clients: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_json(identity_msg)
            except Exception:
                dead_clients.append(client)

        if dead_clients:
            async with self._lock:
                relay = self._rooms.get(room_id)
                if relay:
                    for dc in dead_clients:
                        relay.mobile_clients.discard(dc)

    def get_room_status(self, room_id: str) -> dict:
        """Get relay status for a room."""
        relay = self._rooms.get(room_id)
        if not relay:
            return {"active": False}
        return {
            "active": True,
            "edge_connected": relay.edge_ws is not None,
            "mobile_viewers": len(relay.mobile_clients),
            "identity_cache_size": len(relay.identity_cache),
            "last_update": relay.last_update_time,
        }


# Module-level singleton
edge_relay_manager = EdgeRelayManager()
```

**Step 2: Verify file was created correctly**

Run: `cd /Users/cjjutba/Projects/iams && python -c "from backend.app.services.edge_relay_service import edge_relay_manager; print('OK')"`

**Step 3: Commit**

```bash
git add backend/app/services/edge_relay_service.py
git commit -m "feat: add EdgeRelayManager for edge-to-mobile bbox relay"
```

---

### Task 2: Backend — Edge WebSocket endpoint

**Files:**
- Create: `backend/app/routers/edge_ws.py`
- Modify: `backend/app/main.py` (register new router)

**Step 1: Create the edge WebSocket router**

```python
"""
Edge Device WebSocket Endpoint

RPi edge devices connect here to push real-time bounding box data.
The EdgeRelayManager fans out these detections to mobile clients.
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.services.edge_relay_service import edge_relay_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def edge_websocket(
    websocket: WebSocket,
    room_id: str = Query(..., description="Room UUID"),
):
    """
    WebSocket endpoint for RPi edge devices.

    The edge device sends detection messages:
    {
        "type": "edge_detections",
        "room_id": "uuid",
        "timestamp": "ISO",
        "frame_width": 896,
        "frame_height": 512,
        "detections": [
            {"bbox": [x, y, w, h], "confidence": 0.95, "track_id": "t-1"},
            ...
        ]
    }

    Server may send:
    {
        "type": "pong"
    }
    """
    await websocket.accept()
    logger.info(f"Edge device connecting for room {room_id}")

    await edge_relay_manager.register_edge(room_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "edge_detections":
                await edge_relay_manager.relay_edge_detections(room_id, data)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"Edge device disconnected from room {room_id}")
    except Exception as e:
        logger.error(f"Edge WebSocket error for room {room_id}: {e}")
    finally:
        await edge_relay_manager.unregister_edge(room_id)
```

**Step 2: Register the router in main.py**

In `backend/app/main.py`, add the import and router registration. Find the existing router registrations (around line 490-520) and add:

```python
from app.routers import edge_ws
```

And register it:

```python
app.include_router(edge_ws.router, prefix="/api/v1/edge", tags=["edge"])
```

**Step 3: Verify the endpoint is registered**

Run: `cd /Users/cjjutba/Projects/iams/backend && python -c "from app.main import app; routes = [r.path for r in app.routes]; print('/api/v1/edge/ws' in str(routes) or 'edge' in str(routes))"`

**Step 4: Commit**

```bash
git add backend/app/routers/edge_ws.py backend/app/main.py
git commit -m "feat: add /api/v1/edge/ws WebSocket endpoint for RPi bbox relay"
```

---

### Task 3: Backend — Integrate edge relay into live_stream router

**Files:**
- Modify: `backend/app/routers/live_stream.py`

**Step 1: Register mobile clients with EdgeRelayManager on connect**

In the `_webrtc_mode()` function (around line 400), after the `connected` message is sent, register the mobile WebSocket with the edge relay:

```python
from app.services.edge_relay_service import edge_relay_manager
```

After sending the `connected` message (around line 432), add:

```python
# Register with edge relay to receive real-time bounding boxes from RPi
await edge_relay_manager.register_mobile(room_id, websocket)
```

**Step 2: Update the detection polling loop to check for edge relay**

In the detection polling loop inside `_webrtc_mode()` (around lines 456-514), the existing logic polls `recognition_service.get_latest_detections()` and sends `type: "detections"` messages. We need to keep recognition running (at lower FPS) but change it to send `identity_update` messages instead, since the edge relay now handles real-time boxes.

Replace the detection polling section with logic that:
1. Checks recognition service for new identities (at 2 FPS cadence)
2. When new recognitions arrive, pushes identity updates via `edge_relay_manager.push_identity_update()`
3. Keeps the WebSocket alive with ping handling (edge relay handles sending boxes)

The modified loop should:
- Still poll recognition service but only for identity mapping
- When recognition finds a match, call `edge_relay_manager.push_identity_update(room_id, mappings)`
- Handle incoming ping/pong messages from mobile client
- **Remove** direct `detections` message sending (edge relay handles this now)

**Key change in the loop:**

```python
# Old: send detections directly to mobile
# New: push identity updates via relay

# Poll recognition for identity updates
result = recognition_service.get_latest_detections(room_id)
if result:
    dets_dicts, seq, det_w, det_h = result
    if seq != last_seq:
        last_seq = seq
        # Build identity mappings from recognized faces
        mappings = []
        for det in dets_dicts:
            if det.get("user_id"):
                # Need track_id to map identity to edge boxes
                # Use bbox center as approximate track_id match
                mappings.append({
                    "track_id": None,  # Will be matched by bbox proximity
                    "bbox": det.get("bbox"),
                    "user_id": det["user_id"],
                    "name": det.get("name", ""),
                    "student_id": det.get("student_id", ""),
                    "confidence": det.get("similarity", 0),
                })
        if mappings:
            await edge_relay_manager.push_identity_update(room_id, mappings)
```

**Step 3: Add cleanup on disconnect**

In the `finally` block of `_webrtc_mode()`, add:

```python
await edge_relay_manager.unregister_mobile(room_id, websocket)
```

Do the same for `_hls_mode()` if it exists as a fallback.

**Step 4: Commit**

```bash
git add backend/app/routers/live_stream.py
git commit -m "feat: integrate edge relay into live stream for real-time bbox forwarding"
```

---

### Task 4: Backend — Lower recognition FPS to 2

**Files:**
- Modify: `backend/app/config.py`

**Step 1: Change RECOGNITION_FPS default**

In `backend/app/config.py` (around line 135), change:

```python
# Old
RECOGNITION_FPS: float = float(os.getenv("RECOGNITION_FPS", "15"))

# New
RECOGNITION_FPS: float = float(os.getenv("RECOGNITION_FPS", "2"))
```

This reduces VPS CPU usage from ~80% to ~30% since recognition is now only for identity resolution, not bounding box generation.

**Step 2: Commit**

```bash
git add backend/app/config.py
git commit -m "perf: lower RECOGNITION_FPS to 2 (identity-only, edge handles boxes)"
```

---

### Task 5: Edge — Add WebSocket config

**Files:**
- Modify: `edge/app/config.py`

**Step 1: Add EDGE_WS_URL configuration**

In `edge/app/config.py`, in the Config class, add a new section for the edge WebSocket after the stream relay section (around line 100):

```python
# Edge WebSocket (real-time bbox push to VPS)
EDGE_WS_ENABLED: bool = os.getenv("EDGE_WS_ENABLED", "true").lower() in ("true", "1", "yes")
EDGE_WS_URL: str = os.getenv("EDGE_WS_URL", "")  # Derived from BACKEND_URL if empty
EDGE_WS_RECONNECT_DELAY: int = int(os.getenv("EDGE_WS_RECONNECT_DELAY", "3"))
```

Also add a property or method to derive the WebSocket URL from BACKEND_URL if not explicitly set:

```python
def get_edge_ws_url(self) -> str:
    """Get WebSocket URL for edge bbox relay. Derives from BACKEND_URL if not set."""
    if self.EDGE_WS_URL:
        return self.EDGE_WS_URL
    # Convert http://host to ws://host/api/v1/edge/ws
    base = self.BACKEND_URL.rstrip("/")
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
    return f"{ws_base}/api/v1/edge/ws"
```

**Step 2: Commit**

```bash
git add edge/app/config.py
git commit -m "feat: add EDGE_WS_URL config for real-time bbox push"
```

---

### Task 6: Edge — Create EdgeWebSocket client

**Files:**
- Create: `edge/app/edge_websocket.py`

**Step 1: Create the WebSocket client module**

This runs in a background thread, maintains a persistent WebSocket connection to the VPS, and provides a non-blocking `send_detections()` method.

```python
"""
Edge WebSocket Client — Real-Time Bounding Box Push

Maintains a persistent WebSocket connection to the VPS backend.
Sends bounding box data from MediaPipe detections in real-time.

Design:
- Runs in a background thread (non-blocking for scan loop)
- Auto-reconnects with exponential backoff on disconnect
- Uses a queue to decouple detection thread from WebSocket send
- Drops old messages if queue backs up (freshness > completeness)
"""

import json
import queue
import threading
import time
from datetime import datetime, timezone

from app.config import config, logger

# Try to import websocket-client (ws4py alternative)
try:
    import websocket
except ImportError:
    websocket = None
    logger.warning("websocket-client not installed — edge WebSocket disabled")


class EdgeWebSocketClient:
    """Persistent WebSocket client for pushing bounding boxes to VPS."""

    def __init__(self) -> None:
        self._ws: websocket.WebSocketApp | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._connected = threading.Event()
        self._send_queue: queue.Queue = queue.Queue(maxsize=30)
        self._room_id: str | None = None
        self._url: str = ""
        self._reconnect_delay: float = config.EDGE_WS_RECONNECT_DELAY

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    def start(self, room_id: str) -> bool:
        """Start the WebSocket client in a background thread."""
        if websocket is None:
            logger.error("websocket-client not installed, cannot start edge WS")
            return False

        if not config.EDGE_WS_ENABLED:
            logger.debug("Edge WebSocket disabled")
            return False

        self._room_id = room_id
        self._url = f"{config.get_edge_ws_url()}?room_id={room_id}"
        self._stop_event.clear()

        # Start sender thread
        self._thread = threading.Thread(
            target=self._run_loop,
            name="edge-ws",
            daemon=True,
        )
        self._thread.start()

        logger.info(f"Edge WebSocket started → {self._url}")
        return True

    def stop(self) -> None:
        """Stop the WebSocket client."""
        self._stop_event.set()
        self._connected.clear()

        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        logger.info("Edge WebSocket stopped")

    def send_detections(
        self,
        detections: list[dict],
        frame_width: int,
        frame_height: int,
    ) -> None:
        """
        Queue bounding box data for sending (non-blocking).

        Args:
            detections: List of detection dicts:
                [{"bbox": [x,y,w,h], "confidence": float, "track_id": str}, ...]
            frame_width: Source frame width
            frame_height: Source frame height
        """
        if not self._connected.is_set():
            return

        message = {
            "type": "edge_detections",
            "room_id": self._room_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frame_width": frame_width,
            "frame_height": frame_height,
            "detections": detections,
        }

        try:
            # Drop oldest if queue is full (freshness > completeness)
            if self._send_queue.full():
                try:
                    self._send_queue.get_nowait()
                except queue.Empty:
                    pass
            self._send_queue.put_nowait(json.dumps(message))
        except queue.Full:
            pass  # Drop silently

    def _run_loop(self) -> None:
        """Background thread: maintain WebSocket connection and send queued messages."""
        backoff = 1.0
        max_backoff = 30.0

        while not self._stop_event.is_set():
            try:
                self._connect_and_send()
            except Exception as e:
                logger.error(f"Edge WS error: {e}")

            if not self._stop_event.is_set():
                self._connected.clear()
                logger.info(f"Edge WS: reconnecting in {backoff:.0f}s...")
                self._stop_event.wait(backoff)
                backoff = min(backoff * 2, max_backoff)

    def _connect_and_send(self) -> None:
        """Connect to VPS and continuously send queued messages."""
        logger.info(f"Edge WS: connecting to {self._url}")

        ws = websocket.WebSocket()
        ws.settimeout(5)

        try:
            ws.connect(self._url)
        except Exception as e:
            logger.warning(f"Edge WS: connection failed: {e}")
            raise

        self._ws = ws
        self._connected.set()
        logger.info("Edge WS: connected")

        # Reset backoff on successful connection
        # (accessed via closure in _run_loop)

        try:
            while not self._stop_event.is_set():
                try:
                    # Get message with timeout so we can check stop_event
                    msg = self._send_queue.get(timeout=0.1)
                    ws.send(msg)
                except queue.Empty:
                    # Send ping to keep alive
                    try:
                        ws.ping()
                    except Exception:
                        break
                except websocket.WebSocketConnectionClosedException:
                    logger.warning("Edge WS: connection closed")
                    break
                except Exception as e:
                    logger.warning(f"Edge WS: send error: {e}")
                    break
        finally:
            self._connected.clear()
            try:
                ws.close()
            except Exception:
                pass

    def get_status(self) -> dict:
        return {
            "enabled": config.EDGE_WS_ENABLED,
            "connected": self.is_connected,
            "url": self._url,
            "queue_size": self._send_queue.qsize(),
        }


# Module-level singleton
edge_ws_client = EdgeWebSocketClient()
```

**Step 2: Add websocket-client to requirements.txt**

In `edge/requirements.txt`, add:

```
websocket-client>=1.6.0
```

**Step 3: Commit**

```bash
git add edge/app/edge_websocket.py edge/requirements.txt
git commit -m "feat: add EdgeWebSocketClient for real-time bbox push to VPS"
```

---

### Task 7: Edge — Integrate WebSocket into scan loop

**Files:**
- Modify: `edge/app/main.py`

**Step 1: Import and initialize the edge WebSocket client**

At the top of `edge/app/main.py`, add:

```python
from app.edge_websocket import edge_ws_client
```

In `EdgeDevice.__init__()` (around line 42), no changes needed — the singleton is ready.

**Step 2: Start edge WebSocket when session becomes active**

In `EdgeDevice._check_session()` (around line 166), where stream relay is started on session activation, also start the edge WebSocket:

```python
# Existing: stream_relay.start(self.room_id)
# Add after:
edge_ws_client.start(self.room_id)
```

**Step 3: Stop edge WebSocket when session ends**

In `_check_session()` where stream relay is stopped on session deactivation, add:

```python
edge_ws_client.stop()
```

Also in `shutdown()` (around line 137), add:

```python
edge_ws_client.stop()
```

**Step 4: Push detections after MediaPipe detection**

In `run_single_scan()` (around line 210), after MediaPipe detection produces `face_boxes` (list of FaceBox), push them to the WebSocket **before** processing crops:

```python
# After: face_boxes = detector.detect(frame)
# Add: Push raw bounding boxes to VPS via WebSocket
if face_boxes and edge_ws_client.is_connected:
    ws_detections = []
    for i, fb in enumerate(face_boxes):
        # Use smart_sampler track_id if available, else use index
        track_id = str(i)
        ws_detections.append({
            "bbox": fb.to_list(),
            "confidence": fb.confidence,
            "track_id": track_id,
        })
    edge_ws_client.send_detections(
        ws_detections,
        frame_width=frame.shape[1],
        frame_height=frame.shape[0],
    )
elif not face_boxes and edge_ws_client.is_connected:
    # Send empty detections so mobile clears boxes
    edge_ws_client.send_detections([], frame.shape[1], frame.shape[0])
```

**Step 5: Use SmartSampler track IDs for consistency**

If the smart sampler is enabled, the track IDs from the sampler should be used instead of simple indices. After the smart sampler update call (which returns matched track IDs), update the WebSocket detections to use those track IDs.

Find the smart sampler update call (around line 270):

```python
# After smart_sampler.update() returns faces_to_send, gone_track_ids
# The sampler's _tracks dict maps track_id -> TrackedFace
# Use this for the WebSocket push
if self.smart_sampler and face_boxes:
    # Build detection list with sampler-assigned track IDs
    ws_detections = []
    for det_bbox, face_data in zip(detections_for_sampler, face_data_list):
        # Match back to sampler tracks by bbox
        matched_track_id = None
        for tid, track in self.smart_sampler._tracks.items():
            if track.bbox == det_bbox:
                matched_track_id = str(tid)
                break
        ws_detections.append({
            "bbox": det_bbox,
            "confidence": face_data.confidence if face_data else 0.5,
            "track_id": matched_track_id or f"t-{hash(tuple(det_bbox)) % 10000}",
        })
    edge_ws_client.send_detections(
        ws_detections,
        frame_width=frame.shape[1],
        frame_height=frame.shape[0],
    )
```

**Step 6: Commit**

```bash
git add edge/app/main.py
git commit -m "feat: push MediaPipe bounding boxes via WebSocket after detection"
```

---

### Task 8: Mobile — Update useDetectionWebSocket for dual-channel messages

**Files:**
- Modify: `mobile/src/hooks/useDetectionWebSocket.ts`

**Step 1: Add new message types and identity cache**

Add new interfaces for the edge detection and identity update messages:

```typescript
interface EdgeDetectionsMessage {
  type: 'edge_detections';
  room_id: string;
  timestamp: string;
  frame_width: number;
  frame_height: number;
  detections: Array<{
    bbox: [number, number, number, number]; // [x, y, w, h]
    confidence: number;
    track_id: string;
    // These are merged by relay if identity is cached:
    user_id?: string;
    name?: string;
    student_id?: string;
    similarity?: number;
  }>;
}

interface IdentityUpdateMessage {
  type: 'identity_update';
  mappings: Array<{
    track_id?: string;
    bbox?: { x: number; y: number; width: number; height: number };
    user_id: string;
    name: string;
    student_id: string;
    confidence: number;
  }>;
}
```

**Step 2: Add identity cache ref**

```typescript
// Identity cache: maps track_id -> identity info
const identityCacheRef = useRef<Map<string, {
  user_id: string;
  name: string;
  student_id: string;
  confidence: number;
}>>(new Map());
```

**Step 3: Handle edge_detections messages (replace detections handler)**

When an `edge_detections` message arrives, convert to DetectionItem[] and apply immediately (no delay queue):

```typescript
if (message.type === 'edge_detections') {
  const edgeMsg = message as EdgeDetectionsMessage;

  // Update detection frame dimensions
  if (edgeMsg.frame_width && edgeMsg.frame_height) {
    setDetectionWidth(edgeMsg.frame_width);
    setDetectionHeight(edgeMsg.frame_height);
  }

  // Convert to DetectionItem format, merging cached identities
  const items: DetectionItem[] = (edgeMsg.detections || []).map((det) => {
    const cached = det.user_id
      ? { user_id: det.user_id, name: det.name, student_id: det.student_id, confidence: det.similarity }
      : identityCacheRef.current.get(det.track_id);

    return {
      bbox: {
        x: det.bbox[0],
        y: det.bbox[1],
        width: det.bbox[2],
        height: det.bbox[3],
      },
      confidence: det.confidence,
      user_id: cached?.user_id ?? null,
      student_id: cached?.student_id ?? null,
      name: cached?.name ?? null,
      similarity: cached?.confidence ?? null,
      // Pass track_id through for tracker
      track_id: det.track_id,
    } as DetectionItem & { track_id: string };
  });

  // Apply immediately — no delay queue needed (frame-aligned)
  setDetections(items);

  // Update studentMap from identified detections
  // ... (same logic as existing applyDetection studentMap update)
}
```

**Step 4: Handle identity_update messages**

```typescript
if (message.type === 'identity_update') {
  const idMsg = message as IdentityUpdateMessage;

  // Update identity cache
  for (const mapping of idMsg.mappings) {
    if (mapping.track_id) {
      identityCacheRef.current.set(mapping.track_id, {
        user_id: mapping.user_id,
        name: mapping.name,
        student_id: mapping.student_id,
        confidence: mapping.confidence,
      });
    }
  }

  // Cap cache size
  if (identityCacheRef.current.size > 200) {
    const keys = Array.from(identityCacheRef.current.keys());
    for (const key of keys.slice(0, keys.length - 200)) {
      identityCacheRef.current.delete(key);
    }
  }

  // Re-apply identities to current detections
  setDetections((prev) =>
    prev.map((det) => {
      const trackDet = det as DetectionItem & { track_id?: string };
      if (trackDet.track_id && !det.user_id) {
        const cached = identityCacheRef.current.get(trackDet.track_id);
        if (cached) {
          return {
            ...det,
            user_id: cached.user_id,
            name: cached.name,
            student_id: cached.student_id,
            similarity: cached.confidence,
          };
        }
      }
      return det;
    })
  );
}
```

**Step 5: Keep backward compatibility with `detections` type**

Keep the existing `detections` handler as a fallback for when edge relay is not active (non-WebRTC rooms, legacy mode, etc.). The delay queue can stay for HLS fallback but should be bypassed when `edge_detections` messages are arriving.

**Step 6: Remove the detection delay queue drain interval** (optional — can keep for fallback)

If edge detections are the primary path, the 50ms drain interval is no longer needed for WebRTC mode. Add a flag to skip it:

```typescript
const usingEdgeDetectionsRef = useRef(false);
// Set to true on first edge_detections message
// In drain interval: skip if usingEdgeDetectionsRef.current
```

**Step 7: Commit**

```bash
git add mobile/src/hooks/useDetectionWebSocket.ts
git commit -m "feat: handle edge_detections + identity_update messages for real-time tracking"
```

---

### Task 9: Mobile — Add track_id to DetectionItem type

**Files:**
- Modify: `mobile/src/components/video/DetectionOverlay.tsx`
- Modify: `mobile/src/hooks/useDetectionTracker.ts`

**Step 1: Extend DetectionItem with optional track_id**

In `DetectionOverlay.tsx`, update the `DetectionItem` interface:

```typescript
export interface DetectionItem {
  bbox: DetectionBBox;
  confidence: number;
  user_id: string | null;
  student_id: string | null;
  name: string | null;
  similarity: number | null;
  /** Track ID from edge device (used for identity mapping). */
  track_id?: string;
}
```

**Step 2: Use edge track_id in useDetectionTracker**

In `useDetectionTracker.ts`, when a detection has a `track_id` from the edge, use it directly instead of generating one:

```typescript
// For detections with edge track_id, use it directly
if (det.track_id) {
  const prevIdx = prevTracks.findIndex((t) => t.trackId === det.track_id);
  if (prevIdx >= 0) usedPrevIndices.add(prevIdx);

  newTracks.push({
    ...det,
    trackId: det.track_id,
    staleFrames: 0,
  });
  continue;
}
```

This goes before the existing known-face (user_id) matching block, so edge track IDs take priority.

**Step 3: Commit**

```bash
git add mobile/src/components/video/DetectionOverlay.tsx mobile/src/hooks/useDetectionTracker.ts
git commit -m "feat: use edge track_id for stable cross-frame bbox tracking"
```

---

### Task 10: Backend — Update recognition service to push identity via relay

**Files:**
- Modify: `backend/app/services/recognition_service.py`

**Step 1: Import edge relay manager**

At the top:

```python
from app.services.edge_relay_service import edge_relay_manager
```

**Step 2: After processing a frame, push identity updates**

In `_process_frame()` or `_process_frame_ml()` (around line 297-428), after FAISS search produces matched user_ids, push identity updates through the relay:

After the detection loop that creates Detection objects with user_id populated (around line 413-423), add:

```python
# Push identity updates to edge relay for mobile clients
import asyncio

identity_mappings = []
for det in detections:
    if det.user_id:
        identity_mappings.append({
            "bbox": {"x": det.x, "y": det.y, "width": det.width, "height": det.height},
            "user_id": det.user_id,
            "name": det.name or "",
            "student_id": det.student_id or "",
            "confidence": det.similarity or 0.0,
        })

if identity_mappings:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(
                edge_relay_manager.push_identity_update(room_id, identity_mappings)
            )
        else:
            loop.run_until_complete(
                edge_relay_manager.push_identity_update(room_id, identity_mappings)
            )
    except Exception as e:
        logger.debug(f"Failed to push identity update: {e}")
```

Note: Since `_process_frame_ml` runs in a thread executor, we need to handle the async call properly. The `asyncio.ensure_future` approach works when the event loop is running (which it is, since FastAPI uses asyncio).

A cleaner approach: use `asyncio.run_coroutine_threadsafe()`:

```python
if identity_mappings:
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(
            edge_relay_manager.push_identity_update(state.room_id, identity_mappings),
            loop,
        )
    except Exception as e:
        logger.debug(f"Failed to push identity update: {e}")
```

**Step 3: Commit**

```bash
git add backend/app/services/recognition_service.py
git commit -m "feat: push identity updates via edge relay after FAISS recognition"
```

---

### Task 11: Deploy and test end-to-end

**Files:**
- No new files

**Step 1: Deploy backend to VPS**

```bash
cd /Users/cjjutba/Projects/iams
bash deploy/deploy.sh
```

**Step 2: Install websocket-client on RPi**

```bash
ssh pi@192.168.1.18 "cd ~/iams-edge && source venv/bin/activate && pip install websocket-client>=1.6.0"
```

**Step 3: Sync edge code to RPi**

```bash
rsync -avz --exclude='venv' --exclude='__pycache__' --exclude='.env' \
  edge/ pi@192.168.1.18:~/iams-edge/
```

**Step 4: Restart edge service on RPi**

```bash
ssh pi@192.168.1.18 "cd ~/iams-edge && source venv/bin/activate && python run.py"
```

**Step 5: Test on mobile app**

1. Open faculty live feed screen
2. Verify bounding boxes appear and track faces smoothly at camera FPS
3. Verify identity labels appear after 1-2 seconds (async recognition)
4. Verify boxes stay aligned with faces in the WebRTC video
5. Move face quickly — boxes should follow without lag

**Step 6: Check VPS logs for edge WebSocket connections**

```bash
ssh root@167.71.217.44 "docker logs iams-backend 2>&1 | tail -50"
```

Look for:
- "Edge device registered for room XXX"
- "Mobile client registered for room XXX"

**Step 7: Commit any fixes**

```bash
git add -A
git commit -m "fix: post-integration adjustments for real-time tracking"
```

---

## Implementation Order Summary

| Task | Component | Description | Dependencies |
|------|-----------|-------------|--------------|
| 1 | Backend | EdgeRelayManager singleton | None |
| 2 | Backend | Edge WebSocket endpoint + router | Task 1 |
| 3 | Backend | Integrate relay into live_stream | Tasks 1, 2 |
| 4 | Backend | Lower RECOGNITION_FPS to 2 | None |
| 5 | Edge | Add EDGE_WS_URL config | None |
| 6 | Edge | EdgeWebSocketClient module | Task 5 |
| 7 | Edge | Integrate WS into scan loop | Tasks 5, 6 |
| 8 | Mobile | Dual-channel message handling | None |
| 9 | Mobile | track_id in DetectionItem | Task 8 |
| 10 | Backend | Recognition → identity push | Tasks 1, 3 |
| 11 | All | Deploy + end-to-end test | All above |

## Parallelization

Tasks 1-4 (backend), 5-7 (edge), and 8-9 (mobile) can be developed in parallel since they touch different codebases. Task 10 depends on Task 1. Task 11 depends on all.
