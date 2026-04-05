"""
Integration Tests for Health Endpoint

Verifies that the system health check endpoint responds
correctly through the full FastAPI stack.
"""

import pytest

from app.config import settings


API = settings.API_PREFIX


class TestHealthEndpoint:
    """Tests for GET /api/v1/health."""

    def test_health_check_returns_200(self, client):
        """Health check should return HTTP 200."""
        response = client.get(f"{API}/health")
        assert response.status_code == 200

    def test_health_check_has_status(self, client):
        """Response body should include a status field."""
        response = client.get(f"{API}/health")
        data = response.json()
        assert "status" in data
        assert data["status"] in ("healthy", "unhealthy")

    def test_health_check_has_role(self, client):
        """Response should include the service role."""
        response = client.get(f"{API}/health")
        data = response.json()
        assert "role" in data

    def test_health_check_has_uptime(self, client):
        """Response should include uptime_seconds."""
        response = client.get(f"{API}/health")
        data = response.json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], int)

    def test_health_check_has_components(self, client):
        """Response should include component health details."""
        response = client.get(f"{API}/health")
        data = response.json()
        assert "components" in data
        assert "database" in data["components"]
