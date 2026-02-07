"""
End-to-End System Tests

Tests complete system workflows from student registration through
a full class session with attendance tracking and early leave detection.
"""

import pytest
import io
from PIL import Image
from datetime import datetime, date, time, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
import numpy as np

from app.config import settings


API = settings.API_PREFIX


class TestCompleteClassSessionFlow:
    """
    End-to-end test simulating a complete class session:

    1. Student registers (face)
    2. Schedule starts
    3. Edge device detects faces
    4. Backend recognizes and marks attendance
    5. Presence tracking runs (60s intervals)
    6. Student leaves early (3 consecutive misses)
    7. Early leave alert triggered
    8. Session ends
    9. Verify all data correctly persisted
    """

    @pytest.mark.asyncio
    async def test_complete_class_session_with_early_leave(
        self,
        db_session,
        test_student,
        test_faculty,
        test_room,
        test_schedule,
        test_enrollment
    ):
        """
        Simulate complete class session with early leave detection.

        This is the most comprehensive test covering the entire system.
        """
        from app.services.face_service import FaceService
        from app.services.presence_service import PresenceService
        from app.repositories.attendance_repository import AttendanceRepository
        from app.models.attendance_record import AttendanceStatus

        # ============================================================
        # STEP 1: Student registers face
        # ============================================================

        with patch('app.services.face_service.facenet_model') as mock_facenet, \
             patch('app.services.face_service.faiss_manager') as mock_faiss:

            # Mock FaceNet to return consistent embedding
            student_embedding = np.random.randn(512).astype(np.float32)
            student_embedding = student_embedding / np.linalg.norm(student_embedding)

            mock_facenet.generate_embedding = MagicMock(return_value=student_embedding)
            mock_faiss.add = MagicMock(return_value=1)
            mock_faiss.save = MagicMock()

            face_service = FaceService(db_session)

            # Create test images
            from fastapi import UploadFile
            images = []
            for i in range(3):
                img = Image.new('RGB', (160, 160), color='blue')
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='JPEG')
                img_bytes.seek(0)
                images.append(UploadFile(
                    filename=f"face_{i}.jpg",
                    file=img_bytes,
                    content_type="image/jpeg"
                ))

            # Register face
            faiss_id, message = await face_service.register_face(
                str(test_student.id),
                images
            )

            assert faiss_id == 1
            print("✓ Step 1: Student registered face")

            # ============================================================
            # STEP 2: Schedule starts (session begins)
            # ============================================================

            presence_service = PresenceService(db_session)

            session = await presence_service.start_session(str(test_schedule.id))

            assert session is not None
            assert len(session.student_states) == 1
            print("✓ Step 2: Class session started")

            # ============================================================
            # STEP 3: Edge device detects student (first scan)
            # ============================================================

            # Mock FAISS search to recognize student
            mock_faiss.search = MagicMock(
                return_value=[(str(test_student.id), 0.89)]
            )

            # Simulate edge device sending face
            await presence_service.log_detection(
                schedule_id=str(test_schedule.id),
                user_id=str(test_student.id),
                confidence=0.89
            )

            # Check attendance marked as PRESENT
            repo = AttendanceRepository(db_session)
            record = repo.get_by_student_date(
                str(test_student.id),
                str(test_schedule.id),
                date.today()
            )

            assert record.status == AttendanceStatus.PRESENT
            assert record.check_in_time is not None
            print("✓ Step 3: Student detected and marked present")

            # ============================================================
            # STEP 4: Presence tracking - multiple scans (student present)
            # ============================================================

            # Simulate 5 more scans where student is present
            for i in range(5):
                await presence_service.log_detection(
                    schedule_id=str(test_schedule.id),
                    user_id=str(test_student.id),
                    confidence=0.85 + (i * 0.01)  # Vary confidence
                )

            # Check presence logs
            logs = repo.get_recent_logs(str(record.id), limit=10)
            assert len(logs) >= 6  # Initial + 5 more
            print("✓ Step 4: Multiple presence scans recorded")

            # ============================================================
            # STEP 5: Student leaves early (3 consecutive misses)
            # ============================================================

            # Simulate 3 scan cycles where student is NOT detected
            for i in range(3):
                session.scan_count += 1
                await presence_service.process_session_scan(str(test_schedule.id))

            # Check early leave was detected
            db_session.refresh(record)
            assert record.status == AttendanceStatus.EARLY_LEAVE

            # Check early leave event created
            events = repo.get_early_leave_events(str(record.id))
            assert len(events) >= 1
            assert events[0].consecutive_misses == 3
            print("✓ Step 5: Early leave detected after 3 consecutive misses")

            # ============================================================
            # STEP 6: Session ends
            # ============================================================

            await presence_service.end_session(str(test_schedule.id))

            # Check session is no longer active
            assert not presence_service.is_session_active(str(test_schedule.id))

            # Check check-out time was recorded
            db_session.refresh(record)
            assert record.check_out_time is not None
            print("✓ Step 6: Session ended, check-out time recorded")

            # ============================================================
            # STEP 7: Verify final data state
            # ============================================================

            # Verify attendance record
            assert record.student_id == test_student.id
            assert record.schedule_id == test_schedule.id
            assert record.status == AttendanceStatus.EARLY_LEAVE
            assert record.check_in_time is not None
            assert record.check_out_time is not None
            assert record.total_scans > 0
            assert record.scans_present > 0
            assert record.presence_score > 0  # Some presence before leaving

            # Verify presence logs exist
            all_logs = repo.get_recent_logs(str(record.id), limit=100)
            assert len(all_logs) >= 9  # 6 present + 3 absent

            # Verify early leave event
            assert len(events) == 1
            assert events[0].attendance_id == record.id

            print("✓ Step 7: All data correctly persisted")
            print("\n✅ END-TO-END TEST PASSED: Complete class session with early leave")


class TestCompleteClassSessionNormalAttendance:
    """Test complete session where student stays entire time"""

    @pytest.mark.asyncio
    async def test_complete_session_full_attendance(
        self,
        db_session,
        test_student,
        test_schedule,
        test_enrollment
    ):
        """Student attends entire class (no early leave)"""
        from app.services.presence_service import PresenceService
        from app.repositories.attendance_repository import AttendanceRepository
        from app.models.attendance_record import AttendanceStatus

        presence_service = PresenceService(db_session)

        # Start session
        await presence_service.start_session(str(test_schedule.id))

        # Log initial detection
        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id=str(test_student.id),
            confidence=0.90
        )

        # Simulate 10 scans where student is consistently present
        for i in range(10):
            await presence_service.log_detection(
                schedule_id=str(test_schedule.id),
                user_id=str(test_student.id),
                confidence=0.88
            )

        # End session
        await presence_service.end_session(str(test_schedule.id))

        # Verify perfect attendance
        repo = AttendanceRepository(db_session)
        record = repo.get_by_student_date(
            str(test_student.id),
            str(test_schedule.id),
            date.today()
        )

        assert record.status == AttendanceStatus.PRESENT
        assert record.presence_score == 100.0
        assert record.scans_present == record.total_scans

        # No early leave event
        events = repo.get_early_leave_events(str(record.id))
        assert len(events) == 0


class TestMultipleStudentsSession:
    """Test session with multiple students"""

    @pytest.mark.asyncio
    async def test_session_with_multiple_students(
        self,
        db_session,
        test_schedule,
        test_faculty,
        test_room
    ):
        """Test session with multiple enrolled students"""
        from app.services.presence_service import PresenceService
        from app.repositories.attendance_repository import AttendanceRepository
        from app.models.user import User, UserRole
        from app.models.enrollment import Enrollment
        from app.utils.security import hash_password
        import uuid

        # Create additional students
        students = []
        for i in range(3):
            student = User(
                id=uuid.uuid4(),
                email=f"student{i}@test.edu",
                password_hash=hash_password("TestPass123"),
                role=UserRole.STUDENT,
                first_name=f"Student{i}",
                last_name="Test",
                student_id=f"STU-{i}",
                is_active=True
            )
            db_session.add(student)
            students.append(student)

        db_session.commit()

        # Enroll all students
        for student in students:
            enrollment = Enrollment(
                id=uuid.uuid4(),
                student_id=student.id,
                schedule_id=test_schedule.id
            )
            db_session.add(enrollment)

        db_session.commit()

        # Start session
        presence_service = PresenceService(db_session)
        session = await presence_service.start_session(str(test_schedule.id))

        # Should create attendance records for all students
        assert len(session.student_states) == 3

        # Log detections for 2 students (1 absent)
        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id=str(students[0].id),
            confidence=0.85
        )

        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id=str(students[1].id),
            confidence=0.82
        )

        # End session
        await presence_service.end_session(str(test_schedule.id))

        # Verify attendance
        repo = AttendanceRepository(db_session)

        # Student 0: Present
        record0 = repo.get_by_student_date(
            str(students[0].id),
            str(test_schedule.id),
            date.today()
        )
        assert record0.check_in_time is not None

        # Student 1: Present
        record1 = repo.get_by_student_date(
            str(students[1].id),
            str(test_schedule.id),
            date.today()
        )
        assert record1.check_in_time is not None

        # Student 2: Absent
        record2 = repo.get_by_student_date(
            str(students[2].id),
            str(test_schedule.id),
            date.today()
        )
        assert record2.check_in_time is None


class TestEdgeToEndSystemIntegration:
    """Test edge device → backend → database → notification flow"""

    def test_edge_api_to_attendance_integration(
        self,
        client,
        test_room,
        test_schedule,
        test_student,
        test_enrollment,
        test_face_image_base64
    ):
        """
        Test complete flow:
        1. Edge device sends face
        2. Backend recognizes
        3. Attendance marked
        4. Response sent back
        """
        with patch('app.routers.face.FaceService') as mock_face_service, \
             patch('app.routers.face.PresenceService') as mock_presence_service:

            # Mock face recognition
            face_instance = MagicMock()
            face_instance.facenet.decode_base64_image = MagicMock(return_value=MagicMock())

            async def mock_recognize(img_bytes, threshold=None):
                return str(test_student.id), 0.88

            face_instance.recognize_face = AsyncMock(side_effect=mock_recognize)
            mock_face_service.return_value = face_instance

            # Mock presence logging
            presence_instance = MagicMock()
            presence_instance.log_detection = AsyncMock()
            mock_presence_service.return_value = presence_instance

            # Mock schedule repository
            with patch('app.routers.face.ScheduleRepository') as mock_sched_repo:
                repo_instance = MagicMock()
                repo_instance.get_current_schedule = MagicMock(return_value=test_schedule)
                mock_sched_repo.return_value = repo_instance

                # Send edge request
                payload = {
                    "room_id": str(test_room.id),
                    "timestamp": datetime.utcnow().isoformat(),
                    "faces": [
                        {"image": test_face_image_base64, "bbox": [100, 100, 112, 112]}
                    ]
                }

                response = client.post(f"{API}/face/process", json=payload)

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["data"]["processed"] == 1
        assert len(data["data"]["matched"]) == 1
        assert data["data"]["matched"][0]["user_id"] == str(test_student.id)

        # Verify presence was logged
        presence_instance.log_detection.assert_called_once()


class TestSystemErrorRecovery:
    """Test system behavior during failures"""

    @pytest.mark.asyncio
    async def test_session_continues_after_detection_error(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """Session continues even if one detection fails"""
        from app.services.presence_service import PresenceService

        presence_service = PresenceService(db_session)

        # Start session
        await presence_service.start_session(str(test_schedule.id))

        # First detection succeeds
        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id=str(test_student.id),
            confidence=0.85
        )

        # Try to log detection for non-enrolled student (should handle gracefully)
        await presence_service.log_detection(
            schedule_id=str(test_schedule.id),
            user_id="non-existent-user-id",
            confidence=0.80
        )

        # Session should still be active
        assert presence_service.is_session_active(str(test_schedule.id))

        # End session should work
        await presence_service.end_session(str(test_schedule.id))


class TestSystemPerformanceMetrics:
    """Test system performance under normal load"""

    @pytest.mark.asyncio
    async def test_rapid_detections_performance(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """System handles rapid sequential detections"""
        from app.services.presence_service import PresenceService
        import time

        presence_service = PresenceService(db_session)

        # Start session
        await presence_service.start_session(str(test_schedule.id))

        # Log 50 rapid detections
        start_time = time.time()

        for i in range(50):
            await presence_service.log_detection(
                schedule_id=str(test_schedule.id),
                user_id=str(test_student.id),
                confidence=0.85
            )

        elapsed = time.time() - start_time

        # Should complete in reasonable time (< 5 seconds)
        assert elapsed < 5.0

        # Verify all logs were created
        from app.repositories.attendance_repository import AttendanceRepository
        repo = AttendanceRepository(db_session)

        record = repo.get_by_student_date(
            str(test_student.id),
            str(test_schedule.id),
            date.today()
        )

        assert record.scans_present == 50
