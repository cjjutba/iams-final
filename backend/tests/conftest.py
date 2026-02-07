"""
Shared Test Fixtures for IAMS Backend

Provides database sessions, test client, user fixtures, and auth helpers.
Uses SQLite in-memory database with UUID compatibility workarounds.
"""

import os
import uuid
from datetime import datetime, time
from unittest.mock import patch, MagicMock

import pytest

# ============================================================
# Environment variable overrides MUST happen before any app
# imports, because app.config.Settings reads from env at import
# time and app.database creates the SQLAlchemy engine eagerly.
# ============================================================
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key-for-testing-only")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-32chars!!")
os.environ.setdefault("DEBUG", "false")

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


@pytest.fixture(scope="function")
def db_session():
    """
    Provide a clean database session for each test.

    Creates all tables before the test and drops them afterward to ensure
    full isolation between tests.
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
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
                 is_active=True):
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
    """Create a test schedule in the database (requires faculty and room)."""
    from app.models.schedule import Schedule

    schedule = Schedule(
        id=uuid.uuid4(),
        subject_code="CPE301",
        subject_name="Microprocessors",
        faculty_id=test_faculty.id,
        room_id=test_room.id,
        day_of_week=0,  # Monday
        start_time=time(8, 0),
        end_time=time(10, 0),
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
