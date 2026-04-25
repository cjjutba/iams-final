"""
TrackPresenceService — continuous time-based presence tracking.

Replaces scan-count logic with continuous time tracking:
  - Unit: seconds (not scan count)
  - Early leave: absent > EARLY_LEAVE_TIMEOUT (45s default)
  - DB writes: buffered, flushed every PRESENCE_FLUSH_INTERVAL (10s)
  - Name lookup: loaded once at session start

| Aspect           | Old (PresenceService)       | New (TrackPresenceService) |
|------------------|-----------------------------|----------------------------|
| Unit             | scan count (every 15s)      | continuous time (seconds)  |
| Early leave      | 3 consecutive misses        | absent > 45s               |
| DB writes        | every scan (~90 ops)        | buffered, every 10s (~5)   |
| Name lookup      | N+1 per scan                | loaded once at start       |
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import settings
from app.models.attendance_record import AttendanceStatus
from app.models.early_leave_event import EarlyLeaveEvent
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.repositories.user_repository import UserRepository
from app.services.realtime_tracker import TrackFrame

logger = logging.getLogger(__name__)


@dataclass
class StudentPresenceState:
    """In-memory presence state for one student in one session."""

    student_id: str
    attendance_id: str
    name: str
    status: AttendanceStatus = AttendanceStatus.ABSENT
    check_in_time: datetime | None = None
    last_seen_time: float | None = None  # monotonic timestamp
    last_seen_at: datetime | None = None  # wall-clock of last detection (for check_out_time on early-leave)
    total_present_seconds: float = 0.0
    last_presence_start: float | None = None  # monotonic ts when current presence began
    absent_since: float | None = None  # monotonic ts when absence began
    early_leave_flagged: bool = False
    early_leave_returned: bool = False


class TrackPresenceService:
    """Track-based continuous presence tracking with buffered DB writes.

    One instance per active session (created by SessionPipeline).
    """

    def __init__(self, db: Session, schedule_id: str) -> None:
        self.db = db
        self.schedule_id = schedule_id
        self.attendance_repo = AttendanceRepository(db)
        self.schedule_repo = ScheduleRepository(db)
        self.user_repo = UserRepository(db)

        # In-memory state
        self._students: dict[str, StudentPresenceState] = {}  # user_id -> state
        self._session_start: datetime | None = None
        self._name_map: dict[str, str] = {}  # user_id -> display name
        self._enrolled_ids: set[str] = set()
        self._pending_log_writes: list[dict] = []
        self._schedule = None  # Cached schedule object
        self._early_leave_timeout: float = settings.EARLY_LEAVE_TIMEOUT  # per-schedule override

        # Camera-offline pause state. When the pipeline detects the camera has
        # been offline for a few seconds, it calls pause_absence_tracking().
        # This records the pause start time so that upon resume we can shift
        # every student's absent_since timer forward by the offline duration —
        # preventing camera downtime from falsely triggering early-leave events.
        self._paused_at: float | None = None

    def rebind_db(self, db: Session) -> None:
        """Swap the underlying DB session (for short-lived session pattern)."""
        self.db = db
        self.attendance_repo = AttendanceRepository(db)
        self.schedule_repo = ScheduleRepository(db)
        self.user_repo = UserRepository(db)

    @property
    def name_map(self) -> dict[str, str]:
        return self._name_map

    @property
    def enrolled_ids(self) -> set[str]:
        return self._enrolled_ids

    def set_early_leave_timeout(self, seconds: float) -> None:
        """Update the early leave timeout (GIL-safe for mid-session changes)."""
        self._early_leave_timeout = seconds

    def pause_absence_tracking(self, now_mono: float) -> None:
        """Freeze absence timers for all tracked students (camera went offline).

        Called by SessionPipeline when the camera has been offline for ~2
        seconds. Stores the pause start time. When the camera comes back and
        the next frame arrives, resume_absence_tracking() shifts every timer
        forward by the offline duration so camera downtime is NOT counted as
        student absence.

        Idempotent — safe to call multiple times while already paused.
        """
        if self._paused_at is None:
            self._paused_at = now_mono
            logger.info(
                "Presence tracking PAUSED for schedule %s (camera offline)",
                self.schedule_id[:8],
            )

    def resume_absence_tracking(self, now_mono: float) -> None:
        """Unfreeze absence timers after camera comes back online.

        Shifts every student's absent_since and last_seen_time forward by the
        pause duration so the early-leave timeout check (now_mono - absent_since)
        effectively excludes the offline period. Also extends presence-start
        timers so total_present_seconds doesn't double-count downtime.

        Called automatically from process_track_frame() when a frame arrives
        while paused.
        """
        if self._paused_at is None:
            return
        offline_duration = now_mono - self._paused_at
        if offline_duration <= 0:
            self._paused_at = None
            return

        for state in self._students.values():
            if state.absent_since is not None:
                state.absent_since += offline_duration
            if state.last_seen_time is not None:
                state.last_seen_time += offline_duration
            if state.last_presence_start is not None:
                state.last_presence_start += offline_duration

        logger.info(
            "Presence tracking RESUMED for schedule %s (camera back after %.1fs offline)",
            self.schedule_id[:8],
            offline_duration,
        )
        self._paused_at = None

    def start_session(self) -> None:
        """Load all enrolled students and create attendance records in batch.

        Also auto-enrolls face-registered students who match the schedule's
        target course/year but aren't enrolled yet, ensuring attendance is
        tracked for anyone whose face can be recognized.
        """
        self._schedule = self.schedule_repo.get_by_id(self.schedule_id)
        if not self._schedule:
            raise ValueError(f"Schedule not found: {self.schedule_id}")

        # Load per-schedule early leave timeout (fall back to global default)
        if getattr(self._schedule, "early_leave_timeout_minutes", None) is not None:
            self._early_leave_timeout = self._schedule.early_leave_timeout_minutes * 60.0

        self._session_start = datetime.now()

        # Auto-enroll face-registered students who match this schedule
        self._auto_enroll_matching_students()

        students = self.schedule_repo.get_enrolled_students(self.schedule_id)

        today = date.today()
        for student in students:
            sid = str(student.id)
            self._enrolled_ids.add(sid)
            name = student.first_name
            self._name_map[sid] = name

            # Get or create attendance record
            existing = self.attendance_repo.get_by_student_date(sid, self.schedule_id, today)
            if not existing:
                record = self.attendance_repo.create(
                    {
                        "student_id": sid,
                        "schedule_id": self.schedule_id,
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

            self._students[sid] = StudentPresenceState(
                student_id=sid,
                attendance_id=attendance_id,
                name=name,
            )

        if not students:
            logger.warning(
                "TrackPresenceService: NO enrolled students for schedule %s (%s). "
                "Attendance will not be tracked. Check enrollments. "
                "target_course=%s, target_year_level=%s",
                self.schedule_id,
                self._schedule.subject_code,
                getattr(self._schedule, "target_course", None),
                getattr(self._schedule, "target_year_level", None),
            )
        else:
            logger.info(
                "TrackPresenceService started for schedule %s (%s) with %d enrolled students. "
                "enrolled_ids=%s, target_course=%s, target_year_level=%s",
                self.schedule_id,
                self._schedule.subject_code,
                len(students),
                list(self._enrolled_ids),
                getattr(self._schedule, "target_course", None),
                getattr(self._schedule, "target_year_level", None),
            )

    def _jit_enroll_student(self, user_id: str) -> bool:
        """Just-in-time enroll a recognized student who isn't pre-enrolled.

        Called when the pipeline recognizes a face that isn't in _enrolled_ids.
        Creates enrollment + attendance record on the spot so the normal
        check-in flow can proceed. Only fires once per user per session.
        """
        try:
            from app.models.enrollment import Enrollment
            from app.models.user import User, UserRole

            user = (
                self.db.query(User)
                .filter(User.id == user_id, User.role == UserRole.STUDENT, User.is_active == True)
                .first()
            )
            if not user:
                logger.warning(
                    "JIT enroll failed: user_id=%s not found or not active student in schedule %s",
                    user_id,
                    self.schedule_id,
                )
                return False

            # Create enrollment if missing
            existing_enrollment = (
                self.db.query(Enrollment)
                .filter(
                    Enrollment.student_id == user.id,
                    Enrollment.schedule_id == self._schedule.id,
                )
                .first()
            )
            if not existing_enrollment:
                self.db.add(Enrollment(student_id=user.id, schedule_id=self._schedule.id))
                self.db.commit()

            # Create attendance record if missing for today
            today = date.today()
            sid = str(user.id)
            existing = self.attendance_repo.get_by_student_date(sid, self.schedule_id, today)
            if not existing:
                record = self.attendance_repo.create(
                    {
                        "student_id": sid,
                        "schedule_id": self.schedule_id,
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

            name = user.first_name
            self._enrolled_ids.add(sid)
            self._name_map[sid] = name
            self._students[sid] = StudentPresenceState(
                student_id=sid,
                attendance_id=attendance_id,
                name=name,
            )

            logger.info(
                "JIT enrolled student %s (%s) into schedule %s (%s)",
                sid,
                name,
                self.schedule_id,
                self._schedule.subject_code,
            )
            return True

        except Exception:
            logger.exception(
                "JIT enrollment DB error for user_id=%s in schedule %s",
                user_id,
                self.schedule_id,
            )
            return False

    def _auto_enroll_matching_students(self) -> None:
        """Auto-enroll face-registered students who match this schedule's target.

        Catches students who registered after the schedule was created, or whose
        auto-enrollment during registration was skipped/failed.
        """
        from app.models.enrollment import Enrollment
        from app.models.face_registration import FaceRegistration
        from app.models.student_record import StudentRecord
        from app.models.user import User, UserRole

        schedule = self._schedule
        target_course = schedule.target_course
        target_year = schedule.target_year_level

        if not target_course and not target_year:
            return

        # Find face-registered students matching the target course/year
        query = (
            self.db.query(User)
            .join(FaceRegistration, FaceRegistration.user_id == User.id)
            .join(StudentRecord, StudentRecord.student_id == User.student_id)
            .filter(
                User.role == UserRole.STUDENT,
                User.is_active == True,
                FaceRegistration.is_active == True,
            )
        )
        if target_course:
            query = query.filter(StudentRecord.course == target_course)
        if target_year:
            query = query.filter(StudentRecord.year_level == target_year)

        matching_students = query.all()

        # Get already-enrolled student IDs
        existing_enrollments = self.db.query(Enrollment.student_id).filter(Enrollment.schedule_id == schedule.id).all()
        enrolled_user_ids = {row[0] for row in existing_enrollments}

        # Enroll missing students
        newly_enrolled = 0
        for student in matching_students:
            if student.id not in enrolled_user_ids:
                enrollment = Enrollment(
                    student_id=student.id,
                    schedule_id=schedule.id,
                )
                self.db.add(enrollment)
                newly_enrolled += 1

        if newly_enrolled:
            self.db.commit()
            logger.info(
                "Auto-enrolled %d face-registered students into schedule %s (%s)",
                newly_enrolled,
                self.schedule_id,
                schedule.subject_code,
            )

    def process_track_frame(self, track_frame: TrackFrame, now_mono: float) -> list[dict]:
        """Update in-memory presence state from a TrackFrame.

        Returns list of events (check_in, early_leave, early_leave_return) for
        downstream notification/broadcasting.
        """
        events: list[dict] = []

        # Auto-resume absence tracking if we were paused (camera just came back online).
        # This shifts all absent_since timers forward by the offline duration so we
        # don't falsely trigger early_leave events for students who were present
        # before the camera outage.
        if self._paused_at is not None:
            self.resume_absence_tracking(now_mono)

        # Collect recognized user_ids from this frame
        present_user_ids: set[str] = set()
        for track in track_frame.tracks:
            if track.user_id and track.user_id in self._enrolled_ids:
                present_user_ids.add(track.user_id)
            elif track.user_id and track.user_id not in self._enrolled_ids:
                # JIT enroll recognized student who isn't pre-enrolled
                if self._jit_enroll_student(track.user_id):
                    present_user_ids.add(track.user_id)
                else:
                    logger.warning(
                        "Recognized face user_id=%s but JIT enrollment failed — attendance NOT tracked (schedule %s)",
                        track.user_id,
                        self.schedule_id,
                    )

        for sid, state in self._students.items():
            try:
                is_present = sid in present_user_ids

                if is_present:
                    # Student detected
                    if state.status == AttendanceStatus.ABSENT:
                        # First detection → check in
                        now_dt = datetime.now()
                        grace_time = (
                            datetime.combine(date.today(), self._schedule.start_time)
                            + timedelta(minutes=settings.GRACE_PERIOD_MINUTES)
                        ).time()
                        new_status = AttendanceStatus.PRESENT if now_dt.time() <= grace_time else AttendanceStatus.LATE
                        state.status = new_status
                        state.check_in_time = now_dt
                        state.last_seen_time = now_mono
                        state.last_seen_at = now_dt
                        state.last_presence_start = now_mono
                        state.absent_since = None

                        # Write check-in to DB immediately
                        self.attendance_repo.update(
                            state.attendance_id,
                            {
                                "status": new_status,
                                "check_in_time": now_dt,
                            },
                        )

                        events.append(
                            {
                                "event": "check_in",
                                "student_id": sid,
                                "student_name": state.name,
                                "status": new_status.value,
                                "check_in_time": now_dt.isoformat(),
                                "attendance_id": state.attendance_id,
                            }
                        )

                        logger.info(
                            "Student %s (%s) checked in: %s",
                            sid,
                            state.name,
                            new_status.value,
                        )

                    elif state.early_leave_flagged and not state.early_leave_returned:
                        # Returned after early leave — restore status but keep flag for logging.
                        # CRITICAL: compute absence duration BEFORE clearing absent_since,
                        # otherwise the EarlyLeaveEvent update below stores None.
                        absent_duration = None
                        if state.absent_since is not None:
                            absent_duration = int(now_mono - state.absent_since)
                        state.early_leave_returned = True
                        state.absent_since = None
                        state.last_presence_start = now_mono

                        # Restore attendance record to original status (PRESENT/LATE)
                        # and clear the stale check_out_time written when we
                        # flagged early-leave; end_session will re-stamp it.
                        restored_status = state.status
                        self.attendance_repo.update(
                            state.attendance_id,
                            {
                                "status": restored_status,
                                "check_out_time": None,
                            },
                        )

                        # Persist return to EarlyLeaveEvent record.
                        # Coerce string UUID → uuid.UUID for cross-DB compatibility.
                        _att_uuid = (
                            uuid.UUID(state.attendance_id)
                            if isinstance(state.attendance_id, str)
                            else state.attendance_id
                        )
                        early_event = (
                            self.db.query(EarlyLeaveEvent)
                            .filter(
                                EarlyLeaveEvent.attendance_id == _att_uuid,
                                EarlyLeaveEvent.returned == False,
                            )
                            .order_by(desc(EarlyLeaveEvent.detected_at))
                            .first()
                        )
                        if early_event:
                            early_event.returned = True
                            early_event.returned_at = datetime.now()
                            if absent_duration is not None:
                                early_event.absence_duration_seconds = absent_duration
                            self.db.commit()

                        events.append(
                            {
                                "event": "early_leave_return",
                                "student_id": sid,
                                "student_name": state.name,
                                "restored_status": restored_status.value,
                                "returned_at": datetime.now().isoformat(),
                                "attendance_id": state.attendance_id,
                            }
                        )
                        logger.info("Student %s returned after early leave, restored to %s", sid, restored_status.value)

                    else:
                        # Already present — accumulate time
                        state.absent_since = None
                        if state.last_presence_start is None:
                            state.last_presence_start = now_mono

                    state.last_seen_time = now_mono
                    state.last_seen_at = datetime.now()

                else:
                    # Student NOT detected
                    if state.last_presence_start is not None:
                        # Was present, now absent — accumulate elapsed time
                        elapsed = now_mono - state.last_presence_start
                        state.total_present_seconds += elapsed
                        state.last_presence_start = None

                    if state.status != AttendanceStatus.ABSENT and (
                        not state.early_leave_flagged or state.early_leave_returned
                    ):
                        # Track absence duration
                        if state.absent_since is None:
                            state.absent_since = now_mono
                        elif (now_mono - state.absent_since) > self._early_leave_timeout:
                            # Trigger early leave
                            state.early_leave_flagged = True
                            state.early_leave_returned = False  # Reset return flag for new absence
                            absent_seconds = now_mono - state.absent_since
                            events.append(
                                {
                                    "event": "early_leave",
                                    "student_id": sid,
                                    "student_name": state.name,
                                    "attendance_id": state.attendance_id,
                                    "absent_seconds": absent_seconds,
                                }
                            )
                            # Stamp check_out_time with the actual last
                            # detection so end_session() (which only fills
                            # null check-outs) doesn't clobber it with the
                            # session-end timestamp.
                            update_payload: dict = {"status": AttendanceStatus.EARLY_LEAVE}
                            if state.last_seen_at is not None:
                                update_payload["check_out_time"] = state.last_seen_at
                            self.attendance_repo.update(state.attendance_id, update_payload)

                            # Persist EarlyLeaveEvent to DB
                            consecutive_misses = int(absent_seconds / settings.SCAN_INTERVAL_SECONDS)
                            # Coerce string UUID → uuid.UUID (SQLAlchemy UUID column on
                            # SQLite requires object; PostgreSQL works with either).
                            _attendance_uuid = (
                                uuid.UUID(state.attendance_id)
                                if isinstance(state.attendance_id, str)
                                else state.attendance_id
                            )
                            early_leave_event = EarlyLeaveEvent(
                                attendance_id=_attendance_uuid,
                                detected_at=datetime.now(),
                                last_seen_at=(state.last_seen_at or state.check_in_time or datetime.now()),
                                consecutive_misses=max(1, consecutive_misses),
                                context_severity="auto_detected",
                            )
                            self.db.add(early_leave_event)
                            self.db.commit()

                            logger.warning(
                                "Early leave: student %s absent for %.0fs",
                                sid,
                                absent_seconds,
                            )

            except Exception:
                logger.exception(
                    "Error processing presence for student %s in schedule %s",
                    sid,
                    self.schedule_id,
                )

        return events

    def flush_presence_logs(self) -> None:
        """Batch write presence metrics to DB.

        Called periodically by the pipeline (every PRESENCE_FLUSH_INTERVAL).
        """
        if not self._session_start:
            return

        now = datetime.now()
        session_duration = (now - self._session_start).total_seconds()
        if session_duration <= 0:
            return

        for _sid, state in self._students.items():
            if state.status == AttendanceStatus.ABSENT:
                continue

            try:
                total_seconds = state.total_present_seconds
                # Add current ongoing presence if still present
                if state.last_presence_start is not None:
                    import time

                    total_seconds += time.monotonic() - state.last_presence_start

                presence_score = min(100.0, (total_seconds / session_duration) * 100.0)

                # Map time-based to scan-equivalent for backward compatibility
                scan_equivalent_total = max(1, int(session_duration / settings.SCAN_INTERVAL_SECONDS))
                scan_equivalent_present = int(scan_equivalent_total * (presence_score / 100.0))

                self.attendance_repo.update(
                    state.attendance_id,
                    {
                        "total_scans": scan_equivalent_total,
                        "scans_present": scan_equivalent_present,
                        "presence_score": round(presence_score, 2),
                        "total_present_seconds": round(total_seconds, 2),
                    },
                )
            except Exception:
                logger.exception(
                    "Error flushing presence for student %s in schedule %s",
                    _sid,
                    self.schedule_id,
                )

        logger.debug(
            "Flushed presence for schedule %s (%d students)",
            self.schedule_id,
            len(self._students),
        )

    def end_session(self) -> dict:
        """Final flush and session summary.

        Returns:
            Summary dict with counts and stats.
        """
        import time as _time

        now_mono = _time.monotonic()

        # Finalize any ongoing presence periods
        for state in self._students.values():
            if state.last_presence_start is not None:
                state.total_present_seconds += now_mono - state.last_presence_start
                state.last_presence_start = None

        # Final flush
        self.flush_presence_logs()

        # Set check-out times. Skip the check_out_time write when it's
        # already populated (early-leavers carry their last_seen_at from
        # flag_early_leave); only PRESENT/LATE students who stayed through
        # the session get the session-end timestamp here.
        now_dt = datetime.now()
        for state in self._students.values():
            if state.status == AttendanceStatus.ABSENT:
                continue
            current = self.attendance_repo.get_by_id(state.attendance_id)
            update_payload: dict = {
                "total_present_seconds": round(state.total_present_seconds, 2),
            }
            if current is None or current.check_out_time is None:
                update_payload["check_out_time"] = now_dt
            self.attendance_repo.update(state.attendance_id, update_payload)

        summary = {
            "total_students": len(self._students),
            "present_count": sum(
                1
                for s in self._students.values()
                if s.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
                and not (s.early_leave_flagged and not s.early_leave_returned)
            ),
            "early_leave_count": sum(
                1 for s in self._students.values() if s.early_leave_flagged and not s.early_leave_returned
            ),
            "absent_count": sum(1 for s in self._students.values() if s.status == AttendanceStatus.ABSENT),
        }

        logger.info("Session ended for schedule %s: %s", self.schedule_id, summary)
        return summary

    def get_attendance_summary(self) -> dict:
        """Build current attendance summary for WebSocket broadcast."""
        present = []
        absent = []
        late = []
        early_leave = []
        early_leave_returned = []

        for sid, state in self._students.items():
            info = {"user_id": sid, "name": state.name}

            if state.early_leave_flagged and not state.early_leave_returned:
                # Still absent after early leave
                early_leave.append(info)
            elif state.early_leave_flagged and state.early_leave_returned:
                # Returned after early leave — show in original category AND early_leave_returned
                early_leave_returned.append(info)
                if state.status == AttendanceStatus.LATE:
                    late.append(info)
                elif state.status == AttendanceStatus.PRESENT:
                    present.append(info)
            elif state.status == AttendanceStatus.ABSENT:
                absent.append(info)
            elif state.status == AttendanceStatus.LATE:
                late.append(info)
            elif state.status == AttendanceStatus.PRESENT:
                present.append(info)

        return {
            "type": "attendance_summary",
            "schedule_id": self.schedule_id,
            "present_count": len(present) + len(late),
            "on_time_count": len(present),
            "late_count": len(late),
            "absent_count": len(absent),
            "early_leave_count": len(early_leave),
            "total_enrolled": len(self._students),
            "present": present,
            "absent": absent,
            "late": late,
            "early_leave": early_leave,
            "early_leave_returned": early_leave_returned,
        }
