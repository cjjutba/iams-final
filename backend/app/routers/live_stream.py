"""
Live Stream Router

WebSocket endpoint for streaming annotated camera feed to the mobile app.
Faculty connects via WebSocket for a given schedule_id; the backend opens
the room's RTSP camera, runs face detection + recognition, and pushes
annotated JPEG frames as base64 JSON messages.

Message format sent to client:
    {
        "type": "frame",
        "data": "<base64-encoded JPEG>",
        "timestamp": "2026-02-16T10:30:00+00:00",
        "detections": [
            {
                "bbox": {"x": 100, "y": 50, "width": 80, "height": 100},
                "confidence": 0.95,
                "user_id": "uuid-or-null",
                "student_id": "21-A-02177",
                "name": "Christian Jutba",
                "similarity": 0.87
            }
        ]
    }
"""

import asyncio
import uuid as uuid_mod
from typing import Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.config import settings, logger
from app.database import SessionLocal
from app.repositories.schedule_repository import ScheduleRepository
from app.services.camera_config import get_camera_url
from app.services.live_stream_service import live_stream_service

router = APIRouter()

# Cache resolved student names so we don't hit the DB on every frame.
# Maps user_id -> (name, student_id). Cleared when the stream stops.
_name_cache: Dict[str, tuple] = {}


def _enrich_and_cache(detections_dicts: list, state) -> list:
    """
    Enrich detection dicts with cached student names.
    Only hits the DB for user_ids not yet in the cache.
    Returns the (potentially updated) detections list.
    """
    needs_lookup = [
        d for d in detections_dicts
        if d.get("user_id") and not d.get("name") and d["user_id"] not in _name_cache
    ]

    if needs_lookup:
        db = SessionLocal()
        try:
            live_stream_service.enrich_detections(state.last_detections, db)
            # Refresh dicts and populate cache
            for det in state.last_detections:
                if det.user_id and det.name:
                    _name_cache[det.user_id] = (det.name, det.student_id)
            detections_dicts = [d.to_dict() for d in state.last_detections]
        finally:
            db.close()

    # Apply cache to any dicts that are missing names
    for d in detections_dicts:
        uid = d.get("user_id")
        if uid and not d.get("name") and uid in _name_cache:
            d["name"], d["student_id"] = _name_cache[uid]

    return detections_dicts


@router.websocket("/{schedule_id}")
async def live_stream_ws(schedule_id: str, websocket: WebSocket):
    """
    Live stream WebSocket endpoint.

    Accepts a WebSocket connection, verifies the schedule exists, resolves the
    room's RTSP camera URL, then continuously pushes annotated frames to the
    client until disconnection.
    """
    # Generate a unique viewer ID for this connection
    viewer_id = str(uuid_mod.uuid4())

    # --- Validate schedule and resolve camera URL (need a DB session) ---
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

    # --- Accept the WebSocket connection ---
    await websocket.accept()
    logger.info(
        f"Live stream WS connected: viewer={viewer_id}, "
        f"schedule={schedule_id}, room={room_id}"
    )

    # Send initial metadata
    await websocket.send_json({
        "type": "connected",
        "schedule_id": schedule_id,
        "room_id": room_id,
        "stream_fps": settings.STREAM_FPS,
        "stream_resolution": f"{settings.STREAM_WIDTH}x{settings.STREAM_HEIGHT}",
    })

    # --- Start or join stream ---
    started = await live_stream_service.start_stream(room_id, rtsp_url, viewer_id)
    if not started:
        await websocket.send_json({
            "type": "error",
            "message": "Failed to open camera stream",
        })
        await websocket.close(code=4002, reason="Camera unavailable")
        return

    # --- Receive task: handle pings / close in a separate coroutine ---
    stop_event = asyncio.Event()

    async def _receive_loop():
        """Listen for client messages (ping, close) without blocking the send loop."""
        try:
            while not stop_event.is_set():
                msg = await websocket.receive_json()
                if isinstance(msg, dict):
                    msg_type = msg.get("type", "")
                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong"})
        except (WebSocketDisconnect, Exception):
            stop_event.set()

    receive_task = asyncio.create_task(_receive_loop())

    # --- Push frames to client ---
    # Poll interval: how often we check for a new frame from the capture loop.
    # This should be shorter than 1/FPS to minimise latency.
    poll_interval = 0.025  # 25ms = up to 40 checks/sec
    last_seq = -1

    try:
        while not stop_event.is_set():
            # Get the latest frame (pre-computed base64 + detection dicts)
            result = live_stream_service.get_latest(room_id)

            if result is not None:
                b64_jpeg, detections_dicts, timestamp, frame_seq = result

                # Only send if this is a NEW frame (avoid duplicates)
                if frame_seq != last_seq:
                    last_seq = frame_seq

                    # Enrich with cached names (DB lookup only for new user_ids)
                    state = live_stream_service._active_streams.get(room_id)
                    if state and any(d.get("user_id") for d in detections_dicts):
                        detections_dicts = _enrich_and_cache(detections_dicts, state)

                    await websocket.send_json({
                        "type": "frame",
                        "data": b64_jpeg,
                        "timestamp": timestamp,
                        "detections": detections_dicts,
                    })

            # Short sleep — yields to the event loop and limits poll rate.
            # No additional throttle needed because we only send NEW frames
            # (gated by frame_seq), and the capture loop already throttles
            # to STREAM_FPS.
            await asyncio.sleep(poll_interval)

    except WebSocketDisconnect:
        logger.info(f"Live stream WS disconnected: viewer={viewer_id}")
    except Exception as exc:
        logger.error(f"Live stream WS error (viewer={viewer_id}): {exc}")
    finally:
        stop_event.set()
        receive_task.cancel()
        try:
            await receive_task
        except (asyncio.CancelledError, Exception):
            pass

        # Remove viewer and potentially stop the stream
        await live_stream_service.stop_stream(room_id, viewer_id)
        # Ensure the socket is closed
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass


@router.get("/status")
async def stream_status():
    """
    Get live stream system status.

    Returns active rooms and viewer counts.
    """
    active_rooms = live_stream_service.get_active_rooms()
    rooms = []
    for rid in active_rooms:
        rooms.append({
            "room_id": rid,
            "viewers": live_stream_service.get_viewer_count(rid),
        })

    return {
        "success": True,
        "data": {
            "active_streams": len(active_rooms),
            "rooms": rooms,
            "stream_fps": settings.STREAM_FPS,
            "stream_resolution": f"{settings.STREAM_WIDTH}x{settings.STREAM_HEIGHT}",
        },
    }
