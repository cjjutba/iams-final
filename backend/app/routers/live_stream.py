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
from app.models.room import Room
from app.repositories.schedule_repository import ScheduleRepository
from app.services.track_fusion_service import get_track_fusion_engine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/{schedule_id}")
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
        # Use stream_key (e.g. "eb-226") as the room identifier for track fusion,
        # since the RPi/detection workers use stream_key, not UUID
        room = db.query(Room).filter(Room.id == schedule.room_id).first()
        room_id = room.stream_key if room and room.stream_key else str(schedule.room_id)
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
            fw, fh = engine.get_frame_dims(room_id)

            # Send fused tracks
            msg = {
                "type": "fused_tracks",
                "room_id": room_id,
                "ts": int(time.time() * 1000),
                "frame_width": fw,
                "frame_height": fh,
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
