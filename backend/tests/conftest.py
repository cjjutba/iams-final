"""
Shared Test Fixtures for IAMS Backend

Provides database sessions, test client, user fixtures, and auth helpers.
Uses SQLite in-memory database with UUID compatibility workarounds.
"""

import os
import uuid
from datetime import datetime, time, date
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

# ============================================================
# Environment variable overrides MUST happen before any app
# imports, because app.config.Settings reads from env at import
# time and app.database creates the SQLAlchemy engine eagerly.
# ============================================================
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key-for-testing-only")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key-for-testing-only")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-32chars!!")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("USE_SUPABASE_AUTH", "false")
os.environ.setdefault("SUPABASE_WEBHOOK_SECRET", "test-webhook-secret-for-testing")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.config import settings

# Import all models so they register with Base.metadata BEFORE create_all()
import app.models  # noqa: F401

# ---------------------------------------------------------------------------
# SQLite in-memory engine for tests
# ---------------------------------------------------------------------------
# PostgreSQL UUID columns work transparently with SQLite when we register a
# type adapter.  SQLAlchemy's UUID type falls back to CHAR(32) on non-PG
# dialects automatically in SQLAlchemy 2.x.
# ---------------------------------------------------------------------------
SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ---------------------------------------------------------------------------
# Core Fixtures
# ---------------------------------------------------------------------------

# Student IDs that must exist in student_records for registration/verify tests
_TEST_STUDENT_IDS = [
    "STU-2024-001",
    "STU-2024-100", "STU-2024-101", "STU-2024-102", "STU-2024-103",
    "STU-2024-104", "STU-2024-105", "STU-2024-106",
    "STU-LOGIN-001", "STU-LOGIN-002", "STU-LOGIN-003",
    "STU-REFRESH-001",
]


def _seed_test_student_records(session):
    """
    Seed student_records with all test IDs so verify_student_id() can
    find them in the reference table during registration tests.
    """
    from app.models.student_record import StudentRecord

    for i, sid in enumerate(_TEST_STUDENT_IDS):
        session.add(StudentRecord(
            student_id=sid,
            first_name="Test",
            last_name=f"Student{i + 1}",
            email=f"teststudent{i + 1}@test.jrmsu.edu.ph",
            course="BSCPE",
            year_level=1,
            section="A",
            is_active=True,
        ))
    session.commit()


@pytest.fixture(scope="function")
def db_session():
    """
    Provide a clean database session for each test.

    Creates all tables before the test, seeds student_records with test IDs,
    then drops everything afterward to ensure full isolation between tests.
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    _seed_test_student_records(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    Provide a FastAPI TestClient that uses the test database session.

    Overrides the ``get_db`` dependency so every request executed through
    this client uses the in-memory SQLite session instead of the real
    PostgreSQL database.

    The heavy startup operations (FaceNet model loading, FAISS index,
    APScheduler, and the real DB connection check) are mocked out so that
    the test client starts quickly without requiring ML models or a
    PostgreSQL server.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    # The startup event does several things wrapped in try/except:
    #   1. check_db_connection() -- would try the real PG URL; patch it.
    #   2. FaceNet/FAISS loading -- in try/except, so failures are logged and
    #      the app keeps running.  We do NOT need to patch these.
    #   3. APScheduler setup -- in try/except.  We patch the scheduler to
    #      prevent it from actually running background jobs.
    # The shutdown event also tries to save FAISS and stop the scheduler,
    # but those are similarly wrapped in try/except.
    with patch("app.main.check_db_connection", return_value=True), \
         patch("app.main.scheduler") as mock_scheduler:
        mock_scheduler.running = False
        mock_scheduler.start = MagicMock()
        mock_scheduler.shutdown = MagicMock()
        mock_scheduler.add_job = MagicMock()

        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# User factory helpers
# ---------------------------------------------------------------------------

def _create_user(db_session, *, role, email, first_name, last_name,
                 student_id=None, password="TestPass123",
                 is_active=True, email_verified=True):
    """
    Helper to insert a User row directly into the test database.

    Returns the created User ORM instance.
    """
    from app.models.user import User, UserRole
    from app.utils.security import hash_password

    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(password),
        role=role,
        first_name=first_name,
        last_name=last_name,
        student_id=student_id,
        is_active=is_active,
        email_verified=email_verified,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def test_student(db_session):
    """Create a test student user in the database."""
    from app.models.user import UserRole
    return _create_user(
        db_session,
        role=UserRole.STUDENT,
        email="student@test.jrmsu.edu.ph",
        first_name="Juan",
        last_name="Dela Cruz",
        student_id="STU-2024-001",
    )


@pytest.fixture()
def test_faculty(db_session):
    """Create a test faculty user in the database."""
    from app.models.user import UserRole
    return _create_user(
        db_session,
        role=UserRole.FACULTY,
        email="faculty@test.jrmsu.edu.ph",
        first_name="Maria",
        last_name="Santos",
    )


@pytest.fixture()
def test_admin(db_session):
    """Create a test admin user in the database."""
    from app.models.user import UserRole
    return _create_user(
        db_session,
        role=UserRole.ADMIN,
        email="admin@test.jrmsu.edu.ph",
        first_name="Admin",
        last_name="User",
    )


@pytest.fixture()
def inactive_student(db_session):
    """Create an inactive student user in the database."""
    from app.models.user import UserRole
    return _create_user(
        db_session,
        role=UserRole.STUDENT,
        email="inactive@test.jrmsu.edu.ph",
        first_name="Inactive",
        last_name="Student",
        student_id="STU-2024-999",
        is_active=False,
    )


@pytest.fixture()
def test_room(db_session):
    """Create a test room in the database."""
    from app.models.room import Room

    room = Room(
        id=uuid.uuid4(),
        name="Room 101",
        building="Engineering Building",
        capacity=40,
        camera_endpoint="http://192.168.1.100:5000",
        is_active=True,
    )
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


@pytest.fixture()
def test_schedule(db_session, test_faculty, test_room):
    """Create a test schedule in the database (requires faculty and room).

    Uses current time as start_time to ensure tests run within grace period.
    """
    from app.models.schedule import Schedule
    from datetime import datetime

    # Use current time as start, ensuring tests are within grace period
    now = datetime.now()
    current_time = now.time()

    # End time is 2 hours later
    end_hour = (now.hour + 2) % 24
    end_time_obj = time(end_hour, now.minute)

    schedule = Schedule(
        id=uuid.uuid4(),
        subject_code="CPE301",
        subject_name="Microprocessors",
        faculty_id=test_faculty.id,
        room_id=test_room.id,
        day_of_week=now.weekday(),  # Current day of week
        start_time=current_time,
        end_time=end_time_obj,
        semester="1st",
        academic_year="2024-2025",
        is_active=True,
    )
    db_session.add(schedule)
    db_session.commit()
    db_session.refresh(schedule)
    return schedule


# ---------------------------------------------------------------------------
# Auth header helpers
# ---------------------------------------------------------------------------

def _make_auth_headers(user):
    """Generate an Authorization header dict with a valid JWT for *user*."""
    from app.utils.security import create_access_token
    token = create_access_token({"user_id": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_headers_student(test_student):
    """Authorization headers for the test student."""
    return _make_auth_headers(test_student)


@pytest.fixture()
def auth_headers_faculty(test_faculty):
    """Authorization headers for the test faculty."""
    return _make_auth_headers(test_faculty)


@pytest.fixture()
def auth_headers_admin(test_admin):
    """Authorization headers for the test admin."""
    return _make_auth_headers(test_admin)


# ---------------------------------------------------------------------------
# Integration test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_enrollment(db_session, test_student, test_schedule):
    """Create a test enrollment linking student to schedule."""
    from app.models.enrollment import Enrollment

    enrollment = Enrollment(
        id=uuid.uuid4(),
        student_id=test_student.id,
        schedule_id=test_schedule.id,
        enrolled_at=datetime.utcnow()
    )
    db_session.add(enrollment)
    db_session.commit()
    db_session.refresh(enrollment)
    return enrollment


@pytest.fixture()
def test_face_image_base64():
    """Generate a simple test image as Base64 for face processing tests."""
    from PIL import Image
    import base64
    import io

    # Create a simple 112x112 test image
    img = Image.new('RGB', (112, 112), color='blue')

    # Convert to Base64
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes = img_bytes.getvalue()

    return base64.b64encode(img_bytes).decode('utf-8')


@pytest.fixture()
def mock_facenet():
    """Mock FaceNet model for face recognition tests."""
    from unittest.mock import MagicMock, patch
    import numpy as np

    mock = MagicMock()

    # Mock generate_embedding to return a random 512-dim vector
    def mock_generate_embedding(image_bytes):
        embedding = np.random.randn(512).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)  # L2 normalize
        return embedding

    mock.generate_embedding = mock_generate_embedding
    mock.decode_base64_image = MagicMock(return_value=Image.new('RGB', (112, 112)))

    return mock


@pytest.fixture()
def mock_faiss():
    """Mock FAISS manager for face search tests."""
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.add = MagicMock(return_value=1)  # Return FAISS ID
    mock.search = MagicMock(return_value=[])  # Empty by default
    mock.save = MagicMock()
    mock.user_map = {}

    return mock


@pytest.fixture()
def test_attendance_record(db_session, test_student, test_schedule):
    """Create a test attendance record."""
    from app.models.attendance_record import AttendanceRecord, AttendanceStatus

    record = AttendanceRecord(
        id=uuid.uuid4(),
        student_id=test_student.id,
        schedule_id=test_schedule.id,
        date=date.today(),
        status=AttendanceStatus.ABSENT,
        total_scans=0,
        scans_present=0,
        presence_score=0.0
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


@pytest.fixture()
def mock_ws_manager():
    """Mock WebSocket manager for notification tests."""
    from unittest.mock import AsyncMock, MagicMock

    mock = MagicMock()
    mock.broadcast = AsyncMock()
    mock.send_to_user = AsyncMock()
    mock.send_to_role = AsyncMock()

    return mock


@pytest.fixture()
def mock_face_service():
    """Mock FaceService for testing face recognition flows."""
    from unittest.mock import AsyncMock, MagicMock
    import numpy as np

    mock = MagicMock()

    # Mock recognize_face to return None (no match) by default
    async def mock_recognize(image_bytes):
        return (None, None)

    mock.recognize_face = AsyncMock(side_effect=mock_recognize)

    # Mock register_face
    async def mock_register(user_id, images):
        return {"embedding_id": 1, "message": "Face registered successfully"}

    mock.register_face = AsyncMock(side_effect=mock_register)

    # Mock get_face_status
    mock.get_face_status = MagicMock(return_value={
        "registered": False,
        "registered_at": None,
        "embedding_id": None
    })

    return mock
