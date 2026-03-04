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

    def auto_enroll_student(
        self,
        user_id,
        student_id: str,
        *,
        record: "StudentRecord | None" = None,
        skip_duplicate_check: bool = False,
    ) -> List[Enrollment]:
        """
        Auto-enroll a student into all matching active schedules.

        Matches based on:
        - student_record.course == schedule.target_course
        - student_record.year_level == schedule.target_year_level
        - schedule.is_active == True

        Args:
            user_id: The user's UUID (from users table)
            student_id: The school-issued student ID (e.g., "21-A-11111")
            record: Pre-fetched StudentRecord to avoid redundant DB query.
            skip_duplicate_check: When True (e.g. during registration of a
                brand-new user), skip the per-schedule EXISTS checks since
                no enrollments can exist yet.

        Returns:
            List of created Enrollment records
        """
        # Use provided record or fetch from DB
        if record is None:
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

        # Determine which schedule IDs already have enrollments (single query)
        if skip_duplicate_check:
            existing_schedule_ids = set()
        else:
            schedule_ids = [s.id for s in matching_schedules]
            rows = self.db.query(Enrollment.schedule_id).filter(
                Enrollment.student_id == user_id,
                Enrollment.schedule_id.in_(schedule_ids),
            ).all()
            existing_schedule_ids = {r[0] for r in rows}

        # Create enrollments (skip duplicates)
        created = []
        for schedule in matching_schedules:
            if schedule.id not in existing_schedule_ids:
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
