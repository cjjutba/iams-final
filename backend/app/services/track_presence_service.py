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
from dataclasses import dataclass, field
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

    def start_session(self) -> None:
        """Load all enrolled students and create attendance records in batch."""
        self._schedule = self.schedule_repo.get_by_id(self.schedule_id)
        if not self._schedule:
            raise ValueError(f"Schedule not found: {self.schedule_id}")

        # Load per-schedule early leave timeout (fall back to global default)
        if getattr(self._schedule, "early_leave_timeout_minutes", None) is not None:
            self._early_leave_timeout = self._schedule.early_leave_timeout_minutes * 60.0

        self._session_start = datetime.now()
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
                record = self.attendance_repo.create({
                    "student_id": sid,
                    "schedule_id": self.schedule_id,
                    "date": today,
                    "status": AttendanceStatus.ABSENT,
                    "total_scans": 0,
                    "scans_present": 0,
                    "presence_score": 0.0,
                })
                attendance_id = str(record.id)
            else:
                attendance_id = str(existing.id)

            self._students[sid] = StudentPresenceState(
                student_id=sid,
                attendance_id=attendance_id,
                name=name,
            )

        logger.info(
            "TrackPresenceService started for schedule %s with %d students",
            self.schedule_id, len(students),
        )

    def process_track_frame(self, track_frame: TrackFrame, now_mono: float) -> list[dict]:
        """Update in-memory presence state from a TrackFrame.

        Returns list of events (check_in, early_leave, early_leave_return) for
        downstream notification/broadcasting.
        """
        events: list[dict] = []

        # Collect recognized user_ids from this frame
        present_user_ids: set[str] = set()
        for track in track_frame.tracks:
            if track.user_id and track.user_id in self._enrolled_ids:
                present_user_ids.add(track.user_id)

        for sid, state in self._students.items():
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
                    new_status = (
                        AttendanceStatus.PRESENT
                        if now_dt.time() <= grace_time
                        else AttendanceStatus.LATE
                    )
                    state.status = new_status
                    state.check_in_time = now_dt
                    state.last_seen_time = now_mono
                    state.last_presence_start = now_mono
                    state.absent_since = None

                    # Write check-in to DB immediately
                    self.attendance_repo.update(state.attendance_id, {
                        "status": new_status,
                        "check_in_time": now_dt,
                    })

                    events.append({
                        "event": "check_in",
                        "student_id": sid,
                        "student_name": state.name,
                        "status": new_status.value,
                        "check_in_time": now_dt.isoformat(),
                    })

                    logger.info("Student %s checked in: %s", sid, new_status.value)

                elif state.early_leave_flagged and not state.early_leave_returned:
                    # Returned after early leave — restore status but keep flag for logging
                    state.early_leave_returned = True
                    state.absent_since = None
                    state.last_presence_start = now_mono

                    # Restore attendance record to original status (PRESENT/LATE)
                    restored_status = state.status
                    self.attendance_repo.update(state.attendance_id, {
                        "status": restored_status,
                    })

                    # Persist return to EarlyLeaveEvent record
                    early_event = (
                        self.db.query(EarlyLeaveEvent)
                        .filter(
                            EarlyLeaveEvent.attendance_id == state.attendance_id,
                            EarlyLeaveEvent.returned == False,
                        )
                        .order_by(desc(EarlyLeaveEvent.detected_at))
                        .first()
                    )
                    if early_event:
                        early_event.returned = True
                        early_event.returned_at = datetime.now()
                        if state.absent_since is not None:
                            early_event.absence_duration_seconds = int(now_mono - state.absent_since)
                        self.db.commit()

                    events.append({
                        "event": "early_leave_return",
                        "student_id": sid,
                        "student_name": state.name,
                        "restored_status": restored_status.value,
                        "returned_at": datetime.now().isoformat(),
                    })
                    logger.info("Student %s returned after early leave, restored to %s", sid, restored_status.value)

                else:
                    # Already present — accumulate time
                    state.absent_since = None
                    if state.last_presence_start is None:
                        state.last_presence_start = now_mono

                state.last_seen_time = now_mono

            else:
                # Student NOT detected
                if state.last_presence_start is not None:
                    # Was present, now absent — accumulate elapsed time
                    elapsed = now_mono - state.last_presence_start
                    state.total_present_seconds += elapsed
                    state.last_presence_start = None

                if state.status != AttendanceStatus.ABSENT and (not state.early_leave_flagged or state.early_leave_returned):
                    # Track absence duration
                    if state.absent_since is None:
                        state.absent_since = now_mono
                    elif (now_mono - state.absent_since) > self._early_leave_timeout:
                        # Trigger early leave
                        state.early_leave_flagged = True
                        state.early_leave_returned = False  # Reset return flag for new absence
                        absent_seconds = now_mono - state.absent_since
                        events.append({
                            "event": "early_leave",
                            "student_id": sid,
                            "student_name": state.name,
                            "attendance_id": state.attendance_id,
                            "absent_seconds": absent_seconds,
                        })
                        self.attendance_repo.update(
                            state.attendance_id,
                            {"status": AttendanceStatus.EARLY_LEAVE},
                        )

                        # Persist EarlyLeaveEvent to DB
                        consecutive_misses = int(
                            absent_seconds / settings.SCAN_INTERVAL_SECONDS
                        )
                        early_leave_event = EarlyLeaveEvent(
                            attendance_id=state.attendance_id,
                            detected_at=datetime.now(),
                            last_seen_at=(
                                state.check_in_time
                                if state.check_in_time
                                else datetime.now()
                            ),
                            consecutive_misses=max(1, consecutive_misses),
                            context_severity="auto_detected",
                        )
                        self.db.add(early_leave_event)
                        self.db.commit()

                        logger.warning(
                            "Early leave: student %s absent for %.0fs",
                            sid, absent_seconds,
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

        for sid, state in self._students.items():
            if state.status == AttendanceStatus.ABSENT:
                continue

            total_seconds = state.total_present_seconds
            # Add current ongoing presence if still present
            if state.last_presence_start is not None:
                import time
                total_seconds += time.monotonic() - state.last_presence_start

            presence_score = min(100.0, (total_seconds / session_duration) * 100.0)

            # Map time-based to scan-equivalent for backward compatibility
            scan_equivalent_total = max(1, int(session_duration / settings.SCAN_INTERVAL_SECONDS))
            scan_equivalent_present = int(scan_equivalent_total * (presence_score / 100.0))

            self.attendance_repo.update(state.attendance_id, {
                "total_scans": scan_equivalent_total,
                "scans_present": scan_equivalent_present,
                "presence_score": round(presence_score, 2),
            })

        logger.debug(
            "Flushed presence for schedule %s (%d students)",
            self.schedule_id, len(self._students),
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

        # Set check-out times
        now_dt = datetime.now()
        for state in self._students.values():
            if state.status != AttendanceStatus.ABSENT:
                self.attendance_repo.update(state.attendance_id, {
                    "check_out_time": now_dt,
                })

        summary = {
            "total_students": len(self._students),
            "present_count": sum(
                1 for s in self._students.values()
                if s.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
            ),
            "early_leave_count": sum(
                1 for s in self._students.values() if s.early_leave_flagged
            ),
            "absent_count": sum(
                1 for s in self._students.values()
                if s.status == AttendanceStatus.ABSENT
            ),
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
                # Returned after early leave — show in both present/late AND early_leave_returned
                early_leave_returned.append(info)
                if state.status == AttendanceStatus.LATE:
                    late.append(info)
                    present.append(info)
                elif state.status == AttendanceStatus.PRESENT:
                    present.append(info)
            elif state.status == AttendanceStatus.ABSENT:
                absent.append(info)
            elif state.status == AttendanceStatus.LATE:
                late.append(info)
                present.append(info)
            elif state.status == AttendanceStatus.PRESENT:
                present.append(info)

        return {
            "type": "attendance_summary",
            "schedule_id": self.schedule_id,
            "present_count": len(present),
            "total_enrolled": len(self._students),
            "present": present,
            "absent": absent,
            "late": late,
            "early_leave": early_leave,
            "early_leave_returned": early_leave_returned,
        }
