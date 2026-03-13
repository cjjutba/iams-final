"""
Presence Tracking Service

Business logic for continuous presence monitoring and early-leave detection.

This is the core service that implements IAMS's unique feature:
continuous attendance tracking throughout the class session.
"""

import asyncio
import contextlib
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.config import logger, settings
from app.models.attendance_record import AttendanceStatus
from app.models.schedule import Schedule
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.repositories.user_repository import UserRepository
from app.services import session_manager
from app.services.notification_service import NotificationService
from app.services.tracking_service import Detection, get_tracking_service
from app.utils.exceptions import NotFoundError


def compute_early_leave_severity(
    leave_time: datetime,
    class_start: time,
    class_end: time,
) -> str:
    """Compute context-aware severity based on when in class the leave occurred.

    - Near start (<30% elapsed) → "high"
    - Mid class (30-85% elapsed) → "medium"
    - Near end (>85% elapsed) → "low"
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
        self.student_states: dict[str, dict] = {}  # student_id → state
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
    - Real-time alert generation
    """

    # Class-level shared state: sessions persist across all instances/requests
    _active_sessions: dict[str, SessionState] = {}
    _lock = asyncio.Lock()

    def __init__(self, db: Session, ws_manager=None):
        self.db = db
        self.attendance_repo = AttendanceRepository(db)
        self.schedule_repo = ScheduleRepository(db)
        self.user_repo = UserRepository(db)

        # WebSocket notification service (optional, for real-time alerts)
        self.notification_service = None
        if ws_manager:
            self.notification_service = NotificationService(ws_manager, db)

        # Reference the class-level dict so all instances share session state
        self.active_sessions = PresenceService._active_sessions

        # Tracking service for continuous face tracking
        self.tracking_service = get_tracking_service()

    async def start_session(self, schedule_id: str) -> SessionState:
        """
        Start attendance session for a schedule

        Creates attendance records for all enrolled students
        and initializes session state.

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

            # Initialize tracking session
            self.tracking_service.start_session(schedule_id)

            # Register in global session manager for cross-module access
            session_manager.register_session(
                schedule_id,
                {
                    "subject_code": schedule.subject_code,
                    "subject_name": schedule.subject_name,
                    "student_count": len(students),
                },
            )

        # Notify faculty via WebSocket (outside lock — no session mutation)
        if self.notification_service:
            try:
                await self.notification_service.notify_session_start(schedule_id)
            except Exception as e:
                logger.error(f"Failed to send session start notification: {e}")

        logger.info(f"Session started with {len(students)} students")

        return session

    async def handle_face_gone(self, room_id: str, track_ids: list, timestamp: str):
        """Handle face_gone events from RPi smart sampler.

        Provides early warning that a student may be leaving.
        The 60-second confirmation scan still runs as the authoritative check.
        """
        logger.info(f"Face gone event: room={room_id}, tracks={track_ids}")

    async def feed_detection(self, schedule_id: str, user_id: str, confidence: float, bbox: list[float] | None = None):
        """Feed a detection into the tracking service without updating attendance.
        Attendance updates happen solely in run_scan_cycle()."""
        async with self._lock:
            if schedule_id not in self.active_sessions:
                logger.debug(f"No active session for {schedule_id}, skipping detection feed")
                return

        detection = Detection(
            bbox=bbox or [0, 0, 0, 0],
            confidence=1.0,
            user_id=user_id,
            recognition_confidence=confidence,
        )
        self.tracking_service.update(schedule_id, [detection])
        logger.debug(f"Fed detection to tracking: user={user_id}, schedule={schedule_id}")

    async def log_detection(self, schedule_id: str, user_id: str, confidence: float, bbox: list[float] | None = None):
        """
        Log student detection during active session

        Called by face recognition endpoint when student is detected.
        Integrates with tracking service to maintain persistent track IDs.

        Args:
            schedule_id: Schedule UUID
            user_id: Student UUID
            confidence: Recognition confidence (0-1)
            bbox: Optional bounding box [x1, y1, x2, y2]
        """
        # Auto-start session if not active (outside lock to avoid deadlock
        # since start_session also acquires _lock)
        if schedule_id not in self.active_sessions:
            logger.warning(f"No active session for schedule {schedule_id}, auto-starting...")
            await self.start_session(schedule_id)

        # Acquire lock to safely read/write session state
        async with self._lock:
            session = self.active_sessions.get(schedule_id)
            if session is None:
                logger.error(f"Session unexpectedly missing for schedule {schedule_id}")
                return

            # Check if student is in this session
            if user_id not in session.student_states:
                logger.warning(f"Student {user_id} not enrolled in schedule {schedule_id}")
                return

            student_state = session.student_states[user_id]
            attendance_id = student_state["attendance_id"]
            scan_number = session.scan_count

        # DB and tracking operations (outside lock — no session mutation)
        attendance = self.attendance_repo.get_by_id(attendance_id)
        if not attendance:
            logger.error(f"Attendance record not found: {attendance_id}")
            return

        # Update tracking (if bbox provided)
        if bbox:
            detection = Detection(
                bbox=bbox,
                confidence=1.0,  # Detection confidence (assume 1.0 for now)
                user_id=user_id,
                recognition_confidence=confidence,
            )
            self.tracking_service.update(schedule_id, [detection])

        # Check if this is first detection (check-in)
        if attendance.status == AttendanceStatus.ABSENT:
            # Determine if late
            current_time = datetime.now().time()
            grace_time = (
                datetime.combine(date.today(), attendance.schedule.start_time)
                + timedelta(minutes=settings.GRACE_PERIOD_MINUTES)
            ).time()

            if current_time <= grace_time:
                status = AttendanceStatus.PRESENT
            else:
                status = AttendanceStatus.LATE

            # Update attendance record
            check_in_time = datetime.now()
            self.attendance_repo.update(attendance_id, {"status": status, "check_in_time": check_in_time})

            logger.info(f"Student {user_id} checked in: {status}")

            # Notify faculty of attendance update
            if self.notification_service:
                try:
                    await self.notification_service.notify_attendance_update(
                        schedule_id=str(attendance.schedule_id),
                        student_id=user_id,
                        status=status.value,
                        check_in_time=check_in_time,
                    )
                except Exception as e:
                    logger.error(f"Failed to send attendance update notification: {e}")

        # Re-acquire lock to update session state
        async with self._lock:
            session = self.active_sessions.get(schedule_id)
            if session:
                session.update_student(user_id, detected=True)

        # Log presence
        self.attendance_repo.log_presence(
            attendance_id,
            {"scan_number": scan_number, "scan_time": datetime.now(), "detected": True, "confidence": confidence},
        )

        # Update attendance metrics
        attendance = self.attendance_repo.get_by_id(attendance_id)
        scans_present = attendance.scans_present + 1
        total_scans = attendance.total_scans + 1
        presence_score = self.calculate_presence_score(total_scans, scans_present)

        self.attendance_repo.update(
            attendance_id,
            {"scans_present": scans_present, "total_scans": total_scans, "presence_score": presence_score},
        )

    async def run_scan_cycle(self):
        """
        Run scan cycle for all active sessions

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
        Process one scan cycle for a session

        Uses tracking service to determine which students are currently present.
        Logs presence for all enrolled students and flags early leaves.

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
            student_snapshot = {
                sid: {
                    "attendance_id": s["attendance_id"],
                    "early_leave_flagged": s["early_leave_flagged"],
                }
                for sid, s in session.student_states.items()
            }

        logger.debug(f"Processing scan #{scan_count} for schedule {schedule_id}")

        # Get currently identified users from tracking service (no lock needed)
        identified_users = self.tracking_service.get_identified_users(schedule_id)
        present_user_ids = set(identified_users.keys())

        logger.debug(
            f"Scan #{scan_count}: {len(present_user_ids)} students detected "
            f"(tracking stats: {self.tracking_service.get_session_stats(schedule_id)})"
        )

        # Check each enrolled student
        early_leave_candidates = []
        for student_id, snap in student_snapshot.items():
            attendance_id = snap["attendance_id"]

            # Get attendance record
            attendance = self.attendance_repo.get_by_id(attendance_id)
            if not attendance:
                continue

            # Handle students who are still ABSENT: check if they were just detected
            if attendance.status == AttendanceStatus.ABSENT:
                if student_id in present_user_ids:
                    # First detection → check in as PRESENT or LATE
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
                    track = identified_users.get(student_id)
                    confidence = track.recognition_confidence if track else None
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

                    # Send WebSocket notification if available
                    if self.notification_service:
                        try:
                            await self.notification_service.notify_attendance_update(
                                schedule_id=schedule_id,
                                student_id=student_id,
                                status=new_status.value,
                                check_in_time=check_in_time,
                            )
                        except Exception as e:
                            logger.error(f"Failed to send check-in notification: {e}")

                    logger.info(f"Student {student_id} checked in via scan cycle: {new_status.value}")
                continue

            # Handle return detection for previously flagged students
            if snap["early_leave_flagged"]:
                is_present_now = student_id in present_user_ids
                if is_present_now:
                    await self._handle_early_leave_return(attendance_id, student_id)
                continue

            # Check if student is currently present (detected by tracker)
            is_present = student_id in present_user_ids

            if is_present:
                # Get recognition confidence from track
                track = identified_users[student_id]
                confidence = track.recognition_confidence

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

        # Handle early leave flagging outside per-student loop (WebSocket calls inside)
        for attendance_id, student_id, consecutive_misses in early_leave_candidates:
            await self.flag_early_leave(attendance_id, student_id, consecutive_misses)

    async def flag_early_leave(self, attendance_id: str, student_id: str, consecutive_misses: int):
        """
        Flag student for early leave

        Updates attendance status and creates early leave event.
        Sends real-time alert to faculty (via WebSocket in Phase 3.4).

        Args:
            attendance_id: Attendance record UUID
            student_id: Student UUID
            consecutive_misses: Number of consecutive misses
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

        # Create early leave event
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

        # Send WebSocket alert to faculty
        if self.notification_service:
            try:
                await self.notification_service.notify_early_leave(attendance)
            except Exception as e:
                logger.error(f"Failed to send early leave notification: {e}")

    async def _handle_early_leave_return(self, attendance_id: str, student_id: str):
        """Handle a student returning after being flagged for early leave.

        Updates the most recent early leave event with return info.
        """
        from app.models.early_leave_event import EarlyLeaveEvent

        # Find the most recent unflagged-returned event for this attendance
        event = (
            self.db.query(EarlyLeaveEvent)
            .filter(
                EarlyLeaveEvent.attendance_id == attendance_id,
                not EarlyLeaveEvent.returned,
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

        # Send return notification
        if self.notification_service:
            try:
                attendance = self.attendance_repo.get_by_id(attendance_id)
                if attendance:
                    await self.notification_service.notify_early_leave_return(
                        attendance, event.absence_duration_seconds
                    )
            except Exception as e:
                logger.error(f"Failed to send early leave return notification: {e}")

    async def end_session(self, schedule_id: str):
        """
        End attendance session

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

            # Remove from active sessions
            del self.active_sessions[schedule_id]

            # End tracking session
            self.tracking_service.end_session(schedule_id)

            # Unregister from global session manager
            session_manager.unregister_session(schedule_id)

        # Clear Redis presence state for this session
        try:
            await self._redis_clear_room(schedule_id)
        except Exception as e:
            logger.error(f"Failed to clear Redis presence state for {schedule_id}: {e}")

        # Notify faculty of session end (outside lock — no session mutation)
        if self.notification_service:
            try:
                await self.notification_service.notify_session_end(schedule_id, summary)
            except Exception as e:
                logger.error(f"Failed to send session end notification: {e}")

        logger.info(f"Session ended for schedule {schedule_id}")

    def calculate_presence_score(self, total_scans: int, scans_present: int) -> float:
        """
        Calculate presence percentage

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

    async def _redis_update_presence(self, room_id: str, student_id: str, timestamp: float):
        """Update student presence state in Redis."""
        from app.config import settings
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
        from app.config import settings
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
        from app.config import settings
        from app.redis_client import get_redis

        r = await get_redis()
        key = f"{settings.REDIS_PRESENCE_PREFIX}:{room_id}:{student_id}"
        return await r.hincrby(key, "miss_count", 1)

    async def _redis_increment_total_scans(self, room_id: str, student_id: str):
        """Increment total scan count."""
        from app.config import settings
        from app.redis_client import get_redis

        r = await get_redis()
        key = f"{settings.REDIS_PRESENCE_PREFIX}:{room_id}:{student_id}"
        await r.hincrby(key, "total_scans", 1)

    async def _redis_clear_room(self, room_id: str):
        """Clear all presence state for a room (on session end)."""
        from app.config import settings
        from app.redis_client import get_redis

        r = await get_redis()
        async for key in r.scan_iter(match=f"{settings.REDIS_PRESENCE_PREFIX}:{room_id}:*"):
            await r.delete(key)

    def get_session_state(self, schedule_id: str) -> SessionState | None:
        """
        Get current session state

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
