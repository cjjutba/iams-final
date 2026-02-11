"""
Supabase Admin Client

Singleton service for Supabase Auth administration.
Uses the service role key for server-side operations like:
- Creating users with admin privileges
- Generating email verification / password reset links
- Managing user accounts
"""

from typing import Optional
from supabase import create_client, Client

from app.config import settings, logger


class SupabaseAdmin:
    """Singleton wrapper around the Supabase admin client."""

    _client: Optional[Client] = None

    @classmethod
    def get_client(cls) -> Client:
        """Return (and lazily create) the Supabase admin client."""
        if cls._client is None:
            if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
                raise RuntimeError(
                    "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set "
                    "to use Supabase Auth features"
                )
            cls._client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_KEY,
            )
            logger.info("Supabase admin client initialized")
        return cls._client

    @classmethod
    def reset(cls) -> None:
        """Reset the client (useful for testing)."""
        cls._client = None


def get_supabase_admin() -> Client:
    """FastAPI dependency to obtain the Supabase admin client."""
    return SupabaseAdmin.get_client()
