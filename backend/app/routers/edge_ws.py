"""
Edge WebSocket Router

WebSocket endpoint for Raspberry Pi edge devices to push real-time
face detection bounding boxes to the backend, which relays them to
mobile clients.

Protocol:
    Edge -> VPS:
        { "type": "edge_detections", "detections": [...], "timestamp": "..." }
        { "type": "ping" }

    VPS -> Edge:
        { "type": "pong" }
"""

import contextlib

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.config import logger
from app.services.edge_relay_service import edge_relay_manager

router = APIRouter()


@router.websocket("/ws")
async def edge_websocket(
    websocket: WebSocket,
    room_id: str = Query(...),
):
    """
    WebSocket endpoint for edge devices.

    Query params:
        room_id: The room this edge device is monitoring.

    Message types (edge -> VPS):
        - edge_detections: bounding box data from MediaPipe
        - ping: keepalive

    On disconnect or error, the edge device is automatically unregistered.
    """
    await websocket.accept()
    await edge_relay_manager.register_edge(room_id, websocket)

    logger.info(f"Edge WS: device connected for room {room_id}")

    try:
        while True:
            message = await websocket.receive_json()

            if not isinstance(message, dict):
                continue

            msg_type = message.get("type")

            if msg_type == "edge_detections":
                await edge_relay_manager.relay_edge_detections(room_id, message)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"Edge WS: device disconnected for room {room_id}")
    except Exception as exc:
        logger.error(f"Edge WS: error for room {room_id}: {exc}")
    finally:
        await edge_relay_manager.unregister_edge(room_id)

        if websocket.client_state == WebSocketState.CONNECTED:
            with contextlib.suppress(Exception):
                await websocket.close()
