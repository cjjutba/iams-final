"""
Integration Tests for Health and Root Endpoints

Verifies that the system health check and root endpoints respond
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

    def test_health_check_status_healthy(self, client):
        """Response body should include status = 'healthy'."""
        response = client.get(f"{API}/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_check_contains_app_name(self, client):
        """Response should include the application name."""
        response = client.get(f"{API}/health")
        data = response.json()
        assert data["app"] == settings.APP_NAME

    def test_health_check_contains_version(self, client):
        """Response should include a version string."""
        response = client.get(f"{API}/health")
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_health_check_contains_debug_flag(self, client):
        """Response should include the debug flag."""
        response = client.get(f"{API}/health")
        data = response.json()
        assert "debug" in data
        assert isinstance(data["debug"], bool)


class TestRootEndpoint:
    """Tests for GET /."""

    def test_root_endpoint_returns_200(self, client):
        """Root endpoint should return HTTP 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_endpoint_has_message(self, client):
        """Root response should contain a descriptive message."""
        response = client.get("/")
        data = response.json()
        assert "message" in data
        assert settings.APP_NAME in data["message"]

    def test_root_endpoint_has_docs_link(self, client):
        """Root response should include a docs URL."""
        response = client.get("/")
        data = response.json()
        assert "docs" in data
        assert "/docs" in data["docs"]
