"""
Performance and Load Tests

Tests system performance under various load conditions including:
- Concurrent face recognition requests
- Multiple active sessions
- Database query performance
- FAISS index scalability
"""

import pytest
import time
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
import concurrent.futures
import numpy as np

from app.config import settings


API = settings.API_PREFIX


class TestFaceRecognitionPerformance:
    """Test face recognition performance"""

    @pytest.mark.asyncio
    async def test_100_sequential_recognitions(
        self,
        db_session
    ):
        """
        Performance test: 100 sequential face recognitions

        Target: < 5 seconds total (50ms per recognition)
        """
        from app.services.face_service import FaceService

        with patch('app.services.face_service.facenet_model') as mock_facenet, \
             patch('app.services.face_service.faiss_manager') as mock_faiss:

            # Mock FaceNet (fast)
            mock_embedding = np.random.randn(512).astype(np.float32)
            mock_embedding = mock_embedding / np.linalg.norm(mock_embedding)
            mock_facenet.generate_embedding = MagicMock(return_value=mock_embedding)

            # Mock FAISS (fast)
            mock_faiss.search = MagicMock(return_value=[("user-123", 0.85)])

            face_service = FaceService(db_session)

            # Test image
            from PIL import Image
            import io
            img = Image.new('RGB', (112, 112), color='blue')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='JPEG')
            img_bytes = img_bytes.getvalue()

            # Measure time for 100 recognitions
            start_time = time.time()

            for i in range(100):
                user_id, confidence = await face_service.recognize_face(img_bytes)

            elapsed = time.time() - start_time

            print(f"\n100 recognitions completed in {elapsed:.2f} seconds")
            print(f"Average: {elapsed/100*1000:.2f}ms per recognition")

            # Should complete in < 5 seconds (allowing for mock overhead)
            assert elapsed < 5.0

    @pytest.mark.asyncio
    async def test_concurrent_face_recognitions(
        self,
        db_session
    ):
        """
        Performance test: 50 concurrent face recognitions

        Tests system behavior under concurrent load.
        """
        from app.services.face_service import FaceService
        import asyncio

        with patch('app.services.face_service.facenet_model') as mock_facenet, \
             patch('app.services.face_service.faiss_manager') as mock_faiss:

            # Mock FaceNet
            mock_embedding = np.random.randn(512).astype(np.float32)
            mock_embedding = mock_embedding / np.linalg.norm(mock_embedding)
            mock_facenet.generate_embedding = MagicMock(return_value=mock_embedding)

            # Mock FAISS
            mock_faiss.search = MagicMock(return_value=[("user-456", 0.88)])

            face_service = FaceService(db_session)

            # Test image
            from PIL import Image
            import io
            img = Image.new('RGB', (112, 112), color='red')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='JPEG')
            img_bytes = img_bytes.getvalue()

            # Run 50 concurrent recognitions
            async def recognize():
                return await face_service.recognize_face(img_bytes)

            start_time = time.time()

            tasks = [recognize() for _ in range(50)]
            results = await asyncio.gather(*tasks)

            elapsed = time.time() - start_time

            print(f"\n50 concurrent recognitions completed in {elapsed:.2f} seconds")

            # All should succeed
            assert len(results) == 50
            assert all(user_id == "user-456" for user_id, _ in results)

            # Should complete reasonably fast
            assert elapsed < 10.0


class TestEdgeAPIPerformance:
    """Test Edge API performance under load"""

    def test_edge_api_response_time(
        self,
        client,
        test_room,
        test_face_image_base64
    ):
        """
        Test Edge API response time

        Target: < 500ms per request (P95)
        """
        with patch('app.routers.face.FaceService') as mock_service:
            service_instance = MagicMock()
            service_instance.facenet.decode_base64_image = MagicMock(
                return_value=MagicMock()
            )

            async def mock_recognize(img_bytes, threshold=None):
                return "user-789", 0.90

            service_instance.recognize_face = AsyncMock(side_effect=mock_recognize)
            mock_service.return_value = service_instance

            with patch('app.routers.face.PresenceService'):
                payload = {
                    "room_id": str(test_room.id),
                    "timestamp": datetime.utcnow().isoformat(),
                    "faces": [{"image": test_face_image_base64}]
                }

                # Measure response time for 20 requests
                times = []

                for i in range(20):
                    start = time.time()
                    response = client.post(f"{API}/face/process", json=payload)
                    elapsed = time.time() - start

                    assert response.status_code == 200
                    times.append(elapsed * 1000)  # Convert to ms

                # Calculate statistics
                avg_time = sum(times) / len(times)
                p95_time = sorted(times)[int(len(times) * 0.95)]

                print(f"\nEdge API Performance:")
                print(f"Average: {avg_time:.2f}ms")
                print(f"P95: {p95_time:.2f}ms")
                print(f"Min: {min(times):.2f}ms")
                print(f"Max: {max(times):.2f}ms")

                # P95 should be < 500ms (mocked, so should be fast)
                assert p95_time < 500

    def test_edge_api_batch_processing_performance(
        self,
        client,
        test_room,
        test_face_image_base64
    ):
        """
        Test Edge API with multiple faces in single request

        Simulates classroom with 10 students detected (max batch size).
        """
        with patch('app.routers.face.FaceService') as mock_service:
            service_instance = MagicMock()
            service_instance.facenet.decode_base64_image = MagicMock(
                return_value=MagicMock()
            )

            async def mock_recognize(img_bytes, threshold=None):
                return f"user-{np.random.randint(1000)}", 0.85

            service_instance.recognize_face = AsyncMock(side_effect=mock_recognize)
            mock_service.return_value = service_instance

            with patch('app.routers.face.PresenceService'):
                # 10 faces in one request (max_length=10 in schema)
                payload = {
                    "room_id": str(test_room.id),
                    "timestamp": datetime.utcnow().isoformat(),
                    "faces": [
                        {"image": test_face_image_base64, "bbox": [i*20, 100, 112, 112]}
                        for i in range(10)
                    ]
                }

                start_time = time.time()
                response = client.post(f"{API}/face/process", json=payload)
                elapsed = time.time() - start_time

                assert response.status_code == 200
                data = response.json()

                assert data["data"]["processed"] == 10

                print(f"\nProcessed 10 faces in {elapsed:.2f} seconds")
                print(f"Average: {elapsed/10*1000:.2f}ms per face")

                # Should process all faces in reasonable time (< 3 seconds)
                assert elapsed < 3.0


class TestDatabaseQueryPerformance:
    """Test database query performance"""

    def test_attendance_query_performance(
        self,
        db_session,
        test_student,
        test_schedule
    ):
        """
        Test attendance query performance with many records

        Creates 100 attendance records across different dates and queries them.
        """
        from app.repositories.attendance_repository import AttendanceRepository
        from app.models.attendance_record import AttendanceStatus
        import uuid

        repo = AttendanceRepository(db_session)

        # Create 100 attendance records on different dates (to avoid UNIQUE constraint)
        base_date = date.today()
        for i in range(100):
            record_date = date(base_date.year, base_date.month, 1) if base_date.month == 1 else base_date
            # Vary the date by going back i days
            record_date = date.fromordinal(record_date.toordinal() - i)

            repo.create({
                "student_id": str(test_student.id),
                "schedule_id": str(test_schedule.id),
                "date": record_date,
                "status": AttendanceStatus.PRESENT,
                "total_scans": i,
                "scans_present": i,
                "presence_score": 100.0
            })

        # Query performance test
        start_time = time.time()

        # Query by student history (no date filters to get all records)
        records = repo.get_student_history(str(test_student.id))

        elapsed = time.time() - start_time

        assert len(records) >= 100
        print(f"\nQueried {len(records)} records in {elapsed*1000:.2f}ms")

        # Should be fast (< 200ms - adjusted for SQLite)
        assert elapsed < 0.2

    def test_presence_log_query_performance(
        self,
        db_session,
        test_attendance_record
    ):
        """
        Test presence log query performance

        Creates 1000 presence logs and queries them.
        """
        from app.repositories.attendance_repository import AttendanceRepository

        repo = AttendanceRepository(db_session)

        # Create 1000 presence logs
        for i in range(1000):
            repo.log_presence(str(test_attendance_record.id), {
                "scan_number": i,
                "scan_time": datetime.now(),
                "detected": i % 2 == 0,
                "confidence": 0.85 if i % 2 == 0 else None
            })

        # Query performance test
        start_time = time.time()

        logs = repo.get_recent_logs(str(test_attendance_record.id), limit=100)

        elapsed = time.time() - start_time

        assert len(logs) == 100
        print(f"\nQueried 100 recent logs from 1000 total in {elapsed*1000:.2f}ms")

        # Should be fast (< 50ms)
        assert elapsed < 0.05


class TestSessionScalability:
    """Test system with multiple concurrent sessions"""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_sessions(
        self,
        db_session,
        test_faculty,
        test_room
    ):
        """
        Test system with 10 concurrent active sessions

        Simulates 10 different classes happening simultaneously.
        """
        from app.services.presence_service import PresenceService
        from app.models.schedule import Schedule
        from app.models.user import User, UserRole
        from app.models.enrollment import Enrollment
        from app.utils.security import hash_password
        import uuid

        presence_service = PresenceService(db_session)

        # Create 10 schedules
        schedules = []
        for i in range(10):
            schedule = Schedule(
                id=uuid.uuid4(),
                subject_code=f"SUBJ{i:03d}",
                subject_name=f"Subject {i}",
                faculty_id=test_faculty.id,
                room_id=test_room.id,
                day_of_week=0,
                start_time=datetime.now().time(),
                end_time=(datetime.now() + timedelta(hours=2)).time(),
                semester="1st",
                academic_year="2024-2025",
                is_active=True
            )
            db_session.add(schedule)
            schedules.append(schedule)

        db_session.commit()

        # Create 5 students per schedule
        for schedule in schedules:
            for j in range(5):
                student = User(
                    id=uuid.uuid4(),
                    email=f"s{schedule.subject_code}_{j}@test.edu",
                    password_hash=hash_password("pass"),
                    role=UserRole.STUDENT,
                    first_name=f"Student{j}",
                    last_name="Test",
                    student_id=f"S-{schedule.subject_code}-{j}",
                    is_active=True
                )
                db_session.add(student)

                enrollment = Enrollment(
                    id=uuid.uuid4(),
                    student_id=student.id,
                    schedule_id=schedule.id
                )
                db_session.add(enrollment)

        db_session.commit()

        # Start all sessions
        start_time = time.time()

        for schedule in schedules:
            await presence_service.start_session(str(schedule.id))

        elapsed = time.time() - start_time

        print(f"\nStarted 10 sessions (50 students) in {elapsed:.2f} seconds")

        # Check all sessions are active
        assert len(presence_service.get_active_sessions()) == 10

        # End all sessions
        for schedule in schedules:
            await presence_service.end_session(str(schedule.id))

        assert len(presence_service.get_active_sessions()) == 0


class TestFAISSIndexPerformance:
    """Test FAISS index performance with many registrations"""

    def test_faiss_search_performance_1000_embeddings(self):
        """
        Test FAISS search performance with 1000 registered faces

        This simulates a large institution with many registered users.
        """
        from app.services.ml.faiss_manager import FAISSManager

        faiss_manager = FAISSManager()

        # Add 1000 embeddings
        embeddings = []
        for i in range(1000):
            emb = np.random.randn(512).astype(np.float32)
            emb = emb / np.linalg.norm(emb)
            embeddings.append((emb, f"user-{i}"))

        faiss_manager.rebuild(embeddings)

        # Test search performance
        query_embedding = np.random.randn(512).astype(np.float32)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)

        # 100 searches
        start_time = time.time()

        for i in range(100):
            results = faiss_manager.search(query_embedding, k=1)

        elapsed = time.time() - start_time

        print(f"\n100 FAISS searches against 1000 embeddings in {elapsed:.2f} seconds")
        print(f"Average: {elapsed/100*1000:.2f}ms per search")

        # Should be very fast (< 1 second total)
        assert elapsed < 1.0


class TestMemoryUsage:
    """Test memory usage under load"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="psutil not in requirements - optional performance test")
    async def test_session_memory_leak(
        self,
        db_session,
        test_schedule,
        test_student,
        test_enrollment
    ):
        """
        Test for memory leaks in session management

        Starts and ends sessions repeatedly to check for leaks.
        NOTE: Requires psutil (not in requirements.txt)
        """
        from app.services.presence_service import PresenceService
        import psutil
        import os

        presence_service = PresenceService(db_session)

        # Get initial memory
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Start and end session 50 times
        for i in range(50):
            await presence_service.start_session(str(test_schedule.id))
            await presence_service.end_session(str(test_schedule.id))

        # Get final memory
        final_memory = process.memory_info().rss / 1024 / 1024  # MB

        memory_increase = final_memory - initial_memory

        print(f"\nMemory usage:")
        print(f"Initial: {initial_memory:.2f} MB")
        print(f"Final: {final_memory:.2f} MB")
        print(f"Increase: {memory_increase:.2f} MB")

        # Memory increase should be minimal (< 50 MB)
        # This is a loose check as Python's GC is non-deterministic
        assert memory_increase < 50


class TestRateLimiting:
    """Test system behavior under rate limiting scenarios"""

    def test_rapid_edge_requests(
        self,
        client,
        test_room,
        test_face_image_base64
    ):
        """
        Test 100 rapid requests to Edge API

        Verifies system handles burst traffic.
        """
        with patch('app.routers.face.FaceService') as mock_service:
            service_instance = MagicMock()
            service_instance.facenet.decode_base64_image = MagicMock(
                return_value=MagicMock()
            )

            async def mock_recognize(img_bytes, threshold=None):
                return "user-burst", 0.85

            service_instance.recognize_face = AsyncMock(side_effect=mock_recognize)
            mock_service.return_value = service_instance

            with patch('app.routers.face.PresenceService'):
                payload = {
                    "room_id": str(test_room.id),
                    "timestamp": datetime.utcnow().isoformat(),
                    "faces": [{"image": test_face_image_base64}]
                }

                # Send 100 rapid requests
                start_time = time.time()

                success_count = 0
                for i in range(100):
                    response = client.post(f"{API}/face/process", json=payload)
                    if response.status_code == 200:
                        success_count += 1

                elapsed = time.time() - start_time

                print(f"\n100 requests in {elapsed:.2f} seconds")
                print(f"{success_count} successful")

                # Most should succeed (allowing for some rate limiting)
                assert success_count >= 90
