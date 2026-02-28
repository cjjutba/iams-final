"""
Tests for EnrollmentService.auto_enroll_student().

Validates automatic enrollment of students into schedules based on
matching course and year_level from their StudentRecord.
"""

import uuid
from datetime import time

import pytest

from app.models.enrollment import Enrollment
from app.models.schedule import Schedule
from app.models.student_record import StudentRecord
from app.services.enrollment_service import EnrollmentService


def _make_schedule(
    db_session,
    faculty_id,
    room_id,
    *,
    subject_code="CPE301",
    subject_name="Microprocessors",
    day_of_week=0,
    start_time_val=time(8, 0),
    end_time_val=time(10, 0),
    target_course="BSCPE",
    target_year_level=1,
    is_active=True,
    semester="1st",
    academic_year="2024-2025",
):
    """Helper to create and persist a Schedule row."""
    schedule = Schedule(
        id=uuid.uuid4(),
        subject_code=subject_code,
        subject_name=subject_name,
        faculty_id=faculty_id,
        room_id=room_id,
        day_of_week=day_of_week,
        start_time=start_time_val,
        end_time=end_time_val,
        semester=semester,
        academic_year=academic_year,
        target_course=target_course,
        target_year_level=target_year_level,
        is_active=is_active,
    )
    db_session.add(schedule)
    db_session.commit()
    return schedule


class TestAutoEnrollStudent:
    """Tests for EnrollmentService.auto_enroll_student()."""

    def test_enroll_matching_schedules(
        self, db_session, test_student, test_faculty, test_room
    ):
        """Two schedules match BSCPE/year-1 -- both should produce enrollments."""
        _make_schedule(
            db_session,
            test_faculty.id,
            test_room.id,
            subject_code="CPE301",
            subject_name="Microprocessors",
            day_of_week=0,
        )
        _make_schedule(
            db_session,
            test_faculty.id,
            test_room.id,
            subject_code="CPE302",
            subject_name="Digital Systems",
            day_of_week=1,
        )

        service = EnrollmentService(db_session)
        result = service.auto_enroll_student(test_student.id, test_student.student_id)

        assert len(result) == 2
        count = (
            db_session.query(Enrollment)
            .filter(Enrollment.student_id == test_student.id)
            .count()
        )
        assert count == 2

    def test_no_matching_schedules(
        self, db_session, test_student, test_faculty, test_room
    ):
        """Schedules for a different course/year should not match."""
        _make_schedule(
            db_session,
            test_faculty.id,
            test_room.id,
            target_course="BSIT",
            target_year_level=3,
        )

        service = EnrollmentService(db_session)
        result = service.auto_enroll_student(test_student.id, test_student.student_id)

        assert result == []
        count = (
            db_session.query(Enrollment)
            .filter(Enrollment.student_id == test_student.id)
            .count()
        )
        assert count == 0

    def test_skip_inactive_schedules(
        self, db_session, test_student, test_faculty, test_room
    ):
        """Inactive schedules (is_active=False) should be skipped."""
        _make_schedule(
            db_session,
            test_faculty.id,
            test_room.id,
            is_active=False,
        )

        service = EnrollmentService(db_session)
        result = service.auto_enroll_student(test_student.id, test_student.student_id)

        assert result == []
        count = (
            db_session.query(Enrollment)
            .filter(Enrollment.student_id == test_student.id)
            .count()
        )
        assert count == 0

    def test_skip_duplicate_enrollment(
        self, db_session, test_student, test_faculty, test_room
    ):
        """If the student is already enrolled, auto_enroll should not duplicate."""
        schedule = _make_schedule(
            db_session,
            test_faculty.id,
            test_room.id,
        )

        # Manually create the enrollment first
        existing = Enrollment(
            id=uuid.uuid4(),
            student_id=test_student.id,
            schedule_id=schedule.id,
        )
        db_session.add(existing)
        db_session.commit()

        service = EnrollmentService(db_session)
        result = service.auto_enroll_student(test_student.id, test_student.student_id)

        # Should create 0 new enrollments (skip the duplicate)
        assert len(result) == 0
        count = (
            db_session.query(Enrollment)
            .filter(Enrollment.student_id == test_student.id)
            .count()
        )
        assert count == 1  # Still only the original

    def test_missing_student_record(
        self, db_session, test_student, test_faculty, test_room
    ):
        """A student_id with no matching StudentRecord should return empty."""
        _make_schedule(db_session, test_faculty.id, test_room.id)

        service = EnrollmentService(db_session)
        result = service.auto_enroll_student(test_student.id, "NONEXISTENT-999")

        assert result == []

    def test_null_course_in_record(
        self, db_session, test_student, test_faculty, test_room
    ):
        """StudentRecord with course=None should match nothing."""
        # Create a separate student record with null course
        null_record = StudentRecord(
            student_id="STU-NULL-COURSE",
            first_name="Null",
            last_name="Course",
            course=None,
            year_level=1,
        )
        db_session.add(null_record)
        db_session.commit()

        _make_schedule(db_session, test_faculty.id, test_room.id)

        service = EnrollmentService(db_session)
        result = service.auto_enroll_student(test_student.id, "STU-NULL-COURSE")

        assert result == []

    def test_null_year_in_record(
        self, db_session, test_student, test_faculty, test_room
    ):
        """StudentRecord with year_level=None should match nothing."""
        null_record = StudentRecord(
            student_id="STU-NULL-YEAR",
            first_name="Null",
            last_name="Year",
            course="BSCPE",
            year_level=None,
        )
        db_session.add(null_record)
        db_session.commit()

        _make_schedule(db_session, test_faculty.id, test_room.id)

        service = EnrollmentService(db_session)
        result = service.auto_enroll_student(test_student.id, "STU-NULL-YEAR")

        assert result == []

    def test_multiple_matching_schedules(
        self, db_session, test_student, test_faculty, test_room
    ):
        """All 5 matching schedules should produce 5 enrollments."""
        subjects = [
            ("CPE301", "Microprocessors"),
            ("CPE302", "Digital Systems"),
            ("CPE303", "Embedded Systems"),
            ("CPE304", "Computer Networks"),
            ("CPE305", "Operating Systems"),
        ]
        for i, (code, name) in enumerate(subjects):
            _make_schedule(
                db_session,
                test_faculty.id,
                test_room.id,
                subject_code=code,
                subject_name=name,
                day_of_week=i,
            )

        service = EnrollmentService(db_session)
        result = service.auto_enroll_student(test_student.id, test_student.student_id)

        assert len(result) == 5
        count = (
            db_session.query(Enrollment)
            .filter(Enrollment.student_id == test_student.id)
            .count()
        )
        assert count == 5

    def test_mixed_matching(
        self, db_session, test_student, test_faculty, test_room
    ):
        """3 matching + 2 non-matching schedules -- only 3 enrollments created."""
        # 3 matching (BSCPE, year 1)
        for i, code in enumerate(["CPE301", "CPE302", "CPE303"]):
            _make_schedule(
                db_session,
                test_faculty.id,
                test_room.id,
                subject_code=code,
                subject_name=f"Subject {code}",
                day_of_week=i,
                target_course="BSCPE",
                target_year_level=1,
            )

        # 2 non-matching (different course/year)
        _make_schedule(
            db_session,
            test_faculty.id,
            test_room.id,
            subject_code="IT201",
            subject_name="IT Elective",
            day_of_week=3,
            target_course="BSIT",
            target_year_level=2,
        )
        _make_schedule(
            db_session,
            test_faculty.id,
            test_room.id,
            subject_code="ECE401",
            subject_name="ECE Elective",
            day_of_week=4,
            target_course="BSECE",
            target_year_level=4,
        )

        service = EnrollmentService(db_session)
        result = service.auto_enroll_student(test_student.id, test_student.student_id)

        assert len(result) == 3
        count = (
            db_session.query(Enrollment)
            .filter(Enrollment.student_id == test_student.id)
            .count()
        )
        assert count == 3

    def test_idempotent(
        self, db_session, test_student, test_faculty, test_room
    ):
        """Calling auto_enroll twice should not create duplicate enrollments."""
        _make_schedule(
            db_session,
            test_faculty.id,
            test_room.id,
            subject_code="CPE301",
            subject_name="Microprocessors",
        )
        _make_schedule(
            db_session,
            test_faculty.id,
            test_room.id,
            subject_code="CPE302",
            subject_name="Digital Systems",
            day_of_week=1,
        )

        service = EnrollmentService(db_session)

        # First call -- should create 2
        first_result = service.auto_enroll_student(
            test_student.id, test_student.student_id
        )
        assert len(first_result) == 2

        # Second call -- should create 0 new
        second_result = service.auto_enroll_student(
            test_student.id, test_student.student_id
        )
        assert len(second_result) == 0

        # Total in DB should still be 2
        count = (
            db_session.query(Enrollment)
            .filter(Enrollment.student_id == test_student.id)
            .count()
        )
        assert count == 2
