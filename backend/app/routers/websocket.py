"""
WebSocket Router

Real-time communication for attendance updates and early-leave alerts.
"""

from typing import Dict, Set
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
        self.active_connections: Dict[str, WebSocket] = {}

        # Schedule subscriptions: schedule_id → set of user_ids
        self.schedule_connections: Dict[str, Set[str]] = {}

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
            f"Broadcast to schedule {schedule_id} ({message.get('event')}): "
            f"{sent_count} sent, {failed_count} failed"
        )

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
        await websocket.send_json({
            "event": "connected",
            "data": {
                "user_id": user_id,
                "timestamp": str(__import__('datetime').datetime.now())
            }
        })

        # Keep connection alive and listen for incoming messages
        while True:
            # Receive messages from client (optional, for heartbeat/ping)
            data = await websocket.receive_text()

            # Echo back (for testing/heartbeat)
            # In production, you might handle client commands here
            logger.debug(f"Received from {user_id}: {data}")

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
    return {
        "success": True,
        "data": {
            "active_connections": manager.get_connection_count(),
            "status": "running"
        }
    }
