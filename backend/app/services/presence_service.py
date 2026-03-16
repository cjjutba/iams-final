"""
Presence Tracking Service

Business logic for continuous presence monitoring and early-leave detection.

This is the core service that implements IAMS's unique feature:
continuous attendance tracking throughout the class session.

I/O contract (Redis Streams pipeline):
  - INPUT:  TrackFusionEngine.get_identified_users(room_id)
  - OUTPUT: StreamBus.publish_attendance() / StreamBus.publish_alert()
  - DB:     attendance_records, presence_logs, early_leave_events (unchanged)
"""

import asyncio
import contextlib
import json
from datetime import date, datetime, time, timedelta

import redis as redis_lib

from sqlalchemy.orm import Session

from app.config import logger, settings
from app.models.attendance_record import AttendanceStatus
from app.models.schedule import Schedule
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.repositories.user_repository import UserRepository
from app.services import session_manager
from app.services.stream_bus import get_stream_bus
from app.services.track_fusion_service import get_track_fusion_engine
from app.utils.exceptions import NotFoundError


def compute_early_leave_severity(
    leave_time: datetime,
    class_start: time,
    class_end: time,
) -> str:
    """Compute context-aware severity based on when in class the leave occurred.

    - Near start (<30% elapsed) -> "high"
    - Mid class (30-85% elapsed) -> "medium"
    - Near end (>85% elapsed) -> "low"
    """
    now_time = leave_time.time()
    start_secs = class_start.hour * 3600 + class_start.minute * 60 + class_start.second
    end_secs = class_end.hour * 3600 + class_end.minute * 60 + class_end.second
    now_secs = now_time.hour * 3600 + now_time.minute * 60 + now_time.second

    total_duration = end_secs - start_secs
    if total_duration <= 0:
        return "medium"

    elapsed = now_secs - start_secs
    ratio = elapsed / total_duration

    if ratio < 0.30:
        return "high"
    elif ratio > 0.85:
        return "low"
    return "medium"


class SessionState:
    """Represents an active attendance session"""

    def __init__(self, schedule_id: str, schedule: Schedule):
        self.schedule_id = schedule_id
        self.schedule = schedule
        self.start_time = datetime.now()
        self.scan_count = 0
        self.student_states: dict[str, dict] = {}  # student_id -> state
        self.is_active = True

    def add_student(self, student_id: str, attendance_id: str):
        """Add student to session tracking"""
        self.student_states[student_id] = {
            "attendance_id": attendance_id,
            "consecutive_misses": 0,
            "last_seen": None,
            "early_leave_flagged": False,
        }

    def update_student(self, student_id: str, detected: bool):
        """Update student detection state"""
        if student_id in self.student_states:
            if detected:
                self.student_states[student_id]["consecutive_misses"] = 0
                self.student_states[student_id]["last_seen"] = datetime.now()
            else:
                self.student_states[student_id]["consecutive_misses"] += 1

    def get_student_state(self, student_id: str) -> dict | None:
        """Get student state"""
        return self.student_states.get(student_id)


class PresenceService:
    """
    Service for presence tracking and early-leave detection

    Key Features:
    - Continuous presence monitoring (60-second scans)
    - Early leave detection (3 consecutive misses)
    - Session lifecycle management (start/end)
    - Presence score calculation
    - Real-time event publishing via Redis Streams
    """

    # Class-level shared state: sessions persist across all instances/requests
    _active_sessions: dict[str, SessionState] = {}
    _lock = asyncio.Lock()

    def __init__(self, db: Session):
        self.db = db
        self.attendance_repo = AttendanceRepository(db)
        self.schedule_repo = ScheduleRepository(db)
        self.user_repo = UserRepository(db)

        # Reference the class-level dict so all instances share session state
        self.active_sessions = PresenceService._active_sessions

    # ── helpers ──────────────────────────────────────────────────

    async def _publish_attendance(self, schedule_id: str, payload: dict):
        """Publish an attendance event to Redis Streams."""
        try:
            bus = await get_stream_bus()
            await bus.publish_attendance(schedule_id, payload)
        except Exception as e:
            logger.error(f"Failed to publish attendance event: {e}")

    async def _publish_alert(self, alert: dict):
        """Publish an alert event to Redis Streams."""
        try:
            bus = await get_stream_bus()
            await bus.publish_alert(alert)
        except Exception as e:
            logger.error(f"Failed to publish alert: {e}")

    def _get_room_id(self, schedule: Schedule) -> str:
        """Extract the room_id string from a schedule (used as fusion engine key)."""
        return str(schedule.room_id)

    def _get_identified_users_from_pipeline(self, room_id: str) -> list[dict]:
        """Read identified users from the video pipeline's Redis state."""
        try:
            r = redis_lib.Redis.from_url(settings.REDIS_URL)
            raw = r.get(f"pipeline:{room_id}:state")
            if raw is None:
                return []
            state = json.loads(raw)
            return state.get("identified_users", [])
        except Exception as e:
            logger.error(f"Failed to read pipeline state for {room_id}: {e}")
            return []

    def _get_student_info(self, student_id: str) -> dict:
        """Look up student name/student_id from the user repository."""
        user = self.user_repo.get_by_id(student_id)
        if user:
            return {
                "user_id": student_id,
                "name": f"{user.first_name} {user.last_name}",
                "student_id": user.student_id,
            }
        return {"user_id": student_id, "name": "Unknown", "student_id": None}

    # ── session lifecycle ────────────────────────────────────────

    async def start_session(self, schedule_id: str) -> SessionState:
        """
        Start attendance session for a schedule.

        Creates attendance records for all enrolled students
        and initialises session state.

        Args:
            schedule_id: Schedule UUID

        Returns:
            SessionState object

        Raises:
            NotFoundError: If schedule not found
        """
        async with self._lock:
            # Check if session already active
            if schedule_id in self.active_sessions:
                logger.warning(f"Session already active for schedule {schedule_id}")
                return self.active_sessions[schedule_id]

            # Get schedule
            schedule = self.schedule_repo.get_by_id(schedule_id)
            if not schedule:
                raise NotFoundError(f"Schedule not found: {schedule_id}")

            logger.info(f"Starting session for schedule {schedule_id} ({schedule.subject_code})")

            # Create session state
            session = SessionState(schedule_id, schedule)

            # Get enrolled students
            students = self.schedule_repo.get_enrolled_students(schedule_id)

            # Create attendance records for all students (initially absent)
            today = date.today()
            for student in students:
                # Check if record already exists
                existing = self.attendance_repo.get_by_student_date(str(student.id), schedule_id, today)

                if not existing:
                    # Create new attendance record
                    record = self.attendance_repo.create(
                        {
                            "student_id": str(student.id),
                            "schedule_id": schedule_id,
                            "date": today,
                            "status": AttendanceStatus.ABSENT,
                            "total_scans": 0,
                            "scans_present": 0,
                            "presence_score": 0.0,
                        }
                    )
                    attendance_id = str(record.id)
                else:
                    attendance_id = str(existing.id)

                # Add to session tracking
                session.add_student(str(student.id), attendance_id)

            # Store active session
            self.active_sessions[schedule_id] = session

            # Register in global session manager for cross-module access
            session_manager.register_session(
                schedule_id,
                {
                    "subject_code": schedule.subject_code,
                    "subject_name": schedule.subject_name,
                    "student_count": len(students),
                },
            )

        # Publish session-start event via Redis Streams (outside lock)
        await self._publish_attendance(
            schedule_id,
            {
                "event": "session_start",
                "schedule_id": schedule_id,
                "subject_code": schedule.subject_code,
                "subject_name": schedule.subject_name,
                "student_count": len(students),
                "start_time": datetime.now().isoformat(),
            },
        )

        logger.info(f"Session started with {len(students)} students")
        return session

    async def end_session(self, schedule_id: str):
        """
        End attendance session.

        Calculates final presence scores and removes from active sessions.

        Args:
            schedule_id: Schedule UUID
        """
        async with self._lock:
            if schedule_id not in self.active_sessions:
                logger.warning(f"No active session to end: {schedule_id}")
                return

            session = self.active_sessions[schedule_id]

            logger.info(f"Ending session for schedule {schedule_id} (Total scans: {session.scan_count})")

            # Update final check-out times and presence scores
            for _student_id, student_state in session.student_states.items():
                attendance_id = student_state["attendance_id"]

                attendance = self.attendance_repo.get_by_id(attendance_id)
                if not attendance:
                    continue

                # Set check-out time
                if attendance.status != AttendanceStatus.ABSENT:
                    self.attendance_repo.update(attendance_id, {"check_out_time": datetime.now()})

            # Build session summary
            summary = {
                "total_scans": session.scan_count,
                "total_students": len(session.student_states),
                "present_count": sum(1 for s in session.student_states.values() if not s.get("early_leave_flagged")),
                "early_leave_count": sum(1 for s in session.student_states.values() if s.get("early_leave_flagged")),
            }

            schedule = session.schedule

            # Remove from active sessions
            del self.active_sessions[schedule_id]

            # Unregister from global session manager
            session_manager.unregister_session(schedule_id)

        # Clear Redis presence state for this session
        try:
            await self._redis_clear_room(schedule_id)
        except Exception as e:
            logger.error(f"Failed to clear Redis presence state for {schedule_id}: {e}")

        # Publish session-end event via Redis Streams (outside lock)
        await self._publish_attendance(
            schedule_id,
            {
                "event": "session_end",
                "schedule_id": schedule_id,
                "subject_code": schedule.subject_code,
                "subject_name": schedule.subject_name,
                "end_time": datetime.now().isoformat(),
                "summary": summary,
            },
        )

        logger.info(f"Session ended for schedule {schedule_id}")

    # ── scan cycle (called by APScheduler every 60 s) ────────────

    async def run_scan_cycle(self):
        """
        Run scan cycle for all active sessions.

        This should be called every 60 seconds (configurable).
        Checks each student's detection status and flags early leaves.

        Called by background scheduler (APScheduler).
        """
        if not self.active_sessions:
            return

        logger.debug(f"Running scan cycle for {len(self.active_sessions)} active sessions")

        for schedule_id, _session in list(self.active_sessions.items()):
            try:
                await self.process_session_scan(schedule_id)
            except Exception as e:
                logger.error(f"Failed to process scan for session {schedule_id}: {e}")

    async def process_session_scan(self, schedule_id: str):
        """
        Process one scan cycle for a session.

        Queries the TrackFusionEngine for identified users in the room,
        compares against enrolled students, updates attendance records,
        and publishes events via Redis Streams.

        Args:
            schedule_id: Schedule UUID
        """
        # Snapshot session state under lock
        async with self._lock:
            if schedule_id not in self.active_sessions:
                return

            session = self.active_sessions[schedule_id]
            session.scan_count += 1
            scan_count = session.scan_count
            room_id = self._get_room_id(session.schedule)
            student_snapshot = {
                sid: {
                    "attendance_id": s["attendance_id"],
                    "early_leave_flagged": s["early_leave_flagged"],
                }
                for sid, s in session.student_states.items()
            }

        logger.debug(f"Processing scan #{scan_count} for schedule {schedule_id}")

        # Try pipeline Redis first, fall back to TrackFusionEngine
        pipeline_users = self._get_identified_users_from_pipeline(room_id)
        if pipeline_users:
            # Pipeline returns list[dict] — convert to dict keyed by user_id
            identified_users = {
                u["user_id"]: u for u in pipeline_users if "user_id" in u
            }
        else:
            try:
                engine = get_track_fusion_engine()
                identified_users = engine.get_identified_users(room_id)
            except Exception:
                identified_users = {}
        present_user_ids = set(identified_users.keys())

        logger.debug(
            f"Scan #{scan_count}: {len(present_user_ids)} students detected in room {room_id}"
        )

        # Check each enrolled student
        early_leave_candidates = []
        present_students = []

        for student_id, snap in student_snapshot.items():
            attendance_id = snap["attendance_id"]

            # Get attendance record
            attendance = self.attendance_repo.get_by_id(attendance_id)
            if not attendance:
                continue

            # Handle students who are still ABSENT: check if they were just detected
            if attendance.status == AttendanceStatus.ABSENT:
                if student_id in present_user_ids:
                    # First detection -> check in as PRESENT or LATE
                    current_time = datetime.now().time()
                    grace_time = (
                        datetime.combine(date.today(), session.schedule.start_time)
                        + timedelta(minutes=settings.GRACE_PERIOD_MINUTES)
                    ).time()

                    new_status = AttendanceStatus.PRESENT if current_time <= grace_time else AttendanceStatus.LATE
                    check_in_time = datetime.now()

                    self.attendance_repo.update(
                        attendance_id,
                        {
                            "status": new_status,
                            "check_in_time": check_in_time,
                            "scans_present": 1,
                            "total_scans": 1,
                            "presence_score": 100.0,
                        },
                    )

                    # Log initial presence
                    user_info = identified_users.get(student_id, {})
                    confidence = user_info.get("similarity")
                    self.attendance_repo.log_presence(
                        attendance_id,
                        {
                            "scan_number": scan_count,
                            "scan_time": check_in_time,
                            "detected": True,
                            "confidence": confidence,
                        },
                    )

                    # Update session state
                    async with self._lock:
                        if schedule_id in self.active_sessions:
                            self.active_sessions[schedule_id].update_student(student_id, detected=True)

                    student_info = self._get_student_info(student_id)
                    present_students.append({
                        **student_info,
                        "status": new_status.value,
                        "check_in_time": check_in_time.isoformat(),
                    })

                    # Publish individual check-in event
                    await self._publish_attendance(
                        schedule_id,
                        {
                            "event": "check_in",
                            "schedule_id": schedule_id,
                            "student_id": student_id,
                            "student_name": student_info["name"],
                            "student_student_id": student_info["student_id"],
                            "status": new_status.value,
                            "check_in_time": check_in_time.isoformat(),
                        },
                    )

                    logger.info(f"Student {student_id} checked in via scan cycle: {new_status.value}")
                continue

            # Handle return detection for previously flagged students
            if snap["early_leave_flagged"]:
                is_present_now = student_id in present_user_ids
                if is_present_now:
                    await self._handle_early_leave_return(attendance_id, student_id, schedule_id)
                continue

            # Check if student is currently present (detected by fusion engine)
            is_present = student_id in present_user_ids

            if is_present:
                # Get recognition similarity from fusion track
                user_info = identified_users[student_id]
                confidence = user_info.get("similarity")

                # Log presence
                self.attendance_repo.log_presence(
                    attendance_id,
                    {
                        "scan_number": scan_count,
                        "scan_time": datetime.now(),
                        "detected": True,
                        "confidence": confidence,
                    },
                )

                # Update attendance metrics
                scans_present = attendance.scans_present + 1
                total_scans = attendance.total_scans + 1
                presence_score = self.calculate_presence_score(total_scans, scans_present)

                self.attendance_repo.update(
                    attendance_id,
                    {"scans_present": scans_present, "total_scans": total_scans, "presence_score": presence_score},
                )

                student_info = self._get_student_info(student_id)
                present_students.append({
                    **student_info,
                    "status": attendance.status.value,
                    "presence_score": presence_score,
                })

            else:
                # Log as not detected
                self.attendance_repo.log_presence(
                    attendance_id,
                    {"scan_number": scan_count, "scan_time": datetime.now(), "detected": False, "confidence": None},
                )

                # Update total scans
                total_scans = attendance.total_scans + 1
                presence_score = self.calculate_presence_score(total_scans, attendance.scans_present)

                self.attendance_repo.update(
                    attendance_id, {"total_scans": total_scans, "presence_score": presence_score}
                )

            # Update session state under lock after DB ops
            async with self._lock:
                if schedule_id in self.active_sessions:
                    self.active_sessions[schedule_id].update_student(student_id, detected=is_present)
                    if not is_present:
                        consecutive_misses = self.active_sessions[schedule_id].student_states[student_id][
                            "consecutive_misses"
                        ]
                        if consecutive_misses >= settings.EARLY_LEAVE_THRESHOLD:
                            early_leave_candidates.append((attendance_id, student_id, consecutive_misses))
                            self.active_sessions[schedule_id].student_states[student_id]["early_leave_flagged"] = True

        # Handle early leave flagging outside per-student loop
        for attendance_id, student_id, consecutive_misses in early_leave_candidates:
            await self.flag_early_leave(attendance_id, student_id, consecutive_misses, schedule_id)

        # Publish scan-complete summary via Redis Streams
        await self._publish_attendance(
            schedule_id,
            {
                "event": "scan_complete",
                "schedule_id": schedule_id,
                "scan_number": scan_count,
                "present_count": len(present_students),
                "total_enrolled": len(student_snapshot),
                "students": present_students,
                "timestamp": datetime.now().isoformat(),
            },
        )

    # ── early leave handling ─────────────────────────────────────

    async def flag_early_leave(self, attendance_id: str, student_id: str, consecutive_misses: int, schedule_id: str):
        """
        Flag student for early leave.

        Updates attendance status, creates early leave event in DB,
        and publishes an alert via Redis Streams.

        Args:
            attendance_id: Attendance record UUID
            student_id: Student UUID
            consecutive_misses: Number of consecutive misses
            schedule_id: Schedule UUID (for alert routing)
        """
        logger.warning(f"Early leave detected: student {student_id}, {consecutive_misses} consecutive misses")

        # Update attendance status
        self.attendance_repo.update(attendance_id, {"status": AttendanceStatus.EARLY_LEAVE})

        # Get attendance record for last seen time
        attendance = self.attendance_repo.get_by_id(attendance_id)
        recent_logs = self.attendance_repo.get_recent_logs(attendance_id, limit=consecutive_misses + 1)

        # Find last time student was detected
        last_seen = None
        for log in reversed(recent_logs):
            if log.detected:
                last_seen = log.scan_time
                break

        # Compute context severity based on schedule
        severity = "medium"
        schedule = getattr(attendance, "schedule", None)
        if schedule:
            s_time = getattr(schedule, "start_time", None)
            e_time = getattr(schedule, "end_time", None)
            if s_time and e_time and hasattr(s_time, "hour") and hasattr(e_time, "hour"):
                with contextlib.suppress(TypeError, AttributeError):
                    severity = compute_early_leave_severity(datetime.now(), s_time, e_time)

        # Create early leave event in DB
        event = self.attendance_repo.create_early_leave_event(
            {
                "attendance_id": attendance_id,
                "detected_at": datetime.now(),
                "last_seen_at": last_seen or attendance.check_in_time,
                "consecutive_misses": consecutive_misses,
                "notified": False,
                "context_severity": severity,
            }
        )

        logger.info(f"Early leave event created: {event.id}")

        # Look up student info and faculty for alert routing
        student_info = self._get_student_info(student_id)
        faculty_user_id = str(attendance.schedule.faculty_id) if attendance.schedule else None

        # Build list of user IDs to notify (faculty + student)
        notify_user_ids = [uid for uid in [faculty_user_id, student_id] if uid]

        # Publish early-leave alert via Redis Streams
        await self._publish_alert({
            "type": "early_leave",
            "student_id": student_id,
            "student_name": student_info["name"],
            "student_student_id": student_info["student_id"],
            "schedule_id": schedule_id,
            "attendance_id": attendance_id,
            "consecutive_misses": consecutive_misses,
            "last_seen_at": last_seen.isoformat() if last_seen else None,
            "severity": severity,
            "notify_user_ids": notify_user_ids,
            "timestamp": datetime.now().isoformat(),
        })

    async def _handle_early_leave_return(self, attendance_id: str, student_id: str, schedule_id: str):
        """Handle a student returning after being flagged for early leave.

        Updates the most recent early leave event with return info
        and publishes a return alert via Redis Streams.
        """
        from app.models.early_leave_event import EarlyLeaveEvent

        # Find the most recent unflagged-returned event for this attendance
        event = (
            self.db.query(EarlyLeaveEvent)
            .filter(
                EarlyLeaveEvent.attendance_id == attendance_id,
                EarlyLeaveEvent.returned.is_(False),
            )
            .order_by(EarlyLeaveEvent.detected_at.desc())
            .first()
        )

        if not event:
            return

        now = datetime.now()
        event.returned = True
        event.returned_at = now
        event.absence_duration_seconds = int((now - event.detected_at).total_seconds())
        self.db.commit()

        logger.info(
            f"Student {student_id} returned after early leave "
            f"(absent {event.absence_duration_seconds}s, severity={event.context_severity})"
        )

        # Get student and schedule info for alert
        student_info = self._get_student_info(student_id)
        attendance = self.attendance_repo.get_by_id(attendance_id)
        faculty_user_id = str(attendance.schedule.faculty_id) if attendance and attendance.schedule else None
        notify_user_ids = [uid for uid in [faculty_user_id, student_id] if uid]

        # Publish return alert via Redis Streams
        await self._publish_alert({
            "type": "early_leave_return",
            "student_id": student_id,
            "student_name": student_info["name"],
            "schedule_id": schedule_id,
            "attendance_id": attendance_id,
            "absence_duration_seconds": event.absence_duration_seconds,
            "returned_at": now.isoformat(),
            "notify_user_ids": notify_user_ids,
        })

    # ── presence score ───────────────────────────────────────────

    def calculate_presence_score(self, total_scans: int, scans_present: int) -> float:
        """
        Calculate presence percentage.

        Args:
            total_scans: Total number of scans
            scans_present: Number of scans where student was detected

        Returns:
            Presence score (0-100)
        """
        if total_scans == 0:
            return 0.0

        score = (scans_present / total_scans) * 100.0
        return round(score, 2)

    # ── Redis presence helpers ───────────────────────────────────

    async def _redis_update_presence(self, room_id: str, student_id: str, timestamp: float):
        """Update student presence state in Redis."""
        from app.redis_client import get_redis

        r = await get_redis()
        key = f"{settings.REDIS_PRESENCE_PREFIX}:{room_id}:{student_id}"
        await r.hset(
            key,
            mapping={
                "last_seen": str(timestamp),
                "miss_count": "0",
            },
        )
        await r.hincrby(key, "present_count", 1)

    async def _redis_get_presence(self, room_id: str, student_id: str) -> dict:
        """Get student presence state from Redis."""
        from app.redis_client import get_redis

        r = await get_redis()
        key = f"{settings.REDIS_PRESENCE_PREFIX}:{room_id}:{student_id}"
        data = await r.hgetall(key)
        if not data:
            return {"last_seen": 0, "miss_count": 0, "present_count": 0, "total_scans": 0}
        return {
            "last_seen": float(data.get(b"last_seen", 0)),
            "miss_count": int(data.get(b"miss_count", 0)),
            "present_count": int(data.get(b"present_count", 0)),
            "total_scans": int(data.get(b"total_scans", 0)),
        }

    async def _redis_increment_miss(self, room_id: str, student_id: str) -> int:
        """Increment miss counter, return new value."""
        from app.redis_client import get_redis

        r = await get_redis()
        key = f"{settings.REDIS_PRESENCE_PREFIX}:{room_id}:{student_id}"
        return await r.hincrby(key, "miss_count", 1)

    async def _redis_increment_total_scans(self, room_id: str, student_id: str):
        """Increment total scan count."""
        from app.redis_client import get_redis

        r = await get_redis()
        key = f"{settings.REDIS_PRESENCE_PREFIX}:{room_id}:{student_id}"
        await r.hincrby(key, "total_scans", 1)

    async def _redis_clear_room(self, room_id: str):
        """Clear all presence state for a room (on session end)."""
        from app.redis_client import get_redis

        r = await get_redis()
        async for key in r.scan_iter(match=f"{settings.REDIS_PRESENCE_PREFIX}:{room_id}:*"):
            await r.delete(key)

    # ── query helpers ────────────────────────────────────────────

    def get_session_state(self, schedule_id: str) -> SessionState | None:
        """
        Get current session state.

        Args:
            schedule_id: Schedule UUID

        Returns:
            SessionState if active, None otherwise
        """
        return self.active_sessions.get(schedule_id)

    def is_session_active(self, schedule_id: str) -> bool:
        """Check if session is active"""
        return schedule_id in self.active_sessions

    def get_active_sessions(self) -> list[str]:
        """Get list of active schedule IDs"""
        return list(self.active_sessions.keys())


# Note: Background scheduler (APScheduler) would be initialized in main.py
# and would call presence_service.run_scan_cycle() every 60 seconds
