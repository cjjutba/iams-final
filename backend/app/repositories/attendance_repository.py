"""
Attendance Repository

Data access layer for Attendance, PresenceLog, and EarlyLeaveEvent operations.
"""

from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.attendance_record import AttendanceRecord, AttendanceStatus
from app.models.presence_log import PresenceLog
from app.models.early_leave_event import EarlyLeaveEvent
from app.utils.exceptions import NotFoundError


class AttendanceRepository:
    """Repository for Attendance CRUD operations"""

    def __init__(self, db: Session):
        self.db = db

    # ===== AttendanceRecord Operations =====

    def get_by_id(self, attendance_id: str) -> Optional[AttendanceRecord]:
        """Get attendance record by ID"""
        return self.db.query(AttendanceRecord).filter(AttendanceRecord.id == attendance_id).first()

    def get_by_student_date(self, student_id: str, schedule_id: str, attendance_date: date) -> Optional[AttendanceRecord]:
        """Get attendance record for a student on a specific date"""
        return self.db.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.schedule_id == schedule_id,
                AttendanceRecord.date == attendance_date
            )
        ).first()

    def get_by_schedule_date(self, schedule_id: str, attendance_date: date) -> List[AttendanceRecord]:
        """Get all attendance records for a schedule on a specific date"""
        return self.db.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.schedule_id == schedule_id,
                AttendanceRecord.date == attendance_date
            )
        ).all()

    def get_student_history(
        self,
        student_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[AttendanceRecord]:
        """
        Get attendance history for a student

        Args:
            student_id: Student UUID
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of attendance records
        """
        query = self.db.query(AttendanceRecord).filter(AttendanceRecord.student_id == student_id)

        if start_date:
            query = query.filter(AttendanceRecord.date >= start_date)
        if end_date:
            query = query.filter(AttendanceRecord.date <= end_date)

        return query.order_by(AttendanceRecord.date.desc()).all()

    def create(self, attendance_data: dict) -> AttendanceRecord:
        """
        Create new attendance record

        Args:
            attendance_data: Attendance data dictionary

        Returns:
            Created attendance record
        """
        attendance = AttendanceRecord(**attendance_data)
        self.db.add(attendance)
        self.db.commit()
        self.db.refresh(attendance)
        return attendance

    def update(self, attendance_id: str, update_data: dict) -> AttendanceRecord:
        """
        Update attendance record

        Args:
            attendance_id: Attendance UUID
            update_data: Fields to update

        Returns:
            Updated attendance record

        Raises:
            NotFoundError: If attendance record not found
        """
        attendance = self.get_by_id(attendance_id)
        if not attendance:
            raise NotFoundError(f"Attendance record not found: {attendance_id}")

        for key, value in update_data.items():
            if hasattr(attendance, key) and value is not None:
                setattr(attendance, key, value)

        self.db.commit()
        self.db.refresh(attendance)
        return attendance

    def get_summary(self, student_id: str, start_date: date, end_date: date) -> dict:
        """
        Get attendance summary for a student

        Args:
            student_id: Student UUID
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with attendance statistics
        """
        records = self.db.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.date >= start_date,
                AttendanceRecord.date <= end_date
            )
        ).all()

        total = len(records)
        present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        late = sum(1 for r in records if r.status == AttendanceStatus.LATE)
        absent = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        early_leave = sum(1 for r in records if r.status == AttendanceStatus.EARLY_LEAVE)

        return {
            "total_classes": total,
            "present_count": present,
            "late_count": late,
            "absent_count": absent,
            "early_leave_count": early_leave,
            "attendance_rate": (present + late) / total * 100 if total > 0 else 0.0
        }

    # ===== PresenceLog Operations =====

    def log_presence(self, attendance_id: str, scan_data: dict) -> PresenceLog:
        """
        Create a presence log entry

        Args:
            attendance_id: Attendance record UUID
            scan_data: Scan data (scan_number, detected, confidence)

        Returns:
            Created presence log
        """
        log = PresenceLog(attendance_id=attendance_id, **scan_data)
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_presence_logs(self, attendance_id: str) -> List[PresenceLog]:
        """Get all presence logs for an attendance record"""
        return self.db.query(PresenceLog).filter(
            PresenceLog.attendance_id == attendance_id
        ).order_by(PresenceLog.scan_number).all()

    def get_recent_logs(self, attendance_id: str, limit: int = 3) -> List[PresenceLog]:
        """
        Get most recent presence logs

        Args:
            attendance_id: Attendance record UUID
            limit: Number of logs to retrieve

        Returns:
            List of recent logs (most recent first)
        """
        return self.db.query(PresenceLog).filter(
            PresenceLog.attendance_id == attendance_id
        ).order_by(PresenceLog.scan_number.desc()).limit(limit).all()

    # ===== EarlyLeaveEvent Operations =====

    def create_early_leave_event(self, event_data: dict) -> EarlyLeaveEvent:
        """
        Create early leave event

        Args:
            event_data: Event data dictionary

        Returns:
            Created early leave event
        """
        event = EarlyLeaveEvent(**event_data)
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_early_leave_events(
        self,
        schedule_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[EarlyLeaveEvent]:
        """
        Get early leave events with optional filters

        Args:
            schedule_id: Optional schedule filter
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of early leave events
        """
        from app.models.attendance_record import AttendanceRecord

        query = self.db.query(EarlyLeaveEvent).join(
            AttendanceRecord, EarlyLeaveEvent.attendance_id == AttendanceRecord.id
        )

        if schedule_id:
            query = query.filter(AttendanceRecord.schedule_id == schedule_id)
        if start_date:
            query = query.filter(AttendanceRecord.date >= start_date)
        if end_date:
            query = query.filter(AttendanceRecord.date <= end_date)

        return query.order_by(EarlyLeaveEvent.detected_at.desc()).all()

    def update_early_leave_event(self, event_id: str, update_data: dict) -> EarlyLeaveEvent:
        """
        Update early leave event (e.g., mark as notified)

        Args:
            event_id: Event UUID
            update_data: Fields to update

        Returns:
            Updated event

        Raises:
            NotFoundError: If event not found
        """
        event = self.db.query(EarlyLeaveEvent).filter(EarlyLeaveEvent.id == event_id).first()
        if not event:
            raise NotFoundError(f"Early leave event not found: {event_id}")

        for key, value in update_data.items():
            if hasattr(event, key) and value is not None:
                setattr(event, key, value)

        self.db.commit()
        self.db.refresh(event)
        return event
