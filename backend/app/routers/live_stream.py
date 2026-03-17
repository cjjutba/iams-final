"""
Live Stream WebSocket — lightweight signaling for the mobile app.

Replaces the old fused_tracks WebSocket with a minimal endpoint that:
1. Sends a "connected" message so the mobile app starts WebRTC
2. Handles ping/pong keepalive
3. Sends pipeline state updates (detected counts) periodically

The actual video with bounding boxes is delivered via WebRTC from
the annotated mediamtx stream — this WebSocket only carries metadata.
"""

import asyncio
import json
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.config import logger, settings
from app.database import SessionLocal
from app.models.room import Room
from app.repositories.schedule_repository import ScheduleRepository

router = APIRouter()


@router.websocket("/{schedule_id}")
async def live_stream_ws(
    websocket: WebSocket,
    schedule_id: str,
    token: str = Query(default=""),
):
    """
    Live stream signaling WebSocket.

    Mobile connects here to:
    1. Get stream mode ("webrtc") and start WebRTC
    2. Receive periodic detection counts for the bottom panel
    """
    await websocket.accept()

    # Resolve schedule → room
    db: Session = SessionLocal()
    try:
        schedule_repo = ScheduleRepository(db)
        schedule = schedule_repo.get_by_id(schedule_id)
        if schedule is None:
            await websocket.send_json({"type": "error", "message": "Schedule not found"})
            await websocket.close()
            return

        room_id = str(schedule.room_id)
        room = db.query(Room).filter(Room.id == schedule.room_id).first()
        room_name = room.name if room else ""
    finally:
        db.close()

    # Send "connected" message — tells mobile to start WebRTC
    await websocket.send_json({
        "type": "connected",
        "schedule_id": schedule_id,
        "room_id": room_id,
        "mode": "webrtc",
        "detection_source": "composited",
        "stream_fps": settings.PIPELINE_FPS,
        "stream_resolution": f"{settings.PIPELINE_WIDTH}x{settings.PIPELINE_HEIGHT}",
    })

    logger.info(f"Live stream WS connected: schedule={schedule_id}, room={room_id}")

    try:
        # Import Redis here to avoid import errors if Redis isn't available
        import redis as redis_lib
        r = redis_lib.Redis.from_url(settings.REDIS_URL)
    except Exception:
        r = None

    try:
        while True:
            # Wait for client messages (ping) with a timeout for sending state updates
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                if raw == "ping":
                    await websocket.send_text("pong")
                    continue

                # Try to parse JSON messages
                try:
                    msg = json.loads(raw)
                    if msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Send pipeline state update every 5 seconds
                if r:
                    try:
                        state_raw = r.get(f"pipeline:{room_id}:state")
                        if state_raw:
                            state = json.loads(state_raw)
                            await websocket.send_json({
                                "type": "pipeline_state",
                                "total_tracks": state.get("total_tracks", 0),
                                "identified_count": state.get("identified_count", 0),
                                "identified_users": state.get("identified_users", []),
                            })
                    except Exception:
                        pass

    except WebSocketDisconnect:
        logger.debug(f"Live stream WS disconnected: schedule={schedule_id}")
    except Exception as e:
        logger.debug(f"Live stream WS error: {e}")
