# backend/tests/integration/test_webrtc_router.py
"""Integration tests for the WebRTC router."""
import uuid as uuid_mod
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Local fixtures — thin aliases over shared conftest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_headers(auth_headers_faculty):
    """Auth headers for the faculty user (owns test_schedule)."""
    return auth_headers_faculty


@pytest.fixture()
def sample_schedule(test_schedule):
    """A persisted schedule owned by the faculty user."""
    return test_schedule


_NONEXISTENT_UUID = "00000000-0000-0000-0000-000000000000"


class TestGetWebRTCConfig:
    def test_returns_ice_servers(self, client):
        with patch("app.routers.webrtc.webrtc_service") as mock_svc:
            mock_svc.get_ice_servers.return_value = [
                {"urls": ["stun:stun.l.google.com:19302"]}
            ]
            resp = client.get("/api/v1/webrtc/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["data"]["ice_servers"]) >= 1
        assert "urls" in data["data"]["ice_servers"][0]


class TestWebRTCOffer:
    def test_requires_auth(self, client):
        resp = client.post(
            f"/api/v1/webrtc/{_NONEXISTENT_UUID}/offer",
            json={"sdp": "v=0\r\n", "type": "offer"},
        )
        assert resp.status_code == 401

    def test_invalid_uuid_returns_422(self, client, auth_headers):
        """Non-UUID path param is rejected before reaching the handler."""
        resp = client.post(
            "/api/v1/webrtc/not-a-uuid/offer",
            json={"sdp": "v=0\r\n", "type": "offer"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_returns_404_for_unknown_schedule(self, client, auth_headers):
        """A valid UUID that maps to no schedule returns 404."""
        with patch("app.routers.webrtc.ScheduleRepository") as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_id.return_value = None
            resp = client.post(
                f"/api/v1/webrtc/{_NONEXISTENT_UUID}/offer",
                json={"sdp": "v=0\r\n", "type": "offer"},
                headers=auth_headers,
            )
        assert resp.status_code == 404

    def test_faculty_cannot_access_another_facultys_schedule(
        self, client, auth_headers, sample_schedule
    ):
        """Faculty can only stream their own schedules."""
        other_faculty_schedule = MagicMock()
        other_faculty_schedule.id = sample_schedule.id
        other_faculty_schedule.room_id = sample_schedule.room_id
        other_faculty_schedule.faculty_id = uuid_mod.uuid4()  # different faculty
        with patch("app.routers.webrtc.ScheduleRepository") as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_id.return_value = other_faculty_schedule
            resp = client.post(
                f"/api/v1/webrtc/{sample_schedule.id}/offer",
                json={"sdp": "v=0\r\n", "type": "offer"},
                headers=auth_headers,
            )
        assert resp.status_code == 403

    def test_student_not_enrolled_cannot_access(
        self, client, auth_headers_student, sample_schedule
    ):
        """A student not enrolled in the schedule cannot stream it."""
        with patch("app.routers.webrtc.ScheduleRepository") as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_id.return_value = sample_schedule
            resp = client.post(
                f"/api/v1/webrtc/{sample_schedule.id}/offer",
                json={"sdp": "v=0\r\n", "type": "offer"},
                headers=auth_headers_student,
            )
        assert resp.status_code == 403

    def test_returns_503_when_no_camera_and_no_push(self, client, auth_headers, sample_schedule):
        """When rtsp_url is None (push mode) and edge device isn't streaming, return 503."""
        with patch("app.routers.webrtc.ScheduleRepository") as mock_repo_cls, \
             patch("app.routers.webrtc.get_camera_url", return_value=None), \
             patch("app.routers.webrtc.webrtc_service") as mock_svc:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_id.return_value = sample_schedule
            mock_svc.check_path_exists = AsyncMock(return_value=False)
            resp = client.post(
                f"/api/v1/webrtc/{sample_schedule.id}/offer",
                json={"sdp": "v=0\r\n", "type": "offer"},
                headers=auth_headers,
            )
        assert resp.status_code == 503
        assert "edge device" in resp.json()["detail"].lower()

    def test_returns_503_when_mediamtx_down(self, client, auth_headers, sample_schedule):
        with patch("app.routers.webrtc.ScheduleRepository") as mock_repo_cls, \
             patch("app.routers.webrtc.get_camera_url", return_value="rtsp://cam/stream"), \
             patch("app.routers.webrtc.webrtc_service") as mock_svc:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_id.return_value = sample_schedule
            mock_svc.ensure_path = AsyncMock(return_value=False)
            resp = client.post(
                f"/api/v1/webrtc/{sample_schedule.id}/offer",
                json={"sdp": "v=0\r\n", "type": "offer"},
                headers=auth_headers,
            )
        assert resp.status_code == 503
        assert "webrtc" in resp.json()["detail"].lower()

    def test_returns_sdp_answer_on_success(self, client, auth_headers, sample_schedule):
        fake_answer = "v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\n"
        with patch("app.routers.webrtc.ScheduleRepository") as mock_repo_cls, \
             patch("app.routers.webrtc.get_camera_url", return_value="rtsp://cam/stream"), \
             patch("app.routers.webrtc.webrtc_service") as mock_svc:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_id.return_value = sample_schedule
            mock_svc.ensure_path = AsyncMock(return_value=True)
            mock_svc.forward_whep_offer = AsyncMock(return_value=(fake_answer, "/session/x"))
            resp = client.post(
                f"/api/v1/webrtc/{sample_schedule.id}/offer",
                json={"sdp": "v=0\r\n", "type": "offer"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["type"] == "answer"
        assert "v=0" in body["data"]["sdp"]

    def test_oversized_sdp_returns_422(self, client, auth_headers, sample_schedule):
        """SDP exceeding 64 KB is rejected before reaching the handler."""
        huge_sdp = "v=0\r\n" + "a=" + "x" * 70_000
        resp = client.post(
            f"/api/v1/webrtc/{sample_schedule.id}/offer",
            json={"sdp": huge_sdp, "type": "offer"},
            headers=auth_headers,
        )
        assert resp.status_code == 422
