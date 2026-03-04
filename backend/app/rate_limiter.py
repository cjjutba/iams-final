"""
Rate Limiter Module

Provides a shared SlowAPI limiter instance, separated from main.py
to avoid circular imports when routers need to apply rate limiting.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.RATE_LIMIT_ENABLED,
)
