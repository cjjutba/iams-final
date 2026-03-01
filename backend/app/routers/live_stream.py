"""
Live Stream Router

WebSocket endpoint for live camera streaming to the mobile app.

Supports two modes controlled by ``USE_HLS_STREAMING``:

**HLS mode (default):**
    Video is delivered via FFmpeg → HLS segments (see hls.py router).
    This WebSocket only pushes lightweight detection metadata (~200 bytes):
        { "type": "detections", "timestamp": "...", "detections": [...] }
    The ``connected`` message includes ``hls_url`` so the client knows
    where to point its native video player.

**Legacy mode (USE_HLS_STREAMING=false):**
    Frames are JPEG-encoded, base64'd, and sent as ``type: "frame"``
    messages (the original behaviour, ~50-100KB per frame).
"""

import asyncio
import time as _time
import threading as _threading
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.config import settings, logger
from app.database import SessionLocal
from app.repositories.schedule_repository import ScheduleRepository
from app.services.camera_config import get_camera_url
from app.services.recognition_service import recognition_service
from app.services.hls_service import hls_service

router = APIRouter()


class NameCache:
    """Thread-safe student name cache with per-entry TTL."""

    def __init__(self, ttl_seconds: float = 300.0):
        self._lock = _threading.Lock()
        # uid → ((name, student_id), inserted_at_monotonic)
        self._store: Dict[str, tuple] = {}
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
        d for d in detections_dicts
        if d.get("user_id") and not d.get("name") and _name_cache.get(d["user_id"]) is None
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
    camera RTSP URL, then either:
    - (HLS mode) starts HLS + recognition and pushes detection metadata
    - (Legacy mode) pushes annotated JPEG frames
    """
    viewer_id = str(uuid_mod.uuid4())

    # --- Validate schedule and resolve camera URL ---
    db = SessionLocal()
    try:
        schedule_repo = ScheduleRepository(db)
        schedule = schedule_repo.get_by_id(schedule_id)

        if schedule is None:
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "message": f"Schedule not found: {schedule_id}",
            })
            await websocket.close(code=4004, reason="Schedule not found")
            return

        room_id = str(schedule.room_id)
        rtsp_url = get_camera_url(room_id, db)

        if rtsp_url is None:
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "message": "No camera configured for this room",
            })
            await websocket.close(code=4003, reason="No camera configured")
            return

    except Exception as exc:
        logger.error(f"Live stream setup error: {exc}")
        try:
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "message": "Internal server error during setup",
            })
            await websocket.close(code=4500, reason="Internal error")
        except Exception:
            pass
        return
    finally:
        db.close()

    # --- Accept WebSocket ---
    await websocket.accept()
    if settings.USE_WEBRTC_STREAMING:
        _mode_label = "webrtc"
    elif settings.USE_HLS_STREAMING:
        _mode_label = "hls"
    else:
        _mode_label = "legacy"
    logger.info(
        f"Live stream WS connected: viewer={viewer_id}, "
        f"schedule={schedule_id}, room={room_id}, "
        f"mode={_mode_label}"
    )

    if settings.USE_WEBRTC_STREAMING:
        await _webrtc_mode(websocket, viewer_id, schedule_id, room_id, rtsp_url)
    elif settings.USE_HLS_STREAMING:
        await _hls_mode(websocket, viewer_id, schedule_id, room_id, rtsp_url)
    else:
        await _legacy_mode(websocket, viewer_id, schedule_id, room_id, rtsp_url)


# ---------------------------------------------------------------------------
# HLS mode: metadata-only WebSocket
# ---------------------------------------------------------------------------

async def _hls_mode(
    websocket: WebSocket,
    viewer_id: str,
    schedule_id: str,
    room_id: str,
    rtsp_url: str,
):
    """
    HLS mode: start FFmpeg HLS stream + recognition pipeline,
    then push only detection metadata over WebSocket.
    """
    # Start HLS stream
    hls_ok = await hls_service.start_stream(room_id, rtsp_url, viewer_id)
    if not hls_ok:
        await websocket.send_json({
            "type": "error",
            "message": "Failed to start HLS stream (is FFmpeg installed?)",
        })
        await websocket.close(code=4002, reason="HLS unavailable")
        return

    # Start recognition pipeline (use high-res stream if configured)
    recog_url = settings.RECOGNITION_RTSP_URL or rtsp_url
    recog_ok = await recognition_service.start(room_id, recog_url, viewer_id)
    if not recog_ok:
        logger.warning("Recognition service failed to start — HLS video will stream without overlays")

    # Build HLS URL relative to API base
    hls_url = f"{settings.API_PREFIX}/hls/{room_id}/playlist.m3u8"

    # Send initial connected message with HLS URL
    await websocket.send_json({
        "type": "connected",
        "schedule_id": schedule_id,
        "room_id": room_id,
        "hls_url": hls_url,
        "stream_fps": settings.STREAM_FPS,
        "stream_resolution": f"{settings.STREAM_WIDTH}x{settings.STREAM_HEIGHT}",
        "mode": "hls",
    })

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

    # --- Push detection metadata ---
    poll_interval = 0.100  # 100ms = 10Hz, matching RECOGNITION_FPS
    last_seq = -1
    last_send_time = asyncio.get_event_loop().time()
    heartbeat_interval = 5.0  # send heartbeat every 5s even when no detections change
    stale_count = 0

    try:
        while not stop_event.is_set():
            now = asyncio.get_event_loop().time()
            result = recognition_service.get_latest_detections(room_id)

            if result is not None:
                detections_dicts, update_seq, det_w, det_h = result
                stale_count = 0

                if update_seq != last_seq:
                    last_seq = update_seq

                    # Enrich with cached names
                    if any(d.get("user_id") for d in detections_dicts):
                        det_objects = recognition_service.get_detections_objects(room_id)
                        detections_dicts = _enrich_and_cache(
                            detections_dicts, det_objects, SessionLocal
                        )

                    ts = datetime.now(timezone.utc).isoformat()
                    await websocket.send_json({
                        "type": "detections",
                        "timestamp": ts,
                        "detections": detections_dicts,
                        "detection_width": det_w,
                        "detection_height": det_h,
                    })
                    last_send_time = now

                elif (now - last_send_time) >= heartbeat_interval:
                    # Heartbeat keeps client connection alive
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    last_send_time = now
            else:
                # Recognition service not running for this room
                stale_count += 1
                if stale_count >= 100:  # ~10s of no recognition service (100 × 100ms)
                    logger.warning(
                        f"Live stream: recognition service gone for room {room_id}, "
                        "attempting restart"
                    )
                    recog_url = settings.RECOGNITION_RTSP_URL or rtsp_url
                    await recognition_service.start(room_id, recog_url, viewer_id)
                    stale_count = 0

                # Still send heartbeat
                if (now - last_send_time) >= heartbeat_interval:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    last_send_time = now

            await asyncio.sleep(poll_interval)

    except WebSocketDisconnect:
        logger.info(f"Live stream WS disconnected (HLS): viewer={viewer_id}")
    except Exception as exc:
        logger.error(f"Live stream WS error (HLS, viewer={viewer_id}): {exc}")
    finally:
        stop_event.set()
        receive_task.cancel()
        try:
            await receive_task
        except (asyncio.CancelledError, Exception):
            pass

        await hls_service.stop_stream(room_id, viewer_id)
        await recognition_service.stop(room_id, viewer_id)

        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass


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
    WebRTC signalling layer — this socket never touches hls_service.
    """
    # Start recognition pipeline (use high-res stream if configured)
    recog_url = settings.RECOGNITION_RTSP_URL or rtsp_url
    recog_ok = await recognition_service.start(room_id, recog_url, viewer_id)
    if not recog_ok:
        logger.warning("Recognition service failed to start — WebRTC stream will have no overlays")

    # Send initial connected message (no hls_url)
    await websocket.send_json({
        "type": "connected",
        "schedule_id": schedule_id,
        "room_id": room_id,
        "mode": "webrtc",
        "stream_fps": settings.STREAM_FPS,
        "stream_resolution": f"{settings.STREAM_WIDTH}x{settings.STREAM_HEIGHT}",
    })

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

    # --- Push detection metadata ---
    poll_interval = 0.100  # 100ms = 10Hz, matching RECOGNITION_FPS
    last_seq = -1
    last_send_time = asyncio.get_event_loop().time()
    heartbeat_interval = 5.0  # send heartbeat every 5s even when no detections change
    stale_count = 0

    try:
        while not stop_event.is_set():
            now = asyncio.get_event_loop().time()
            result = recognition_service.get_latest_detections(room_id)

            if result is not None:
                detections_dicts, update_seq, det_w, det_h = result
                stale_count = 0

                if update_seq != last_seq:
                    last_seq = update_seq

                    # Enrich with cached names
                    if any(d.get("user_id") for d in detections_dicts):
                        det_objects = recognition_service.get_detections_objects(room_id)
                        detections_dicts = _enrich_and_cache(
                            detections_dicts, det_objects, SessionLocal
                        )

                    ts = datetime.now(timezone.utc).isoformat()
                    await websocket.send_json({
                        "type": "detections",
                        "timestamp": ts,
                        "detections": detections_dicts,
                        "detection_width": det_w,
                        "detection_height": det_h,
                    })
                    last_send_time = now

                elif (now - last_send_time) >= heartbeat_interval:
                    # Heartbeat keeps client connection alive
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    last_send_time = now
            else:
                # Recognition service not running for this room
                stale_count += 1
                if stale_count >= 100:  # ~10s of no recognition service (100 × 100ms)
                    logger.warning(
                        f"Live stream: recognition service gone for room {room_id}, "
                        "attempting restart"
                    )
                    recog_url = settings.RECOGNITION_RTSP_URL or rtsp_url
                    await recognition_service.start(room_id, recog_url, viewer_id)
                    stale_count = 0

                # Still send heartbeat
                if (now - last_send_time) >= heartbeat_interval:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    last_send_time = now

            await asyncio.sleep(poll_interval)

    except WebSocketDisconnect:
        logger.info(f"Live stream WS disconnected (WebRTC): viewer={viewer_id}")
    except Exception as exc:
        logger.error(f"Live stream WS error (WebRTC, viewer={viewer_id}): {exc}")
    finally:
        stop_event.set()
        receive_task.cancel()
        try:
            await receive_task
        except (asyncio.CancelledError, Exception):
            pass

        await recognition_service.stop(room_id, viewer_id)

        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Legacy mode: base64 JPEG frames over WebSocket
# ---------------------------------------------------------------------------

async def _legacy_mode(
    websocket: WebSocket,
    viewer_id: str,
    schedule_id: str,
    room_id: str,
    rtsp_url: str,
):
    """
    Legacy mode: push annotated base64 JPEG frames (original behaviour).
    Kept for backward compatibility when USE_HLS_STREAMING=false.
    """
    from app.services.live_stream_service import live_stream_service

    # Send initial metadata
    await websocket.send_json({
        "type": "connected",
        "schedule_id": schedule_id,
        "room_id": room_id,
        "stream_fps": settings.STREAM_FPS,
        "stream_resolution": f"{settings.STREAM_WIDTH}x{settings.STREAM_HEIGHT}",
        "mode": "legacy",
    })

    # Start or join stream
    started = await live_stream_service.start_stream(room_id, rtsp_url, viewer_id)
    if not started:
        await websocket.send_json({
            "type": "error",
            "message": "Failed to open camera stream",
        })
        await websocket.close(code=4002, reason="Camera unavailable")
        return

    # --- Receive task ---
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

    # --- Push frames ---
    poll_interval = 0.025
    last_seq = -1

    try:
        while not stop_event.is_set():
            result = live_stream_service.get_latest(room_id)

            if result is not None:
                b64_jpeg, detections_dicts, timestamp, frame_seq = result

                if frame_seq != last_seq:
                    last_seq = frame_seq

                    # Enrich with cached names
                    state = live_stream_service._active_streams.get(room_id)
                    if state and any(d.get("user_id") for d in detections_dicts):
                        det_objects = state.last_detections
                        detections_dicts = _enrich_and_cache(
                            detections_dicts, det_objects, SessionLocal
                        )

                    await websocket.send_json({
                        "type": "frame",
                        "data": b64_jpeg,
                        "timestamp": timestamp,
                        "detections": detections_dicts,
                    })

            await asyncio.sleep(poll_interval)

    except WebSocketDisconnect:
        logger.info(f"Live stream WS disconnected (legacy): viewer={viewer_id}")
    except Exception as exc:
        logger.error(f"Live stream WS error (legacy, viewer={viewer_id}): {exc}")
    finally:
        stop_event.set()
        receive_task.cancel()
        try:
            await receive_task
        except (asyncio.CancelledError, Exception):
            pass

        await live_stream_service.stop_stream(room_id, viewer_id)

        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Status endpoint
# ---------------------------------------------------------------------------

@router.get("/status")
async def stream_status():
    """Get live stream system status (works for both modes)."""
    if settings.USE_HLS_STREAMING:
        from app.services.hls_service import hls_service
        active_rooms = hls_service.get_active_rooms()
        rooms = [
            {
                "room_id": rid,
                "viewers": hls_service.get_viewer_count(rid),
            }
            for rid in active_rooms
        ]
        mode = "hls"
    else:
        from app.services.live_stream_service import live_stream_service
        active_rooms = live_stream_service.get_active_rooms()
        rooms = [
            {
                "room_id": rid,
                "viewers": live_stream_service.get_viewer_count(rid),
            }
            for rid in active_rooms
        ]
        mode = "legacy"

    return {
        "success": True,
        "data": {
            "mode": mode,
            "active_streams": len(active_rooms),
            "rooms": rooms,
            "stream_fps": settings.STREAM_FPS,
            "stream_resolution": f"{settings.STREAM_WIDTH}x{settings.STREAM_HEIGHT}",
        },
    }
