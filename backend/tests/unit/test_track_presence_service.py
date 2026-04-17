"""
Tests for TrackPresenceService — presence state machine, early-leave detection,
student return flow, and camera-offline pause behavior.
"""

import uuid
from datetime import datetime, date, time

import pytest

from app.models.attendance_record import AttendanceRecord, AttendanceStatus
from app.models.early_leave_event import EarlyLeaveEvent
from app.models.enrollment import Enrollment
from app.models.room import Room
from app.models.schedule import Schedule
from app.models.user import User, UserRole
from app.services.realtime_tracker import TrackFrame, TrackResult
from app.services.track_presence_service import TrackPresenceService
from app.utils.security import hash_password


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def student(db_session):
    user = User(
        id=uuid.uuid4(),
        email="presence-student@test.jrmsu.edu.ph",
        password_hash=hash_password("TestPass123"),
        role=UserRole.STUDENT,
        first_name="Christian",
        last_name="Jutba",
        student_id="STU-2024-100",
        is_active=True,
        email_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def faculty(db_session):
    user = User(
        id=uuid.uuid4(),
        email="presence-faculty@test.jrmsu.edu.ph",
        password_hash=hash_password("TestPass123"),
        role=UserRole.FACULTY,
        first_name="Test",
        last_name="Faculty",
        is_active=True,
        email_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def room(db_session):
    r = Room(
        id=uuid.uuid4(),
        name="Presence Test Room",
        building="Test",
        capacity=40,
        camera_endpoint="rtsp://test/stream",
        is_active=True,
    )
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    return r


@pytest.fixture
def schedule(db_session, faculty, room):
    now = datetime.now()
    sched = Schedule(
        id=uuid.uuid4(),
        subject_code="TEST101",
        subject_name="Test Subject",
        faculty_id=faculty.id,
        room_id=room.id,
        day_of_week=now.weekday(),
        # Start 10 minutes ago so student counts as PRESENT (within grace)
        start_time=time((now.hour - 0) % 24, max(0, now.minute - 10)),
        end_time=time((now.hour + 2) % 24, now.minute),
        semester="1st",
        academic_year="2024-2025",
        is_active=True,
    )
    db_session.add(sched)
    db_session.commit()
    db_session.refresh(sched)
    return sched


@pytest.fixture
def enrollment(db_session, student, schedule):
    e = Enrollment(
        id=uuid.uuid4(),
        student_id=student.id,
        schedule_id=schedule.id,
        enrolled_at=datetime.utcnow(),
    )
    db_session.add(e)
    db_session.commit()
    return e


def make_frame(user_ids: list[str], timestamp: float) -> TrackFrame:
    """Build a TrackFrame containing recognized tracks for given user_ids."""
    tracks = [
        TrackResult(
            track_id=i + 1,
            bbox=[0.1, 0.1, 0.3, 0.4],
            velocity=[0.0, 0.0, 0.0, 0.0],
            user_id=uid,
            name=f"User{i}",
            confidence=0.80,
            status="recognized",
            is_active=True,
        )
        for i, uid in enumerate(user_ids)
    ]
    return TrackFrame(
        tracks=tracks, fps=20.0, processing_ms=15.0, timestamp=timestamp
    )


def empty_frame(timestamp: float) -> TrackFrame:
    return TrackFrame(tracks=[], fps=20.0, processing_ms=5.0, timestamp=timestamp)


# ---------------------------------------------------------------------------
# Phase 4 Test: Leave and return flow
# ---------------------------------------------------------------------------


def test_student_leave_and_return_flow(db_session, student, schedule, enrollment):
    """Student checks in, disappears past early-leave timeout, returns.

    Verifies:
    - Check-in transitions ABSENT -> PRESENT and generates check_in event
    - After EARLY_LEAVE_TIMEOUT of absence, status becomes EARLY_LEAVE
    - When student returns, status restored to PRESENT
    - EarlyLeaveEvent is marked returned=True with correct duration
    """
    service = TrackPresenceService(db_session, str(schedule.id))
    # Override early-leave timeout for faster test (10s instead of 300s default)
    service.start_session()
    service.set_early_leave_timeout(10.0)

    student_id = str(student.id)

    # t=0: student detected, checks in
    events = service.process_track_frame(make_frame([student_id], 0.0), now_mono=0.0)
    check_in_events = [e for e in events if e.get("event") == "check_in"]
    assert len(check_in_events) == 1, f"Expected check_in event, got {events}"

    # Verify DB: status is PRESENT or LATE (depends on grace period)
    record = (
        db_session.query(AttendanceRecord)
        .filter_by(student_id=student.id, schedule_id=schedule.id)
        .first()
    )
    assert record is not None
    assert record.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
    initial_status = record.status

    # t=0..5: student continuously present
    for i in range(1, 6):
        service.process_track_frame(make_frame([student_id], float(i)), now_mono=float(i))

    # t=6..25: student absent (past 10s early-leave timeout)
    early_leave_fired_at = None
    for i in range(6, 26):
        events = service.process_track_frame(empty_frame(float(i)), now_mono=float(i))
        if any(e.get("event") == "early_leave" for e in events):
            early_leave_fired_at = i
            break

    assert early_leave_fired_at is not None, "early_leave event never fired"
    # Absent since ~t=5 (last seen). Early leave timeout = 10s → should fire around t=15
    assert 15 <= early_leave_fired_at <= 20, f"Fired at t={early_leave_fired_at}"

    # Verify DB: status is now EARLY_LEAVE
    db_session.refresh(record)
    assert record.status == AttendanceStatus.EARLY_LEAVE

    # Verify EarlyLeaveEvent created (linked via attendance_id)
    event_row = (
        db_session.query(EarlyLeaveEvent)
        .filter_by(attendance_id=record.id)
        .first()
    )
    assert event_row is not None
    assert event_row.returned is False

    # t=30: student returns
    events = service.process_track_frame(
        make_frame([student_id], 30.0), now_mono=30.0
    )
    return_events = [e for e in events if e.get("event") == "early_leave_return"]
    assert len(return_events) == 1, f"Expected return event, got {events}"

    # Verify DB: status restored to original (PRESENT or LATE)
    db_session.refresh(record)
    assert record.status == initial_status

    # Verify EarlyLeaveEvent marked returned with duration
    db_session.refresh(event_row)
    assert event_row.returned is True
    assert event_row.absence_duration_seconds is not None
    assert event_row.absence_duration_seconds > 0


# ---------------------------------------------------------------------------
# Phase 2 Test: Camera offline does NOT trigger early-leave
# ---------------------------------------------------------------------------


def test_camera_offline_does_not_trigger_early_leave(
    db_session, student, schedule, enrollment
):
    """Camera goes offline for longer than EARLY_LEAVE_TIMEOUT.

    Before fix: absent_since timer kept counting, early_leave fired falsely.
    After fix: pause_absence_tracking freezes timers; resume shifts them forward
    so the offline duration doesn't count as absence.
    """
    service = TrackPresenceService(db_session, str(schedule.id))
    service.start_session()
    service.set_early_leave_timeout(10.0)  # 10s timeout for faster test

    student_id = str(student.id)

    # t=0..5: student present
    for i in range(0, 6):
        service.process_track_frame(make_frame([student_id], float(i)), now_mono=float(i))

    # t=5: camera goes offline — pipeline would call pause_absence_tracking
    # Simulate the pipeline's behavior: after 2s of no frames, pause
    service.pause_absence_tracking(now_mono=7.0)

    # 30 seconds of camera downtime (exceeds 10s early-leave timeout)
    # Pipeline is NOT calling process_track_frame during this period

    # t=37: camera back online, first frame arrives. Auto-resume fires inside
    # process_track_frame which shifts absent_since and last_seen forward.
    # Student is detected again.
    events = service.process_track_frame(
        make_frame([student_id], 37.0), now_mono=37.0
    )

    # CRITICAL: no early_leave event should have been generated
    early_leave_events = [e for e in events if e.get("event") == "early_leave"]
    assert len(early_leave_events) == 0, (
        f"Early leave should NOT fire during camera offline period, got {events}"
    )

    # Also no early_leave_return (because no early_leave happened)
    return_events = [e for e in events if e.get("event") == "early_leave_return"]
    assert len(return_events) == 0

    # Verify DB: student still marked as PRESENT/LATE, not EARLY_LEAVE
    record = (
        db_session.query(AttendanceRecord)
        .filter_by(student_id=student.id, schedule_id=schedule.id)
        .first()
    )
    assert record is not None
    assert record.status != AttendanceStatus.EARLY_LEAVE
    assert record.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)


def test_pause_resume_is_idempotent(db_session, student, schedule, enrollment):
    """Calling pause multiple times is safe; resume without pause is no-op."""
    service = TrackPresenceService(db_session, str(schedule.id))
    service.start_session()

    # Resume without pause — should be no-op
    service.resume_absence_tracking(now_mono=10.0)
    assert service._paused_at is None

    # Pause, pause again — second call should be no-op
    service.pause_absence_tracking(now_mono=20.0)
    first_pause = service._paused_at
    service.pause_absence_tracking(now_mono=25.0)
    assert service._paused_at == first_pause  # didn't overwrite

    # Resume clears pause state
    service.resume_absence_tracking(now_mono=30.0)
    assert service._paused_at is None
