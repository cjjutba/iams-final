"""
Enrollment Service

Business logic for auto-enrolling students into schedules
based on their course and year level from student_records.
"""

from typing import List
from sqlalchemy.orm import Session

from app.models.enrollment import Enrollment
from app.models.schedule import Schedule
from app.models.student_record import StudentRecord
from app.config import logger


class EnrollmentService:
    """Service for managing student enrollments"""

    def __init__(self, db: Session):
        self.db = db

    def auto_enroll_student(self, user_id, student_id: str) -> List[Enrollment]:
        """
        Auto-enroll a student into all matching active schedules.

        Matches based on:
        - student_record.course == schedule.target_course
        - student_record.year_level == schedule.target_year_level
        - schedule.is_active == True

        Args:
            user_id: The user's UUID (from users table)
            student_id: The school-issued student ID (e.g., "21-A-11111")

        Returns:
            List of created Enrollment records
        """
        # Look up student record to get course + year_level
        record = self.db.query(StudentRecord).filter(
            StudentRecord.student_id == student_id
        ).first()

        if not record or not record.course or not record.year_level:
            logger.info(f"No course/year info for {student_id}, skipping auto-enrollment")
            return []

        # Find matching active schedules
        matching_schedules = self.db.query(Schedule).filter(
            Schedule.target_course == record.course,
            Schedule.target_year_level == record.year_level,
            Schedule.is_active == True,
        ).all()

        if not matching_schedules:
            logger.info(f"No matching schedules for {record.course} Year {record.year_level}")
            return []

        # Create enrollments (skip duplicates)
        created = []
        for schedule in matching_schedules:
            existing = self.db.query(Enrollment).filter(
                Enrollment.student_id == user_id,
                Enrollment.schedule_id == schedule.id,
            ).first()

            if not existing:
                enrollment = Enrollment(
                    student_id=user_id,
                    schedule_id=schedule.id,
                )
                self.db.add(enrollment)
                created.append(enrollment)

        if created:
            self.db.flush()
            logger.info(
                f"Auto-enrolled {student_id} into {len(created)} schedules "
                f"(course={record.course}, year={record.year_level})"
            )

        return created
