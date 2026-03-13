"""
Notification Service

Handles real-time notifications via WebSocket for attendance events.
"""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import logger
from app.models.attendance_record import AttendanceRecord
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.schedule import Schedule
from app.models.user import User


class NotificationService:
    """
    Service for sending real-time notifications via WebSocket

    Handles:
    - Early leave alerts to faculty
    - Attendance updates (check-in notifications)
    - Session start/end notifications
    - Broadcast messages to all users in a schedule
    - Anomaly alerts, attendance confirmations, low attendance warnings
    - Persisted notifications with preference gating
    """

    def __init__(self, ws_manager, db: Session):
        """
        Initialize notification service

        Args:
            ws_manager: WebSocket ConnectionManager instance
            db: Database session
        """
        self.ws_manager = ws_manager
        self.db = db

    def _check_preference(self, user_id: str, pref_field: str) -> bool:
        """Check if a user has a specific notification preference enabled."""
        import uuid

        pref = (
            self.db.query(NotificationPreference).filter(NotificationPreference.user_id == uuid.UUID(user_id)).first()
        )
        if pref is None:
            return True  # Default to enabled if no preference record
        return getattr(pref, pref_field, True)

    def create_persisted_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: str = "system",
        data: dict[str, Any] = None,
        reference_id: str = None,
        reference_type: str = None,
    ) -> Notification:
        """Create a notification in the DB and push via WebSocket."""
        import uuid

        notif = Notification(
            user_id=uuid.UUID(user_id),
            title=title,
            message=message,
            type=notification_type,
            reference_id=reference_id,
            reference_type=reference_type,
        )
        self.db.add(notif)
        self.db.commit()
        self.db.refresh(notif)

        # Also push via WebSocket
        ws_message = {
            "event": "notification",
            "data": {
                "id": str(notif.id),
                "title": title,
                "message": message,
                "type": notification_type,
                "timestamp": notif.created_at.isoformat(),
            },
        }
        if data:
            ws_message["data"]["extra"] = data

        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.ws_manager.send_personal(user_id, ws_message))
            else:
                loop.run_until_complete(self.ws_manager.send_personal(user_id, ws_message))
        except Exception as e:
            logger.debug(f"WebSocket push failed (notification still persisted): {e}")

        return notif

    async def notify_early_leave(self, attendance: AttendanceRecord):
        """
        Send early leave alert to faculty member

        Notifies the faculty teaching the class that a student has left early.

        Args:
            attendance: AttendanceRecord with early leave status
        """
        try:
            # Get schedule to find faculty
            schedule = self.db.query(Schedule).filter(Schedule.id == attendance.schedule_id).first()

            if not schedule:
                logger.error(f"Schedule not found for attendance {attendance.id}")
                return

            # Get student info
            student = self.db.query(User).filter(User.id == attendance.student_id).first()
            if not student:
                logger.error(f"Student not found: {attendance.student_id}")
                return

            # Build notification message
            message = {
                "event": "early_leave",
                "data": {
                    "attendance_id": str(attendance.id),
                    "student_id": str(attendance.student_id),
                    "student_name": f"{student.first_name} {student.last_name}",
                    "student_student_id": student.student_id,
                    "schedule_id": str(attendance.schedule_id),
                    "subject_code": schedule.subject_code,
                    "subject_name": schedule.subject_name,
                    "detected_at": datetime.now().isoformat(),
                    "last_seen_at": None,  # Will be populated from presence logs
                    "consecutive_misses": 3,  # From settings.EARLY_LEAVE_THRESHOLD
                },
            }

            # Get last seen time from recent logs
            if attendance.presence_logs:
                recent_detected = [log for log in attendance.presence_logs if log.detected]
                if recent_detected:
                    recent_detected.sort(key=lambda x: x.scan_time, reverse=True)
                    message["data"]["last_seen_at"] = recent_detected[0].scan_time.isoformat()

            # Send to faculty
            faculty_id = str(schedule.faculty_id)
            await self.ws_manager.send_personal(faculty_id, message)

            logger.info(f"Early leave notification sent to faculty {faculty_id} for student {student.student_id}")

        except Exception as e:
            logger.error(f"Failed to send early leave notification: {e}")

    async def notify_early_leave_return(self, attendance: AttendanceRecord, absence_duration_seconds: int):
        """Send notification that a student returned after early leave."""
        try:
            schedule = self.db.query(Schedule).filter(Schedule.id == attendance.schedule_id).first()
            if not schedule:
                return

            student = self.db.query(User).filter(User.id == attendance.student_id).first()
            if not student:
                return

            message = {
                "event": "early_leave_return",
                "data": {
                    "attendance_id": str(attendance.id),
                    "student_id": str(attendance.student_id),
                    "student_name": f"{student.first_name} {student.last_name}",
                    "schedule_id": str(attendance.schedule_id),
                    "subject_code": schedule.subject_code,
                    "absence_duration_seconds": absence_duration_seconds,
                    "returned_at": datetime.now().isoformat(),
                },
            }

            faculty_id = str(schedule.faculty_id)
            await self.ws_manager.send_personal(faculty_id, message)

            logger.info(
                f"Early leave return notification sent for student {student.student_id} "
                f"(absent {absence_duration_seconds}s)"
            )
        except Exception as e:
            logger.error(f"Failed to send early leave return notification: {e}")

    async def notify_attendance_update(
        self, schedule_id: str, student_id: str, status: str, check_in_time: datetime = None
    ):
        """
        Send attendance update notification to faculty

        Notifies faculty when a student checks in.

        Args:
            schedule_id: Schedule UUID
            student_id: Student UUID
            status: Attendance status (present, late, etc.)
            check_in_time: Time of check-in
        """
        try:
            # Get schedule
            schedule = self.db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not schedule:
                logger.error(f"Schedule not found: {schedule_id}")
                return

            # Get student
            student = self.db.query(User).filter(User.id == student_id).first()
            if not student:
                logger.error(f"Student not found: {student_id}")
                return

            # Build message
            message = {
                "event": "attendance_update",
                "data": {
                    "student_id": str(student_id),
                    "student_name": f"{student.first_name} {student.last_name}",
                    "student_student_id": student.student_id,
                    "schedule_id": str(schedule_id),
                    "subject_code": schedule.subject_code,
                    "status": status,
                    "check_in_time": check_in_time.isoformat() if check_in_time else None,
                    "timestamp": datetime.now().isoformat(),
                },
            }

            # Send to faculty
            faculty_id = str(schedule.faculty_id)
            await self.ws_manager.send_personal(faculty_id, message)

            logger.debug(
                f"Attendance update sent to faculty {faculty_id}: Student {student.student_id} marked {status}"
            )

        except Exception as e:
            logger.error(f"Failed to send attendance update: {e}")

    async def notify_session_start(self, schedule_id: str):
        """
        Notify faculty that attendance session has started

        Args:
            schedule_id: Schedule UUID
        """
        try:
            schedule = self.db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not schedule:
                return

            message = {
                "event": "session_start",
                "data": {
                    "schedule_id": str(schedule_id),
                    "subject_code": schedule.subject_code,
                    "subject_name": schedule.subject_name,
                    "start_time": datetime.now().isoformat(),
                },
            }

            faculty_id = str(schedule.faculty_id)
            await self.ws_manager.send_personal(faculty_id, message)

            logger.info(f"Session start notification sent for schedule {schedule_id}")

        except Exception as e:
            logger.error(f"Failed to send session start notification: {e}")

    async def notify_session_end(self, schedule_id: str, summary: dict[str, Any]):
        """
        Notify faculty that attendance session has ended

        Args:
            schedule_id: Schedule UUID
            summary: Session summary statistics
        """
        try:
            schedule = self.db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not schedule:
                return

            message = {
                "event": "session_end",
                "data": {
                    "schedule_id": str(schedule_id),
                    "subject_code": schedule.subject_code,
                    "subject_name": schedule.subject_name,
                    "end_time": datetime.now().isoformat(),
                    "summary": summary,
                },
            }

            faculty_id = str(schedule.faculty_id)
            await self.ws_manager.send_personal(faculty_id, message)

            logger.info(f"Session end notification sent for schedule {schedule_id}")

        except Exception as e:
            logger.error(f"Failed to send session end notification: {e}")

    async def broadcast_session_summary(self, schedule_id: str, summary: dict[str, Any]):
        """
        Broadcast session summary to all participants in a schedule

        Args:
            schedule_id: Schedule UUID
            summary: Session summary data
        """
        try:
            message = {
                "event": "session_summary",
                "data": {"schedule_id": str(schedule_id), "summary": summary, "timestamp": datetime.now().isoformat()},
            }

            # Use ConnectionManager's broadcast_to_schedule if implemented
            # For now, send to faculty only
            schedule = self.db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if schedule:
                faculty_id = str(schedule.faculty_id)
                await self.ws_manager.send_personal(faculty_id, message)

        except Exception as e:
            logger.error(f"Failed to broadcast session summary: {e}")

    async def notify_anomaly_detected(self, faculty_id: str, anomaly_type: str, student_name: str, severity: str):
        """Send anomaly detection alert to faculty (if preference allows)."""
        if not self._check_preference(faculty_id, "anomaly_alerts"):
            return

        message = {
            "event": "anomaly_detected",
            "data": {
                "anomaly_type": anomaly_type,
                "student_name": student_name,
                "severity": severity,
                "timestamp": datetime.now().isoformat(),
            },
        }
        try:
            await self.ws_manager.send_personal(faculty_id, message)
        except Exception as e:
            logger.error(f"Failed to send anomaly notification: {e}")

    async def notify_attendance_confirmation(
        self, student_id: str, subject_name: str, status: str, check_in_time: datetime
    ):
        """Send attendance confirmation to student (if preference allows)."""
        if not self._check_preference(student_id, "attendance_confirmation"):
            return

        message = {
            "event": "attendance_confirmed",
            "data": {
                "subject_name": subject_name,
                "status": status,
                "check_in_time": check_in_time.isoformat() if check_in_time else None,
                "timestamp": datetime.now().isoformat(),
            },
        }
        try:
            await self.ws_manager.send_personal(student_id, message)
        except Exception as e:
            logger.error(f"Failed to send attendance confirmation: {e}")

    async def notify_low_attendance_warning(
        self, student_id: str, subject_name: str, current_rate: float, threshold: float
    ):
        """Send low attendance warning to student (if preference allows)."""
        if not self._check_preference(student_id, "low_attendance_warning"):
            return

        message = {
            "event": "low_attendance_warning",
            "data": {
                "subject_name": subject_name,
                "current_rate": round(current_rate, 1),
                "threshold": threshold,
                "timestamp": datetime.now().isoformat(),
            },
        }
        try:
            await self.ws_manager.send_personal(student_id, message)
        except Exception as e:
            logger.error(f"Failed to send low attendance warning: {e}")
