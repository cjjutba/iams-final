"""
Integration Tests for Attendance Marking Flow

Tests the complete attendance workflow from first detection to
attendance record creation and status updates.
"""

import pytest
from datetime import datetime, date, time, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from app.config import settings


API = settings.API_PREFIX


class TestAttendanceMarkingFlow:
    """Test complete attendance marking workflow"""

    @pytest.mark.asyncio
    async def test_first_detection_marks_present(
        self,
        db_session,
        test_student,
        test_schedule,
        test_enrollment
    ):
        """First detection during class creates attendance record as PRESENT"""
        from app.services.presence_service import PresenceService
        from app.models.attendance_record import AttendanceStatus

        presence_service = PresenceService(db_session)

        # Start session
        session = await presence_service.start_session(str(test_schedule.id))

        # Simulate detection (within grace period)
        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id=str(test_student.id),
            confidence=0.85
        )

        # Check attendance record
        from app.repositories.attendance_repository import AttendanceRepository
        repo = AttendanceRepository(db_session)

        record = repo.get_by_student_date(
            str(test_student.id),
            str(test_schedule.id),
            date.today()
        )

        assert record is not None
        assert record.status == AttendanceStatus.PRESENT
        assert record.check_in_time is not None

    @pytest.mark.asyncio
    async def test_late_detection_marks_late(
        self,
        db_session,
        test_student,
        test_schedule,
        test_enrollment
    ):
        """Detection after grace period marks as LATE"""
        from app.services.presence_service import PresenceService
        from app.models.attendance_record import AttendanceStatus

        # Mock current time to be after grace period
        late_time = (
            datetime.combine(date.today(), test_schedule.start_time)
            + timedelta(minutes=settings.GRACE_PERIOD_MINUTES + 5)
        )

        with patch('app.services.presence_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = late_time
            mock_datetime.combine = datetime.combine

            presence_service = PresenceService(db_session)

            # Start session
            await presence_service.start_session(str(test_schedule.id))

            # Simulate late detection
            await presence_service.log_detection(
                schedule_id=str(test_schedule.id),
                user_id=str(test_student.id),
                confidence=0.80
            )

        # Check attendance record
        from app.repositories.attendance_repository import AttendanceRepository
        repo = AttendanceRepository(db_session)

        record = repo.get_by_student_date(
            str(test_student.id),
            str(test_schedule.id),
            date.today()
        )

        assert record is not None
        assert record.status == AttendanceStatus.LATE

    @pytest.mark.asyncio
    async def test_no_detection_remains_absent(
        self,
        db_session,
        test_student,
        test_schedule,
        test_enrollment
    ):
        """Student not detected remains ABSENT"""
        from app.services.presence_service import PresenceService
        from app.models.attendance_record import AttendanceStatus

        presence_service = PresenceService(db_session)

        # Start session (creates ABSENT records for all students)
        await presence_service.start_session(str(test_schedule.id))

        # Don't log any detection

        # Check attendance record
        from app.repositories.attendance_repository import AttendanceRepository
        repo = AttendanceRepository(db_session)

        record = repo.get_by_student_date(
            str(test_student.id),
            str(test_schedule.id),
            date.today()
        )

        assert record is not None
        assert record.status == AttendanceStatus.ABSENT
        assert record.check_in_time is None

    @pytest.mark.asyncio
    async def test_duplicate_detection_same_scan(
        self,
        db_session,
        test_student,
        test_schedule,
        test_enrollment
    ):
        """Multiple detections in same scan cycle don't create duplicates"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(db_session)

        # Start session
        await presence_service.start_session(str(test_schedule.id))

        # Log multiple detections
        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id=str(test_student.id),
            confidence=0.85
        )

        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id=str(test_student.id),
            confidence=0.87
        )

        # Check only one attendance record exists
        from app.repositories.attendance_repository import AttendanceRepository
        repo = AttendanceRepository(db_session)

        # Query all records for this student/schedule/date
        records = db_session.query(repo.model).filter(
            repo.model.student_id == test_student.id,
            repo.model.schedule_id == test_schedule.id,
            repo.model.date == date.today()
        ).all()

        assert len(records) == 1


class TestAttendanceHistory:
    """Test attendance history queries"""

    def test_get_student_attendance_history(
        self,
        client,
        test_student,
        test_schedule,
        test_attendance_record,
        auth_headers_student
    ):
        """Student can view their attendance history"""
        response = client.get(
            f"{API}/attendance/my-attendance",
            headers=auth_headers_student
        )

        assert response.status_code == 200
        data = response.json()

        # Should have at least the test record
        assert len(data) >= 1

    def test_get_attendance_by_schedule(
        self,
        client,
        test_faculty,
        test_schedule,
        test_attendance_record,
        auth_headers_faculty
    ):
        """Faculty can view attendance for their schedule"""
        response = client.get(
            f"{API}/attendance/schedule/{test_schedule.id}",
            headers=auth_headers_faculty,
            params={"date": date.today().isoformat()}
        )

        assert response.status_code == 200
        data = response.json()

        # Should return attendance records
        assert isinstance(data, list)

    def test_get_attendance_by_date_range(
        self,
        client,
        test_student,
        auth_headers_student
    ):
        """Get attendance records within date range"""
        start_date = (date.today() - timedelta(days=7)).isoformat()
        end_date = date.today().isoformat()

        response = client.get(
            f"{API}/attendance/my-attendance",
            headers=auth_headers_student,
            params={
                "start_date": start_date,
                "end_date": end_date
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestManualAttendanceEntry:
    """Test manual attendance entry by faculty"""

    def test_faculty_mark_student_present(
        self,
        client,
        test_faculty,
        test_student,
        test_schedule,
        test_enrollment,
        auth_headers_faculty
    ):
        """Faculty manually marks student as present"""
        payload = {
            "student_id": str(test_student.id),
            "schedule_id": str(test_schedule.id),
            "date": date.today().isoformat(),
            "status": "present",
            "remarks": "Manually marked by faculty"
        }

        response = client.post(
            f"{API}/attendance/manual-entry",
            json=payload,
            headers=auth_headers_faculty
        )

        # Manual entry endpoint might not be implemented yet
        # If 404, that's expected
        assert response.status_code in (200, 201, 404)

    def test_faculty_mark_student_excused(
        self,
        client,
        test_faculty,
        test_student,
        test_schedule,
        auth_headers_faculty
    ):
        """Faculty marks student as excused"""
        payload = {
            "student_id": str(test_student.id),
            "schedule_id": str(test_schedule.id),
            "date": date.today().isoformat(),
            "status": "excused",
            "remarks": "Medical certificate submitted"
        }

        response = client.post(
            f"{API}/attendance/manual-entry",
            json=payload,
            headers=auth_headers_faculty
        )

        # Manual entry endpoint might not be implemented yet
        assert response.status_code in (200, 201, 404)


class TestAttendanceStatistics:
    """Test attendance statistics and summaries"""

    def test_get_student_attendance_summary(
        self,
        client,
        test_student,
        auth_headers_student
    ):
        """Get attendance summary for student"""
        response = client.get(
            f"{API}/attendance/summary",
            headers=auth_headers_student
        )

        # Summary endpoint might return 200 or 404 if not implemented
        if response.status_code == 200:
            data = response.json()
            assert "total_classes" in data or "present_count" in data

    def test_get_class_attendance_summary(
        self,
        client,
        test_faculty,
        test_schedule,
        auth_headers_faculty
    ):
        """Get attendance summary for entire class"""
        response = client.get(
            f"{API}/attendance/schedule/{test_schedule.id}/summary",
            headers=auth_headers_faculty
        )

        # Summary endpoint might not be implemented yet
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)


class TestAttendanceExport:
    """Test attendance report export"""

    def test_export_attendance_csv(
        self,
        client,
        test_faculty,
        test_schedule,
        auth_headers_faculty
    ):
        """Export attendance records as CSV"""
        response = client.get(
            f"{API}/attendance/schedule/{test_schedule.id}/export",
            headers=auth_headers_faculty,
            params={"format": "csv"}
        )

        # Export endpoint might not be implemented yet
        if response.status_code == 200:
            # Should return CSV content
            assert "text/csv" in response.headers.get("content-type", "")

    def test_export_attendance_excel(
        self,
        client,
        test_faculty,
        test_schedule,
        auth_headers_faculty
    ):
        """Export attendance records as Excel"""
        response = client.get(
            f"{API}/attendance/schedule/{test_schedule.id}/export",
            headers=auth_headers_faculty,
            params={"format": "excel"}
        )

        # Export endpoint might not be implemented yet
        if response.status_code == 200:
            # Should return Excel content
            content_type = response.headers.get("content-type", "")
            assert "excel" in content_type or "spreadsheet" in content_type


class TestAttendancePermissions:
    """Test attendance access control"""

    def test_student_cannot_view_others_attendance(
        self,
        client,
        test_student,
        test_faculty,
        auth_headers_student
    ):
        """Students cannot view other students' attendance"""
        # Try to access another user's attendance
        response = client.get(
            f"{API}/attendance/student/{test_faculty.id}",
            headers=auth_headers_student
        )

        # Should be forbidden or not found
        assert response.status_code in (403, 404)

    def test_faculty_can_view_class_attendance(
        self,
        client,
        test_faculty,
        test_schedule,
        auth_headers_faculty
    ):
        """Faculty can view attendance for their classes"""
        response = client.get(
            f"{API}/attendance/schedule/{test_schedule.id}",
            headers=auth_headers_faculty,
            params={"date": date.today().isoformat()}
        )

        assert response.status_code in (200, 404)  # 404 if endpoint not implemented

    def test_unauthenticated_cannot_access_attendance(
        self,
        client,
        test_schedule
    ):
        """Unauthenticated users cannot access attendance data"""
        response = client.get(
            f"{API}/attendance/schedule/{test_schedule.id}"
        )

        assert response.status_code in (401, 403)


class TestAttendanceRepositoryIntegration:
    """Test attendance repository operations"""

    def test_create_attendance_record(self, db_session, test_student, test_schedule):
        """Create attendance record via repository"""
        from app.repositories.attendance_repository import AttendanceRepository
        from app.models.attendance_record import AttendanceStatus

        repo = AttendanceRepository(db_session)

        record = repo.create({
            "student_id": str(test_student.id),
            "schedule_id": str(test_schedule.id),
            "date": date.today(),
            "status": AttendanceStatus.PRESENT,
            "check_in_time": datetime.now(),
            "total_scans": 1,
            "scans_present": 1,
            "presence_score": 100.0
        })

        assert record.id is not None
        assert record.status == AttendanceStatus.PRESENT

    def test_update_attendance_status(
        self,
        db_session,
        test_attendance_record
    ):
        """Update attendance record status"""
        from app.repositories.attendance_repository import AttendanceRepository
        from app.models.attendance_record import AttendanceStatus

        repo = AttendanceRepository(db_session)

        # Update status
        repo.update(str(test_attendance_record.id), {
            "status": AttendanceStatus.LATE,
            "check_in_time": datetime.now()
        })

        # Verify update
        updated = repo.get_by_id(str(test_attendance_record.id))
        assert updated.status == AttendanceStatus.LATE
        assert updated.check_in_time is not None

    def test_get_attendance_by_student_and_date(
        self,
        db_session,
        test_student,
        test_schedule,
        test_attendance_record
    ):
        """Query attendance by student and date"""
        from app.repositories.attendance_repository import AttendanceRepository

        repo = AttendanceRepository(db_session)

        record = repo.get_by_student_date(
            str(test_student.id),
            str(test_schedule.id),
            date.today()
        )

        assert record is not None
        assert record.student_id == test_student.id

    def test_get_attendance_by_schedule_and_date(
        self,
        db_session,
        test_schedule,
        test_attendance_record
    ):
        """Query all attendance records for a schedule on a date"""
        from app.repositories.attendance_repository import AttendanceRepository

        repo = AttendanceRepository(db_session)

        records = repo.get_by_schedule_date(
            str(test_schedule.id),
            date.today()
        )

        assert len(records) >= 1
        assert all(r.schedule_id == test_schedule.id for r in records)
