# Smooth Real-Time Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate bounding box delay by switching to WebRTC-only streaming with fast MediaPipe detection driving boxes at 30 FPS, and event-driven recognition for identity labels.

**Architecture:** Backend captures from local webcam (dev) or receives from RPi (prod), runs MediaPipe detection at 15-30 FPS, pushes video to mediamtx for WebRTC delivery, fuses detections via Kalman filter at 30 FPS, and sends `fused_tracks` over WebSocket. Recognition runs asynchronously only on new/unidentified tracks.

**Tech Stack:** FastAPI, OpenCV, MediaPipe, mediamtx (WebRTC/WHEP), React Native, react-native-webrtc, react-native-reanimated

---

## Task 1: Add Config Flags for Detection Source and Camera

**Files:**
- Modify: `backend/app/config.py:104-138`

**Step 1: Add new config settings**

In `backend/app/config.py`, add these settings after the WebRTC section (after line 132):

```python
    # Detection source
    DETECTION_SOURCE: str = "local"  # "local" = backend runs MediaPipe, "edge" = RPi sends via WebSocket
    CAMERA_SOURCE: str = "0"  # Webcam index (e.g. "0") or RTSP URL for local mode
    LOCAL_DETECTION_FPS: float = 30.0  # MediaPipe detection FPS in local mode
```

**Step 2: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(config): add DETECTION_SOURCE and CAMERA_SOURCE settings"
```

---

## Task 2: Create LocalCameraService

**Files:**
- Create: `backend/app/services/local_camera_service.py`

**Step 1: Write the LocalCameraService**

This service captures from the MacBook webcam, runs MediaPipe face detection, pushes the raw stream to mediamtx via FFmpeg RTSP, and feeds detections into `track_fusion_service`.

```python
"""
Local Camera Service

Captures from a local webcam (or RTSP URL), runs MediaPipe face detection
on each frame, pushes the video stream to mediamtx via FFmpeg RTSP, and
feeds detections into the track fusion service.

Used for localhost development. In production, the RPi edge device handles
detection and stream relay instead.
"""

import asyncio
import contextlib
import subprocess
import threading
import time

import cv2
import numpy as np

from app.config import logger, settings


class LocalCameraService:
    """
    Local webcam capture + MediaPipe detection + RTSP push to mediamtx.

    Replaces the RPi edge device for localhost development. Produces the
    same detection format that the edge WebSocket would send, so the rest
    of the pipeline (track fusion, WebSocket broadcast) is identical.
    """

    def __init__(self):
        self._active: dict[str, dict] = {}  # room_id → state
        self._lock = threading.Lock()
        self._detector = None
        self._detector_checked = False

    def _ensure_detector(self):
        """Lazy-load MediaPipe face detection."""
        if self._detector_checked:
            return
        try:
            import mediapipe as mp
            self._detector = mp.solutions.face_detection.FaceDetection(
                model_selection=0,  # short-range (< 2m, faster)
                min_detection_confidence=0.5,
            )
            logger.info("LocalCamera: MediaPipe face detection loaded")
        except Exception as exc:
            logger.warning(f"LocalCamera: MediaPipe unavailable: {exc}")
        self._detector_checked = True

    async def start(self, room_id: str, viewer_id: str) -> bool:
        """Start local camera capture and detection for a room."""
        with self._lock:
            if room_id in self._active:
                state = self._active[room_id]
                state["viewers"].add(viewer_id)
                logger.info(f"LocalCamera: viewer {viewer_id} joined room {room_id}")
                return True

        self._ensure_detector()

        # Open camera
        source = settings.CAMERA_SOURCE
        try:
            cam_index = int(source)
        except ValueError:
            cam_index = source  # RTSP URL string

        loop = asyncio.get_event_loop()
        cap = await loop.run_in_executor(None, self._open_capture, cam_index)
        if cap is None:
            return False

        # Get frame dimensions
        fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30

        # Start FFmpeg RTSP push to mediamtx
        ffmpeg_proc = self._start_ffmpeg_push(room_id, fw, fh, fps)

        state = {
            "room_id": room_id,
            "capture": cap,
            "ffmpeg": ffmpeg_proc,
            "stop_event": threading.Event(),
            "viewers": {viewer_id},
            "frame_width": fw,
            "frame_height": fh,
            "fps": fps,
            "latest_frame": None,
            "latest_frame_lock": threading.Lock(),
        }

        with self._lock:
            self._active[room_id] = state

        # Start capture + detection thread
        thread = threading.Thread(
            target=self._capture_loop, args=(state,), daemon=True
        )
        thread.start()

        logger.info(
            f"LocalCamera: started for room {room_id} "
            f"({fw}x{fh} @ {fps} FPS, source={source})"
        )
        return True

    async def stop(self, room_id: str, viewer_id: str | None = None) -> None:
        """Remove a viewer. If none remain, stop the camera."""
        with self._lock:
            state = self._active.get(room_id)
            if state is None:
                return

            if viewer_id is not None:
                state["viewers"].discard(viewer_id)
                if state["viewers"]:
                    return

            state["stop_event"].set()
            self._active.pop(room_id, None)

        # Cleanup
        if state.get("capture"):
            with contextlib.suppress(Exception):
                state["capture"].release()
        if state.get("ffmpeg"):
            with contextlib.suppress(Exception):
                state["ffmpeg"].stdin.close()
                state["ffmpeg"].terminate()
                state["ffmpeg"].wait(timeout=5)

        logger.info(f"LocalCamera: stopped for room {room_id}")

    def get_latest_frame(self, room_id: str) -> np.ndarray | None:
        """Return the latest captured frame (for recognition service)."""
        state = self._active.get(room_id)
        if state is None:
            return None
        with state["latest_frame_lock"]:
            return state["latest_frame"]

    def get_frame_dimensions(self, room_id: str) -> tuple[int, int]:
        """Return (width, height) for a room."""
        state = self._active.get(room_id)
        if state is None:
            return (0, 0)
        return (state["frame_width"], state["frame_height"])

    def is_active(self, room_id: str) -> bool:
        """Check if camera is active for a room."""
        return room_id in self._active

    def _open_capture(self, source) -> cv2.VideoCapture | None:
        """Open webcam or RTSP source."""
        try:
            cap = cv2.VideoCapture(source)
            if not cap.isOpened():
                logger.error(f"LocalCamera: failed to open camera source: {source}")
                return None
            # Set buffer size to 1 for minimal latency
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return cap
        except Exception as exc:
            logger.error(f"LocalCamera: capture open error: {exc}")
            return None

    def _start_ffmpeg_push(
        self, room_id: str, width: int, height: int, fps: int
    ) -> subprocess.Popen | None:
        """Start FFmpeg to push raw frames to mediamtx via RTSP."""
        rtsp_url = f"{settings.MEDIAMTX_RTSP_URL}/{room_id}"
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}",
            "-r", str(fps),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-g", str(fps),  # keyframe every 1s
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            rtsp_url,
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info(f"LocalCamera: FFmpeg RTSP push started → {rtsp_url}")
            return proc
        except Exception as exc:
            logger.error(f"LocalCamera: FFmpeg start error: {exc}")
            return None

    def _capture_loop(self, state: dict) -> None:
        """Main capture + detection loop (runs in a background thread)."""
        from app.services.edge_relay_service import track_fusion_service

        cap = state["capture"]
        ffmpeg = state["ffmpeg"]
        stop_event = state["stop_event"]
        room_id = state["room_id"]
        target_interval = 1.0 / settings.LOCAL_DETECTION_FPS
        next_track_id = 1
        # Simple centroid tracker for stable IDs
        prev_centroids: list[tuple[int, float, float]] = []  # (track_id, cx, cy)
        MAX_DIST = 80.0  # max pixels for centroid match

        while not stop_event.is_set():
            frame_start = time.monotonic()

            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            # Store latest frame for recognition service
            with state["latest_frame_lock"]:
                state["latest_frame"] = frame.copy()

            # Push frame to FFmpeg for RTSP relay
            if ffmpeg and ffmpeg.stdin and ffmpeg.poll() is None:
                try:
                    ffmpeg.stdin.write(frame.tobytes())
                except (BrokenPipeError, OSError):
                    pass

            # Run MediaPipe face detection
            detections = self._detect_faces(frame)
            h, w = frame.shape[:2]

            # Assign stable track IDs via centroid matching
            current_centroids = []
            edge_dets = []
            used_prev = set()

            for det in detections:
                bx, by, bw, bh = det
                cx = bx + bw / 2
                cy = by + bh / 2

                # Find closest previous centroid
                best_dist = MAX_DIST
                best_tid = None
                for idx, (tid, pcx, pcy) in enumerate(prev_centroids):
                    if idx in used_prev:
                        continue
                    dist = ((cx - pcx) ** 2 + (cy - pcy) ** 2) ** 0.5
                    if dist < best_dist:
                        best_dist = dist
                        best_tid = tid
                        best_idx = idx

                if best_tid is not None:
                    used_prev.add(best_idx)
                    tid = best_tid
                else:
                    tid = next_track_id
                    next_track_id += 1

                current_centroids.append((tid, cx, cy))
                edge_dets.append({
                    "track_id": tid,
                    "bbox": [bx, by, bw, bh],
                    "confidence": 0.9,
                    "velocity": [0.0, 0.0],
                })

            prev_centroids = current_centroids

            # Feed into track fusion service (same path as edge WebSocket)
            if edge_dets:
                track_fusion_service.update_from_edge(room_id, edge_dets, w, h)

            # Throttle to target FPS
            elapsed = time.monotonic() - frame_start
            sleep_time = target_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.info(f"LocalCamera: capture loop ended for room {room_id}")

    def _detect_faces(self, frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Run MediaPipe face detection. Returns list of (x, y, w, h) bounding boxes."""
        if self._detector is None:
            return []

        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._detector.process(rgb)

        boxes = []
        if results.detections:
            for det in results.detections:
                bb = det.location_data.relative_bounding_box
                x = max(0, int(bb.xmin * w))
                y = max(0, int(bb.ymin * h))
                bw = min(int(bb.width * w), w - x)
                bh = min(int(bb.height * h), h - y)
                if bw > 10 and bh > 10:
                    boxes.append((x, y, bw, bh))

        return boxes

    async def cleanup_all(self) -> None:
        """Stop all camera pipelines (app shutdown)."""
        for room_id in list(self._active.keys()):
            await self.stop(room_id)


# Global singleton
local_camera_service = LocalCameraService()
```

**Step 2: Commit**

```bash
git add backend/app/services/local_camera_service.py
git commit -m "feat(backend): add LocalCameraService for webcam capture + MediaPipe detection"
```

---

## Task 3: Simplify live_stream.py — WebRTC-Only Mode

**Files:**
- Modify: `backend/app/routers/live_stream.py`

This is the largest refactor. We remove `_hls_mode()`, `_legacy_mode()`, and the mode negotiation logic. The `_webrtc_mode()` function is simplified and gets local camera integration.

**Step 1: Replace the router file**

The new `live_stream.py` should:

1. Remove all HLS imports (`hls_service`)
2. Remove `_hls_mode()` function (lines 472-668)
3. Remove `_legacy_mode()` function (lines 861-957)
4. Remove HLS/legacy mode negotiation in `live_stream_ws()` (lines 327-356)
5. Keep `RecognitionTracker` and `NameCache` (still needed for no-edge fallback)
6. Add local camera service integration in `_webrtc_mode()`:
   - If `DETECTION_SOURCE=local`: start `local_camera_service` instead of relying on edge WebSocket
   - The local camera service feeds directly into `track_fusion_service`
7. Simplify mode to always WebRTC
8. Simplify status endpoint to WebRTC only

Key changes to `_webrtc_mode()`:
- Import and use `local_camera_service` when `DETECTION_SOURCE == "local"`
- Start local camera before recognition
- The fused_tracks loop stays the same (it reads from track_fusion_service regardless of detection source)

**Detailed edits:**

a) Update imports (line 39-42): Remove `hls_service` import, add `local_camera_service`:

```python
from app.services.edge_relay_service import edge_relay_manager, track_fusion_service
from app.services.local_camera_service import local_camera_service
from app.services.recognition_service import recognition_service
from app.services.webrtc_service import webrtc_service
```

b) In `live_stream_ws()` (line 236), simplify the mode decision to always WebRTC. Remove HLS/legacy branches. After the schedule/room validation, go straight to WebRTC mode:

```python
@router.websocket("/{schedule_id}")
async def live_stream_ws(schedule_id: str, websocket: WebSocket):
    """
    Live stream WebSocket endpoint (WebRTC mode only).

    Accepts a WebSocket connection, verifies the schedule, resolves the
    camera RTSP URL, then pushes detection metadata while video is
    delivered via mediamtx WebRTC (WHEP).
    """
    viewer_id = str(uuid_mod.uuid4())

    # --- Validate schedule and resolve camera URL ---
    db = SessionLocal()
    try:
        schedule_repo = ScheduleRepository(db)
        schedule = schedule_repo.get_by_id(schedule_id)

        if schedule is None:
            await websocket.accept()
            await websocket.send_json(
                {"type": "error", "message": f"Schedule not found: {schedule_id}"}
            )
            await websocket.close(code=4004, reason="Schedule not found")
            return

        room_id = str(schedule.room_id)
        rtsp_url = get_camera_url(room_id, db)
    except Exception as exc:
        logger.error(f"Live stream setup error: {exc}")
        try:
            await websocket.accept()
            await websocket.send_json(
                {"type": "error", "message": "Internal server error during setup"}
            )
            await websocket.close(code=4500, reason="Internal error")
        except Exception:
            pass
        return
    finally:
        db.close()

    await websocket.accept()

    using_local = settings.DETECTION_SOURCE == "local"

    # For local mode, ensure mediamtx path exists (camera will push to it)
    if using_local:
        # Local camera service will push RTSP to mediamtx at this path
        await webrtc_service.ensure_path(room_id, None)
    else:
        # Edge/production: check if mediamtx has the stream
        if rtsp_url:
            mediamtx_ok = await webrtc_service.ensure_path(room_id, rtsp_url)
        else:
            mediamtx_ok = await webrtc_service.check_path_exists(room_id)

        if not mediamtx_ok and not rtsp_url:
            # Wait for camera to come online
            resolved = await _wait_for_camera(
                websocket, schedule_id, room_id, db_factory=SessionLocal,
            )
            if resolved is None:
                return
            _, rtsp_url = resolved

    logger.info(
        f"Live stream WS connected: viewer={viewer_id}, "
        f"schedule={schedule_id}, room={room_id}, "
        f"mode=webrtc, detection_source={settings.DETECTION_SOURCE}"
    )

    await _webrtc_mode(websocket, viewer_id, schedule_id, room_id, rtsp_url)
```

c) Simplify `_webrtc_mode()` — integrate local camera:

```python
async def _webrtc_mode(
    websocket: WebSocket,
    viewer_id: str,
    schedule_id: str,
    room_id: str,
    rtsp_url: str | None,
):
    """
    WebRTC mode: push detection metadata via WebSocket.
    Video delivery is handled by mediamtx WebRTC (WHEP).

    Detection source is determined by DETECTION_SOURCE setting:
    - "local": backend captures webcam + MediaPipe detection
    - "edge": RPi sends detections via EdgeRelayManager
    """
    using_local = settings.DETECTION_SOURCE == "local"

    await websocket.send_json({
        "type": "connected",
        "schedule_id": schedule_id,
        "room_id": room_id,
        "mode": "webrtc",
        "stream_fps": settings.STREAM_FPS,
        "stream_resolution": f"{settings.STREAM_WIDTH}x{settings.STREAM_HEIGHT}",
    })

    # Register for edge relay (production mode)
    await edge_relay_manager.register_mobile(room_id, websocket)

    # Start local camera if in local mode
    if using_local:
        cam_ok = await local_camera_service.start(room_id, viewer_id)
        if not cam_ok:
            logger.warning("Local camera failed to start — no bounding boxes")

    # Start recognition pipeline
    if using_local:
        # In local mode, recognition reads from mediamtx RTSP (fed by local camera)
        recog_url = f"{settings.MEDIAMTX_RTSP_URL}/{room_id}"
    else:
        recog_url = settings.RECOGNITION_RTSP_URL or rtsp_url
        if not recog_url:
            recog_url = f"{settings.MEDIAMTX_RTSP_URL}/{room_id}"

    recog_ok = await recognition_service.start(room_id, recog_url, viewer_id)
    if not recog_ok:
        logger.warning("Recognition service failed to start — no identity labels")

    # --- Receive task (handle pings/close) ---
    stop_event = asyncio.Event()

    async def _receive_loop():
        try:
            while not stop_event.is_set():
                msg = await websocket.receive_json()
                if isinstance(msg, dict) and msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except (WebSocketDisconnect, Exception):
            stop_event.set()

    receive_task = asyncio.create_task(_receive_loop())

    # --- Push fused tracks at 30 FPS ---
    FUSED_INTERVAL = 1.0 / 30.0
    last_fused_send = 0.0
    fused_seq = 0
    last_update_seq = track_fusion_service.get_update_seq(room_id)
    last_heartbeat = _time.time()
    last_recog_check = _time.time()
    last_recog_seq = 0
    last_recog_feed_seq = 0

    try:
        while not stop_event.is_set():
            now = _time.time()

            # Health check: restart stalled recognition
            if now - last_recog_check > 10.0:
                current_recog_seq = track_fusion_service.get_update_seq(room_id)
                if current_recog_seq == last_recog_seq and current_recog_seq > 0:
                    logger.warning(f"Recognition stalled for room {room_id}, restarting")
                    await recognition_service.stop(room_id, viewer_id)
                    await recognition_service.start(room_id, recog_url, viewer_id)
                last_recog_seq = current_recog_seq
                last_recog_check = now

            # When no edge device and not using local camera,
            # feed recognition results into fusion (fallback)
            if not using_local and not edge_relay_manager.has_edge_device(room_id):
                recog_result = recognition_service.get_latest_detections(room_id)
                if recog_result is not None:
                    det_dicts, recog_seq, fw, fh = recog_result
                    if recog_seq > last_recog_feed_seq and det_dicts:
                        last_recog_feed_seq = recog_seq

                        det_objects = recognition_service.get_detections_objects(room_id)
                        det_dicts = _enrich_and_cache(det_dicts, det_objects, SessionLocal)

                        tracked = _recognition_tracker.assign(room_id, det_dicts)

                        edge_dets = []
                        for tid, det in tracked:
                            bbox = det.get("bbox", {})
                            edge_dets.append({
                                "track_id": tid,
                                "bbox": [bbox.get("x", 0), bbox.get("y", 0),
                                         bbox.get("width", 0), bbox.get("height", 0)],
                                "confidence": det.get("confidence", 0.5),
                                "velocity": [0.0, 0.0],
                            })
                        track_fusion_service.update_from_edge(room_id, edge_dets, fw, fh)
                        for tid, det in tracked:
                            if det.get("user_id") and det.get("name"):
                                track_fusion_service.update_identity(
                                    room_id, tid, det["user_id"],
                                    det.get("name", ""), det.get("student_id", ""),
                                    det.get("similarity", 0.0),
                                )

            elapsed = now - last_fused_send
            if elapsed >= FUSED_INTERVAL:
                current_seq = track_fusion_service.get_update_seq(room_id)
                if current_seq == last_update_seq:
                    track_fusion_service.predict(room_id, dt=min(elapsed, 0.1))
                last_update_seq = current_seq

                tracks = track_fusion_service.get_tracks(room_id)
                fw, fh = track_fusion_service.get_room_dimensions(room_id)
                fused_seq += 1

                if tracks:
                    await websocket.send_json({
                        "type": "fused_tracks",
                        "room_id": room_id,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "seq": fused_seq,
                        "frame_width": fw,
                        "frame_height": fh,
                        "tracks": tracks,
                    })

                last_fused_send = now

            if now - last_heartbeat > 5.0:
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.now(UTC).isoformat(),
                })
                last_heartbeat = now

            await asyncio.sleep(0.01)

    except WebSocketDisconnect:
        logger.info(f"Live stream WS disconnected: viewer={viewer_id}")
    except Exception as exc:
        logger.error(f"Live stream WS error (viewer={viewer_id}): {exc}")
    finally:
        stop_event.set()
        receive_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await receive_task

        await edge_relay_manager.unregister_mobile(room_id, websocket)
        if using_local:
            await local_camera_service.stop(room_id, viewer_id)
        await recognition_service.stop(room_id, viewer_id)
        track_fusion_service.cleanup_room(room_id)
        _recognition_tracker.cleanup(room_id)

        if websocket.client_state == WebSocketState.CONNECTED:
            with contextlib.suppress(Exception):
                await websocket.close()
```

d) Simplify status endpoint:

```python
@router.get("/status")
async def stream_status():
    """Get live stream system status."""
    return {
        "success": True,
        "data": {
            "mode": "webrtc",
            "detection_source": settings.DETECTION_SOURCE,
            "stream_fps": settings.STREAM_FPS,
            "stream_resolution": f"{settings.STREAM_WIDTH}x{settings.STREAM_HEIGHT}",
        },
    }
```

**Step 2: Verify backend starts**

Run: `cd backend && python -c "from app.routers.live_stream import router; print('OK')"`

**Step 3: Commit**

```bash
git add backend/app/routers/live_stream.py
git commit -m "refactor(backend): simplify live_stream to WebRTC-only with local camera support"
```

---

## Task 4: Wire Recognition to Identify New Tracks (Event-Driven)

**Files:**
- Modify: `backend/app/services/recognition_service.py`
- Modify: `backend/app/services/track_fusion_service.py`

**Step 1: Add method to track_fusion_service for getting unidentified tracks**

Add this method to `TrackFusionService` class in `backend/app/services/track_fusion_service.py`:

```python
    def get_unidentified_track_ids(self, room_id: str) -> list[int]:
        """Return edge_track_ids of confirmed tracks that have no identity."""
        room = self._rooms.get(room_id)
        if room is None:
            return []
        with room.lock:
            return [
                t.edge_track_id
                for t in room.tracks.values()
                if t.is_confirmed and t.user_id is None
            ]

    def get_track_count(self, room_id: str) -> int:
        """Return total number of active tracks."""
        room = self._rooms.get(room_id)
        if room is None:
            return 0
        with room.lock:
            return len(room.tracks)
```

**Step 2: Add frame provider to recognition service**

Modify `recognition_service.py` to support getting frames from `local_camera_service` when in local mode. Add a `set_frame_provider` method and modify `_read_frame` to use it as an alternative:

In `RecognitionState`, add:
```python
    frame_provider: object | None = None  # callable that returns latest frame
```

In `RecognitionService.start()`, after opening capture, add frame provider support:
```python
        # If local camera is providing frames, use it instead of RTSP
        if settings.DETECTION_SOURCE == "local":
            from app.services.local_camera_service import local_camera_service
            state.frame_provider = lambda: local_camera_service.get_latest_frame(room_id)
```

In `_read_frame()`, add frame provider check at the top:
```python
    def _read_frame(self, state: RecognitionState):
        """Read the freshest frame (from provider or RTSP capture)."""
        # Try frame provider first (local camera mode)
        if state.frame_provider is not None:
            frame = state.frame_provider()
            if frame is not None:
                return True, frame
            return True, None  # Provider exists but no frame yet

        # Original RTSP capture logic follows...
```

**Step 3: Commit**

```bash
git add backend/app/services/recognition_service.py backend/app/services/track_fusion_service.py
git commit -m "feat(backend): add frame provider to recognition and unidentified track query"
```

---

## Task 5: Tune Kalman Filter for Smoother Bounding Boxes

**Files:**
- Modify: `backend/app/services/track_fusion_service.py:26-34`

**Step 1: Adjust Kalman parameters**

The current Q_BASE and R matrices produce jittery motion. Lower process noise for position, higher for velocity (trust measurements more):

```python
# Base process noise (scaled by dt) — lower position noise for smoother motion
Q_BASE = np.diag([0.5, 0.5, 0.25, 0.25, 3.0, 3.0, 0.5, 0.5])

# Measurement noise — slightly higher to trust Kalman prediction more (smooths jitter)
R = np.diag([6.0, 6.0, 6.0, 6.0])
```

Also reduce `max_missed_frames` from 10 to 8 (faster cleanup of ghost tracks):

```python
    def __init__(self, max_missed_frames: int = 8, confirm_threshold: int = 3):
```

**Step 2: Commit**

```bash
git add backend/app/services/track_fusion_service.py
git commit -m "tune(backend): adjust Kalman parameters for smoother bounding box motion"
```

---

## Task 6: Simplify useDetectionWebSocket — WebRTC Only

**Files:**
- Modify: `mobile/src/hooks/useDetectionWebSocket.ts`

**Step 1: Remove delay queue and legacy message handlers**

The simplified hook should:
1. Remove `DETECTION_DELAY` constant and delay queue logic (lines 131-149, 258-288)
2. Remove `detections` message handler (lines 365-382) — not used in WebRTC+fused_tracks mode
3. Remove `edge_detections` message handler (lines 383-470) — replaced by fused_tracks
4. Remove `identity_update` message handler (lines 518-580) — identity comes in fused_tracks
5. Remove `identityCacheRef` and `usingEdgeDetectionsRef` refs
6. Keep only: `connected`, `fused_tracks`, `heartbeat/pong`, `waiting`, `error`
7. Remove `hlsUrl` state (not needed for WebRTC)
8. Simplify `streamMode` to always be `'webrtc'`

The simplified hook interface:
```typescript
export interface UseDetectionWebSocketReturn {
  fusedTracks: FusedTrack[];
  isConnected: boolean;
  isConnecting: boolean;
  isWaitingForCamera: boolean;
  streamMode: 'webrtc' | null;
  studentMap: Map<string, DetectedStudent>;
  connectionError: string | null;
  reconnect: () => void;
  detectionWidth: number;
  detectionHeight: number;
}
```

Remove `detections`, `hlsUrl` from the return value.

The `onmessage` handler should only process:
```typescript
if (message.type === 'connected') {
  // Set stream mode, stop loading
} else if (message.type === 'fused_tracks') {
  // Update fusedTracks + studentMap
} else if (message.type === 'pong' || message.type === 'heartbeat') {
  // No-op
} else if (message.type === 'waiting') {
  // Show waiting state
} else if (message.type === 'error') {
  // Show error
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd mobile && npx tsc --noEmit --pretty 2>&1 | head -30`
Fix any type errors.

**Step 3: Commit**

```bash
git add mobile/src/hooks/useDetectionWebSocket.ts
git commit -m "refactor(mobile): simplify useDetectionWebSocket to WebRTC + fused_tracks only"
```

---

## Task 7: Simplify FacultyLiveFeedScreen — WebRTC Only

**Files:**
- Modify: `mobile/src/screens/faculty/FacultyLiveFeedScreen.tsx`

**Step 1: Remove HLS/legacy video player and overlay branches**

1. Remove HLS-related imports: `useVideoPlayer`, `VideoView` from `expo-video` (line 41)
2. Remove `hlsUrl` from destructured `useDetectionWebSocket` return
3. Remove `detections` and `trackedDetections` (no longer returned from hook)
4. Remove `useDetectionTracker` import and usage (line 53, 195)
5. Remove `player` creation (lines 208-221) and all player effects (lines 224-259)
6. Remove HLS video branch in JSX (lines 726-751)
7. Keep only WebRTC branch: `RTCView` + `FusedDetectionOverlay`
8. Remove `DetectionOverlay` import — only use `FusedDetectionOverlay`
9. Update `detectedCount` and `unknownCount` to use `fusedTracks` instead of `detections`
10. Simplify `isVideoReady` to only check WebRTC

Key JSX for the feed container:
```tsx
{/* Camera feed: WebRTC video + fused detection overlay */}
<View style={styles.feedContainer} onLayout={handleVideoLayout}>
  {remoteStream ? (
    <>
      <RTCView
        streamURL={remoteStream.toURL()}
        style={styles.video}
        objectFit="contain"
        mirror={false}
        zOrder={0}
      />
      <FusedDetectionOverlay
        tracks={fusedTracks}
        videoWidth={detectionWidth}
        videoHeight={detectionHeight}
        containerWidth={containerLayout.width}
        containerHeight={containerLayout.height}
      />
    </>
  ) : (
    <View style={styles.noFeedPlaceholder}>
      {/* ... waiting/connecting/failed states ... */}
    </View>
  )}
</View>
```

**Step 2: Verify TypeScript compiles**

Run: `cd mobile && npx tsc --noEmit --pretty 2>&1 | head -30`

**Step 3: Commit**

```bash
git add mobile/src/screens/faculty/FacultyLiveFeedScreen.tsx
git commit -m "refactor(mobile): simplify FacultyLiveFeedScreen to WebRTC + FusedDetectionOverlay only"
```

---

## Task 8: Update .env for Local Development

**Files:**
- Modify: `backend/.env`

**Step 1: Add/update environment variables**

Ensure these are in `backend/.env`:
```
DETECTION_SOURCE=local
CAMERA_SOURCE=0
LOCAL_DETECTION_FPS=30.0
USE_WEBRTC_STREAMING=true
USE_HLS_STREAMING=false
RECOGNITION_FPS=2.0
```

Note: `RECOGNITION_FPS` stays at 2.0 because recognition is now event-driven and only runs on new faces — the rate just sets the polling frequency for checking RTSP frames.

**Step 2: Commit**

```bash
git add backend/.env
git commit -m "config: set local camera + WebRTC defaults for localhost development"
```

---

## Task 9: Integration Test — End-to-End Smoke Test

**Step 1: Start mediamtx**

```bash
cd backend && ./bin/mediamtx mediamtx.yml &
```

**Step 2: Start backend**

```bash
cd backend && python run.py
```

**Step 3: Verify webcam capture starts**

Watch the backend logs for:
- `LocalCamera: started for room <id> (WxH @ FPS)`
- `LocalCamera: MediaPipe face detection loaded`
- `LocalCamera: FFmpeg RTSP push started`

**Step 4: Connect mobile app**

```bash
cd mobile && pnpm android  # or pnpm ios
```

Navigate to a schedule's live feed. Verify:
- [ ] WebRTC video appears (from webcam via mediamtx)
- [ ] Bounding boxes appear around faces within 1 second
- [ ] Boxes move smoothly with face movement (no jumping)
- [ ] Name labels appear after recognition identifies the person
- [ ] Boxes fade out smoothly when face leaves frame
- [ ] No "Unknown" flickering

**Step 5: Check performance metrics**

In backend logs, look for recognition timing. Verify:
- Detection runs at ~30 FPS (local mode)
- Fused tracks sent at ~30 FPS via WebSocket
- Recognition triggers only for new faces

**Step 6: Commit any fixes**

```bash
git add -A
git commit -m "fix: integration test fixes for smooth real-time pipeline"
```

---

## Task 10: Cleanup — Remove Dead Code

**Files:**
- Modify: `mobile/src/hooks/useDetectionWebSocket.ts` (if not already cleaned)
- Modify: `mobile/src/screens/faculty/FacultyLiveFeedScreen.tsx` (if not already cleaned)
- Review: `backend/app/routers/live_stream.py`

**Step 1: Remove unused imports and dead code**

After integration testing confirms everything works:

1. Remove `useDetectionTracker` hook file if no longer imported anywhere
2. Remove `DetectionOverlay` component if only `FusedDetectionOverlay` is used
3. Clean up any remaining HLS references in other files

**Step 2: Verify no broken imports**

```bash
cd mobile && npx tsc --noEmit --pretty
cd backend && python -c "from app.main import app; print('Backend OK')"
```

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore: remove dead HLS/legacy code after WebRTC migration"
```
