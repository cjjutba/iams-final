"""
WebSocket Router

Real-time communication for attendance updates and early-leave alerts.
"""

import contextlib
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import logger

router = APIRouter()


class ConnectionManager:
    """
    WebSocket connection manager

    Manages active WebSocket connections for real-time updates.
    """

    def __init__(self):
        # Active connections: user_id → WebSocket
        self.active_connections: dict[str, WebSocket] = {}

        # Schedule subscriptions: schedule_id → set of user_ids
        self.schedule_connections: dict[str, set[str]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        """
        Accept and store WebSocket connection

        Args:
            user_id: User UUID
            websocket: WebSocket connection
        """
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket connected: user {user_id}")

    def register_for_schedule(self, user_id: str, schedule_id: str):
        """
        Register user to receive updates for a specific schedule

        Args:
            user_id: User UUID
            schedule_id: Schedule UUID
        """
        if schedule_id not in self.schedule_connections:
            self.schedule_connections[schedule_id] = set()

        self.schedule_connections[schedule_id].add(user_id)
        logger.debug(f"User {user_id} subscribed to schedule {schedule_id}")

    def unregister_from_schedule(self, user_id: str, schedule_id: str):
        """
        Unregister user from schedule updates

        Args:
            user_id: User UUID
            schedule_id: Schedule UUID
        """
        if schedule_id in self.schedule_connections:
            self.schedule_connections[schedule_id].discard(user_id)

            # Clean up empty sets
            if not self.schedule_connections[schedule_id]:
                del self.schedule_connections[schedule_id]

    def disconnect(self, user_id: str):
        """
        Remove WebSocket connection

        Args:
            user_id: User UUID
        """
        if user_id in self.active_connections:
            del self.active_connections[user_id]

            # Clean up schedule subscriptions
            for schedule_id in list(self.schedule_connections.keys()):
                self.schedule_connections[schedule_id].discard(user_id)
                if not self.schedule_connections[schedule_id]:
                    del self.schedule_connections[schedule_id]

            logger.info(f"WebSocket disconnected: user {user_id}")

    async def send_personal(self, user_id: str, message: dict):
        """
        Send message to specific user

        Args:
            user_id: User UUID
            message: Message dictionary
        """
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
                logger.debug(f"Message sent to user {user_id}: {message.get('event')}")
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
                self.disconnect(user_id)

    async def broadcast_to_schedule(self, schedule_id: str, message: dict):
        """
        Broadcast message to all users subscribed to a schedule

        Sends the message to all users who have registered for updates
        for this specific schedule (faculty and enrolled students).

        Args:
            schedule_id: Schedule UUID
            message: Message dictionary
        """
        if schedule_id not in self.schedule_connections:
            logger.debug(f"No subscribers for schedule {schedule_id}")
            return

        subscribers = self.schedule_connections[schedule_id]
        sent_count = 0
        failed_count = 0

        for user_id in list(subscribers):  # Use list() to avoid modification during iteration
            if user_id in self.active_connections:
                try:
                    await self.active_connections[user_id].send_json(message)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to broadcast to user {user_id}: {e}")
                    self.disconnect(user_id)
                    failed_count += 1

        logger.info(
            f"Broadcast to schedule {schedule_id} ({message.get('event')}): {sent_count} sent, {failed_count} failed"
        )

    # ------ Redis pub/sub for cross-worker broadcast ------

    async def start_redis_listener(self):
        """Subscribe to Redis pub/sub for cross-worker broadcast."""
        import asyncio

        from app.config import settings
        from app.redis_client import get_redis

        r = await get_redis()
        self._pubsub = r.pubsub()
        await self._pubsub.subscribe(settings.REDIS_WS_CHANNEL)
        self._listener_task = asyncio.create_task(self._listen_redis())
        logger.info(f"Redis WS listener subscribed to channel: {settings.REDIS_WS_CHANNEL}")

    async def _listen_redis(self):
        """Process messages from Redis and broadcast to local WebSocket clients."""
        from app.config import settings

        while True:
            try:
                async for message in self._pubsub.listen():
                    if message["type"] in ("message", b"message"):
                        try:
                            raw = message["data"]
                            # decode_responses=False so data arrives as bytes
                            if isinstance(raw, bytes):
                                raw = raw.decode("utf-8")
                            data = json.loads(raw)
                            await self._broadcast_batch_results(data)
                        except Exception:
                            logger.exception("Redis WS listener error")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Redis WS listener connection lost, reconnecting...")
                await asyncio.sleep(1)
                try:
                    await self._pubsub.subscribe(settings.REDIS_WS_CHANNEL)
                except Exception:
                    logger.exception("Redis WS listener re-subscribe failed")

    async def _broadcast_batch_results(self, data: dict):
        """Send batch recognition results to relevant WebSocket clients."""
        results = data.get("results", [])
        room_id = data.get("room_id")

        # Send individual check-in notifications to matched students
        for result in results:
            user_id = result.get("user_id")
            if user_id and user_id in self.active_connections:
                await self.send_personal(
                    user_id,
                    {
                        "event": "student_checked_in",
                        "data": {
                            "user_id": user_id,
                            "room_id": room_id,
                            "confidence": result.get("confidence"),
                            "timestamp": data.get("timestamp"),
                        },
                    },
                )

        # Broadcast attendance update to all schedule subscribers
        # (faculty watching this room)
        for _schedule_id, user_ids in self.schedule_connections.items():
            for uid in list(user_ids):
                if uid in self.active_connections:
                    with contextlib.suppress(Exception):
                        await self.send_personal(
                            uid,
                            {
                                "event": "attendance_update",
                                "data": {
                                    "room_id": room_id,
                                    "results": results,
                                    "processing_time_ms": data.get("processing_time_ms"),
                                    "batch_size": data.get("batch_size"),
                                },
                            },
                        )

    async def stop_redis_listener(self):
        """Stop the Redis pub/sub listener."""
        import asyncio
        import contextlib

        if hasattr(self, "_listener_task") and self._listener_task:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task
        if hasattr(self, "_pubsub") and self._pubsub:
            await self._pubsub.unsubscribe()
        logger.info("Redis WS listener stopped")

    # ------ Connection info helpers ------

    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)

    def get_schedule_subscriber_count(self, schedule_id: str) -> int:
        """
        Get number of subscribers for a schedule

        Args:
            schedule_id: Schedule UUID

        Returns:
            Number of subscribed users
        """
        return len(self.schedule_connections.get(schedule_id, set()))


# Global connection manager
manager = ConnectionManager()


@router.websocket("/{user_id}")
async def websocket_endpoint(user_id: str, websocket: WebSocket):
    """
    **WebSocket Endpoint**

    Real-time communication channel for attendance updates and alerts.

    **Connection:**
    ```javascript
    const ws = new WebSocket(`ws://localhost:8000/api/v1/ws/${userId}`);
    ```

    **Message Format:**
    ```json
    {
      "event": "early_leave" | "attendance_update" | "session_start" | "session_end",
      "data": {...}
    }
    ```

    **Events:**

    1. **early_leave**: Student left class early
    ```json
    {
      "event": "early_leave",
      "data": {
        "student_id": "uuid",
        "student_name": "John Doe",
        "schedule_id": "uuid",
        "detected_at": "2024-01-15T10:30:00Z",
        "consecutive_misses": 3
      }
    }
    ```

    2. **attendance_update**: Attendance status changed
    ```json
    {
      "event": "attendance_update",
      "data": {
        "student_id": "uuid",
        "schedule_id": "uuid",
        "status": "present",
        "check_in_time": "2024-01-15T08:00:00Z"
      }
    }
    ```

    3. **session_start**: Class session started
    ```json
    {
      "event": "session_start",
      "data": {
        "schedule_id": "uuid",
        "start_time": "2024-01-15T08:00:00Z"
      }
    }
    ```

    4. **session_end**: Class session ended
    ```json
    {
      "event": "session_end",
      "data": {
        "schedule_id": "uuid",
        "end_time": "2024-01-15T10:00:00Z",
        "summary": {...}
      }
    }
    ```

    **Usage (Client):**
    ```javascript
    const ws = new WebSocket(`ws://localhost:8000/api/v1/ws/${userId}`);

    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('Received:', message.event, message.data);

      if (message.event === 'early_leave') {
        // Show alert to faculty
        showAlert(`Student ${message.data.student_name} left early`);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
    };
    ```

    **Authentication:**
    - No token validation for MVP (trusted network)
    - In production: Verify JWT token before accepting connection

    Args:
        user_id: User UUID (from URL path)
        websocket: WebSocket connection
    """
    await manager.connect(user_id, websocket)

    try:
        # Send welcome message
        await websocket.send_json(
            {
                "event": "connected",
                "data": {"user_id": user_id, "timestamp": str(__import__("datetime").datetime.now())},
            }
        )

        # Keep connection alive and listen for incoming messages
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received from {user_id}: {data}")

            # Handle application-level ping/pong for heartbeat
            try:
                message = json.loads(data)
                if message.get("event") == "ping":
                    await websocket.send_json({"event": "pong", "data": {}})
                    continue
            except (json.JSONDecodeError, TypeError):
                pass

    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(user_id)


@router.get("/status")
async def websocket_status():
    """
    **WebSocket Status**

    Get WebSocket server status and connection count.

    Returns:
        dict: Status information
    """
    return {"success": True, "data": {"active_connections": manager.get_connection_count(), "status": "running"}}
