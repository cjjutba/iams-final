"""
Tests for Presence Service

Tests continuous presence monitoring including:
- Session start/end
- Presence logging
- Early leave detection (3 consecutive miss threshold)
- Presence score calculation
- Integration with tracking service
"""

import pytest
from datetime import datetime, date, time, timedelta
from sqlalchemy.orm import Session
from unittest.mock import Mock, AsyncMock, patch

from app.services.presence_service import PresenceService, SessionState
from app.models.attendance_record import AttendanceRecord, AttendanceStatus
from app.models.schedule import Schedule
from app.models.user import User, UserRole
from app.models.enrollment import Enrollment


@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def mock_schedule():
    """Mock schedule"""
    schedule = Mock(spec=Schedule)
    schedule.id = "schedule-123"
    schedule.subject_code = "CPE301"
    schedule.subject_name = "Data Structures"
    schedule.start_time = time(8, 0)
    schedule.end_time = time(10, 0)
    return schedule


@pytest.fixture
def mock_students():
    """Mock student list"""
    students = []
    for i in range(3):
        student = Mock(spec=User)
        student.id = f"student-{i+1}"
        student.full_name = f"Student {i+1}"
        students.append(student)
    return students


class TestPresenceService:
    """Test suite for PresenceService"""

    @pytest.mark.asyncio
    async def test_start_session(self, mock_db, mock_schedule, mock_students):
        """Test starting an attendance session"""
        service = PresenceService(mock_db)

        # Mock repositories
        service.schedule_repo.get_by_id = Mock(return_value=mock_schedule)
        service.schedule_repo.get_enrolled_students = Mock(return_value=mock_students)
        service.attendance_repo.get_by_student_date = Mock(return_value=None)
        service.attendance_repo.create = Mock(side_effect=lambda data: Mock(id=f"att-{data['student_id']}"))

        # Start session
        session = await service.start_session("schedule-123")

        # Verify session created
        assert session.schedule_id == "schedule-123"
        assert len(session.student_states) == 3
        assert session.scan_count == 0
        assert session.is_active is True

        # Verify attendance records created
        assert service.attendance_repo.create.call_count == 3

        # Verify tracking session started
        assert service.tracking_service.get_active_tracks("schedule-123") is not None

    @pytest.mark.asyncio
    async def test_start_session_duplicate(self, mock_db, mock_schedule, mock_students):
        """Test starting a session that's already active"""
        service = PresenceService(mock_db)

        # Mock repositories
        service.schedule_repo.get_by_id = Mock(return_value=mock_schedule)
        service.schedule_repo.get_enrolled_students = Mock(return_value=mock_students)
        service.attendance_repo.get_by_student_date = Mock(return_value=None)
        service.attendance_repo.create = Mock(side_effect=lambda data: Mock(id=f"att-{data['student_id']}"))

        # Start session twice
        session1 = await service.start_session("schedule-123")
        session2 = await service.start_session("schedule-123")

        # Should return same session
        assert session1.schedule_id == session2.schedule_id

    @pytest.mark.asyncio
    async def test_log_detection_first_time(self, mock_db):
        """Test logging first detection (check-in)"""
        service = PresenceService(mock_db)

        # Create mock session
        session = SessionState("schedule-123", Mock())
        session.add_student("student-1", "att-1")
        service.active_sessions["schedule-123"] = session

        # Mock attendance record
        attendance = Mock(spec=AttendanceRecord)
        attendance.id = "att-1"
        attendance.status = AttendanceStatus.ABSENT
        attendance.schedule = Mock(start_time=time(8, 0))
        attendance.scans_present = 0
        attendance.total_scans = 0

        service.attendance_repo.get_by_id = Mock(return_value=attendance)
        service.attendance_repo.update = Mock(return_value=attendance)
        service.attendance_repo.log_presence = Mock()

        # Log detection
        await service.log_detection("schedule-123", "student-1", 0.85)

        # Verify check-in recorded (should be 2 update calls: check-in + metrics)
        assert service.attendance_repo.update.called
        assert service.attendance_repo.update.call_count == 2

        # First call should update check-in time and status
        first_call = service.attendance_repo.update.call_args_list[0]
        assert first_call[0][0] == "att-1"
        assert "check_in_time" in first_call[0][1]
        assert "status" in first_call[0][1]

        # Second call should update metrics
        second_call = service.attendance_repo.update.call_args_list[1]
        assert second_call[0][0] == "att-1"
        assert "scans_present" in second_call[0][1]
        assert "total_scans" in second_call[0][1]

        # Verify presence logged
        assert service.attendance_repo.log_presence.called

    @pytest.mark.asyncio
    async def test_calculate_presence_score(self, mock_db):
        """Test presence score calculation"""
        service = PresenceService(mock_db)

        # Test various scenarios
        assert service.calculate_presence_score(0, 0) == 0.0
        assert service.calculate_presence_score(10, 10) == 100.0
        assert service.calculate_presence_score(10, 5) == 50.0
        assert service.calculate_presence_score(10, 7) == 70.0
        assert service.calculate_presence_score(3, 2) == 66.67

    @pytest.mark.asyncio
    async def test_process_session_scan_all_present(self, mock_db):
        """Test scan cycle when all students present"""
        service = PresenceService(mock_db)

        # Create session with 2 students
        session = SessionState("schedule-123", Mock())
        session.add_student("student-1", "att-1")
        session.add_student("student-2", "att-2")
        service.active_sessions["schedule-123"] = session

        # Mock attendance records
        att1 = Mock(spec=AttendanceRecord)
        att1.id = "att-1"
        att1.status = AttendanceStatus.PRESENT
        att1.scans_present = 0
        att1.total_scans = 0

        att2 = Mock(spec=AttendanceRecord)
        att2.id = "att-2"
        att2.status = AttendanceStatus.PRESENT
        att2.scans_present = 0
        att2.total_scans = 0

        def get_attendance(att_id):
            if att_id == "att-1":
                return att1
            elif att_id == "att-2":
                return att2
            return None

        service.attendance_repo.get_by_id = Mock(side_effect=get_attendance)
        service.attendance_repo.log_presence = Mock()
        service.attendance_repo.update = Mock()

        # Mock tracking service to report both students present
        from app.services.tracking_service import Track
        track1 = Track(track_id=1, user_id="student-1", is_confirmed=True)
        track2 = Track(track_id=2, user_id="student-2", is_confirmed=True)

        service.tracking_service.get_identified_users = Mock(return_value={
            "student-1": track1,
            "student-2": track2
        })

        # Run scan
        await service.process_session_scan("schedule-123")

        # Verify scan count incremented
        assert session.scan_count == 1

        # Verify both students logged as present
        assert service.attendance_repo.log_presence.call_count == 2

        # Verify no early leaves
        assert not session.student_states["student-1"]["early_leave_flagged"]
        assert not session.student_states["student-2"]["early_leave_flagged"]

    @pytest.mark.asyncio
    async def test_process_session_scan_with_absence(self, mock_db):
        """Test scan cycle when one student is absent"""
        service = PresenceService(mock_db)

        # Create session with 2 students
        session = SessionState("schedule-123", Mock())
        session.add_student("student-1", "att-1")
        session.add_student("student-2", "att-2")
        service.active_sessions["schedule-123"] = session

        # Mock attendance records
        att1 = Mock(spec=AttendanceRecord)
        att1.id = "att-1"
        att1.status = AttendanceStatus.PRESENT
        att1.scans_present = 0
        att1.total_scans = 0

        att2 = Mock(spec=AttendanceRecord)
        att2.id = "att-2"
        att2.status = AttendanceStatus.PRESENT
        att2.scans_present = 0
        att2.total_scans = 0

        def get_attendance(att_id):
            if att_id == "att-1":
                return att1
            elif att_id == "att-2":
                return att2
            return None

        service.attendance_repo.get_by_id = Mock(side_effect=get_attendance)
        service.attendance_repo.log_presence = Mock()
        service.attendance_repo.update = Mock()

        # Mock tracking service - only student-1 present
        from app.services.tracking_service import Track
        track1 = Track(track_id=1, user_id="student-1", is_confirmed=True)

        service.tracking_service.get_identified_users = Mock(return_value={
            "student-1": track1
        })

        # Run scan
        await service.process_session_scan("schedule-123")

        # Verify consecutive miss incremented for student-2
        assert session.student_states["student-2"]["consecutive_misses"] == 1
        assert session.student_states["student-1"]["consecutive_misses"] == 0

    @pytest.mark.asyncio
    async def test_early_leave_detection(self, mock_db):
        """Test early leave detection after 3 consecutive misses"""
        service = PresenceService(mock_db)

        # Create session
        session = SessionState("schedule-123", Mock())
        session.add_student("student-1", "att-1")
        service.active_sessions["schedule-123"] = session

        # Mock attendance record
        attendance = Mock(spec=AttendanceRecord)
        attendance.id = "att-1"
        attendance.status = AttendanceStatus.PRESENT
        attendance.check_in_time = datetime.now()
        attendance.scans_present = 5
        attendance.total_scans = 5

        service.attendance_repo.get_by_id = Mock(return_value=attendance)
        service.attendance_repo.log_presence = Mock()
        service.attendance_repo.update = Mock()
        service.attendance_repo.get_recent_logs = Mock(return_value=[])
        service.attendance_repo.create_early_leave_event = Mock(return_value=Mock(id="event-1"))

        # Mock tracking - student not present
        service.tracking_service.get_identified_users = Mock(return_value={})

        # Mock config for threshold
        with patch('app.services.presence_service.settings') as mock_settings:
            mock_settings.EARLY_LEAVE_THRESHOLD = 3

            # Run 3 scans with student missing
            for i in range(3):
                await service.process_session_scan("schedule-123")

        # Verify early leave flagged
        assert session.student_states["student-1"]["early_leave_flagged"] is True
        assert session.student_states["student-1"]["consecutive_misses"] == 3

        # Verify early leave event created
        assert service.attendance_repo.create_early_leave_event.called

    @pytest.mark.asyncio
    async def test_early_leave_not_triggered_with_reset(self, mock_db):
        """Test that consecutive misses reset when student reappears"""
        service = PresenceService(mock_db)

        # Create session
        session = SessionState("schedule-123", Mock())
        session.add_student("student-1", "att-1")
        service.active_sessions["schedule-123"] = session

        # Mock attendance record
        attendance = Mock(spec=AttendanceRecord)
        attendance.id = "att-1"
        attendance.status = AttendanceStatus.PRESENT
        attendance.scans_present = 0
        attendance.total_scans = 0

        service.attendance_repo.get_by_id = Mock(return_value=attendance)
        service.attendance_repo.log_presence = Mock()
        service.attendance_repo.update = Mock()

        # Mock tracking
        from app.services.tracking_service import Track
        track = Track(track_id=1, user_id="student-1", is_confirmed=True)

        # Scan 1: Student absent
        service.tracking_service.get_identified_users = Mock(return_value={})
        await service.process_session_scan("schedule-123")
        assert session.student_states["student-1"]["consecutive_misses"] == 1

        # Scan 2: Student absent
        await service.process_session_scan("schedule-123")
        assert session.student_states["student-1"]["consecutive_misses"] == 2

        # Scan 3: Student present (resets counter)
        service.tracking_service.get_identified_users = Mock(return_value={"student-1": track})
        await service.process_session_scan("schedule-123")
        assert session.student_states["student-1"]["consecutive_misses"] == 0

        # Scan 4: Student absent again
        service.tracking_service.get_identified_users = Mock(return_value={})
        await service.process_session_scan("schedule-123")
        assert session.student_states["student-1"]["consecutive_misses"] == 1

        # Verify no early leave flagged
        assert session.student_states["student-1"]["early_leave_flagged"] is False

    @pytest.mark.asyncio
    async def test_end_session(self, mock_db):
        """Test ending an attendance session"""
        service = PresenceService(mock_db)

        # Create session
        session = SessionState("schedule-123", Mock())
        session.add_student("student-1", "att-1")
        session.add_student("student-2", "att-2")
        session.scan_count = 10
        service.active_sessions["schedule-123"] = session

        # Mock attendance records
        attendance = Mock(spec=AttendanceRecord)
        attendance.id = "att-1"
        attendance.status = AttendanceStatus.PRESENT

        service.attendance_repo.get_by_id = Mock(return_value=attendance)
        service.attendance_repo.update = Mock()

        # End session
        await service.end_session("schedule-123")

        # Verify session removed
        assert "schedule-123" not in service.active_sessions

        # Verify tracking session ended
        assert len(service.tracking_service.get_active_tracks("schedule-123")) == 0

    def test_session_state_operations(self):
        """Test SessionState helper methods"""
        schedule = Mock()
        session = SessionState("schedule-123", schedule)

        # Test add_student
        session.add_student("student-1", "att-1")
        assert "student-1" in session.student_states
        assert session.student_states["student-1"]["attendance_id"] == "att-1"
        assert session.student_states["student-1"]["consecutive_misses"] == 0

        # Test update_student (detected)
        session.update_student("student-1", detected=True)
        assert session.student_states["student-1"]["consecutive_misses"] == 0
        assert session.student_states["student-1"]["last_seen"] is not None

        # Test update_student (not detected)
        session.update_student("student-1", detected=False)
        assert session.student_states["student-1"]["consecutive_misses"] == 1

        session.update_student("student-1", detected=False)
        assert session.student_states["student-1"]["consecutive_misses"] == 2

        # Test get_student_state
        state = session.get_student_state("student-1")
        assert state is not None
        assert state["consecutive_misses"] == 2

    def test_is_session_active(self, mock_db):
        """Test checking if session is active"""
        service = PresenceService(mock_db)

        # No session
        assert not service.is_session_active("schedule-123")

        # Create session
        session = SessionState("schedule-123", Mock())
        service.active_sessions["schedule-123"] = session

        # Session exists
        assert service.is_session_active("schedule-123")

    def test_get_active_sessions(self, mock_db):
        """Test getting list of active sessions"""
        service = PresenceService(mock_db)

        # No sessions
        assert len(service.get_active_sessions()) == 0

        # Create sessions
        service.active_sessions["schedule-1"] = SessionState("schedule-1", Mock())
        service.active_sessions["schedule-2"] = SessionState("schedule-2", Mock())

        # Get active sessions
        active = service.get_active_sessions()
        assert len(active) == 2
        assert "schedule-1" in active
        assert "schedule-2" in active
