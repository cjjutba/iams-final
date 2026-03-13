"""
Session Manager

Shared state for active presence tracking sessions.
This module provides a global registry of active sessions that can be accessed
by both the APScheduler background tasks and API routers.
"""

from datetime import datetime

# Global registry of active sessions
# Key: schedule_id (UUID string)
# Value: dict with session metadata (start_time, scan_count, etc.)
_active_sessions: dict[str, dict] = {}


def register_session(schedule_id: str, metadata: dict = None):
    """
    Register an active session

    Args:
        schedule_id: Schedule UUID
        metadata: Optional session metadata
    """
    _active_sessions[schedule_id] = {"started_at": datetime.now(), "scan_count": 0, **(metadata or {})}


def unregister_session(schedule_id: str):
    """
    Unregister an active session

    Args:
        schedule_id: Schedule UUID
    """
    if schedule_id in _active_sessions:
        del _active_sessions[schedule_id]


def is_session_active(schedule_id: str) -> bool:
    """
    Check if a session is currently active

    Args:
        schedule_id: Schedule UUID

    Returns:
        True if session is active, False otherwise
    """
    return schedule_id in _active_sessions


def get_session_info(schedule_id: str) -> dict | None:
    """
    Get session metadata

    Args:
        schedule_id: Schedule UUID

    Returns:
        Session metadata dict or None if not active
    """
    return _active_sessions.get(schedule_id)


def get_active_session_count() -> int:
    """
    Get count of active sessions

    Returns:
        Number of active sessions
    """
    return len(_active_sessions)


def update_session_scan_count(schedule_id: str):
    """
    Increment scan count for a session

    Args:
        schedule_id: Schedule UUID
    """
    if schedule_id in _active_sessions:
        _active_sessions[schedule_id]["scan_count"] = _active_sessions[schedule_id].get("scan_count", 0) + 1
        _active_sessions[schedule_id]["last_scan_at"] = datetime.now()
