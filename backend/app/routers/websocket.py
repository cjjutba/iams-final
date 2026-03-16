# backend/app/routers/websocket.py
"""
WebSocket Broadcaster — Multi-channel real-time delivery.

Channels:
- /ws/attendance/{schedule_id}  — Live attendance updates
- /ws/alerts/{user_id}          — Early-leave alerts, notifications
- /ws/health                    — System health metrics
"""
import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.stream_bus import (
    STREAM_ALERTS,
    STREAM_ATTENDANCE,
    get_stream_bus,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class BroadcastManager:
    """Manages WebSocket connections and broadcasts from Redis Streams."""

    def __init__(self):
        # schedule_id -> set of WebSocket connections
        self.attendance_clients: dict[str, set[WebSocket]] = {}
        # user_id -> set of WebSocket connections
        self.alert_clients: dict[str, set[WebSocket]] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start consuming Redis Streams and broadcasting to connected clients."""
        self._running = True
        self._task = asyncio.create_task(self._broadcast_loop())
        logger.info("[broadcaster] Started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    # ── Connection management ─────────────────────────────────

    def add_attendance_client(self, schedule_id: str, ws: WebSocket):
        self.attendance_clients.setdefault(schedule_id, set()).add(ws)

    def remove_attendance_client(self, schedule_id: str, ws: WebSocket):
        if schedule_id in self.attendance_clients:
            self.attendance_clients[schedule_id].discard(ws)

    def add_alert_client(self, user_id: str, ws: WebSocket):
        self.alert_clients.setdefault(user_id, set()).add(ws)

    def remove_alert_client(self, user_id: str, ws: WebSocket):
        if user_id in self.alert_clients:
            self.alert_clients[user_id].discard(ws)

    # ── Broadcasting ──────────────────────────────────────────

    async def _broadcast_loop(self):
        bus = await get_stream_bus()
        group = "broadcaster"

        # We dynamically discover attendance streams
        await bus.ensure_group(STREAM_ALERTS, group)

        while self._running:
            try:
                # Discover attendance streams for active schedules
                r = bus.redis
                streams = {STREAM_ALERTS: ">"}
                async for key in r.scan_iter(match=b"stream:attendance:*"):
                    key_str = key.decode() if isinstance(key, bytes) else key
                    await bus.ensure_group(key_str, group)
                    streams[key_str] = ">"

                messages = await bus.consume_multiple(
                    streams=streams,
                    group=group,
                    consumer="broadcaster-1",
                    count=20,
                    block=500,
                )

                for stream, msg_id, data in messages:
                    if "attendance" in stream:
                        # Extract schedule_id from stream name
                        sid = stream.replace("stream:attendance:", "")
                        await self._send_to_attendance_clients(sid, data)
                    elif "alerts" in stream:
                        await self._send_alert(data)
                    await bus.ack(stream, group, msg_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[broadcaster] Error: {e}", exc_info=True)
                await asyncio.sleep(0.5)

    async def _send_to_attendance_clients(self, schedule_id: str, data: dict):
        clients = self.attendance_clients.get(schedule_id, set())
        msg = json.dumps({"type": "attendance_update", **data})
        dead = set()
        for ws in clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        clients -= dead

    async def _send_alert(self, data: dict):
        # Alerts go to specific users (faculty for the schedule, and the student)
        user_ids = data.get("notify_user_ids", [])
        msg = json.dumps({"type": "alert", **data})
        for uid in user_ids:
            clients = self.alert_clients.get(uid, set())
            dead = set()
            for ws in clients:
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.add(ws)
            clients -= dead


# Singleton
_manager: BroadcastManager | None = None


def get_broadcast_manager() -> BroadcastManager:
    global _manager
    if _manager is None:
        _manager = BroadcastManager()
    return _manager


# ── Endpoints ─────────────────────────────────────────────────


@router.websocket("/attendance/{schedule_id}")
async def attendance_websocket(websocket: WebSocket, schedule_id: str):
    await websocket.accept()
    manager = get_broadcast_manager()
    manager.add_attendance_client(schedule_id, websocket)
    logger.info(f"[ws] Attendance client connected for {schedule_id}")

    try:
        while True:
            # Keep connection alive, handle pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove_attendance_client(schedule_id, websocket)


@router.websocket("/alerts/{user_id}")
async def alerts_websocket(websocket: WebSocket, user_id: str):
    await websocket.accept()
    manager = get_broadcast_manager()
    manager.add_alert_client(user_id, websocket)
    logger.info(f"[ws] Alert client connected for {user_id}")

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove_alert_client(user_id, websocket)
