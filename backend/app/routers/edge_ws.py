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
