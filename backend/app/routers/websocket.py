"""Simple WebSocket manager — direct broadcast, no Redis Streams."""
import logging
from collections import defaultdict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """In-memory WebSocket connection manager."""

    def __init__(self):
        self._attendance_clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._alert_clients: dict[str, set[WebSocket]] = defaultdict(set)

    async def add_attendance_client(self, schedule_id: str, ws: WebSocket):
        await ws.accept()
        self._attendance_clients[schedule_id].add(ws)

    def remove_attendance_client(self, schedule_id: str, ws: WebSocket):
        self._attendance_clients[schedule_id].discard(ws)

    async def add_alert_client(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self._alert_clients[user_id].add(ws)

    def remove_alert_client(self, user_id: str, ws: WebSocket):
        self._alert_clients[user_id].discard(ws)

    async def broadcast_attendance(self, schedule_id: str, data: dict):
        dead = []
        for ws in self._attendance_clients.get(schedule_id, set()):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._attendance_clients[schedule_id].discard(ws)

    async def broadcast_alert(self, user_id: str, data: dict):
        dead = []
        for ws in self._alert_clients.get(user_id, set()):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._alert_clients[user_id].discard(ws)

    async def broadcast_scan_result(self, schedule_id: str, detections: list[dict],
                                     present_count: int, total_enrolled: int,
                                     absent: list[str], early_leave: list[str]):
        await self.broadcast_attendance(schedule_id, {
            "type": "scan_result",
            "schedule_id": schedule_id,
            "detections": detections,
            "present_count": present_count,
            "total_enrolled": total_enrolled,
            "absent": absent,
            "early_leave": early_leave,
        })


ws_manager = ConnectionManager()


@router.websocket("/attendance/{schedule_id}")
async def attendance_websocket(websocket: WebSocket, schedule_id: str):
    await ws_manager.add_attendance_client(schedule_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.remove_attendance_client(schedule_id, websocket)


@router.websocket("/alerts/{user_id}")
async def alerts_websocket(websocket: WebSocket, user_id: str):
    await ws_manager.add_alert_client(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.remove_alert_client(user_id, websocket)
