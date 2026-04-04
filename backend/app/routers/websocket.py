"""
WebSocket manager — direct broadcast with optional Redis pub/sub for multi-worker.

Message types:
  - frame_update:        Per-frame tracking data at WS_BROADCAST_FPS (~10fps)
  - attendance_summary:  Periodic attendance state (every 5-10s)
  - check_in:            Student check-in event
  - early_leave:         Early leave detection
  - early_leave_return:  Student return after early leave
  - scan_result:         Legacy scan result (backward compatibility)
"""

import asyncio
import json
import logging
import os
from collections import defaultdict

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from app.config import settings
from app.utils.security import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """WebSocket connection manager with optional Redis pub/sub backing."""

    def __init__(self):
        self._attendance_clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._alert_clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._redis_subscriber_task: asyncio.Task | None = None

    # ── Client management ────────────────────────────────────────

    async def add_attendance_client(self, schedule_id: str, ws: WebSocket):
        await ws.accept()
        self._attendance_clients[schedule_id].add(ws)
        logger.debug("WS client added for schedule %s (total: %d)",
                      schedule_id, len(self._attendance_clients[schedule_id]))

    def remove_attendance_client(self, schedule_id: str, ws: WebSocket):
        self._attendance_clients[schedule_id].discard(ws)

    async def add_alert_client(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self._alert_clients[user_id].add(ws)

    def remove_alert_client(self, user_id: str, ws: WebSocket):
        self._alert_clients[user_id].discard(ws)

    # ── Broadcasting ─────────────────────────────────────────────

    async def broadcast_attendance(self, schedule_id: str, data: dict):
        """Send data to all local clients for a schedule, then publish to Redis."""
        dead = []
        for ws in list(self._attendance_clients.get(schedule_id, set())):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._attendance_clients[schedule_id].discard(ws)

        # Publish to Redis for multi-worker fanout
        await self._redis_publish(schedule_id, data)

    async def broadcast_alert(self, user_id: str, data: dict):
        dead = []
        for ws in list(self._alert_clients.get(user_id, set())):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._alert_clients[user_id].discard(ws)

        # Publish to Redis for multi-worker fanout
        await self._redis_publish_alert(user_id, data)

    async def _redis_publish_alert(self, user_id: str, data: dict) -> None:
        """Publish alert to Redis channel for other workers."""
        channel = f"{settings.REDIS_WS_CHANNEL}:alert:{user_id}"
        try:
            from app.redis_client import get_redis

            r = await get_redis()
            enriched = {**data, "origin_pid": os.getpid(), "_alert_user_id": user_id}
            payload = json.dumps(enriched, default=str)
            await r.publish(channel, payload)
        except Exception as e:
            logger.warning("Redis alert publish failed for %s: %s", user_id, e)

    async def broadcast_scan_result(self, schedule_id: str, detections: list[dict],
                                     present_count: int, total_enrolled: int,
                                     absent: list[str], early_leave: list[str]):
        """Legacy scan_result broadcast (backward compatibility)."""
        await self.broadcast_attendance(schedule_id, {
            "type": "scan_result",
            "schedule_id": schedule_id,
            "detections": detections,
            "present_count": present_count,
            "total_enrolled": total_enrolled,
            "absent": absent,
            "early_leave": early_leave,
        })

    # ── Redis pub/sub (multi-worker support) ─────────────────────

    async def _redis_publish(self, schedule_id: str, data: dict) -> None:
        """Publish message to Redis channel for other workers."""
        channel = f"{settings.REDIS_WS_CHANNEL}:{schedule_id}"
        try:
            from app.redis_client import get_redis

            r = await get_redis()
            enriched = {**data, "origin_pid": os.getpid()}
            payload = json.dumps(enriched, default=str)
            await r.publish(channel, payload)
        except Exception as e:
            logger.warning("Redis publish failed for %s: %s", channel, e)

    async def start_redis_subscriber(self) -> None:
        """Start background task to forward Redis messages to local WS clients."""
        if self._redis_subscriber_task is not None:
            return
        self._redis_subscriber_task = asyncio.create_task(
            self._redis_subscribe_loop(),
            name="ws-redis-subscriber",
        )

    async def _redis_subscribe_loop(self) -> None:
        """Subscribe to Redis ws_broadcast channels and forward to local clients."""
        from app.redis_client import get_redis

        while True:
            try:
                r = await get_redis()
                pubsub = r.pubsub()
                await pubsub.psubscribe(f"{settings.REDIS_WS_CHANNEL}:*")
                logger.info("WebSocket Redis subscriber started")

                async for message in pubsub.listen():
                    if message["type"] != "pmessage":
                        continue
                    try:
                        channel = message["channel"]
                        if isinstance(channel, bytes):
                            channel = channel.decode()
                        data = json.loads(message["data"])

                        # Skip messages originating from this worker (already delivered locally)
                        if data.get("origin_pid") == os.getpid():
                            continue

                        # Determine if this is an alert or attendance channel
                        # Alert channels: ws_broadcast:alert:{user_id}
                        # Attendance channels: ws_broadcast:{schedule_id}
                        parts = channel.split(":")
                        if len(parts) >= 3 and parts[-2] == "alert":
                            # Alert message — forward to alert clients
                            user_id = parts[-1]
                            dead = []
                            for ws in list(self._alert_clients.get(user_id, set())):
                                try:
                                    await ws.send_json(data)
                                except Exception:
                                    dead.append(ws)
                            for ws in dead:
                                self._alert_clients[user_id].discard(ws)
                        else:
                            # Attendance message — forward to attendance clients
                            schedule_id = parts[-1]
                            dead = []
                            for ws in list(self._attendance_clients.get(schedule_id, set())):
                                try:
                                    await ws.send_json(data)
                                except Exception:
                                    dead.append(ws)
                            for ws in dead:
                                self._attendance_clients[schedule_id].discard(ws)

                    except Exception:
                        logger.debug("Failed to process Redis WS message", exc_info=True)

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Redis WS subscriber disconnected, reconnecting...")
                await asyncio.sleep(1)


ws_manager = ConnectionManager()


# IMPORTANT: Specific routes MUST be declared before the catch-all /{user_id}.
# FastAPI matches WebSocket routes in declaration order.


@router.websocket("/attendance/{schedule_id}")
async def attendance_websocket(websocket: WebSocket, schedule_id: str):
    """Real-time attendance tracking WebSocket for a schedule."""
    token = websocket.query_params.get("token")
    if token is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    try:
        verify_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await ws_manager.add_attendance_client(schedule_id, websocket)

    # Trigger on-demand pipeline startup so bounding boxes appear immediately
    # instead of waiting up to 30s for the next scheduler tick.
    ensure_fn = getattr(websocket.app.state, "ensure_pipeline_running", None)
    if ensure_fn is not None:
        asyncio.ensure_future(ensure_fn(schedule_id))

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.warning("Unexpected error on attendance WS for schedule %s", schedule_id, exc_info=True)
    finally:
        ws_manager.remove_attendance_client(schedule_id, websocket)


@router.websocket("/alerts/{user_id}")
async def alerts_websocket(websocket: WebSocket, user_id: str):
    """Early-leave and notification alerts for a specific user."""
    token = websocket.query_params.get("token")
    if token is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    try:
        payload = verify_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    token_user_id = payload.get("user_id")
    if token_user_id != user_id:
        await websocket.close(code=4003, reason="Forbidden")
        return

    await ws_manager.add_alert_client(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.warning("Unexpected error on alert WS for user %s", user_id, exc_info=True)
    finally:
        ws_manager.remove_alert_client(user_id, websocket)


@router.websocket("/{user_id}")
async def general_websocket(websocket: WebSocket, user_id: str):
    """General-purpose notification WebSocket for the admin portal.
    MUST be declared last — catch-all route."""
    token = websocket.query_params.get("token")
    if token is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    try:
        payload = verify_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    token_user_id = payload.get("user_id")
    if token_user_id != user_id:
        await websocket.close(code=4003, reason="Forbidden")
        return

    await ws_manager.add_alert_client(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.warning("Unexpected error on general WS for user %s", user_id, exc_info=True)
    finally:
        ws_manager.remove_alert_client(user_id, websocket)
