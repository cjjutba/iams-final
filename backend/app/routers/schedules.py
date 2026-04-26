"""
Schedules Router

API endpoints for class schedule management.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.config import logger
from app.database import get_db
from app.models.attendance_record import AttendanceRecord, AttendanceStatus
from app.models.enrollment import Enrollment
from app.models.face_registration import FaceRegistration
from app.models.schedule import Schedule
from app.models.user import User, UserRole
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.schedule import (
    ScheduleConfigUpdate,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
    ScheduleWithStudents,
    SessionSummary,
)
from app.services import session_manager
from app.services.notification_service import (
    notify,
    notify_admins,
    notify_schedule_participants,
)
from app.utils.dependencies import get_current_user, require_role

router = APIRouter()


# ---------------------------------------------------------------------------
# Runtime status derivation
#
# `Schedule.is_active` is the enable/archive flag — it does NOT change with
# the clock. The admin "Schedule Management" page used to show "Active" for
# every enabled row, which read as "session is running" to operators. To
# fix that, we compute a presentation-only `runtime_status` per row using
# session_manager (which schedule IDs have a running pipeline?) plus the
# current wall clock (is this schedule's window in the past, present, or
# future?).
#
# Status taxonomy (frontend renders one badge per value):
#   "live"      — register_session() has been called for this schedule.id
#   "upcoming"  — today is the schedule's day, current time is before window
#   "ended"     — today, current time is past the window's end
#   "scheduled" — any other day (the common case for most rows)
#   "disabled"  — schedule.is_active is False (operator-archived)
#
# The "in window today but not live" gap (15 s lifecycle tick hasn't fired
# yet) collapses into "live" optimistically — see lessons file 2026-04-25.
# ---------------------------------------------------------------------------


def _compute_runtime_status(
    schedule: Schedule,
    active_session_ids: set[str],
    now: datetime,
) -> str:
    if not schedule.is_active:
        return "disabled"
    if str(schedule.id) in active_session_ids:
        return "live"
    if schedule.day_of_week != now.weekday():
        return "scheduled"
    now_t = now.time()
    if now_t < schedule.start_time:
        return "upcoming"
    if now_t > schedule.end_time:
        return "ended"
    # Today, in window, not registered — the lifecycle scheduler ticks every
    # 15 s and will register it shortly. Optimistic "live" avoids confusing
    # operators with a flickering "ended/upcoming" label during the gap.
    return "live"


def _serialize_schedule(
    schedule: Schedule,
    active_session_ids: set[str] | None = None,
    now: datetime | None = None,
) -> ScheduleResponse:
    """Build a ScheduleResponse with runtime_status populated.

    For batch endpoints (list_schedules, get_my_schedules) pass a single
    pre-snapshotted `active_session_ids` and `now` so we don't re-fetch them
    per row. Single-row callers may omit both — the helper snapshots once.
    """
    if active_session_ids is None:
        active_session_ids = session_manager.list_active_session_ids()
    if now is None:
        now = datetime.now()
    response = ScheduleResponse.model_validate(schedule)
    response.runtime_status = _compute_runtime_status(schedule, active_session_ids, now)
    return response


@router.get("/", response_model=list[ScheduleResponse], status_code=status.HTTP_200_OK)
def list_schedules(
    day: int | None = Query(None, ge=0, le=6, description="Filter by day (0=Monday, 6=Sunday)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **List All Schedules**

    Get all active schedules, optionally filtered by day of week.

    - **day**: Optional day filter (0=Monday, 6=Sunday)

    Returns list of schedules with faculty and room information.

    Requires authentication.
    """
    schedule_repo = ScheduleRepository(db)

    if day is not None:
        schedules = schedule_repo.get_by_day(day)
    else:
        schedules = schedule_repo.get_all()

    # Snapshot once and reuse across rows so all rows are derived against
    # the same instant — a row processed half a second after another that
    # crossed end_time would otherwise flip from "live" → "ended" mid-list.
    active = session_manager.list_active_session_ids()
    now = datetime.now()
    return [_serialize_schedule(s, active, now) for s in schedules]


@router.get("/me", response_model=list[ScheduleResponse], status_code=status.HTTP_200_OK)
def get_my_schedules(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    **Get My Schedules**

    Get schedules for the current user:
    - **Students**: Enrolled schedules
    - **Faculty**: Teaching schedules

    Returns list of relevant schedules with eager-loaded faculty and room info.

    Requires authentication.
    """
    from app.models.enrollment import Enrollment

    base_query = db.query(Schedule).options(
        joinedload(Schedule.faculty),
        joinedload(Schedule.room),
    )

    if current_user.role == UserRole.FACULTY:
        schedules = base_query.filter(
            Schedule.faculty_id == current_user.id,
            Schedule.is_active,
        ).all()
        logger.info(
            f"GET /schedules/me — faculty={current_user.email} "
            f"(id={current_user.id}), found {len(schedules)} schedule(s)"
        )
    elif current_user.role == UserRole.STUDENT:
        # Single query: join enrollments → schedules with faculty/room
        schedules = (
            base_query.join(Enrollment, Enrollment.schedule_id == Schedule.id)
            .filter(
                Enrollment.student_id == current_user.id,
                Schedule.is_active,
            )
            .all()
        )
        enrollment_count = db.query(Enrollment).filter(Enrollment.student_id == current_user.id).count()
        logger.info(
            f"GET /schedules/me — student={current_user.email} "
            f"(id={current_user.id}), enrollments={enrollment_count}, "
            f"active schedules={len(schedules)}"
        )
    else:
        schedules = base_query.filter(Schedule.is_active).all()
        logger.info(f"GET /schedules/me — admin={current_user.email}, found {len(schedules)} schedule(s)")

    active = session_manager.list_active_session_ids()
    now = datetime.now()
    return [_serialize_schedule(s, active, now) for s in schedules]


@router.get("/{schedule_id}", response_model=ScheduleResponse, status_code=status.HTTP_200_OK)
def get_schedule(schedule_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    **Get Schedule by ID**

    Retrieve detailed schedule information.

    - **schedule_id**: Schedule UUID

    Requires authentication.
    """
    schedule_repo = ScheduleRepository(db)
    schedule = schedule_repo.get_by_id(schedule_id)

    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    return _serialize_schedule(schedule)


@router.get("/{schedule_id}/students", response_model=ScheduleWithStudents, status_code=status.HTTP_200_OK)
def get_enrolled_students(
    schedule_id: str,
    current_user: User = Depends(require_role(UserRole.FACULTY, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    **Get Enrolled Students** (Faculty/Admin Only)

    Get list of students enrolled in a schedule.

    - **schedule_id**: Schedule UUID

    Returns schedule with enrolled students list.

    Requires faculty or admin authentication.
    """
    schedule_repo = ScheduleRepository(db)
    schedule = schedule_repo.get_by_id(schedule_id)

    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    students = schedule_repo.get_enrolled_students(schedule_id)

    # Single batch lookup so we don't N+1 face_registrations per row. The
    # set comprehension narrows to active registrations only — the model
    # has a unique constraint on user_id but `is_active` can flip false
    # when an admin resets a student's face from the user detail page.
    student_ids = [s.id for s in students]
    registered_ids: set[str] = set()
    if student_ids:
        rows = (
            db.query(FaceRegistration.user_id)
            .filter(
                FaceRegistration.user_id.in_(student_ids),
                FaceRegistration.is_active.is_(True),
            )
            .all()
        )
        registered_ids = {str(r[0]) for r in rows}

    # Convert to response format
    response = _serialize_schedule(schedule)
    student_info = [
        {
            "id": str(s.id),
            "student_id": s.student_id,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "email": s.email,
            "has_face_registered": str(s.id) in registered_ids,
        }
        for s in students
    ]

    return ScheduleWithStudents(**response.model_dump(), enrolled_students=student_info)


@router.get(
    "/{schedule_id}/sessions",
    response_model=list[SessionSummary],
    status_code=status.HTTP_200_OK,
)
def get_schedule_sessions(
    schedule_id: str,
    start_date: date | None = Query(None, description="Earliest session date (inclusive)"),
    end_date: date | None = Query(None, description="Latest session date (inclusive)"),
    limit: int = Query(50, ge=1, le=500, description="Max sessions to return"),
    current_user: User = Depends(require_role(UserRole.FACULTY, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """**Get Session History** (Faculty/Admin Only)

    List past sessions for a schedule with per-status counts and the
    derived attendance rate. A "session" is the set of attendance_records
    sharing the same `date` for this schedule_id. Ordered newest first
    and capped by `limit` (default 50).

    Each row carries the schedule's canonical start/end window — the
    actual session boundaries are inferable from presence_logs but at
    this granularity the schedule window is what operators expect.
    """
    schedule_repo = ScheduleRepository(db)
    schedule = schedule_repo.get_by_id(schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    import uuid as _uuid

    schedule_uuid = _uuid.UUID(schedule_id) if isinstance(schedule_id, str) else schedule_id

    # Single GROUP BY date,status pass — one row per (date, status) pair.
    # We pivot client-side because the conditional COUNT pattern below
    # works on both Postgres and SQLite without engine-specific filter
    # syntax.
    q = (
        db.query(
            AttendanceRecord.date.label("date"),
            AttendanceRecord.status.label("status"),
            func.count(AttendanceRecord.id).label("n"),
        )
        .filter(AttendanceRecord.schedule_id == schedule_uuid)
        .group_by(AttendanceRecord.date, AttendanceRecord.status)
    )
    if start_date is not None:
        q = q.filter(AttendanceRecord.date >= start_date)
    if end_date is not None:
        q = q.filter(AttendanceRecord.date <= end_date)

    grouped: dict[date, dict[str, int]] = {}
    for row in q.all():
        d = row.date
        # SQLAlchemy returns the enum's value (a string) on Postgres; on
        # SQLite it's the enum object. Normalize to the string value.
        status_val = row.status.value if hasattr(row.status, "value") else str(row.status)
        bucket = grouped.setdefault(d, {})
        bucket[status_val] = bucket.get(status_val, 0) + int(row.n)

    sessions: list[SessionSummary] = []
    for d in sorted(grouped.keys(), reverse=True)[:limit]:
        b = grouped[d]
        present = b.get(AttendanceStatus.PRESENT.value, 0)
        late = b.get(AttendanceStatus.LATE.value, 0)
        absent = b.get(AttendanceStatus.ABSENT.value, 0)
        early_leave = b.get(AttendanceStatus.EARLY_LEAVE.value, 0)
        excused = b.get(AttendanceStatus.EXCUSED.value, 0)
        total = present + late + absent + early_leave + excused
        rate = round(((present + late) / total) * 100, 1) if total > 0 else None
        sessions.append(
            SessionSummary(
                date=d,
                start_time=schedule.start_time,
                end_time=schedule.end_time,
                present=present,
                late=late,
                absent=absent,
                early_leave=early_leave,
                excused=excused,
                attendance_rate=rate,
                total_records=total,
            )
        )

    return sessions


@router.post("/", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule_data: ScheduleCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    **Create Schedule** (Admin Only)

    Create a new class schedule.

    - **schedule_data**: Schedule information

    Requires admin authentication.
    """
    schedule_repo = ScheduleRepository(db)
    schedule = schedule_repo.create(schedule_data.model_dump())

    logger.info(f"Schedule created: {schedule.subject_code} by admin {current_user.email}")

    # Audit + System Activity feed. Wrapped in a try so a logging failure
    # never undoes the schedule create.
    try:
        from app.utils.audit import log_audit

        log_audit(
            db,
            admin_id=current_user.id,
            action="create",
            target_type="schedule",
            target_id=str(schedule.id),
            details=f"Schedule created: {schedule.subject_code} ({schedule.subject_name})",
            activity_summary=(
                f"Schedule created: {schedule.subject_code} — {schedule.subject_name}"
            ),
            activity_payload={
                "subject_code": schedule.subject_code,
                "subject_name": schedule.subject_name,
                "day_of_week": schedule.day_of_week,
                "start_time": str(schedule.start_time) if schedule.start_time else None,
                "end_time": str(schedule.end_time) if schedule.end_time else None,
                "room_id": str(schedule.room_id) if schedule.room_id else None,
                "faculty_id": str(schedule.faculty_id) if schedule.faculty_id else None,
            },
            activity_severity="success",
        )
    except Exception:
        logger.warning("log_audit failed for schedule.create", exc_info=True)

    # Schedule conflict warning (informational; do NOT abort the create).
    # Checks for overlapping schedules on the same day for the same faculty.
    try:
        if schedule.faculty_id and schedule.day_of_week is not None:
            conflicts = (
                db.query(Schedule)
                .filter(
                    Schedule.faculty_id == schedule.faculty_id,
                    Schedule.day_of_week == schedule.day_of_week,
                    Schedule.id != schedule.id,
                    Schedule.is_active.is_(True),
                    Schedule.start_time < schedule.end_time,
                    Schedule.end_time > schedule.start_time,
                )
                .all()
            )
            if conflicts:
                conflict_codes = ", ".join(c.subject_code for c in conflicts)
                await notify(
                    db,
                    user_id=str(current_user.id),
                    title="Schedule conflict warning",
                    message=(
                        f"Faculty already has {len(conflicts)} schedule(s) "
                        f"overlapping this slot: {conflict_codes}."
                    ),
                    notification_type="schedule_conflict_warning",
                    severity="warn",
                    preference_key="schedule_conflict_alerts",
                    send_email=False,
                    dedup_window_seconds=0,
                    reference_id=(
                        f"conflict:{schedule.faculty_id}:"
                        f"{schedule.day_of_week}:{schedule.start_time}"
                    ),
                    reference_type="composite_key",
                    toast_type="warning",
                )
    except Exception:
        logger.exception("Failed to emit schedule conflict warning")

    # Notify the assigned faculty of the new schedule.
    if schedule.faculty_id is not None:
        try:
            day_labels = [
                "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday",
            ]
            day_name = (
                day_labels[schedule.day_of_week]
                if schedule.day_of_week is not None
                and 0 <= schedule.day_of_week <= 6
                else str(schedule.day_of_week)
            )
            room_name = schedule.room.name if schedule.room else "TBD"
            await notify(
                db,
                user_id=str(schedule.faculty_id),
                title=f"Schedule assigned: {schedule.subject_code}",
                message=(
                    f"You have been assigned a new schedule: "
                    f"{schedule.subject_code} on {day_name} from "
                    f"{schedule.start_time} to {schedule.end_time} "
                    f"in {room_name}."
                ),
                notification_type="schedule_assigned",
                severity="info",
                preference_key=None,
                send_email=True,
                email_template="schedule_assigned",
                email_context={
                    "subject_code": schedule.subject_code,
                    "day_of_week": day_name,
                    "start_time": str(schedule.start_time),
                    "end_time": str(schedule.end_time),
                    "room_name": room_name,
                },
                dedup_window_seconds=0,
                reference_id=str(schedule.id),
                reference_type="schedule",
                toast_type="info",
            )
        except Exception:
            logger.exception("Failed to notify faculty of schedule assignment")

    return _serialize_schedule(schedule)


@router.patch("/{schedule_id}", response_model=ScheduleResponse, status_code=status.HTTP_200_OK)
async def update_schedule(
    schedule_id: str,
    update_data: ScheduleUpdate,
    http_request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    **Update Schedule** (Admin Only)

    Update schedule information.

    - **schedule_id**: Schedule UUID
    - **update_data**: Fields to update (all optional)

    Requires admin authentication.
    """
    schedule_repo = ScheduleRepository(db)

    # Filter out None values
    update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}

    # Snapshot old field values BEFORE applying the patch so we can diff
    # for the participant-facing notification message.
    before = schedule_repo.get_by_id(schedule_id)
    old_room_id = before.room_id if before else None
    old_room_name = (
        before.room.name if before and before.room else None
    )
    old_start_time = before.start_time if before else None
    old_end_time = before.end_time if before else None
    old_day_of_week = before.day_of_week if before else None

    schedule = schedule_repo.update(schedule_id, update_dict)

    logger.info(f"Schedule updated: {schedule_id} by admin {current_user.email}")

    # ---------------------------------------------------------------
    # Room-swap handling for active sessions.
    #
    # When room_id changes mid-session, the running SessionPipeline is
    # still attached to the OLD room's FrameGrabber — the WS broadcasts
    # bboxes in the old camera's coordinate space onto the new camera's
    # video, producing the misaligned-overlay bug seen on 2026-04-26.
    # We hot-swap the pipeline's grabber + reset tracker state so the
    # next frame comes from the NEW camera. Presence accumulation and
    # attendance records are preserved (the session continues from the
    # operator's POV).
    #
    # If the new room has no `camera_endpoint`, we end the session
    # cleanly + emit a warn notification so the operator knows ML
    # tracking stopped (silently keeping the old camera on a "moved"
    # schedule is the worst UX).
    # ---------------------------------------------------------------
    room_changed = (
        "room_id" in update_dict
        and old_room_id is not None
        and old_room_id != schedule.room_id
    )
    if room_changed:
        pipelines = getattr(http_request.app.state, "session_pipelines", None)
        pipeline = pipelines.get(schedule_id) if pipelines else None
        if pipeline is not None and pipeline.is_running:
            from app.models.room import Room

            new_room = db.query(Room).filter(Room.id == schedule.room_id).first()
            new_room_name = new_room.name if new_room else "TBD"
            new_camera = new_room.camera_endpoint if new_room else None

            if not new_camera:
                # New room has no camera — end the session, can't track.
                try:
                    await pipeline.stop()
                except Exception:
                    logger.exception(
                        "[room-swap] pipeline.stop() failed for %s",
                        schedule_id,
                    )
                if pipelines is not None:
                    pipelines.pop(schedule_id, None)

                # Best-effort end of the legacy presence-service session
                # so was_session_ended_today() reflects reality and the
                # SessionStatusPill flips to "ended" cleanly.
                try:
                    from app.services.presence_service import PresenceService

                    presence_svc = PresenceService(db)
                    if schedule_id in presence_svc.active_sessions:
                        await presence_svc.end_session(schedule_id)
                except Exception:
                    logger.exception(
                        "[room-swap] presence_svc.end_session failed for %s",
                        schedule_id,
                    )

                try:
                    await notify_admins(
                        db,
                        title=f"Session ended: {schedule.subject_code}",
                        message=(
                            f"The room was changed to {new_room_name} which "
                            f"has no camera configured. The active session "
                            f"was ended; presence tracking stopped."
                        ),
                        notification_type="session_ended_no_camera",
                        severity="warn",
                        preference_key=None,
                        send_email=False,
                        dedup_window_seconds=0,
                        reference_id=str(schedule.id),
                        reference_type="schedule",
                        toast_type="warning",
                    )
                except Exception:
                    logger.exception(
                        "[room-swap] notify_admins(session_ended_no_camera) failed"
                    )
            else:
                # Hot-swap: get-or-create FrameGrabber for new room,
                # then ask the pipeline to swap onto it.
                grabbers = getattr(
                    http_request.app.state, "frame_grabbers", None
                )
                new_grabber = (
                    grabbers.get(str(schedule.room_id)) if grabbers else None
                )
                if new_grabber is None:
                    try:
                        from app.services.frame_grabber import FrameGrabber

                        new_grabber = FrameGrabber(new_camera, dedup_repeats=True)
                        if grabbers is not None:
                            grabbers[str(schedule.room_id)] = new_grabber
                        logger.info(
                            "[room-swap] Created on-demand FrameGrabber "
                            "for room %s",
                            schedule.room_id,
                        )
                    except Exception:
                        logger.exception(
                            "[room-swap] Failed to create FrameGrabber "
                            "for room %s — leaving pipeline on old "
                            "camera. Operator should retry.",
                            schedule.room_id,
                        )
                        new_grabber = None

                if new_grabber is not None:
                    try:
                        await pipeline.swap_camera(
                            new_grabber, str(schedule.room_id)
                        )
                        logger.info(
                            "[room-swap] Pipeline %s swapped %s -> %s",
                            schedule_id,
                            old_room_name or old_room_id,
                            new_room_name,
                        )

                        # System Activity audit row — visible in the
                        # admin activity timeline so operators can
                        # correlate "boxes shifted at 17:54" with
                        # "admin changed the room at 17:54".
                        try:
                            from app.services.activity_service import (
                                EventSeverity,
                                EventType,
                                emit_system_event,
                            )

                            emit_system_event(
                                db,
                                event_type=EventType.PIPELINE_CAMERA_SWAPPED,
                                summary=(
                                    f"Camera swapped for {schedule.subject_code}: "
                                    f"{old_room_name or 'unknown'} -> {new_room_name}"
                                ),
                                severity=EventSeverity.INFO,
                                schedule_id=str(schedule.id),
                                room_id=str(schedule.room_id),
                                payload={
                                    "subject_code": schedule.subject_code,
                                    "old_room_id": str(old_room_id),
                                    "old_room_name": old_room_name,
                                    "new_room_id": str(schedule.room_id),
                                    "new_room_name": new_room_name,
                                    "actor_email": current_user.email,
                                },
                                autocommit=True,
                            )
                        except Exception:
                            logger.warning(
                                "[room-swap] PIPELINE_CAMERA_SWAPPED emit failed",
                                exc_info=True,
                            )
                    except Exception:
                        logger.exception(
                            "[room-swap] swap_camera failed for %s — "
                            "the pipeline may still be on the old camera",
                            schedule_id,
                        )

    try:
        from app.utils.audit import log_audit

        # Stringify payload values so JSONB serialization never trips on
        # time / UUID objects from the update_dict pass-through.
        safe_changes = {k: str(v) if v is not None else None for k, v in update_dict.items()}

        log_audit(
            db,
            admin_id=current_user.id,
            action="update",
            target_type="schedule",
            target_id=str(schedule.id),
            details=f"Schedule updated: {schedule.subject_code}",
            activity_summary=(
                f"Schedule updated: {schedule.subject_code} — {schedule.subject_name}"
            ),
            activity_payload={
                "subject_code": schedule.subject_code,
                "changes": safe_changes,
            },
        )
    except Exception:
        logger.warning("log_audit failed for schedule.update", exc_info=True)

    # Build a human-readable diff and notify schedule participants when
    # any of the user-visible fields actually changed.
    try:
        changes: list[str] = []
        if old_room_id is not None and old_room_id != schedule.room_id:
            new_room_name = schedule.room.name if schedule.room else "TBD"
            changes.append(
                f"Room: {old_room_name or 'TBD'} -> {new_room_name}"
            )
        if old_start_time is not None and old_start_time != schedule.start_time:
            changes.append(
                f"Start time: {old_start_time} -> {schedule.start_time}"
            )
        if old_end_time is not None and old_end_time != schedule.end_time:
            changes.append(
                f"End time: {old_end_time} -> {schedule.end_time}"
            )
        if (
            old_day_of_week is not None
            and old_day_of_week != schedule.day_of_week
        ):
            changes.append(
                f"Day: {old_day_of_week} -> {schedule.day_of_week}"
            )
        if changes:
            await notify_schedule_participants(
                db,
                schedule_id=schedule.id,
                title=f"Schedule updated: {schedule.subject_code}",
                message=(
                    f"Changes to your schedule for {schedule.subject_code}: "
                    + "; ".join(changes)
                ),
                notification_type="schedule_updated",
                severity="info",
                preference_key=None,
                send_email=True,
                email_template="schedule_updated",
                email_context={
                    "subject_code": schedule.subject_code,
                    "changes": changes,
                },
                dedup_window_seconds=300,
                reference_id=str(schedule.id),
                reference_type="schedule",
                toast_type="info",
                include_admins=False,
            )
    except Exception:
        logger.exception(
            "Failed to notify schedule participants of update"
        )

    # Mirror the create-time conflict check so an UPDATE that introduces
    # a faculty overlap also surfaces a warning. Informational — does
    # NOT abort the update.
    try:
        if schedule.faculty_id and schedule.day_of_week is not None:
            conflicts = (
                db.query(Schedule)
                .filter(
                    Schedule.faculty_id == schedule.faculty_id,
                    Schedule.day_of_week == schedule.day_of_week,
                    Schedule.id != schedule.id,
                    Schedule.is_active.is_(True),
                    Schedule.start_time < schedule.end_time,
                    Schedule.end_time > schedule.start_time,
                )
                .all()
            )
            if conflicts:
                conflict_codes = ", ".join(c.subject_code for c in conflicts)
                await notify(
                    db,
                    user_id=str(current_user.id),
                    title="Schedule conflict warning",
                    message=(
                        f"After update, faculty has {len(conflicts)} "
                        f"schedule(s) overlapping this slot: {conflict_codes}."
                    ),
                    notification_type="schedule_conflict_warning",
                    severity="warn",
                    preference_key="schedule_conflict_alerts",
                    send_email=False,
                    # 5 min dedup keyed on the slot so repeated saves
                    # don't pile up duplicate warnings.
                    dedup_window_seconds=300,
                    reference_id=(
                        f"conflict:{schedule.faculty_id}:"
                        f"{schedule.day_of_week}:{schedule.start_time}"
                    ),
                    reference_type="composite_key",
                    toast_type="warning",
                )
    except Exception:
        logger.exception("Failed to emit schedule conflict warning on update")

    return _serialize_schedule(schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_200_OK)
async def delete_schedule(
    schedule_id: str, current_user: User = Depends(require_role(UserRole.ADMIN)), db: Session = Depends(get_db)
):
    """
    **Delete Schedule** (Admin Only)

    Deactivate a schedule (soft delete).

    - **schedule_id**: Schedule UUID

    Requires admin authentication.
    """
    schedule_repo = ScheduleRepository(db)
    # Capture identifying fields *before* the delete so the audit summary
    # has a human-readable name even on hard-delete (soft-delete keeps the
    # row but a future migration may flip this).
    target = schedule_repo.get_by_id(schedule_id)
    target_subject_code = target.subject_code if target else None
    target_subject_name = target.subject_name if target else None

    # Notify participants BEFORE the delete so we can still resolve the
    # faculty + enrollment FKs even if the delete is a hard-delete.
    if target is not None:
        try:
            await notify_schedule_participants(
                db,
                schedule_id=target.id,
                title=f"Class cancelled: {target.subject_code}",
                message=(
                    f"The class {target.subject_code} on day "
                    f"{target.day_of_week} {target.start_time}-"
                    f"{target.end_time} has been deleted."
                ),
                notification_type="schedule_deleted",
                severity="warn",
                preference_key=None,
                send_email=True,
                email_template="schedule_deleted",
                email_context={
                    "subject_code": target.subject_code,
                    "day_of_week": str(target.day_of_week),
                    "start_time": str(target.start_time),
                    "end_time": str(target.end_time),
                },
                dedup_window_seconds=0,
                reference_id=str(target.id),
                reference_type="schedule",
                toast_type="warning",
                include_admins=False,
            )
        except Exception:
            logger.exception(
                "Failed to notify schedule participants of deletion"
            )

    schedule_repo.delete(schedule_id)

    logger.info(f"Schedule deleted: {schedule_id} by admin {current_user.email}")

    try:
        from app.utils.audit import log_audit

        log_audit(
            db,
            admin_id=current_user.id,
            action="delete",
            target_type="schedule",
            target_id=str(schedule_id),
            details=(
                f"Schedule deleted: {target_subject_code or schedule_id}"
            ),
            activity_summary=(
                f"Schedule deleted: {target_subject_code or schedule_id}"
                + (f" — {target_subject_name}" if target_subject_name else "")
            ),
            activity_payload={
                "subject_code": target_subject_code,
                "subject_name": target_subject_name,
            },
            activity_severity="warn",
        )
    except Exception:
        logger.warning("log_audit failed for schedule.delete", exc_info=True)

    return {"success": True, "message": "Schedule deleted successfully"}


@router.patch("/{schedule_id}/config", response_model=ScheduleResponse, status_code=status.HTTP_200_OK)
def update_schedule_config(
    schedule_id: str,
    config_data: ScheduleConfigUpdate,
    http_request: Request,
    current_user: User = Depends(require_role(UserRole.FACULTY, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    **Update Schedule Config** (Faculty/Admin)

    Faculty can update attendance settings for their own schedules.
    Takes effect immediately on running sessions.

    - **schedule_id**: Schedule UUID
    - **early_leave_timeout_minutes**: 1-15 minutes
    """
    schedule_repo = ScheduleRepository(db)
    schedule = schedule_repo.get_by_id(schedule_id)

    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    # Faculty can only update their own schedules
    if current_user.role == UserRole.FACULTY and str(schedule.faculty_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify another faculty's schedule")

    # Persist to DB
    updated = schedule_repo.update(schedule_id, config_data.model_dump())

    # Update running pipeline if session is active (mid-session change)
    pipelines = getattr(http_request.app.state, "session_pipelines", {})
    pipeline = pipelines.get(schedule_id)
    if pipeline and pipeline.is_running:
        timeout_seconds = config_data.early_leave_timeout_minutes * 60.0
        pipeline.update_early_leave_timeout(timeout_seconds)

    logger.info(
        f"Schedule config updated: {schedule_id} "
        f"early_leave_timeout={config_data.early_leave_timeout_minutes}min "
        f"by {current_user.email}"
    )

    try:
        from app.utils.audit import log_audit

        log_audit(
            db,
            admin_id=current_user.id,
            action="update",
            target_type="schedule",
            target_id=str(schedule_id),
            details=(
                f"Config updated: early_leave_timeout="
                f"{config_data.early_leave_timeout_minutes}min"
            ),
            activity_summary=(
                f"Schedule config updated: {schedule.subject_code} — "
                f"early-leave timeout {config_data.early_leave_timeout_minutes}min"
            ),
            activity_payload={
                "subject_code": schedule.subject_code,
                "early_leave_timeout_minutes": config_data.early_leave_timeout_minutes,
                "actor_role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
            },
        )
    except Exception:
        logger.warning("log_audit failed for schedule.config_update", exc_info=True)

    return _serialize_schedule(updated)


# ===================================================================
# Manual Enrollment
# ===================================================================


@router.post("/{schedule_id}/enroll/{student_user_id}", status_code=status.HTTP_201_CREATED)
async def enroll_student(
    schedule_id: str,
    student_user_id: str,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    **Enroll Student** (Admin Only)

    Manually enroll a student in a schedule.
    """
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    student = db.query(User).filter(User.id == student_user_id, User.role == UserRole.STUDENT).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    existing = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student_user_id, Enrollment.schedule_id == schedule_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Student is already enrolled in this schedule")

    enrollment = Enrollment(student_id=student_user_id, schedule_id=schedule_id)
    db.add(enrollment)
    db.commit()

    logger.info(f"Manual enrollment: {student.email} -> {schedule.subject_code} by {current_user.email}")

    # Notify the student of their new enrollment.
    try:
        room_name = schedule.room.name if schedule.room else "TBD"
        await notify(
            db,
            user_id=str(student.id),
            title=f"Enrolled: {schedule.subject_code}",
            message=f"You have been enrolled in {schedule.subject_code}.",
            notification_type="enrollment_added",
            severity="info",
            preference_key=None,
            send_email=True,
            email_template="enrollment_added",
            email_context={
                "subject_code": schedule.subject_code,
                "day_of_week": str(schedule.day_of_week),
                "start_time": str(schedule.start_time),
                "end_time": str(schedule.end_time),
                "room_name": room_name,
            },
            dedup_window_seconds=0,
            reference_id=str(enrollment.id),
            reference_type="enrollment",
            toast_type="info",
        )
    except Exception:
        logger.exception("Failed to notify student of enrollment")

    try:
        from app.utils.audit import log_audit

        log_audit(
            db,
            admin_id=current_user.id,
            action="create",
            target_type="enrollment",
            target_id=str(enrollment.id),
            details=(
                f"Enrolled {student.email} -> {schedule.subject_code}"
            ),
            activity_summary=(
                f"Enrolled {student.first_name} {student.last_name} "
                f"in {schedule.subject_code}"
            ),
            activity_payload={
                "student_user_id": str(student_user_id),
                "schedule_id": str(schedule_id),
                "subject_code": schedule.subject_code,
                "student_email": student.email,
            },
        )
    except Exception:
        logger.warning("log_audit failed for enrollment.create", exc_info=True)

    return {"success": True, "message": f"{student.first_name} {student.last_name} enrolled successfully"}


@router.delete("/{schedule_id}/enroll/{student_user_id}", status_code=status.HTTP_200_OK)
async def unenroll_student(
    schedule_id: str,
    student_user_id: str,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    **Unenroll Student** (Admin Only)

    Remove a student's enrollment from a schedule.
    """
    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student_user_id, Enrollment.schedule_id == schedule_id)
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    enrollment_id = str(enrollment.id)
    # Resolve names *before* delete so the audit row carries human context
    # even though the FK rows are gone.
    student = db.query(User).filter(User.id == student_user_id).first()
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()

    # Notify the student BEFORE the delete so we still have the IDs and
    # subject_code for the message body / email context.
    if student is not None and schedule is not None:
        try:
            await notify(
                db,
                user_id=str(student.id),
                title=f"Unenrolled: {schedule.subject_code}",
                message=(
                    f"You have been removed from {schedule.subject_code}."
                ),
                notification_type="enrollment_removed",
                severity="info",
                preference_key=None,
                send_email=True,
                email_template="enrollment_removed",
                email_context={
                    "subject_code": schedule.subject_code,
                },
                dedup_window_seconds=0,
                reference_id=enrollment_id,
                reference_type="enrollment",
                toast_type="info",
            )
        except Exception:
            logger.exception("Failed to notify student of unenrollment")

    db.delete(enrollment)
    db.commit()

    logger.info(f"Manual unenrollment: user {student_user_id} from schedule {schedule_id} by {current_user.email}")

    try:
        from app.utils.audit import log_audit

        student_label = (
            f"{student.first_name} {student.last_name}".strip()
            if student
            else str(student_user_id)
        )
        subject_code = schedule.subject_code if schedule else str(schedule_id)
        log_audit(
            db,
            admin_id=current_user.id,
            action="delete",
            target_type="enrollment",
            target_id=enrollment_id,
            details=(
                f"Unenrolled user {student_user_id} from schedule {schedule_id}"
            ),
            activity_summary=f"Unenrolled {student_label} from {subject_code}",
            activity_payload={
                "student_user_id": str(student_user_id),
                "schedule_id": str(schedule_id),
                "subject_code": subject_code,
                "student_email": student.email if student else None,
            },
            activity_severity="warn",
        )
    except Exception:
        logger.warning("log_audit failed for enrollment.delete", exc_info=True)

    return {"success": True, "message": "Student unenrolled successfully"}


@router.get("/student/{student_user_id}/enrollments", status_code=status.HTTP_200_OK)
def get_student_enrollments(
    student_user_id: str,
    limit: int = Query(20, ge=1, le=100, description="Max results per page"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.FACULTY)),
    db: Session = Depends(get_db),
):
    """
    **Get Student Enrollments** (Admin/Faculty)

    Get schedules a student is enrolled in, paginated.

    - **limit**: max results per page (default 20, max 100)
    - **offset**: number of results to skip (default 0)

    Returns `{ items, total, limit, offset, has_more }`.
    """
    base_query = db.query(Enrollment).filter(Enrollment.student_id == student_user_id)
    total = base_query.count()

    enrollments = (
        base_query
        .options(joinedload(Enrollment.schedule).joinedload(Schedule.faculty))
        .options(joinedload(Enrollment.schedule).joinedload(Schedule.room))
        .order_by(Enrollment.enrolled_at.desc(), Enrollment.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    active = session_manager.list_active_session_ids()
    now = datetime.now()
    items = [
        {
            "enrollment_id": str(e.id),
            "schedule_id": str(e.schedule_id),
            "enrolled_at": e.enrolled_at.isoformat() if e.enrolled_at else None,
            "schedule": _serialize_schedule(e.schedule, active, now).model_dump() if e.schedule else None,
        }
        for e in enrollments
    ]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@router.get("/student/{student_user_id}/enrollments/ids", status_code=status.HTTP_200_OK)
def get_student_enrollment_ids(
    student_user_id: str,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.FACULTY)),
    db: Session = Depends(get_db),
):
    """
    **Get Student Enrollment Schedule IDs** (Admin/Faculty)

    Returns a flat list of schedule_ids the student is enrolled in.
    Used by the admin portal's Enroll-in-Schedule dialog to hide already-
    enrolled schedules without loading the paginated enrollment payload.
    """
    rows = (
        db.query(Enrollment.schedule_id)
        .filter(Enrollment.student_id == student_user_id)
        .all()
    )
    return {"schedule_ids": [str(r[0]) for r in rows]}
