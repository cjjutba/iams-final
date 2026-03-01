# backend/tests/integration/test_webrtc_router.py
"""Integration tests for the WebRTC router."""
import pytest
from unittest.mock import patch, AsyncMock


# ---------------------------------------------------------------------------
# The test_app and auth_headers fixtures are local aliases that delegate to
# the shared fixtures already defined in tests/conftest.py so all tests in
# this file read naturally against the task specification.
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_headers(auth_headers_faculty):
    """Auth headers for any authenticated user (reuse faculty fixture)."""
    return auth_headers_faculty


@pytest.fixture()
def sample_schedule(test_schedule):
    """A persisted schedule (reuse the shared test_schedule fixture)."""
    return test_schedule


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
        resp = client.post("/api/v1/webrtc/some-schedule-id/offer",
                           json={"sdp": "v=0\r\n", "type": "offer"})
        assert resp.status_code == 401

    def test_returns_404_for_unknown_schedule(self, client, auth_headers):
        with patch("app.routers.webrtc.ScheduleRepository") as mock_repo_cls:
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_id.return_value = None
            resp = client.post(
                "/api/v1/webrtc/nonexistent-schedule/offer",
                json={"sdp": "v=0\r\n", "type": "offer"},
                headers=auth_headers,
            )
        assert resp.status_code == 404

    def test_returns_503_when_no_camera(self, client, auth_headers, sample_schedule):
        with patch("app.routers.webrtc.ScheduleRepository") as mock_repo_cls, \
             patch("app.routers.webrtc.get_camera_url", return_value=None):
            mock_repo = mock_repo_cls.return_value
            mock_repo.get_by_id.return_value = sample_schedule
            resp = client.post(
                f"/api/v1/webrtc/{sample_schedule.id}/offer",
                json={"sdp": "v=0\r\n", "type": "offer"},
                headers=auth_headers,
            )
        assert resp.status_code == 503
        assert "camera" in resp.json()["detail"].lower()

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
