"""
Schedule Repository

Data access layer for Schedule operations.
"""

from typing import List, Optional
from datetime import time
from sqlalchemy.orm import Session

from app.models.schedule import Schedule
from app.models.user import User
from app.utils.exceptions import NotFoundError


class ScheduleRepository:
    """Repository for Schedule CRUD operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, schedule_id: str) -> Optional[Schedule]:
        """Get schedule by ID"""
        return self.db.query(Schedule).filter(Schedule.id == schedule_id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Schedule]:
        """Get all schedules with pagination"""
        return self.db.query(Schedule).filter(Schedule.is_active == True).offset(skip).limit(limit).all()

    def get_by_faculty(self, faculty_id: str) -> List[Schedule]:
        """Get all schedules taught by a faculty member"""
        return self.db.query(Schedule).filter(
            Schedule.faculty_id == faculty_id,
            Schedule.is_active == True
        ).all()

    def get_by_day(self, day_of_week: int) -> List[Schedule]:
        """
        Get all schedules for a specific day

        Args:
            day_of_week: 0=Monday, 6=Sunday

        Returns:
            List of schedules
        """
        return self.db.query(Schedule).filter(
            Schedule.day_of_week == day_of_week,
            Schedule.is_active == True
        ).all()

    def get_active_at_time(self, day_of_week: int, current_time: time) -> List[Schedule]:
        """
        Get schedules that are active at a specific day and time

        Args:
            day_of_week: 0=Monday, 6=Sunday
            current_time: Current time

        Returns:
            List of active schedules
        """
        return self.db.query(Schedule).filter(
            Schedule.day_of_week == day_of_week,
            Schedule.start_time <= current_time,
            Schedule.end_time >= current_time,
            Schedule.is_active == True
        ).all()

    def get_current_schedule(self, room_id: str, day_of_week: int, current_time: time) -> Optional[Schedule]:
        """
        Get the current schedule for a room at a specific time

        Args:
            room_id: Room UUID
            day_of_week: 0=Monday, 6=Sunday
            current_time: Current time

        Returns:
            Current schedule if found, None otherwise
        """
        return self.db.query(Schedule).filter(
            Schedule.room_id == room_id,
            Schedule.day_of_week == day_of_week,
            Schedule.start_time <= current_time,
            Schedule.end_time >= current_time,
            Schedule.is_active == True
        ).first()

    def get_enrolled_students(self, schedule_id: str) -> List[User]:
        """
        Get all students enrolled in a schedule

        Args:
            schedule_id: Schedule UUID

        Returns:
            List of enrolled students
        """
        from app.models.enrollment import Enrollment
        from app.models.user import User

        return self.db.query(User).join(
            Enrollment, Enrollment.student_id == User.id
        ).filter(
            Enrollment.schedule_id == schedule_id
        ).all()

    def create(self, schedule_data: dict) -> Schedule:
        """
        Create new schedule

        Args:
            schedule_data: Schedule data dictionary

        Returns:
            Created schedule
        """
        schedule = Schedule(**schedule_data)
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def update(self, schedule_id: str, update_data: dict) -> Schedule:
        """
        Update schedule

        Args:
            schedule_id: Schedule UUID
            update_data: Fields to update

        Returns:
            Updated schedule

        Raises:
            NotFoundError: If schedule not found
        """
        schedule = self.get_by_id(schedule_id)
        if not schedule:
            raise NotFoundError(f"Schedule not found: {schedule_id}")

        for key, value in update_data.items():
            if hasattr(schedule, key) and value is not None:
                setattr(schedule, key, value)

        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def delete(self, schedule_id: str) -> bool:
        """
        Delete schedule (soft delete by setting is_active=False)

        Args:
            schedule_id: Schedule UUID

        Returns:
            True if deleted

        Raises:
            NotFoundError: If schedule not found
        """
        schedule = self.get_by_id(schedule_id)
        if not schedule:
            raise NotFoundError(f"Schedule not found: {schedule_id}")

        schedule.is_active = False
        self.db.commit()
        return True

    def count(self) -> int:
        """Get total schedule count"""
        return self.db.query(Schedule).filter(Schedule.is_active == True).count()
