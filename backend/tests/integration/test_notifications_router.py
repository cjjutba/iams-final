"""
Integration tests for the notifications router.

Tests cover all 4 endpoints:
- GET /notifications/ (list with filtering)
- PATCH /notifications/{id}/read (mark single as read)
- POST /notifications/read-all (mark all as read)
- GET /notifications/unread-count (count unread)
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.config import settings
from app.models.notification import Notification

API = settings.API_PREFIX


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_notification(db_session, test_student):
    """Create a single unread notification owned by test_student."""
    notif = Notification(
        id=uuid.uuid4(),
        user_id=test_student.id,
        title="Test Notification",
        message="Test message",
        type="system",
        read=False,
    )
    db_session.add(notif)
    db_session.commit()
    db_session.refresh(notif)
    return notif


@pytest.fixture()
def multiple_notifications(db_session, test_student):
    """Create a mix of read and unread notifications for test_student."""
    notifications = []
    for i in range(5):
        notif = Notification(
            id=uuid.uuid4(),
            user_id=test_student.id,
            title=f"Notification {i}",
            message=f"Message {i}",
            type="system" if i % 2 == 0 else "attendance",
            read=(i < 2),  # first 2 are read, last 3 are unread
        )
        if notif.read:
            notif.read_at = datetime.now(timezone.utc)
        db_session.add(notif)
        notifications.append(notif)
    db_session.commit()
    for n in notifications:
        db_session.refresh(n)
    return notifications


@pytest.fixture()
def faculty_notification(db_session, test_faculty):
    """Create an unread notification owned by test_faculty."""
    notif = Notification(
        id=uuid.uuid4(),
        user_id=test_faculty.id,
        title="Faculty Notification",
        message="Faculty message",
        type="system",
        read=False,
    )
    db_session.add(notif)
    db_session.commit()
    db_session.refresh(notif)
    return notif


# ---------------------------------------------------------------------------
# GET /notifications/ - List notifications
# ---------------------------------------------------------------------------

class TestGetNotifications:
    """Tests for the list notifications endpoint."""

    def test_get_notifications_success(
        self, client, auth_headers_student, multiple_notifications
    ):
        """Authenticated user receives their notifications."""
        response = client.get(
            f"{API}/notifications/",
            headers=auth_headers_student,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 5

    def test_get_notifications_unread_only(
        self, client, auth_headers_student, multiple_notifications
    ):
        """When unread_only=true, only unread notifications are returned."""
        response = client.get(
            f"{API}/notifications/",
            headers=auth_headers_student,
            params={"unread_only": True},
        )
        assert response.status_code == 200
        data = response.json()
        # 3 out of 5 notifications are unread
        assert len(data) == 3
        for notif in data:
            assert notif["read"] is False

    def test_get_notifications_empty_list(
        self, client, auth_headers_student
    ):
        """User with no notifications gets an empty list."""
        response = client.get(
            f"{API}/notifications/",
            headers=auth_headers_student,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_notifications_pagination(
        self, client, auth_headers_student, multiple_notifications
    ):
        """Pagination via skip and limit returns the correct subset."""
        response = client.get(
            f"{API}/notifications/",
            headers=auth_headers_student,
            params={"skip": 2, "limit": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_notifications_unauthenticated(self, client):
        """Request without auth token returns 401."""
        response = client.get(f"{API}/notifications/")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /notifications/{id}/read - Mark notification as read
# ---------------------------------------------------------------------------

class TestMarkNotificationRead:
    """Tests for marking a single notification as read."""

    def test_mark_notification_read_success(
        self, client, auth_headers_student, test_notification
    ):
        """Owner can mark their own notification as read."""
        notif_id = str(test_notification.id)
        response = client.patch(
            f"{API}/notifications/{notif_id}/read",
            headers=auth_headers_student,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == notif_id
        assert data["read"] is True
        assert data["read_at"] is not None

    def test_mark_notification_read_not_found(
        self, client, auth_headers_student
    ):
        """Marking a non-existent notification returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.patch(
            f"{API}/notifications/{fake_id}/read",
            headers=auth_headers_student,
        )
        assert response.status_code == 404

    def test_mark_notification_read_wrong_user(
        self, client, auth_headers_student, faculty_notification
    ):
        """Student cannot mark faculty's notification as read (403)."""
        notif_id = str(faculty_notification.id)
        response = client.patch(
            f"{API}/notifications/{notif_id}/read",
            headers=auth_headers_student,
        )
        assert response.status_code == 403
        data = response.json()
        assert "denied" in data["detail"].lower() or "access" in data["detail"].lower()


# ---------------------------------------------------------------------------
# POST /notifications/read-all - Mark all as read
# ---------------------------------------------------------------------------

class TestMarkAllRead:
    """Tests for marking all notifications as read."""

    def test_mark_all_read_success(
        self, client, auth_headers_student, multiple_notifications
    ):
        """Marks all unread notifications as read and returns count."""
        response = client.post(
            f"{API}/notifications/read-all",
            headers=auth_headers_student,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # 3 unread notifications should be marked
        assert "3" in data["message"]

        # Verify all are now read
        list_response = client.get(
            f"{API}/notifications/",
            headers=auth_headers_student,
            params={"unread_only": True},
        )
        assert list_response.status_code == 200
        assert len(list_response.json()) == 0

    def test_mark_all_read_returns_count(
        self, client, auth_headers_student, test_notification
    ):
        """Returns correct count when only one unread notification exists."""
        response = client.post(
            f"{API}/notifications/read-all",
            headers=auth_headers_student,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "1" in data["message"]


# ---------------------------------------------------------------------------
# GET /notifications/unread-count - Get unread count
# ---------------------------------------------------------------------------

class TestGetUnreadCount:
    """Tests for the unread count endpoint."""

    def test_unread_count_with_notifications(
        self, client, auth_headers_student, multiple_notifications
    ):
        """Returns correct unread count when unread notifications exist."""
        response = client.get(
            f"{API}/notifications/unread-count",
            headers=auth_headers_student,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["unread_count"] == 3

    def test_unread_count_zero(
        self, client, auth_headers_student
    ):
        """Returns zero when user has no notifications."""
        response = client.get(
            f"{API}/notifications/unread-count",
            headers=auth_headers_student,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["unread_count"] == 0
