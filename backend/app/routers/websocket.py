"""
WebSocket manager — direct broadcast with optional Redis pub/sub for multi-worker.

Message types:
  - frame_update:        Per-frame tracking data at WS_BROADCAST_FPS (~10fps)
  - attendance_summary:  Periodic attendance state (every 5-10s)
  - check_in:            Student check-in event
  - early_leave:         Early leave detection
  - early_leave_return:  Student return after early leave
  - scan_result:         Legacy scan result (backward compatibility)
  - activity_event:      Discrete system-wide domain event (admin live tail)
"""

import asyncio
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.utils.security import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()


@dataclass(eq=False)
class ActivityClient:
    """A subscribed /ws/events viewer with per-connection filter.

    Filters are snapshotted at connect time and never mutated — to change
    filters the client reconnects. This keeps the per-message filter check
    a simple set-membership test with no locking.

    ``eq=False`` falls back to identity equality + identity hash so an
    instance can be stored in a ``set`` — which is how the manager
    tracks live connections.
    """

    ws: WebSocket
    event_types: frozenset[str] = field(default_factory=frozenset)
    categories: frozenset[str] = field(default_factory=frozenset)
    severities: frozenset[str] = field(default_factory=frozenset)
    schedule_id: str | None = None
    student_id: str | None = None

    def matches(self, msg: dict) -> bool:
        """Return True iff this client should receive the given message."""
        if self.event_types and msg.get("event_type") not in self.event_types:
            return False
        if self.categories and msg.get("category") not in self.categories:
            return False
        if self.severities and msg.get("severity") not in self.severities:
            return False
        if self.schedule_id and msg.get("subject_schedule_id") != self.schedule_id:
            return False
        if self.student_id and msg.get("subject_user_id") != self.student_id:
            return False
        return True


class ConnectionManager:
    """WebSocket connection manager with optional Redis pub/sub backing."""

    def __init__(self):
        self._attendance_clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._alert_clients: dict[str, set[WebSocket]] = defaultdict(set)
        # Per-student fanout for the Student Record Detail page's "Recent
        # detections" panel. Mirrors the schedule channel: every persisted
        # recognition_event with a non-null student_id is also broadcast
        # here so an open student-detail page updates in real time without
        # waiting for the next REST poll.
        self._student_clients: dict[str, set[WebSocket]] = defaultdict(set)
        # Activity clients are a flat set keyed by filter spec — per-connection
        # filters are server-side-applied on each incoming message.
        self._activity_clients: set[ActivityClient] = set()
        self._redis_subscriber_task: asyncio.Task | None = None

    # ── Client management ────────────────────────────────────────

    async def add_attendance_client(self, schedule_id: str, ws: WebSocket):
        await ws.accept()
        self._attendance_clients[schedule_id].add(ws)
        logger.debug(
            "WS client added for schedule %s (total: %d)", schedule_id, len(self._attendance_clients[schedule_id])
        )

    def remove_attendance_client(self, schedule_id: str, ws: WebSocket):
        self._attendance_clients[schedule_id].discard(ws)

    async def add_alert_client(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self._alert_clients[user_id].add(ws)

    def remove_alert_client(self, user_id: str, ws: WebSocket):
        self._alert_clients[user_id].discard(ws)

    async def add_student_client(self, student_id: str, ws: WebSocket):
        """Subscribe a viewer to a student's live recognition_event stream."""
        await ws.accept()
        self._student_clients[student_id].add(ws)
        logger.debug(
            "WS student client added for %s (total: %d)",
            student_id,
            len(self._student_clients[student_id]),
        )

    def remove_student_client(self, student_id: str, ws: WebSocket):
        self._student_clients[student_id].discard(ws)

    async def add_activity_client(self, client: ActivityClient):
        """Accept a /ws/events viewer (admin live-tail stream)."""
        await client.ws.accept()
        self._activity_clients.add(client)
        logger.debug(
            "WS activity client added (filters: types=%s, cats=%s, sevs=%s, sched=%s, student=%s) — total %d",
            client.event_types or "*",
            client.categories or "*",
            client.severities or "*",
            client.schedule_id or "*",
            client.student_id or "*",
            len(self._activity_clients),
        )

    def remove_activity_client(self, client: ActivityClient):
        self._activity_clients.discard(client)

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

    async def broadcast_student(self, student_id: str, data: dict) -> None:
        """Push ``data`` to all local viewers of one student, then publish to
        Redis so other workers fan out to their local viewers too.

        Used by the recognition-evidence writer to push real-time
        ``recognition_event`` messages to the Student Record Detail page.
        """
        dead = []
        for ws in list(self._student_clients.get(student_id, set())):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._student_clients[student_id].discard(ws)

        await self._redis_publish_student(student_id, data)

    async def _redis_publish_student(self, student_id: str, data: dict) -> None:
        """Publish a per-student message to the shared Redis subchannel."""
        channel = f"{settings.REDIS_WS_CHANNEL}:student:{student_id}"
        try:
            from app.redis_client import get_redis

            r = await get_redis()
            enriched = {**data, "origin_pid": os.getpid(), "_student_id": student_id}
            payload = json.dumps(enriched, default=str)
            await r.publish(channel, payload)
        except Exception as e:
            logger.warning("Redis student publish failed for %s: %s", student_id, e)

    async def broadcast_scan_result(
        self,
        schedule_id: str,
        detections: list[dict],
        present_count: int,
        total_enrolled: int,
        absent: list[str],
        early_leave: list[str],
    ):
        """Legacy scan_result broadcast (backward compatibility)."""
        await self.broadcast_attendance(
            schedule_id,
            {
                "type": "scan_result",
                "schedule_id": schedule_id,
                "detections": detections,
                "present_count": present_count,
                "total_enrolled": total_enrolled,
                "absent": absent,
                "early_leave": early_leave,
            },
        )

    async def broadcast_activity(self, data: dict) -> None:
        """Send an activity event to all matching /ws/events viewers, then
        publish to Redis for multi-worker fanout.

        Per-client filters are applied in-handler against the event's own
        metadata — no server-side fanout key is needed.
        """
        dead: list[ActivityClient] = []
        for client in list(self._activity_clients):
            if not client.matches(data):
                continue
            try:
                await client.ws.send_json(data)
            except Exception:
                dead.append(client)
        for client in dead:
            self._activity_clients.discard(client)

        # Publish to Redis for multi-worker fanout
        await self._redis_publish_activity(data)

    async def _redis_publish_activity(self, data: dict) -> None:
        """Publish activity event to the shared Redis subchannel."""
        channel = f"{settings.REDIS_WS_CHANNEL}:activity:global"
        try:
            from app.redis_client import get_redis

            r = await get_redis()
            enriched = {**data, "origin_pid": os.getpid(), "_activity": True}
            payload = json.dumps(enriched, default=str)
            await r.publish(channel, payload)
        except Exception as e:
            logger.warning("Redis activity publish failed: %s", e)

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

                        # Determine channel type by suffix parts:
                        #   Alert:      ws_broadcast:alert:{user_id}
                        #   Activity:   ws_broadcast:activity:global
                        #   Student:    ws_broadcast:student:{student_id}
                        #   Attendance: ws_broadcast:{schedule_id}
                        parts = channel.split(":")
                        if len(parts) >= 3 and parts[-2] == "alert":
                            # Alert message — forward to alert clients
                            user_id = parts[-1]
                            dead_alerts = []
                            for ws in list(self._alert_clients.get(user_id, set())):
                                try:
                                    await ws.send_json(data)
                                except Exception:
                                    dead_alerts.append(ws)
                            for ws in dead_alerts:
                                self._alert_clients[user_id].discard(ws)
                        elif len(parts) >= 3 and parts[-2] == "student":
                            # Per-student recognition_event — forward to
                            # student-scoped clients on this worker.
                            student_id = parts[-1]
                            dead_students = []
                            for ws in list(self._student_clients.get(student_id, set())):
                                try:
                                    await ws.send_json(data)
                                except Exception:
                                    dead_students.append(ws)
                            for ws in dead_students:
                                self._student_clients[student_id].discard(ws)
                        elif len(parts) >= 3 and parts[-2] == "activity":
                            # Activity event — fan out to all matching
                            # /ws/events viewers, applying per-connection
                            # filters server-side.
                            dead_activity: list[ActivityClient] = []
                            for client in list(self._activity_clients):
                                if not client.matches(data):
                                    continue
                                try:
                                    await client.ws.send_json(data)
                                except Exception:
                                    dead_activity.append(client)
                            for client in dead_activity:
                                self._activity_clients.discard(client)
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

    # Send current attendance summary immediately so the client shows fresh
    # state on connect instead of waiting for the next periodic broadcast.
    # This makes metric cards update instantly when a faculty opens the screen.
    try:
        pipelines = getattr(websocket.app.state, "session_pipelines", {})
        pipeline = pipelines.get(schedule_id)
        if pipeline is not None and pipeline._presence is not None:
            summary = pipeline._presence.get_attendance_summary()
            await websocket.send_text(json.dumps(summary))
    except Exception:
        logger.debug("Failed to send initial attendance summary", exc_info=True)

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

        # If this was the last viewer AND a preview pipeline is running for
        # this schedule, tear it down so we don't leak ML CPU time watching
        # a stream nobody's looking at. Full (attendance) pipelines are owned
        # by the lifecycle scheduler and stay up until session end.
        remaining = ws_manager._attendance_clients.get(schedule_id, set())
        if not remaining:
            stop_preview_fn = getattr(websocket.app.state, "stop_preview_pipeline", None)
            if stop_preview_fn is not None:
                asyncio.ensure_future(stop_preview_fn(schedule_id))


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


def _split_csv_param(value: str | None) -> frozenset[str]:
    """Parse a CSV query param into a frozenset of trimmed non-empty values."""
    if not value:
        return frozenset()
    return frozenset(p.strip() for p in value.split(",") if p.strip())


@router.websocket("/events")
async def events_websocket(websocket: WebSocket):
    """Admin-only live tail of the system activity event stream.

    Query params:
        token:        JWT; must carry role=admin.
        event_type:   CSV of event type names to include.
        category:     CSV of categories to include.
        severity:     CSV of severities to include.
        schedule_id:  Restrict to a single schedule.
        student_id:   Restrict to a single student (subject).

    Filters are snapshotted at connect time and never mutated — to change
    filters the client closes and reopens the socket.
    """
    token = websocket.query_params.get("token")
    if token is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    try:
        payload = verify_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Admin-only: the activity stream can carry any student's check-in
    # moments, login events, etc. — not safe for faculty/student role.
    # Our JWT payload only carries user_id/exp/iat — no role claim — so
    # the role must be resolved via a DB lookup (same pattern as
    # get_current_admin).
    user_id_raw = payload.get("user_id")
    if not user_id_raw:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    try:
        import uuid as _uuid

        from app.database import SessionLocal
        from app.models.user import User, UserRole

        db = SessionLocal()
        try:
            user = (
                db.query(User)
                .filter(User.id == _uuid.UUID(str(user_id_raw)))
                .first()
            )
        finally:
            db.close()
    except Exception:
        logger.warning("Activity WS auth lookup failed", exc_info=True)
        await websocket.close(code=4001, reason="Unauthorized")
        return

    if user is None or not user.is_active or user.role != UserRole.ADMIN:
        await websocket.close(code=4003, reason="Forbidden")
        return

    client = ActivityClient(
        ws=websocket,
        event_types=_split_csv_param(websocket.query_params.get("event_type")),
        categories=_split_csv_param(websocket.query_params.get("category")),
        severities=_split_csv_param(websocket.query_params.get("severity")),
        schedule_id=websocket.query_params.get("schedule_id"),
        student_id=websocket.query_params.get("student_id"),
    )

    await ws_manager.add_activity_client(client)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.warning("Unexpected error on activity events WS", exc_info=True)
    finally:
        ws_manager.remove_activity_client(client)


@router.websocket("/student/{student_id}")
async def student_recognition_websocket(websocket: WebSocket, student_id: str):
    """Admin-only per-student stream of ``recognition_event`` messages.

    Powers the Student Record Detail page's "Recent detections" panel — every
    FAISS decision the writer persists for this student is fanned out here in
    real time, so the panel updates without polling. Other recognition_event
    messages (for other students, or misses with no student_id) are NOT sent
    on this channel.

    Auth pattern matches /ws/events: token must resolve to an active admin
    user. Faculty/student roles are rejected with 4003 because the recognition
    audit trail (probe crops + similarity scores) is admin-only data.
    """
    token = websocket.query_params.get("token")
    if token is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    try:
        payload = verify_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    user_id_raw = payload.get("user_id")
    if not user_id_raw:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Validate the student_id is a real UUID early — saves us from holding
    # an open socket against a bogus path that will never receive messages.
    try:
        import uuid as _uuid

        _uuid.UUID(student_id)
    except Exception:
        await websocket.close(code=4400, reason="Invalid student_id")
        return

    # Admin role check — same pattern as events_websocket.
    try:
        import uuid as _uuid

        from app.database import SessionLocal
        from app.models.user import User, UserRole

        db = SessionLocal()
        try:
            user = (
                db.query(User)
                .filter(User.id == _uuid.UUID(str(user_id_raw)))
                .first()
            )
        finally:
            db.close()
    except Exception:
        logger.warning("Student WS auth lookup failed", exc_info=True)
        await websocket.close(code=4001, reason="Unauthorized")
        return

    if user is None or not user.is_active or user.role != UserRole.ADMIN:
        await websocket.close(code=4003, reason="Forbidden")
        return

    await ws_manager.add_student_client(student_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.warning(
            "Unexpected error on student WS for %s", student_id, exc_info=True
        )
    finally:
        ws_manager.remove_student_client(student_id, websocket)


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
