"""
Integration Tests for Presence Tracking & Early Leave Detection

Tests the continuous presence monitoring system including:
- 60-second scan cycles
- Presence log creation
- 3-consecutive-miss detection
- Early leave event creation
- Presence score calculation
"""

import pytest
from datetime import datetime, date, time, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from app.config import settings


class TestPresenceTrackingSession:
    """Test presence tracking session lifecycle"""

    @pytest.mark.asyncio
    async def test_start_session_creates_attendance_records(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """Starting a session creates attendance records for all enrolled students"""
        from app.services.presence_service import PresenceService
        from app.models.attendance_record import AttendanceStatus

        presence_service = PresenceService(db_session)

        # Start session
        session = await presence_service.start_session(str(test_schedule.id))

        assert session is not None
        assert session.schedule_id == str(test_schedule.id)
        assert len(session.student_states) == 1  # One enrolled student

        # Check attendance record was created
        from app.repositories.attendance_repository import AttendanceRepository
        repo = AttendanceRepository(db_session)

        record = repo.get_by_student_date(
            str(test_student.id),
            str(test_schedule.id),
            date.today()
        )

        assert record is not None
        assert record.status == AttendanceStatus.ABSENT  # Initially absent
        assert record.total_scans == 0

    @pytest.mark.asyncio
    async def test_end_session_updates_checkout_times(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """Ending a session updates check-out times"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(db_session)

        # Start and end session
        await presence_service.start_session(str(test_schedule.id))

        # Log at least one detection so student is marked present
        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id=str(test_student.id),
            confidence=0.85
        )

        await presence_service.end_session(str(test_schedule.id))

        # Check attendance record
        from app.repositories.attendance_repository import AttendanceRepository
        repo = AttendanceRepository(db_session)

        record = repo.get_by_student_date(
            str(test_student.id),
            str(test_schedule.id),
            date.today()
        )

        assert record.check_out_time is not None

    @pytest.mark.asyncio
    async def test_duplicate_session_start(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """Starting a session twice returns the existing session"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(db_session)

        # Start session twice
        session1 = await presence_service.start_session(str(test_schedule.id))
        session2 = await presence_service.start_session(str(test_schedule.id))

        assert session1 is session2


class TestPresenceLogCreation:
    """Test presence log entry creation during scans"""

    @pytest.mark.asyncio
    async def test_log_detection_creates_presence_log(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """Logging detection creates presence log entry"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(db_session)

        # Start session
        await presence_service.start_session(str(test_schedule.id))

        # Log detection
        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id=str(test_student.id),
            confidence=0.88
        )

        # Check presence log was created
        from app.repositories.attendance_repository import AttendanceRepository
        repo = AttendanceRepository(db_session)

        record = repo.get_by_student_date(
            str(test_student.id),
            str(test_schedule.id),
            date.today()
        )

        logs = repo.get_recent_logs(str(record.id), limit=10)
        assert len(logs) >= 1
        assert logs[0].detected is True
        assert logs[0].confidence == 0.88

    @pytest.mark.asyncio
    async def test_presence_score_calculation(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """Presence score is calculated correctly"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(db_session)

        # Start session
        await presence_service.start_session(str(test_schedule.id))

        # Simulate multiple detections
        for i in range(5):
            await presence_service.log_detection(
                schedule_id=str(test_schedule.id),
                user_id=str(test_student.id),
                confidence=0.85
            )

        # Check presence score
        from app.repositories.attendance_repository import AttendanceRepository
        repo = AttendanceRepository(db_session)

        record = repo.get_by_student_date(
            str(test_student.id),
            str(test_schedule.id),
            date.today()
        )

        # 5 out of 5 scans = 100%
        assert record.presence_score == 100.0
        assert record.scans_present == 5
        assert record.total_scans == 5


class TestEarlyLeaveDetection:
    """Test early leave detection (3 consecutive misses)"""

    @pytest.mark.asyncio
    async def test_three_consecutive_misses_triggers_early_leave(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """3 consecutive missed scans triggers early leave event"""
        from app.services.presence_service import PresenceService
        from app.models.attendance_record import AttendanceStatus

        presence_service = PresenceService(db_session)

        # Start session
        session = await presence_service.start_session(str(test_schedule.id))

        # First detection (student present)
        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id=str(test_student.id),
            confidence=0.85
        )

        # Simulate 3 scan cycles where student is not detected
        for i in range(3):
            session.scan_count += 1
            await presence_service.process_session_scan(str(test_schedule.id))

        # Check early leave was flagged
        from app.repositories.attendance_repository import AttendanceRepository
        repo = AttendanceRepository(db_session)

        record = repo.get_by_student_date(
            str(test_student.id),
            str(test_schedule.id),
            date.today()
        )

        assert record.status == AttendanceStatus.EARLY_LEAVE

        # Check early leave event was created
        events = repo.get_early_leave_events(str(record.id))
        assert len(events) >= 1
        assert events[0].consecutive_misses == 3

    @pytest.mark.asyncio
    async def test_student_never_checked_in_no_early_leave(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """Student who never checked in is not flagged for early leave"""
        from app.services.presence_service import PresenceService
        from app.models.attendance_record import AttendanceStatus

        presence_service = PresenceService(db_session)

        # Start session
        session = await presence_service.start_session(str(test_schedule.id))

        # Don't log any detection

        # Simulate 3 scan cycles
        for i in range(3):
            session.scan_count += 1
            await presence_service.process_session_scan(str(test_schedule.id))

        # Check student is still absent (not early leave)
        from app.repositories.attendance_repository import AttendanceRepository
        repo = AttendanceRepository(db_session)

        record = repo.get_by_student_date(
            str(test_student.id),
            str(test_schedule.id),
            date.today()
        )

        assert record.status == AttendanceStatus.ABSENT

    @pytest.mark.asyncio
    async def test_intermittent_detections_reset_miss_counter(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """Detection resets consecutive miss counter"""
        from app.services.presence_service import PresenceService
        from app.models.attendance_record import AttendanceStatus

        presence_service = PresenceService(db_session)

        # Start session
        session = await presence_service.start_session(str(test_schedule.id))

        # First detection
        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id=str(test_student.id),
            confidence=0.85
        )

        # 2 missed scans
        for i in range(2):
            session.scan_count += 1
            await presence_service.process_session_scan(str(test_schedule.id))

        # Student detected again (resets counter)
        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id=str(test_student.id),
            confidence=0.82
        )

        # 2 more missed scans (not enough to trigger early leave)
        for i in range(2):
            session.scan_count += 1
            await presence_service.process_session_scan(str(test_schedule.id))

        # Check student is still present (not early leave)
        from app.repositories.attendance_repository import AttendanceRepository
        repo = AttendanceRepository(db_session)

        record = repo.get_by_student_date(
            str(test_student.id),
            str(test_schedule.id),
            date.today()
        )

        assert record.status != AttendanceStatus.EARLY_LEAVE

    @pytest.mark.asyncio
    async def test_early_leave_only_flagged_once(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """Early leave is only flagged once per session"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(db_session)

        # Start session
        session = await presence_service.start_session(str(test_schedule.id))

        # First detection
        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id=str(test_student.id),
            confidence=0.85
        )

        # 6 consecutive misses (should trigger early leave once)
        for i in range(6):
            session.scan_count += 1
            await presence_service.process_session_scan(str(test_schedule.id))

        # Check only one early leave event
        from app.repositories.attendance_repository import AttendanceRepository
        repo = AttendanceRepository(db_session)

        record = repo.get_by_student_date(
            str(test_student.id),
            str(test_schedule.id),
            date.today()
        )

        events = repo.get_early_leave_events(str(record.id))
        assert len(events) == 1


class TestPresenceScoreCalculation:
    """Test presence score calculation edge cases"""

    def test_calculate_presence_score_perfect_attendance(self):
        """100% presence score for all scans detected"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(None)  # No DB needed for this test

        score = presence_service.calculate_presence_score(
            total_scans=10,
            scans_present=10
        )

        assert score == 100.0

    def test_calculate_presence_score_zero_attendance(self):
        """0% presence score for no scans detected"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(None)

        score = presence_service.calculate_presence_score(
            total_scans=10,
            scans_present=0
        )

        assert score == 0.0

    def test_calculate_presence_score_partial_attendance(self):
        """Correct score for partial attendance"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(None)

        score = presence_service.calculate_presence_score(
            total_scans=10,
            scans_present=7
        )

        assert score == 70.0

    def test_calculate_presence_score_zero_scans(self):
        """Handle zero total scans"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(None)

        score = presence_service.calculate_presence_score(
            total_scans=0,
            scans_present=0
        )

        assert score == 0.0


class TestScanCycleProcessing:
    """Test scan cycle processing"""

    @pytest.mark.asyncio
    async def test_run_scan_cycle_processes_all_sessions(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """run_scan_cycle processes all active sessions"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(db_session)

        # Start multiple sessions (we only have one schedule in fixture)
        await presence_service.start_session(str(test_schedule.id))

        # Log detection
        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id=str(test_student.id),
            confidence=0.85
        )

        # Run scan cycle
        await presence_service.run_scan_cycle()

        # Session scan count should increment
        session = presence_service.get_session_state(str(test_schedule.id))
        assert session.scan_count == 1

    @pytest.mark.asyncio
    async def test_run_scan_cycle_with_no_active_sessions(
        self,
        db_session
    ):
        """run_scan_cycle does nothing when no sessions active"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(db_session)

        # Run scan cycle with no active sessions
        await presence_service.run_scan_cycle()

        # Should not raise error
        assert len(presence_service.get_active_sessions()) == 0


class TestPresenceServiceHelpers:
    """Test presence service helper methods"""

    @pytest.mark.asyncio
    async def test_get_session_state(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """get_session_state returns correct session"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(db_session)

        # Start session
        await presence_service.start_session(str(test_schedule.id))

        # Get session state
        session = presence_service.get_session_state(str(test_schedule.id))

        assert session is not None
        assert session.schedule_id == str(test_schedule.id)

    @pytest.mark.asyncio
    async def test_is_session_active(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """is_session_active returns correct status"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(db_session)

        # Before start
        assert presence_service.is_session_active(str(test_schedule.id)) is False

        # After start
        await presence_service.start_session(str(test_schedule.id))
        assert presence_service.is_session_active(str(test_schedule.id)) is True

        # After end
        await presence_service.end_session(str(test_schedule.id))
        assert presence_service.is_session_active(str(test_schedule.id)) is False

    @pytest.mark.asyncio
    async def test_get_active_sessions(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """get_active_sessions returns list of active schedule IDs"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(db_session)

        # No active sessions
        assert len(presence_service.get_active_sessions()) == 0

        # Start session
        await presence_service.start_session(str(test_schedule.id))

        # One active session
        active = presence_service.get_active_sessions()
        assert len(active) == 1
        assert str(test_schedule.id) in active


class TestPresenceLogRepository:
    """Test presence log repository operations"""

    def test_log_presence_detected(
        self,
        db_session,
        test_attendance_record
    ):
        """Log presence entry with detection"""
        from app.repositories.attendance_repository import AttendanceRepository

        repo = AttendanceRepository(db_session)

        repo.log_presence(str(test_attendance_record.id), {
            "scan_number": 1,
            "scan_time": datetime.now(),
            "detected": True,
            "confidence": 0.92
        })

        # Get logs
        logs = repo.get_recent_logs(str(test_attendance_record.id), limit=1)
        assert len(logs) == 1
        assert logs[0].detected is True
        assert logs[0].confidence == 0.92

    def test_log_presence_not_detected(
        self,
        db_session,
        test_attendance_record
    ):
        """Log presence entry with no detection"""
        from app.repositories.attendance_repository import AttendanceRepository

        repo = AttendanceRepository(db_session)

        repo.log_presence(str(test_attendance_record.id), {
            "scan_number": 1,
            "scan_time": datetime.now(),
            "detected": False,
            "confidence": None
        })

        # Get logs
        logs = repo.get_recent_logs(str(test_attendance_record.id), limit=1)
        assert len(logs) == 1
        assert logs[0].detected is False
        assert logs[0].confidence is None

    def test_get_recent_logs(
        self,
        db_session,
        test_attendance_record
    ):
        """Get recent presence logs"""
        from app.repositories.attendance_repository import AttendanceRepository

        repo = AttendanceRepository(db_session)

        # Create multiple logs
        for i in range(5):
            repo.log_presence(str(test_attendance_record.id), {
                "scan_number": i,
                "scan_time": datetime.now(),
                "detected": i % 2 == 0,  # Alternate
                "confidence": 0.85 if i % 2 == 0 else None
            })

        # Get recent logs
        logs = repo.get_recent_logs(str(test_attendance_record.id), limit=3)
        assert len(logs) == 3
