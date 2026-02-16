"""
Supabase Admin Client (httpx-based)

Lightweight helper for Supabase Auth admin operations using httpx.
Replaces the full supabase-py SDK to avoid heavy transitive dependencies
(storage3 → pyiceberg → Rust compiler) that break on Windows.

Only the GoTrue Admin API endpoints we actually use are implemented:
- create_user: POST /auth/v1/admin/users
- update_user: PUT /auth/v1/admin/users/{id}
- get_user:    GET /auth/v1/admin/users/{id}
"""

from typing import Optional
import httpx

from app.config import settings, logger


class SupabaseAdminAuth:
    """Thin wrapper around GoTrue Admin REST API via httpx."""

    def __init__(self, url: str, service_key: str, anon_key: str):
        self.base_url = f"{url}/auth/v1"
        self.headers = {
            "apikey": anon_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }

    def create_user(self, params: dict) -> dict:
        """
        Create a user via the Admin API.

        Args:
            params: dict with email, password, email_confirm, user_metadata, etc.

        Returns:
            The created user object from Supabase.

        Raises:
            RuntimeError on failure.
        """
        response = httpx.post(
            f"{self.base_url}/admin/users",
            json=params,
            headers=self.headers,
            timeout=15.0,
        )

        if response.status_code >= 400:
            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            msg = body.get("msg") or body.get("message") or body.get("error_description") or response.text
            raise RuntimeError(msg)

        return response.json()

    def update_user_by_id(self, user_id: str, params: dict) -> dict:
        """
        Update a user by ID via the Admin API.

        Args:
            user_id: Supabase Auth user UUID.
            params: dict with fields to update (e.g. {"password": "new"}).

        Returns:
            The updated user object.

        Raises:
            RuntimeError on failure.
        """
        response = httpx.put(
            f"{self.base_url}/admin/users/{user_id}",
            json=params,
            headers=self.headers,
            timeout=15.0,
        )

        if response.status_code >= 400:
            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            msg = body.get("msg") or body.get("message") or body.get("error_description") or response.text
            raise RuntimeError(msg)

        return response.json()

    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """
        Get a user by ID via the Admin API.

        Returns:
            User dict or None if not found.
        """
        response = httpx.get(
            f"{self.base_url}/admin/users/{user_id}",
            headers=self.headers,
            timeout=10.0,
        )

        if response.status_code == 200:
            return response.json()
        return None


class SupabaseAdmin:
    """Singleton providing a lightweight Supabase Auth admin client."""

    _instance: Optional[SupabaseAdminAuth] = None

    @classmethod
    def get_client(cls) -> SupabaseAdminAuth:
        """Return (and lazily create) the admin auth client."""
        if cls._instance is None:
            if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
                raise RuntimeError(
                    "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set "
                    "to use Supabase Auth features"
                )
            cls._instance = SupabaseAdminAuth(
                url=settings.SUPABASE_URL,
                service_key=settings.SUPABASE_SERVICE_KEY,
                anon_key=settings.SUPABASE_ANON_KEY,
            )
            logger.info("Supabase admin client initialized (httpx)")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the client (useful for testing)."""
        cls._instance = None


def get_supabase_admin() -> SupabaseAdminAuth:
    """Get the Supabase admin client singleton."""
    return SupabaseAdmin.get_client()
