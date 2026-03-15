"""
Live Stream Router

WebSocket endpoint for live camera streaming to the mobile app.

**WebRTC mode (always):**
    Video is delivered via mediamtx -> WebRTC (WHEP protocol) at <300ms latency.
    This WebSocket only pushes lightweight detection metadata (~200 bytes):
        { "type": "detections", "timestamp": "...", "detections": [...] }
    The ``connected`` message includes ``"mode": "webrtc"``.
    The mobile app simultaneously calls POST /api/v1/webrtc/{schedule_id}/offer
    to establish the WebRTC peer connection for video.

**Detection sources:**
    - ``DETECTION_SOURCE="local"``: local camera service pushes to mediamtx
    - ``DETECTION_SOURCE="edge"``: RPi edge device pushes to mediamtx
"""

import asyncio
import contextlib
import threading as _threading
import time as _time
import uuid as uuid_mod
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.config import logger, settings
from app.database import SessionLocal
from app.repositories.schedule_repository import ScheduleRepository
from app.services.camera_config import get_camera_url
from app.services.edge_relay_service import edge_relay_manager, track_fusion_service
from app.services.local_camera_service import local_camera_service
from app.services.recognition_service import recognition_service
from app.services.webrtc_service import webrtc_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Lightweight centroid/IoU tracker for stable track IDs across recognition
# frames.  InsightFace doesn't guarantee detection ordering, so we match
# detections between consecutive frames using IoU to maintain persistent IDs.
# ---------------------------------------------------------------------------


class RecognitionTracker:
    """
    Assign stable track IDs to recognition detections using IoU matching
    with centroid distance fallback.

    When recognition runs slowly (due to h264 errors or CPU load), a person
    may move significantly between frames. IoU drops to zero, but centroid
    distance can still match them. This prevents track ID churn that causes
    identity loss in the fusion service.
    """

    def __init__(
        self,
        iou_threshold: float = 0.25,
        max_centroid_dist: float = 120.0,
    ):
        self._iou_threshold = iou_threshold
        self._max_centroid_dist = max_centroid_dist
        self._next_id: int = 1
        # room_id -> list of (track_id, bbox_dict, user_id, det_dict)
        self._prev: dict[str, list[tuple]] = {}

    @staticmethod
    def _iou(a: dict, b: dict) -> float:
        """Compute IoU between two bbox dicts {x, y, width, height}."""
        ax1, ay1 = a["x"], a["y"]
        ax2, ay2 = ax1 + a["width"], ay1 + a["height"]
        bx1, by1 = b["x"], b["y"]
        bx2, by2 = bx1 + b["width"], by1 + b["height"]

        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        if inter == 0:
            return 0.0
        area_a = a["width"] * a["height"]
        area_b = b["width"] * b["height"]
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _centroid_dist(a: dict, b: dict) -> float:
        """Euclidean distance between bbox centroids."""
        acx = a.get("x", 0) + a.get("width", 0) / 2
        acy = a.get("y", 0) + a.get("height", 0) / 2
        bcx = b.get("x", 0) + b.get("width", 0) / 2
        bcy = b.get("y", 0) + b.get("height", 0) / 2
        return ((acx - bcx) ** 2 + (acy - bcy) ** 2) ** 0.5

    def assign(self, room_id: str, det_dicts: list[dict]) -> list[tuple[int, dict]]:
        """
        Match current detections to previous frame via IoU, falling back
        to centroid distance when IoU is too low (e.g. person moved).
        Returns list of (stable_track_id, det_dict) pairs.
        """
        prev = self._prev.get(room_id, [])
        results: list[tuple[int, dict]] = []
        used_prev: set[int] = set()

        for det in det_dicts:
            bbox = det.get("bbox", {})
            if not bbox:
                continue

            best_iou = 0.0
            best_idx = -1
            for idx, (_, prev_bbox, _, _) in enumerate(prev):
                if idx in used_prev:
                    continue
                iou = self._iou(bbox, prev_bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_idx = idx

            if best_iou >= self._iou_threshold and best_idx >= 0:
                # IoU match — reuse previous track ID
                tid = prev[best_idx][0]
                used_prev.add(best_idx)
            else:
                # IoU too low — try centroid distance fallback
                best_dist = float("inf")
                best_dist_idx = -1
                for idx, (_, prev_bbox, _, _) in enumerate(prev):
                    if idx in used_prev:
                        continue
                    dist = self._centroid_dist(bbox, prev_bbox)
                    if dist < best_dist:
                        best_dist = dist
                        best_dist_idx = idx

                if best_dist <= self._max_centroid_dist and best_dist_idx >= 0:
                    tid = prev[best_dist_idx][0]
                    used_prev.add(best_dist_idx)
                else:
                    # Truly new face
                    tid = self._next_id
                    self._next_id += 1

            results.append((tid, det))

        # Store current frame for next matching
        self._prev[room_id] = [
            (tid, det.get("bbox", {}), det.get("user_id"), det)
            for tid, det in results
        ]
        return results

    def cleanup(self, room_id: str) -> None:
        """Remove state for a room."""
        self._prev.pop(room_id, None)


# Global tracker instance shared across all rooms
_recognition_tracker = RecognitionTracker(iou_threshold=0.25, max_centroid_dist=120.0)


class NameCache:
    """Thread-safe student name cache with per-entry TTL."""

    def __init__(self, ttl_seconds: float = 300.0):
        self._lock = _threading.Lock()
        # uid -> ((name, student_id), inserted_at_monotonic)
        self._store: dict[str, tuple] = {}
        self._ttl = ttl_seconds

    def get(self, user_id: str):
        """Return (name, student_id) or None if missing/expired."""
        with self._lock:
            entry = self._store.get(user_id)
            if entry is None:
                return None
            value, inserted_at = entry
            if _time.monotonic() - inserted_at > self._ttl:
                self._store.pop(user_id, None)
                return None
            return value

    def set(self, user_id: str, name: str, student_id: str) -> None:
        """Store (name, student_id) with current timestamp."""
        with self._lock:
            self._store[user_id] = ((name, student_id), _time.monotonic())


# 5-minute TTL — auto-refresh if student name changes in DB
_name_cache = NameCache(ttl_seconds=300)


def _enrich_and_cache(detections_dicts: list, detections_objects, db_session_factory) -> list:
    """
    Enrich detection dicts with cached student names.
    Only hits the DB for user_ids not yet in the cache or whose cache entry has expired.
    Thread-safe via NameCache.
    """
    needs_lookup = [
        d for d in detections_dicts if d.get("user_id") and not d.get("name") and _name_cache.get(d["user_id"]) is None
    ]

    if needs_lookup:
        db = db_session_factory()
        try:
            from app.services.recognition_service import recognition_service

            recognition_service.enrich_detections(detections_objects, db)
            # Populate cache from enriched objects
            for det in detections_objects:
                if det.user_id and det.name:
                    _name_cache.set(det.user_id, det.name, det.student_id or "")
            detections_dicts = [d.to_dict() for d in detections_objects]
        finally:
            db.close()

    # Apply cache to any dicts that are missing names
    for d in detections_dicts:
        uid = d.get("user_id")
        if uid and not d.get("name"):
            cached = _name_cache.get(uid)
            if cached:
                d["name"], d["student_id"] = cached

    return detections_dicts


@router.websocket("/{schedule_id}")
async def live_stream_ws(schedule_id: str, websocket: WebSocket):
    """
    Live stream WebSocket endpoint.

    Accepts a WebSocket connection, verifies the schedule, resolves the
    camera RTSP URL, then runs WebRTC mode with detection metadata push.
    """
    viewer_id = str(uuid_mod.uuid4())
    using_local = settings.DETECTION_SOURCE == "local"

    # --- Validate schedule and resolve camera URL ---
    db = SessionLocal()
    try:
        schedule_repo = ScheduleRepository(db)
        schedule = schedule_repo.get_by_id(schedule_id)

        if schedule is None:
            await websocket.accept()
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Schedule not found: {schedule_id}",
                }
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
                {
                    "type": "error",
                    "message": "Internal server error during setup",
                }
            )
            await websocket.close(code=4500, reason="Internal error")
        except Exception:
            pass
        return
    finally:
        db.close()

    # --- Accept WebSocket ---
    await websocket.accept()

    if using_local:
        # Local camera mode: skip mediamtx path check — local_camera_service
        # will push to mediamtx itself.
        logger.info(
            f"Live stream WS connected: viewer={viewer_id}, schedule={schedule_id}, "
            f"room={room_id}, mode=webrtc, detection_source=local"
        )
    else:
        # Edge mode: check mediamtx path, wait for camera if needed
        if rtsp_url:
            mediamtx_ok = await webrtc_service.ensure_path(room_id, rtsp_url)
        else:
            mediamtx_ok = await webrtc_service.check_path_exists(room_id)

        if not mediamtx_ok and rtsp_url is None:
            # No RTSP URL and mediamtx path not found — wait for edge device
            logger.warning(
                f"Live stream: no RTSP URL and mediamtx path not found "
                f"for room {room_id} — is the edge device streaming?"
            )
            resolved = await _wait_for_camera(
                websocket, schedule_id, room_id, db_factory=SessionLocal,
            )
            if resolved is None:
                return
            _, rtsp_url = resolved
        elif not mediamtx_ok:
            logger.warning(
                f"Live stream: mediamtx unreachable for room {room_id}, "
                f"proceeding anyway"
            )

        logger.info(
            f"Live stream WS connected: viewer={viewer_id}, schedule={schedule_id}, "
            f"room={room_id}, mode=webrtc, detection_source=edge"
        )

    await _webrtc_mode(websocket, viewer_id, schedule_id, room_id, rtsp_url)


# ---------------------------------------------------------------------------
# Camera availability polling (keeps WebSocket open)
# ---------------------------------------------------------------------------

_CAMERA_POLL_INTERVAL = 5.0  # seconds between checks
_CAMERA_POLL_MAX_WAIT = 300.0  # give up after 5 minutes


async def _wait_for_camera(
    websocket: WebSocket,
    schedule_id: str,
    room_id: str,
    *,
    db_factory,
) -> tuple[bool, str] | None:
    """
    Keep the WebSocket open while waiting for a camera stream to become
    available.  Sends periodic ``waiting`` messages so the mobile app can
    show a friendly "Waiting for camera" indicator.

    Returns ``(use_webrtc, rtsp_url)`` once a stream is found, or ``None``
    if the client disconnected or the timeout was reached.
    """
    await websocket.send_json(
        {
            "type": "waiting",
            "message": "Waiting for camera — edge device is not streaming yet",
        }
    )

    # Receive task so we notice if the client disconnects
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
    start = _time.monotonic()

    try:
        while not stop_event.is_set():
            await asyncio.sleep(_CAMERA_POLL_INTERVAL)
            if stop_event.is_set():
                break

            elapsed = _time.monotonic() - start
            if elapsed > _CAMERA_POLL_MAX_WAIT:
                logger.info(
                    f"Camera wait timed out for room {room_id} after {elapsed:.0f}s"
                )
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Camera did not become available. Please check the edge device.",
                    }
                )
                await websocket.close(code=4003, reason="Camera timeout")
                return None

            # Re-check camera availability
            db = db_factory()
            try:
                rtsp_url = get_camera_url(room_id, db)
            finally:
                db.close()

            use_webrtc = False
            if rtsp_url:
                mediamtx_ok = await webrtc_service.ensure_path(room_id, rtsp_url)
            else:
                mediamtx_ok = await webrtc_service.check_path_exists(room_id)
            if mediamtx_ok:
                use_webrtc = True

            if use_webrtc or rtsp_url:
                logger.info(
                    f"Camera became available for room {room_id} "
                    f"(mode=webrtc) after {elapsed:.0f}s"
                )
                return (use_webrtc, rtsp_url)

            # Still waiting — send heartbeat so mobile knows we're alive
            await websocket.send_json(
                {
                    "type": "waiting",
                    "message": "Waiting for camera — edge device is not streaming yet",
                }
            )

    except (WebSocketDisconnect, Exception):
        pass
    finally:
        stop_event.set()
        receive_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await receive_task

    return None


# ---------------------------------------------------------------------------
# WebRTC mode: metadata-only WebSocket (no HLS, no JPEG frames)
# ---------------------------------------------------------------------------


async def _webrtc_mode(
    websocket: WebSocket,
    viewer_id: str,
    schedule_id: str,
    room_id: str,
    rtsp_url: str,
):
    """
    WebRTC mode: start only the recognition pipeline and push detection
    metadata over WebSocket.  Video delivery is handled separately by the
    WebRTC signalling layer.

    When ``DETECTION_SOURCE="local"``, starts the local camera service which
    feeds detections directly into track_fusion_service.

    When an edge device is connected for the room, bounding-box data is
    relayed by EdgeRelayManager (real-time from RPi).  This loop only
    pushes identity updates from the recognition service.  When no edge
    device is connected, falls back to feeding recognition results into
    the fusion service for bounding boxes.
    """
    using_local = settings.DETECTION_SOURCE == "local"

    # Register this mobile client with the edge relay manager
    await edge_relay_manager.register_mobile(room_id, websocket)

    # Start local camera service if using local detection source
    if using_local:
        await local_camera_service.start(room_id)
        recog_url = f"{settings.MEDIAMTX_RTSP_URL}/{room_id}"
        logger.info(f"Local camera started for room {room_id}, recognition URL: {recog_url}")

        # Wait for the RTSP stream to appear in mediamtx before telling the
        # mobile app to start WebRTC — avoids 503 on first offer.
        # In external mode (dev-stream.sh), the stream might not be pushing
        # yet, so send a "waiting" message and poll until it appears.
        stream_ready = False
        for _ in range(120):  # up to 60 seconds (120 × 0.5s)
            if await webrtc_service.check_path_exists(room_id):
                stream_ready = True
                break
            # Let the mobile app know we're waiting for the camera
            if not stream_ready and local_camera_service.is_external:
                await websocket.send_json({
                    "type": "waiting",
                    "message": "Waiting for camera stream — start dev-stream.sh",
                })
            await asyncio.sleep(0.5)

        if not stream_ready:
            logger.warning(f"Stream not available in mediamtx for room {room_id} after 60s")
    else:
        # Start recognition pipeline in the background (use high-res stream if configured)
        recog_url = settings.RECOGNITION_RTSP_URL or rtsp_url
        # In push mode (RPi -> mediamtx), pull frames from mediamtx's internal RTSP
        if not recog_url:
            recog_url = f"{settings.MEDIAMTX_RTSP_URL}/{room_id}"
            logger.info(f"Recognition: push mode — pulling frames from mediamtx at {recog_url}")

    # Send connected message — tells the mobile app to start WebRTC.
    await websocket.send_json(
        {
            "type": "connected",
            "schedule_id": schedule_id,
            "room_id": room_id,
            "mode": "webrtc",
            "detection_source": settings.DETECTION_SOURCE,
            "stream_fps": settings.STREAM_FPS,
            "stream_resolution": f"{settings.STREAM_WIDTH}x{settings.STREAM_HEIGHT}",
        }
    )

    recog_ok = await recognition_service.start(room_id, recog_url, viewer_id)
    if not recog_ok:
        logger.warning("Recognition service failed to start — WebRTC stream will have no overlays")

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

    # --- Push fused track metadata at 30 FPS ---
    FUSED_INTERVAL = 1.0 / 30.0  # 33ms for 30 FPS
    last_fused_send = 0.0
    fused_seq = 0
    last_update_seq = track_fusion_service.get_update_seq(room_id)
    last_heartbeat = _time.time()
    last_recog_check = _time.time()
    last_recog_seq = 0
    last_recog_feed_seq = 0  # track when we last fed recognition results into fusion

    try:
        while not stop_event.is_set():
            now = _time.time()

            # Periodically check if recognition service has stalled
            if now - last_recog_check > 10.0:
                current_recog_seq = track_fusion_service.get_update_seq(room_id)
                if current_recog_seq == last_recog_seq and current_recog_seq > 0:
                    logger.warning(f"Recognition service appears stalled for room {room_id}, restarting")
                    await recognition_service.stop(room_id, viewer_id)
                    await recognition_service.start(room_id, recog_url, viewer_id)
                last_recog_seq = current_recog_seq
                last_recog_check = now

            # Feed recognition results (InsightFace SCRFD, 2 FPS) into the
            # track fusion service for bounding boxes + identity.  Works for
            # both local-camera mode (Reolink via mediamtx) and edge mode.
            # MediaPipe BlazeFace short-range fails at CCTV distance (>2 m),
            # so InsightFace is the primary detection source for all modes.
            if not edge_relay_manager.has_edge_device(room_id):
                recog_result = recognition_service.get_latest_detections(room_id)
                if recog_result is not None:
                    det_dicts, recog_seq, fw, fh = recog_result
                    if recog_seq > last_recog_feed_seq and det_dicts:
                        last_recog_feed_seq = recog_seq

                        # Enrich names via cache before pushing identity
                        det_objects = recognition_service.get_detections_objects(room_id)
                        det_dicts = _enrich_and_cache(det_dicts, det_objects, SessionLocal)

                        # Assign stable track IDs via IoU matching
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
                        track_fusion_service.update_from_edge(
                            room_id, edge_dets, fw, fh,
                        )
                        # Push identity for recognized faces (only if name is available)
                        for tid, det in tracked:
                            if det.get("user_id") and det.get("name"):
                                track_fusion_service.update_identity(
                                    room_id,
                                    tid,
                                    det["user_id"],
                                    det.get("name", ""),
                                    det.get("student_id", ""),
                                    det.get("similarity", 0.0),
                                )

            elapsed = now - last_fused_send

            if elapsed >= FUSED_INTERVAL:
                # Only predict when no edge update arrived since the last tick
                # to avoid double prediction (update_from_edge already does predict+update)
                current_seq = track_fusion_service.get_update_seq(room_id)
                if current_seq == last_update_seq:
                    track_fusion_service.predict(room_id, dt=min(elapsed, 0.1))
                last_update_seq = current_seq

                tracks = track_fusion_service.get_tracks(room_id)
                fw, fh = track_fusion_service.get_room_dimensions(room_id)
                fused_seq += 1

                if tracks:
                    message = {
                        "type": "fused_tracks",
                        "room_id": room_id,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "seq": fused_seq,
                        "frame_width": fw,
                        "frame_height": fh,
                        "tracks": tracks,
                    }
                    await websocket.send_json(message)

                last_fused_send = now

            if now - last_heartbeat > 5.0:
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.now(UTC).isoformat(),
                })
                last_heartbeat = now

            await asyncio.sleep(0.01)

    except WebSocketDisconnect:
        logger.info(f"Live stream WS disconnected (WebRTC): viewer={viewer_id}")
    except Exception as exc:
        logger.error(f"Live stream WS error (WebRTC, viewer={viewer_id}): {exc}")
    finally:
        stop_event.set()
        receive_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await receive_task

        await edge_relay_manager.unregister_mobile(room_id, websocket)
        if using_local:
            await local_camera_service.stop()
        await recognition_service.stop(room_id, viewer_id)
        track_fusion_service.cleanup_room(room_id)
        _recognition_tracker.cleanup(room_id)

        if websocket.client_state == WebSocketState.CONNECTED:
            with contextlib.suppress(Exception):
                await websocket.close()


# ---------------------------------------------------------------------------
# Status endpoint
# ---------------------------------------------------------------------------


@router.get("/status")
async def stream_status():
    return {
        "success": True,
        "data": {
            "mode": "webrtc",
            "detection_source": settings.DETECTION_SOURCE,
            "stream_fps": settings.STREAM_FPS,
            "stream_resolution": f"{settings.STREAM_WIDTH}x{settings.STREAM_HEIGHT}",
        },
    }
